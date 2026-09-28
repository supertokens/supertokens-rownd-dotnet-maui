"""Offline orchestration/control tests. These cannot establish native auth acceptance."""
import sys
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'e2e'))
from refresh_recovery import RefreshRecovery, lifetime


class RefreshBoundaryTests(unittest.TestCase):
    def setUp(self):
        self.journey = Mock(harness='http://fixture', app='sample', platform='android')
        self.flow = RefreshRecovery(self.journey)

    def test_lifetime_exceeds_ios_refresh_margin(self):
        for value in (None, True, '90', 60, 301, 90.5):
            with self.subTest(value=value), self.assertRaises(ValueError):
                lifetime({'accessTokenSeconds': value, 'refreshFailureStatus': 503})
        self.assertEqual(lifetime({'accessTokenSeconds': 90, 'refreshFailureStatus': 503}), 90)

    def test_wrong_failure_mode_rejected(self):
        with self.assertRaises(ValueError):
            lifetime({'accessTokenSeconds': 90, 'refreshFailureStatus': 401})

    def test_failure_control_requires_acknowledgment(self):
        with patch('refresh_recovery.request', return_value={'status': 'ERROR'}) as http:
            with self.assertRaises(AssertionError):
                self.flow.availability(True)
            http.assert_called_once_with('http://fixture/test/refresh-availability', {'unavailable': True})

    def test_probe_waits_for_fresh_completion_and_calls_real_sample_button(self):
        self.journey.driver.text.side_effect = ['1;old', '1;old', 'Pending', '2;Getter error;authenticated=True;signedOut=4']
        self.journey.driver.call.return_value = []
        with patch('refresh_recovery.wait', side_effect=lambda check: check() or check() or check()):
            self.assertEqual(self.flow.probe('getter', 'Getter error', 4), 4)
        self.journey.driver.click.assert_called_once_with('session-probe-getter')

    def test_false_signout_even_if_now_authenticated_fails(self):
        self.journey.driver.text.side_effect = ['Idle', '1;Getter error;authenticated=True;signedOut=5']
        self.journey.driver.call.return_value = []
        with patch('refresh_recovery.wait', side_effect=lambda check: check()), self.assertRaises(AssertionError):
            self.flow.probe('getter', 'Getter error', 4)

    def test_no_session_is_not_recoverable_getter_error(self):
        self.journey.driver.text.side_effect = ['Idle', '1;No session;authenticated=False;signedOut=4']
        self.journey.driver.call.return_value = []
        with patch('refresh_recovery.wait', side_effect=lambda check: check()), self.assertRaises(AssertionError):
            self.flow.probe('getter', 'Getter error', 4)

    def candidate_result(self, outcome):
        self.journey.driver.text.side_effect = ['Idle', '1;Token available;authenticated=True;signedOut=4',
                                               'Idle', '2;' + outcome + ';authenticated=True;signedOut=4']
        self.journey.driver.call.return_value = []

    def test_stale_first_getter_cannot_be_rescued_by_second_getter(self):
        self.candidate_result('HTTP 200 {"userId":"u","sessionFingerprint":"s"}')
        counter = {'stRefresh': 0}
        # The old ordinary protected action would invoke another getter and refresh.
        self.journey.protected.side_effect = lambda *args: counter.update(stRefresh=1)
        with patch('refresh_recovery.wait', side_effect=lambda check: check()), \
             patch.object(self.flow, 'counters', side_effect=lambda: counter):
            with self.assertRaisesRegex(AssertionError, 'Explicit getter'):
                self.flow.refreshed_candidate({'stRefresh': 0}, 'u', 's', 4)
        self.journey.protected.assert_not_called()
        self.assertEqual([call.args[0] for call in self.journey.driver.click.call_args_list], ['session-probe-getter'])

    def test_refresh_counter_alone_cannot_accept_stale_returned_candidate(self):
        self.candidate_result('HTTP 401')
        with patch('refresh_recovery.wait', side_effect=lambda check: check()), \
             patch.object(self.flow, 'counters', return_value={'stRefresh': 1}):
            with self.assertRaisesRegex(AssertionError, 'candidate was not accepted'):
                self.flow.refreshed_candidate({'stRefresh': 0}, 'u', 's', 4)
        self.journey.protected.assert_not_called()

    def test_candidate_requires_exact_user_and_session(self):
        for identity in ('{"userId":"other","sessionFingerprint":"s"}',
                         '{"userId":"u","sessionFingerprint":"other"}',
                         '{"userId":"u"}'):
            with self.subTest(identity=identity):
                self.candidate_result('HTTP 200 ' + identity)
                with patch('refresh_recovery.wait', side_effect=lambda check: check()), \
                     patch.object(self.flow, 'counters', return_value={'stRefresh': 1}), \
                     self.assertRaisesRegex(AssertionError, 'changed protected identity'):
                    self.flow.refreshed_candidate({'stRefresh': 0}, 'u', 's', 4)

    def test_counter_is_checked_between_getter_and_candidate_http(self):
        self.candidate_result('HTTP 200 {"userId":"u","sessionFingerprint":"s"}')
        def counter():
            self.assertEqual([call.args[0] for call in self.journey.driver.click.call_args_list], ['session-probe-getter'])
            return {'stRefresh': 1}
        with patch('refresh_recovery.wait', side_effect=lambda check: check()), \
             patch.object(self.flow, 'counters', side_effect=counter):
            self.flow.refreshed_candidate({'stRefresh': 0}, 'u', 's', 4)
        self.assertEqual([call.args[0] for call in self.journey.driver.click.call_args_list],
                         ['session-probe-getter', 'session-probe-candidate-request'])
        self.journey.protected.assert_not_called()

    def test_visible_hub_fails_even_with_good_host_state(self):
        self.journey.driver.call.side_effect = [[{'element-6066-11e4-a52e-4f735466cecf': 'hub'}], True]
        with self.assertRaises(AssertionError):
            self.flow.no_hub()

    def test_retained_hidden_webview_context_is_not_presentation(self):
        self.journey.driver.call.side_effect = [[{'element-6066-11e4-a52e-4f735466cecf': 'hub'}], False]
        self.flow.no_hub()

    def test_new_consume_is_not_refresh(self):
        with patch.object(self.flow, 'counters', return_value={'passwordlessConsume': 2}), self.assertRaises(AssertionError):
            self.flow.unchanged_login({'passwordlessConsume': 1}, 1)

    def test_failure_always_restores_refresh_control(self):
        self.journey.driver.text.return_value = 'Signed out'
        with patch('refresh_recovery.request', return_value={'accessTokenSeconds': 90, 'refreshFailureStatus': 503}), \
             patch('refresh_recovery.wait', side_effect=lambda check: check()), \
             patch.object(self.flow, 'availability') as availability, \
             patch.object(self.flow, 'probe') as probe, \
             patch.object(self.flow, 'login', side_effect=AssertionError('login failed')):
            with self.assertRaises(AssertionError):
                self.flow.run()
        self.assertEqual([call.args for call in availability.call_args_list], [(False,), (False,)])
        probe.assert_called_once_with('clear', 'Cleared')

    def test_cleanup_failure_does_not_replace_original_journey_failure(self):
        self.journey.driver.text.return_value = 'Signed out'
        with patch('refresh_recovery.request', return_value={'accessTokenSeconds': 90, 'refreshFailureStatus': 503}), \
             patch('refresh_recovery.wait', side_effect=lambda check: check()), \
             patch.object(self.flow, 'availability', side_effect=[None, RuntimeError('fixture unavailable')]) as availability, \
             patch.object(self.flow, 'probe', side_effect=RuntimeError('device unavailable')) as probe, \
             patch.object(self.flow, 'login', side_effect=AssertionError('original login failure')), \
             patch('sys.stderr') as stderr:
            with self.assertRaisesRegex(AssertionError, 'original login failure'):
                self.flow.run()
        self.assertEqual([call.args for call in availability.call_args_list], [(False,), (False,)])
        probe.assert_called_once_with('clear', 'Cleared')
        self.assertTrue(stderr.write.called)

    def test_cleanup_failure_fails_otherwise_successful_journey_and_attempts_both_controls(self):
        with patch.object(self.flow, 'availability', side_effect=RuntimeError('fixture unavailable')), \
             patch.object(self.flow, 'probe') as probe:
            with self.assertRaisesRegex(RuntimeError, 'fixture unavailable'):
                self.flow.cleanup(failed=False)
        probe.assert_called_once_with('clear', 'Cleared')

    def test_outage_cleanup_does_not_clear_candidate_probe_state(self):
        with patch.object(self.flow, 'availability') as availability, patch.object(self.flow, 'probe') as probe:
            self.flow.cleanup(failed=False, clear=False)
        availability.assert_called_once_with(False)
        probe.assert_not_called()

    def test_both_real_login_paths_are_selected_and_outage_restored(self):
        self.journey.driver.text.side_effect = lambda key: {'auth-status': 'Signed out', 'process-id': 'p', 'auth-completions': '1'}[key]
        # Bypass waits only: orchestration must choose both actual login paths and
        # must restore the switch before recovery. No runtime sessions are fabricated.
        with patch('refresh_recovery.request', return_value={'accessTokenSeconds': 90, 'refreshFailureStatus': 503}), \
             patch('refresh_recovery.wait', return_value=True), \
             patch.object(self.flow, 'availability') as availability, \
             patch.object(self.flow, 'login', side_effect=[('u', 's'), ('u', 'new'), ('u', 's2'), ('u', 'new2')]) as login, \
             patch.object(self.flow, 'probe', return_value=0), \
             patch.object(self.flow, 'expire'), \
             patch.object(self.flow, 'no_hub'), \
             patch.object(self.flow, 'unchanged_login'), \
             patch.object(self.flow, 'counters') as counters, \
             patch('builtins.print'):
            values = [0, 0, 1, 1, 2, 2, 3, 3, 4, 4] * 2
            counters.side_effect = [{'stRefresh': n, 'passwordlessConsume': 1} for n in values]
            self.flow.run()
        self.assertEqual([call.args for call in login.call_args_list], [(True,), (True,), (False,), (False,)])
        self.assertEqual([call.args for call in availability.call_args_list], [(False,), (True,), (False,), (True,), (False,), (False,)])
        # Ordinary protected requests remain only in the two relaunch checks per login.
        self.assertEqual(self.journey.protected.call_count, 4)

    def test_assertion_during_outage_restores_backend_before_unwinding(self):
        self.journey.driver.text.side_effect = lambda key: {'auth-status': 'Signed out', 'process-id': 'p', 'auth-completions': '1'}[key]
        with patch('refresh_recovery.request', return_value={'accessTokenSeconds': 90, 'refreshFailureStatus': 503}), \
             patch('refresh_recovery.wait', return_value=True), \
             patch.object(self.flow, 'availability') as availability, \
             patch.object(self.flow, 'login', return_value=('u', 's')), \
             patch.object(self.flow, 'probe', side_effect=[0] * 7 + [AssertionError('unexpected signout'), 0]) as probe, \
             patch.object(self.flow, 'expire'), \
             patch.object(self.flow, 'unchanged_login'), \
             patch.object(self.flow, 'counters', side_effect=[{'stRefresh': n, 'passwordlessConsume': 1} for n in [0, 0, 1, 1]]):
            with self.assertRaises(AssertionError):
                self.flow.run()
        self.assertEqual([call.args for call in availability.call_args_list], [(False,), (True,), (False,), (False,)])
        self.assertEqual(probe.call_args.args, ('clear', 'Cleared'))


class ProbeSourceContractTests(unittest.TestCase):
    def setUp(self):
        self.source = (Path(__file__).resolve().parents[2] / 'samples/Passwordless/SessionProbe.cs').read_text()

    def test_saved_expiry_and_single_use_candidate_have_independent_storage(self):
        self.assertIn('private string? savedToken;', self.source)
        self.assertIn('private string? candidateToken;', self.source)
        self.assertIn('if (action == "save") savedToken = token;', self.source)
        self.assertIn('else candidateToken = token;', self.source)
        http_branch = self.source.split('else if (action is "saved-request" or "candidate-request")')[1].split('\n        else\n')[0]
        self.assertNotIn('GetAccessTokenAsync', http_branch)
        self.assertNotIn('savedToken =', http_branch)
        self.assertIn('if (action == "candidate-request") candidateToken = null;', http_branch)
        self.assertIn('new AuthenticationHeaderValue("Bearer", token)', http_branch)

    def test_probe_is_debug_only_cookie_free_and_clears_on_signout(self):
        self.assertTrue(self.source.startswith('#if DEBUG\n'))
        self.assertTrue(self.source.rstrip().endswith('#endif'))
        self.assertIn('AllowAutoRedirect = false, UseCookies = false', self.source)
        self.assertIn('using var request =', self.source)
        self.assertIn('using var response =', self.source)
        self.assertIn('using var body =', self.source)
        self.assertIn('if (!authenticated) Clear();', self.source)
        self.assertIn('savedToken = candidateToken = null;', self.source)
        self.assertIn('authenticated && epoch == credentialEpoch', self.source)
        self.assertIn('SHA256.HashData', self.source)


if __name__ == '__main__':
    unittest.main()
