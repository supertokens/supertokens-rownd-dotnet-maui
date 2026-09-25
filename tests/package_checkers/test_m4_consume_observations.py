"""Offline consume assertions: fake HTTP, clock and native completion boundary."""
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock, patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'e2e'))
from magic_links import Journey, initial_consume, replay_consumes


class ConsumeObservationTests(unittest.TestCase):
    def setUp(self):
        self.now = 0
        self.ok = {'challenge': 'current', 'status': 'OK', 'userId': 'user'}
        self.failed = {'challenge': 'current', 'status': 'RESTART_FLOW_ERROR'}
        self.journey = Journey('android', {'harness-url': 'http://fake', 'application-id': 'test.app'}, Mock())
        self.addCleanup(patch.stopall)
        patch('magic_links.time.monotonic', side_effect=lambda: self.now).start()
        patch('magic_links.time.sleep', side_effect=self.advance).start()

    def advance(self, seconds):
        self.now += seconds

    def http(self, records):
        def response(url, timeout):
            self.assertEqual(url, 'http://fake/test/m4/observations')
            self.assertGreater(timeout, 0)
            return {'consumes': records(self.now)}
        return patch('magic_links.request', side_effect=response).start()

    def test_initial_success_followed_by_failed_duplicate_is_rejected(self):
        self.http(lambda now: [self.ok] + ([self.failed] if now >= 1 else []))
        with self.assertRaisesRegex(AssertionError, 'exactly one'):
            initial_consume(self.journey.settled_consumes('current'))
        self.assertGreaterEqual(self.now, 4)

    def test_stale_other_challenge_does_not_reset_settling(self):
        self.http(lambda now: [self.ok] + [dict(self.failed, challenge='stale')] * int(now * 4))
        self.assertEqual(initial_consume(self.journey.settled_consumes('current')), 'user')
        self.assertEqual(self.now, 3)

    def test_eventual_first_attempt_waits_for_full_quiet_window(self):
        self.http(lambda now: [] if now < 2 else [self.ok])
        self.assertEqual(self.journey.settled_consumes('current'), [self.ok])
        self.assertEqual(self.now, 5)

    def test_unsettled_attempts_and_missing_attempts_time_out(self):
        for records in (lambda now: [self.ok] + [self.failed] * int(now * 4), lambda now: []):
            with self.subTest(records=records):
                self.now = 0
                self.http(records)
                with self.assertRaises(TimeoutError):
                    self.journey.settled_consumes('current')
                self.assertEqual(self.now, 10)

    def test_http_response_after_deadline_cannot_pass(self):
        def records(now):
            self.advance(11)
            return [self.ok]
        self.http(records)
        with self.assertRaises(TimeoutError):
            self.journey.settled_consumes('current')

    def test_complete_checks_after_protected_request_completion(self):
        self.http(lambda now: [self.ok] + ([self.failed] if now >= 1 else []))
        self.journey.driver.text.return_value = 'Authenticated: user'
        self.journey.touch = Mock()
        self.journey.protected = Mock(side_effect=lambda user: self.advance(1) or 'session')
        with self.assertRaises(AssertionError):
            self.journey.complete('current')
        self.journey.protected.assert_called_once_with('user')

    def test_replay_is_separate_and_may_be_suppressed_or_rejected(self):
        self.assertEqual(replay_consumes([self.ok], [self.ok]), [])
        self.assertEqual(replay_consumes([self.ok], [self.ok, self.failed]), [self.failed])
        with self.assertRaisesRegex(AssertionError, 'another consume'):
            replay_consumes([self.ok], [self.ok, self.ok])
        with self.assertRaisesRegex(AssertionError, 'observations changed'):
            replay_consumes([self.ok], [self.failed])

    def test_initial_rejects_failure_missing_user_and_multiple_successes(self):
        for records in ([], [self.failed], [dict(self.ok, userId='')], [self.ok, self.ok], [self.ok, self.failed]):
            with self.subTest(records=records), self.assertRaises(AssertionError):
                initial_consume(records)


if __name__ == '__main__':
    unittest.main()
