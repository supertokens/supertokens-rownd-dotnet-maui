"""Offline checks only: URL fidelity, external dispatch and observation tooling."""
import importlib.util
import json
from pathlib import Path
import plistlib
import shlex
import sys
import tempfile
import unittest
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
            if calls == 1:
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
        with patch('magic_links.subprocess.run') as run:
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
