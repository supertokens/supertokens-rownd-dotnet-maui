"""M5 real-login orchestration. Only the Debug sample retains access tokens."""
import json
import sys
import time
from appium_smoke import request, wait


def lifetime(config):
    seconds = config.get('accessTokenSeconds')
    if type(seconds) is not int or not 60 < seconds <= 300 or config.get('refreshFailureStatus') != 503:
        raise ValueError('Start the observed short-lived shared fixture (61..300 seconds)')
    return seconds


class RefreshRecovery:
    def __init__(self, journey):
        self.j = journey

    def probe(self, action, expected=None, signed_out=None, identity=None):
        j = self.j
        j.native()
        previous = j.driver.text('session-probe-result')
        j.driver.click('session-probe-' + action)
        text = wait(lambda: self._result(previous))
        fields = text.split(';')
        if len(fields) != 4:
            raise AssertionError('Malformed sample observation')
        sequence, outcome, authenticated, transitions = fields
        if not sequence.isdigit():
            raise AssertionError('Missing completed operation sequence')
        if expected is not None and outcome != expected:
            raise AssertionError('Unexpected sample operation outcome')
        if identity is not None:
            if not outcome.startswith('HTTP 200 '):
                raise AssertionError('Getter candidate was not accepted by protected endpoint')
            observation = json.loads(outcome.removeprefix('HTTP 200 '))
            if (observation.get('userId'), observation.get('sessionFingerprint')) != identity or not all(identity):
                raise AssertionError('Getter candidate changed protected identity/session')
        count = int(transitions.removeprefix('signedOut='))
        if signed_out is not None and (authenticated != 'authenticated=True' or count != signed_out):
            raise AssertionError('Recoverable operation reported signed out')
        return count

    def _result(self, previous):
        self.no_hub()
        value = self.j.driver.text('session-probe-result')
        return value if value != 'Pending' and value != previous else False

    def counters(self):
        return request(self.j.harness + '/counters')

    def refreshed_candidate(self, before, user, session, signed_out):
        self.probe('getter', 'Token available', signed_out)
        if self.counters()['stRefresh'] <= before['stRefresh']:
            raise AssertionError('Explicit getter did not perform native refresh')
        self.probe('candidate-request', signed_out=signed_out, identity=(user, session))

    def availability(self, unavailable):
        result = request(self.j.harness + '/test/refresh-availability', {'unavailable': unavailable})
        if result.get('status') != 'OK':
            raise AssertionError('Refresh control was not acknowledged')

    def no_hub(self):
        j = self.j
        j.native()
        name = 'android.webkit.WebView' if j.platform == 'android' else 'XCUIElementTypeWebView'
        for element in j.driver.call('/elements', {'using': 'class name', 'value': name}):
            key = element['element-6066-11e4-a52e-4f735466cecf']
            if j.driver.call('/element/' + key + '/displayed'):
                raise AssertionError('Native Hub reopened during session operation')

    def expire(self, seconds, check_hub=True):
        # Real Core lifetime, plus clock/timing margin. Keep the Appium session alive.
        deadline = time.monotonic() + seconds + 3
        while time.monotonic() < deadline:
            time.sleep(max(0, min(5, deadline - time.monotonic())))
            self.j.driver.call('/appium/device/app_state', {'appId': self.j.app})
            if check_hub:
                self.no_hub()

    def unchanged_login(self, baseline, completions):
        if self.counters()['passwordlessConsume'] != baseline['passwordlessConsume']:
            raise AssertionError('Unexpected passwordless consume during session operation')
        if int(self.j.driver.text('auth-completions')) != completions:
            raise AssertionError('Unexpected logical sign-in during session operation')
        self.no_hub()

    def login(self, email):
        from magic_links import callback
        j = self.j
        capture, identity = j.create_challenge(email=email)
        if email:
            j.driver.click('[data-testid="rownd-ui-passwordless-waiting-use-code"]', web=True)
            j.driver.fill('#rph-passwordless-code-input', capture['userInputCode'], web=True)
            j.driver.click('[data-testid="rownd-ui-passwordless-code-submit"]', web=True)
        else:
            j.native()
            j.driver.call('/appium/app/background', {'seconds': -1})
            j.external_open(callback(capture['urlWithLinkCode'], j.config['link-scheme']))
        return j.complete(identity)

    def cleanup(self, failed, clear=True):
        # Always attempt both controls. Preserve the original journey failure if
        # Appium or the fixture is also unavailable during final cleanup.
        errors = []
        controls = [lambda: self.availability(False)]
        if clear:
            controls.append(lambda: self.probe('clear', 'Cleared'))
        for control in controls:
            try:
                control()
            except Exception as error:
                errors.append(error)
        if errors:
            if not failed:
                raise errors[0]
            print('CLEANUP INCOMPLETE: restore refresh availability and clear/restart the sample before rerunning',
                  file=sys.stderr, flush=True)

    def run(self):
        j = self.j
        seconds = lifetime(request(j.harness + '/test/m5/config'))
        j.terminate()
        j.activate()
        wait(lambda: j.driver.text('auth-status') == 'Signed out' or
             j.driver.text('auth-status').startswith('Authenticated:'))
        j.process_id = j.driver.text('process-id')
        # Reset only the failure control, never session/counter state mid-journey.
        self.availability(False)
        try:
            for email in (True, False):
                j.mark('refresh/recovery after ' + ('email OTP' if email else 'phone magic link'))
                j.driver.click('sign-out')
                wait(lambda: j.driver.text('auth-status') == 'Signed out')
                user, session = self.login(email)
                signed_out = self.probe('save', 'Token available')
                self.probe('saved-request', 'HTTP 200', signed_out)
                baseline = self.counters()
                completions = int(j.driver.text('auth-completions'))
                self.expire(seconds)
                self.probe('saved-request', 'HTTP 401', signed_out)
                # The saved-token HTTP call must not itself cause native refresh.
                before = self.counters()
                if before['stRefresh'] != baseline['stRefresh']:
                    raise AssertionError('Refresh happened before the explicit getter')
                self.refreshed_candidate(before, user, session, signed_out)
                self.unchanged_login(baseline, completions)

                j.mark('503 faults getter; native session recovers')
                self.probe('save', 'Token available', signed_out)
                self.availability(True)
                try:
                    self.expire(seconds)
                    self.probe('saved-request', 'HTTP 401', signed_out)
                    before = self.counters()
                    self.probe('getter', 'Getter error', signed_out)
                    if self.counters()['stRefresh'] <= before['stRefresh']:
                        raise AssertionError('Getter did not reach failing native refresh')
                    self.unchanged_login(baseline, completions)
                finally:
                    self.cleanup(failed=sys.exc_info()[0] is not None, clear=False)
                before = self.counters()
                self.refreshed_candidate(before, user, session, signed_out)
                self.unchanged_login(baseline, completions)

                j.mark('process relaunch with current then expired native token')
                j.relaunch()
                wait(lambda: j.driver.text('auth-status') == 'Authenticated: ' + user)
                j.protected(user, session)
                self.no_hub()
                j.terminate()
                before = self.counters()
                self.expire(seconds, check_hub=False)
                j.activate()
                wait(lambda: j.driver.text('process-id') != j.process_id)
                j.process_id = j.driver.text('process-id')
                wait(lambda: j.driver.text('auth-status') == 'Authenticated: ' + user)
                j.protected(user, session)
                if self.counters()['stRefresh'] <= before['stRefresh']:
                    raise AssertionError('Expired persisted token did not refresh')
                if self.counters()['passwordlessConsume'] != baseline['passwordlessConsume']:
                    raise AssertionError('Relaunch created another login')
                self.no_hub()

                j.driver.click('sign-out')
                wait(lambda: j.driver.text('auth-status') == 'Signed out')
                self.probe('getter', 'No session')
                j.relaunch()
                wait(lambda: j.driver.text('auth-status') == 'Signed out')
                self.probe('getter', 'No session')
                j.mark('new real login after sign-out and process restart')
                _, new_session = self.login(email)
                if new_session == session:
                    raise AssertionError('New login restored the signed-out session')
                j.driver.click('sign-out')
                wait(lambda: j.driver.text('auth-status') == 'Signed out')
        finally:
            self.cleanup(failed=sys.exc_info()[0] is not None)
        print('PASS: refresh-recovery; OTP and phone link, expiry, native refresh, 503 recovery, relaunch, sign-out')
