"""Offline checks only: URL fidelity, external dispatch and observation tooling."""
import importlib.util
import json
from pathlib import Path
import plistlib
import shlex
import sys
import tempfile
import unittest
import urllib.error
from unittest.mock import Mock, patch
import xml.etree.ElementTree as ET

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tests/e2e'))
from magic_links import Journey, callback, challenge


def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


associations = load('generate-link-associations')
overlay = load('prepare-m4-harness')
LINK = 'https://hub.example.test/account/login?preAuthSessionId=a%2Fb%2Bc&displayContext=mobile_app&next=%252f#code%2B+%3d'


class DriverBoundaryTests(unittest.TestCase):
    def test_mobile_presenter_dismissal_does_not_require_hidden_html_close(self):
        for platform in ('android', 'ios'):
            with self.subTest(platform=platform):
                driver = Mock()
                if platform == 'ios':
                    driver.call.side_effect = [
                        {'width': 400, 'height': 800},
                        {'element-6066-11e4-a52e-4f735466cecf': 'sheet'},
                        {'y': 90}, None,
                    ]
                journey = Journey(platform, {'harness-url': 'http://localhost',
                                             'application-id': 'test.app'}, driver)
                journey.dismiss_hub()
                driver.context.assert_called_once_with('NATIVE_APP')
                driver.click.assert_not_called()
                if platform == 'android':
                    driver.call.assert_any_call('/appium/device/press_keycode', {'keycode': 4})
                else:
                    self.assertEqual(driver.call.call_args.args[0], '/execute/sync')
                    self.assertEqual(driver.call.call_args.args[1]['script'], 'mobile: tap')

    def test_android_keyboard_is_dismissed_before_presenter(self):
        driver = Mock()
        driver.find.side_effect = [RuntimeError('keyboard dismissed; sheet remains'), 'host']
        journey = Journey('android', {'harness-url': 'http://localhost',
                                      'application-id': 'test.app'}, driver)
        with patch('magic_links.time.sleep'):
            journey.dismiss_hub()
        presses = [call for call in driver.call.call_args_list
                   if call.args[0] == '/appium/device/press_keycode']
        self.assertEqual(len(presses), 2)

    def test_ios_open_confirmation_does_not_accept_unrelated_alerts(self):
        driver = Mock()
        journey = Journey('ios', {'harness-url': 'http://localhost',
                                 'application-id': 'test.app'}, driver)
        driver.call.return_value = 'Open in “Passwordless foundation”?'
        journey.confirm_ios_open()
        driver.call.assert_any_call('/alert/accept', {})
        driver.reset_mock()
        driver.call.return_value = 'Apple Account Verification'
        with self.assertRaises(RuntimeError):
            journey.confirm_ios_open()
        self.assertEqual(driver.call.call_count, 1)

    def test_first_protected_request_allows_missing_empty_ios_label(self):
        driver = Mock()
        driver.text.side_effect = [urllib.error.HTTPError('http://localhost', 404, 'no such element', {}, None),
                                  json.dumps({'request': 1, 'userId': 'verified-user', 'sessionFingerprint': 'session'})]
        journey = Journey('ios', {'harness-url': 'http://localhost',
                                 'application-id': 'test.app'}, driver)
        with patch('magic_links.wait', side_effect=lambda check: check()):
            self.assertEqual(journey.protected('verified-user'), 'session')
        driver.click.assert_called_once_with('protected-api')

    def test_same_device_confirmation_fails_without_clicking(self):
        driver = Mock()
        driver.webview.return_value = 'WEBVIEW_test'
        driver.call.return_value = [{'element': 'confirmation'}]
        journey = Journey('android', {'harness-url': 'http://localhost',
                                      'application-id': 'test.app'}, driver)
        with self.assertRaisesRegex(AssertionError, 'cross-device confirmation'):
            journey.reject_cross_device_confirmation()
        driver.click.assert_not_called()
        driver.context.assert_called_with('NATIVE_APP')

    def test_absent_confirmation_does_not_change_the_page(self):
        for webview in (None, 'WEBVIEW_test'):
            with self.subTest(webview=webview):
                driver = Mock()
                driver.webview.return_value = webview
                driver.call.return_value = []
                journey = Journey('android', {'harness-url': 'http://localhost',
                                              'application-id': 'test.app'}, driver)
                journey.reject_cross_device_confirmation()
                driver.click.assert_not_called()
                driver.context.assert_called_with('NATIVE_APP')

    def test_same_device_completion_rejects_chooser_before_backend_acceptance(self):
        driver = Mock()
        driver.text.side_effect = urllib.error.HTTPError('http://localhost', 404, 'sheet covers host', {}, None)
        driver.webview.return_value = 'WEBVIEW_test'
        driver.call.return_value = [{'element': 'confirmation'}]
        journey = Journey('android', {'harness-url': 'http://localhost',
                                      'application-id': 'test.app'}, driver)
        journey.observes = Mock()
        with patch('magic_links.wait', side_effect=lambda check: check()), \
                self.assertRaisesRegex(AssertionError, 'cross-device confirmation'):
            journey.complete(challenge(LINK))
        journey.observes.assert_not_called()
        driver.click.assert_not_called()

    def test_unimplemented_scenario_cannot_silently_run_a_phone_smoke(self):
        driver = Mock()
        journey = Journey('android', {'harness-url': 'http://localhost', 'application-id': 'test.app'}, driver)
        for scenario in ('refresh-recovery', 'typo'):
            with self.assertRaises(ValueError):
                journey.run(scenario)
        self.assertEqual(driver.mock_calls, [])

    def test_capture_must_be_new_and_match_exact_e164_identity(self):
        config = {'harness-url': 'http://localhost', 'application-id': 'test.app', 'phone': '+12025550123'}
        journey = Journey('android', config, Mock())
        journey.hub = lambda: True
        old = {'phoneNumber': config['phone'], 'capturedAt': 1, 'urlWithLinkCode': LINK}
        new = dict(old, capturedAt=2, urlWithLinkCode=LINK.replace('a%2Fb%2Bc', 'new'))
        wrong = dict(new, phoneNumber='+12025550124')
        calls = 0
        def condition(check):
            nonlocal calls
            calls += 1
            if calls in (1, 3):  # Hub available, then challenge-ready UI.
                return check()
            self.assertFalse(check())
            self.assertFalse(check())
            return check()
        with patch('magic_links.request', side_effect=[old, old, wrong, new, {'consumes': []}]) as get, \
                patch('magic_links.wait', side_effect=condition):
            captured, identity = journey.create_challenge()
        self.assertEqual(captured, new)
        self.assertEqual(identity, challenge(new['urlWithLinkCode']))
        self.assertIn('phoneNumber=%2B12025550123', get.call_args_list[0].args[0])

    def test_delivery_capture_alone_does_not_mean_webview_challenge_is_ready(self):
        driver = Mock()
        driver.find.side_effect = urllib.error.HTTPError('http://localhost', 404, 'not ready', {}, None)
        config = {'harness-url': 'http://localhost', 'application-id': 'test.app', 'phone': '+12025550123'}
        journey = Journey('android', config, driver)
        journey.hub = lambda: True
        capture = {'phoneNumber': config['phone'], 'capturedAt': 1, 'urlWithLinkCode': LINK}
        def settle(check):
            try:
                return check()
            except urllib.error.HTTPError:
                raise TimeoutError('challenge UI not ready')
        missing = urllib.error.HTTPError('http://localhost', 404, 'no earlier capture', {}, None)
        with patch('magic_links.request', side_effect=[missing, capture]), \
                patch('magic_links.wait', side_effect=settle), self.assertRaises(TimeoutError):
            journey.create_challenge()
        driver.find.assert_called_once_with('[data-testid="rownd-ui-passwordless-waiting"]', web=True)

    def test_exact_suffix_survives_conversion_and_external_android_shell(self):
        url = callback(LINK, 'sample')
        self.assertEqual(url[url.index('?'):], LINK[LINK.index('?'):])
        journey = Journey('android', {'harness-url': 'http://localhost', 'application-id': 'test.app', 'device-id': 'explicit-device'}, Mock())
        with patch('magic_links.subprocess.run') as run:
            journey.external_open(url)
        command = run.call_args.args[0]
        self.assertEqual(command[:4], ['adb', '-s', 'explicit-device', 'shell'])
        args = shlex.split(command[4])
        self.assertEqual(args[-1], url)
        self.assertNotIn('-n', args)
        self.assertNotIn('-p', args)
        self.assertNotIn('test.app', args)

    def test_ios_dispatch_is_external_and_simulator_explicit(self):
        config = {'harness-url': 'http://localhost', 'application-id': 'test.app', 'device-id': 'explicit-udid', 'ios-device-kind': 'simulator'}
        journey = Journey('ios', config, Mock())
        with patch('magic_links.subprocess.run') as run, patch.object(journey, 'confirm_ios_open'):
            journey.external_open(LINK)
        self.assertEqual(run.call_args.args[0], ['xcrun', 'simctl', 'openurl', 'explicit-udid', LINK])
        config['ios-device-kind'] = 'physical'
        with patch('magic_links.subprocess.run') as run, self.assertRaises(ValueError):
            journey.external_open(LINK)
        run.assert_not_called()

    def test_malformed_or_nonmobile_capture_rejected_before_dispatch(self):
        for link in (LINK.replace('mobile_app', 'browser'), LINK.split('#')[0], LINK.replace('preAuthSessionId', 'missing')):
            with self.assertRaises(ValueError):
                challenge(link)

    def test_protected_request_rejects_stale_result_and_replaced_session(self):
        driver = Mock()
        driver.text.side_effect = [json.dumps({'request': 1}), json.dumps({'request': 1, 'userId': 'u', 'sessionFingerprint': 's'}),
                                   json.dumps({'request': 2, 'userId': 'u', 'sessionFingerprint': 's'})]
        journey = Journey('android', {'harness-url': 'http://localhost', 'application-id': 'test.app'}, driver)
        def check_twice(check):
            self.assertFalse(check())
            return check()
        with patch('magic_links.wait', side_effect=check_twice):
            self.assertEqual(journey.protected('u', 's'), 's')
        driver.text.side_effect = ['{}', json.dumps({'request': 3, 'userId': 'u', 'sessionFingerprint': 'other'})]
        with patch('magic_links.wait', side_effect=lambda check: check()), self.assertRaises(AssertionError):
            journey.protected('u', 's')


class AssociationTests(unittest.TestCase):
    def test_generated_identities_match_platform_registration(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            certificates = [':'.join(['AB'] * 32), ':'.join(['CD'] * 32)]
            associations.generate('auth.example.test', 'test.android.app', certificates, 'TEST123456', 'test.ios.app', output)
            assets = json.loads((output / '.well-known/assetlinks.json').read_text())
            self.assertEqual(assets[0]['target']['sha256_cert_fingerprints'], certificates)
            self.assertEqual(assets[0]['target']['package_name'], 'test.android.app')
            aasa = json.loads((output / '.well-known/apple-app-site-association').read_text())
            self.assertEqual(aasa['applinks']['details'], [{'appID': 'TEST123456.test.ios.app', 'paths': ['/account/login']}])
            with (output / 'Entitlements.plist').open('rb') as file:
                self.assertEqual(plistlib.load(file)['com.apple.developer.associated-domains'], ['applinks:auth.example.test'])
            data = ET.parse(output / 'AndroidManifest.xml').find('./application/activity/intent-filter/data')
            self.assertEqual(data.get('{http://schemas.android.com/apk/res/android}host'), 'auth.example.test')

    def test_missing_signing_inputs_fail_without_output(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'generated'
            with self.assertRaises(ValueError):
                associations.generate('auth.example.test', 'test.app', [], 'TEST123456', 'test.app', output)
            self.assertFalse(output.exists())

    def test_harness_overlay_fails_closed_on_source_drift(self):
        with self.assertRaises(ValueError):
            overlay.transform('unreviewed upstream source')


if __name__ == '__main__':
    unittest.main()
