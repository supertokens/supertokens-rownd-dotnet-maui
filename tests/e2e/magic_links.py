#!/usr/bin/env python3
"""Real Hub -> shared SMS/email capture -> external OS URL -> C# protected request.

No session creation endpoints or native-handler calls. Attach to an existing
Appium session. Only non-secret milestones are printed, including on failure.

Consume records observe completed backend attempts. A bounded quiet window
cannot prove exactly-once native forwarding or exclude later/in-flight attempts;
that acceptance requires a correlated native dispatch counter in the sample.
"""
import hashlib
import json
import os
import shlex
import subprocess
import sys
import time
import urllib.error
import urllib.parse
from appium_smoke import Appium, request, wait

SCENARIOS = frozenset({'smoke', 'sms-otp', 'phone-magic-link', 'cold-phone-magic-link',
                       'delayed-startup', 'email-magic-link', 'expired-link', 'https-magic-link'})


def challenge(link):
    uri = urllib.parse.urlsplit(link)
    query = urllib.parse.parse_qs(uri.query)
    values = query.get('preAuthSessionId', [])
    if query.get('displayContext') != ['mobile_app'] or len(values) != 1 or not values[0] or not uri.fragment:
        raise ValueError('Capture lacks mobile challenge/code')
    return hashlib.sha256(values[0].encode()).hexdigest()


def callback(link, scheme):
    challenge(link)
    # Do not parse/re-encode the signed query or fragment.
    return scheme + '://account/login' + link[link.index('?'):]


def initial_consume(records):
    if len(records) != 1 or records[0].get('status') != 'OK' or not records[0].get('userId'):
        raise AssertionError('Expected exactly one correlated initial consume attempt, with status OK')
    return records[0]['userId']


def replay_consumes(initial, records):
    if records[:len(initial)] != initial:
        raise AssertionError('Initial consume observations changed during replay')
    replay = records[len(initial):]
    if any(r.get('status') == 'OK' for r in replay):
        raise AssertionError('Replay completed another consume')
    return replay


class Journey:
    def __init__(self, platform, config, driver):
        self.platform, self.config, self.driver = platform, config, driver
        self.harness = config['harness-url'].rstrip('/')
        self.app = config['application-id']
        self.stage = 'initialization'

    def mark(self, stage):
        self.stage = stage
        print('STEP: ' + stage, flush=True)

    def native(self):
        self.driver.context('NATIVE_APP')

    def activate(self):
        self.native()
        self.driver.call('/appium/device/activate_app', {'appId': self.app})

    def terminate(self):
        self.native()
        self.driver.call('/appium/device/terminate_app', {'appId': self.app})

    def relaunch(self):
        self.native()
        before = self.process_id
        self.terminate()
        self.activate()
        wait(lambda: self.driver.text('process-id') != before)
        self.process_id = self.driver.text('process-id')

    def external_open(self, url):
        # Commands run on the runner host, with an explicit device. No package,
        # bundle or component target: this exercises OS resolution from outside.
        if self.platform == 'android':
            args = ['am', 'start', '-W', '-a', 'android.intent.action.VIEW',
                    '-c', 'android.intent.category.BROWSABLE', '-d', url]
            command = ['adb', '-s', self.config['device-id'], 'shell', shlex.join(args)]
        else:
            if self.config.get('ios-device-kind') != 'simulator':
                raise ValueError('Physical iOS external taps require the manual routing gate')
            command = ['xcrun', 'simctl', 'openurl', self.config['device-id'], url]
        subprocess.run(command, check=True, capture_output=True, timeout=45)

    def observes(self, identity, timeout=20):
        records = request(self.harness + '/test/m4/observations', timeout=timeout)['consumes']
        return [r for r in records if r['challenge'] == identity]

    def settled_consumes(self, identity, quiet_seconds=3, timeout=10):
        """Bounded backend observation window, not a native dispatch counter."""
        if not 0 < quiet_seconds < timeout:
            raise ValueError('Consume settling requires a positive quiet window below timeout')
        deadline = time.monotonic() + timeout
        previous, stable_since = None, None
        while time.monotonic() < deadline:
            records = self.observes(identity, timeout=max(0.001, deadline - time.monotonic()))
            now = time.monotonic()
            if now >= deadline:
                break
            if records != previous:
                previous, stable_since = records, now
            if records and now - stable_since >= quiet_seconds:
                return records
            time.sleep(min(0.25, deadline - now))
        raise TimeoutError('Correlated consume attempts did not settle')

    def hub(self):
        for context in self.driver.call('/contexts'):
            if not context.startswith('WEBVIEW'):
                continue
            try:
                self.driver.context(context)
                self.driver.find('#rph-sign-in-identifier-input', web=True)
                return True
            except (urllib.error.HTTPError, RuntimeError, KeyError):
                self.native()
        return False

    def create_challenge(self, email=False):
        key, identifier = ('email', self.config['email']) if email else ('phoneNumber', self.config['phone'])
        capture_url = self.harness + '/captures/latest?' + urllib.parse.urlencode({key: identifier})
        previous = None
        try:
            previous = challenge(request(capture_url)['urlWithLinkCode'])
        except urllib.error.HTTPError as error:
            if error.code != 404:
                raise
        self.native()
        self.driver.click('sign-in')
        wait(self.hub)
        if not email and self.config.get('phone-selector'):
            self.driver.click(self.config['phone-selector'], web=True)
        self.driver.fill('#rph-sign-in-identifier-input', identifier, web=True)
        self.driver.click('[data-testid="rownd-ui-login-continue-button"]', web=True)

        def fresh():
            capture = request(capture_url)
            if capture.get(key) != identifier or not capture.get('capturedAt'):
                return False
            return capture if challenge(capture['urlWithLinkCode']) != previous else False

        capture = wait(fresh)
        identity = challenge(capture['urlWithLinkCode'])
        if self.observes(identity):
            raise RuntimeError('Fresh challenge already consumed')
        return capture, identity

    def touch(self):
        self.native()
        before = int(self.driver.text('host-touches'))
        self.driver.click('host-touch')
        wait(lambda: int(self.driver.text('host-touches')) == before + 1)

    def protected(self, user, session=None):
        self.native()
        try:
            previous = json.loads(self.driver.text('protected-result')).get('request', 0)
        except json.JSONDecodeError:
            previous = 0
        self.driver.click('protected-api')

        def verified():
            try:
                result = json.loads(self.driver.text('protected-result'))
                if result.get('request', 0) <= previous or result.get('userId') != user or not result.get('sessionFingerprint'):
                    return False
                if session is not None and result['sessionFingerprint'] != session:
                    raise AssertionError('Native session was replaced')
                return result
            except json.JSONDecodeError:
                return False

        return wait(verified)['sessionFingerprint']

    def complete(self, identity):
        self.native()
        wait(lambda: self.driver.text('auth-status').startswith('Authenticated:'))
        records = wait(lambda: self.observes(identity))
        user = initial_consume(records)
        wait(lambda: self.driver.text('auth-status') == 'Authenticated: ' + user)
        self.touch()
        session = self.protected(user)
        initial_consume(self.settled_consumes(identity))
        return user, session

    def run(self, scenario):
        if scenario not in SCENARIOS or self.platform not in ('android', 'ios'):
            raise ValueError('Unsupported scenario/platform; no device action performed')
        if not self.config.get('device-id') or (self.platform == 'ios' and self.config.get('ios-device-kind') != 'simulator'):
            raise ValueError('Explicit supported external-dispatch device required')
        cold = scenario == 'cold-phone-magic-link' or (scenario == 'https-magic-link' and self.config.get('https-handoff') == 'cold')
        self.terminate()
        self.activate()
        self.native()
        wait(lambda: self.driver.text('auth-status') in ('Signed out',) or
             self.driver.text('auth-status').startswith('Authenticated:'))
        self.process_id = self.driver.text('process-id')
        self.driver.click('sign-out')
        wait(lambda: self.driver.text('auth-status') == 'Signed out')
        completion_baseline = int(self.driver.text('auth-completions'))
        self.mark('cancel and reopen native presenter')
        self.driver.click('sign-in')
        wait(self.hub)
        self.driver.click(self.config.get('hub-close-selector', '.rph-close[aria-label="close"]'), web=True)
        self.native()
        wait(lambda: self.driver.text('auth-status') == 'Signed out')
        self.touch()
        self.mark('real Hub challenge and correlated capture')
        capture, identity = self.create_challenge(email=scenario in ('email-magic-link', 'smoke'))
        link = capture['urlWithLinkCode']
        if scenario == 'https-magic-link' and urllib.parse.urlsplit(link).scheme != 'https':
            raise ValueError('HTTPS acceptance requires an actual captured HTTPS callback')
        url = link if scenario == 'https-magic-link' else callback(link, self.config['link-scheme'])
        if scenario in ('smoke', 'sms-otp'):
            self.driver.click('[data-testid="rownd-ui-passwordless-waiting-use-code"]', web=True)
            self.driver.fill('#rph-passwordless-code-input', capture['userInputCode'], web=True)
            self.driver.click('[data-testid="rownd-ui-passwordless-code-submit"]', web=True)
        self.native()
        if scenario == 'expired-link':
            self.mark('waiting for actual passwordless code expiry')
            seconds = self.config['expiry-wait-seconds']
            if not isinstance(seconds, int) or seconds <= 0:
                raise ValueError('Set the actual fixture code lifetime plus margin')
            self.driver.call('/appium/app/background', {'seconds': -1})
            deadline = time.monotonic() + seconds
            while time.monotonic() < deadline:
                time.sleep(max(0, min(10, deadline - time.monotonic())))
                self.driver.call('/appium/device/app_state', {'appId': self.app})
        elif cold:
            self.terminate()
        elif scenario == 'delayed-startup':
            self.relaunch()
            wait(lambda: self.driver.text('auth-status') == 'Initializing')
        elif scenario not in ('smoke', 'sms-otp'):
            self.driver.call('/appium/app/background', {'seconds': -1})
        if scenario not in ('smoke', 'sms-otp'):
            self.mark('untargeted external OS dispatch')
            self.external_open(url)
        if scenario == 'delayed-startup':
            self.native()
            if self.driver.text('auth-status') != 'Initializing' or any(r['status'] == 'OK' for r in self.observes(identity)):
                raise AssertionError('Callback did not remain queued during observed initialization')
        if scenario == 'expired-link':
            records = wait(lambda: self.observes(identity))
            if any(r['status'] not in ('RESTART_FLOW_ERROR', 'EXPIRED_USER_INPUT_CODE_ERROR') for r in records):
                raise AssertionError('Expected an explicit expired/restart-flow rejection')
            self.terminate()
            self.activate()
            wait(lambda: self.driver.text('auth-status') == 'Signed out')
            self.process_id = self.driver.text('process-id')
            self.driver.click('protected-api')
            wait(lambda: self.driver.text('protected-result') == 'No session')
            self.touch()
            self.mark('fresh challenge recovers after expiry')
            capture, identity = self.create_challenge()
            link = capture['urlWithLinkCode']
            url = callback(link, self.config['link-scheme'])
            self.native()
            self.driver.call('/appium/app/background', {'seconds': -1})
            self.external_open(url)
        user, session = self.complete(identity)
        expected_completions = 1 if cold or scenario in ('delayed-startup', 'expired-link') else completion_baseline + 1
        if int(self.driver.text('auth-completions')) != expected_completions:
            raise AssertionError('Expected one logical authentication transition')
        if cold:
            if self.driver.text('process-id') == self.process_id:
                raise AssertionError('Cold callback did not start a new process')
            self.process_id = self.driver.text('process-id')
        self.mark('replay after adapter deduplication window')
        time.sleep(2.1)
        self.driver.call('/appium/app/background', {'seconds': -1})
        initial = self.settled_consumes(identity)
        initial_consume(initial)
        self.external_open(url)
        self.native()
        # Native may suppress replay before a request, or briefly show/dismiss Hub.
        wait(lambda: self.driver.text('auth-status') == 'Authenticated: ' + user)
        self.touch()
        self.protected(user, session)
        if int(self.driver.text('auth-completions')) != expected_completions:
            raise AssertionError('Replay produced another authentication transition')
        replay_consumes(initial, self.settled_consumes(identity))
        self.mark('native persisted session after process termination')
        self.relaunch()
        wait(lambda: self.driver.text('auth-status') == 'Authenticated: ' + user)
        self.protected(user, session)
        self.driver.click('rebind-subscription')
        self.touch()
        if self.platform == 'android' and self.config.get('debug-lifecycle', False):
            self.mark('activity recreation without process death')
            process = self.driver.text('process-id')
            generation = int(self.driver.text('activity-generation'))
            self.driver.click('recreate-activity')
            wait(lambda: self.driver.text('auth-status') == 'Authenticated: ' + user)
            self.touch()
            wait(lambda: int(self.driver.text('activity-generation')) > generation)
            if self.driver.text('process-id') != process:
                raise AssertionError('Activity recreation unexpectedly killed process')
            wait(lambda: self.driver.text('auth-status') == 'Authenticated: ' + user)
            self.protected(user, session)
            self.touch()
        self.driver.click('sign-out')
        wait(lambda: self.driver.text('auth-status') == 'Signed out')
        self.driver.click('protected-api')
        wait(lambda: self.driver.text('protected-result') == 'No session')
        self.relaunch()
        wait(lambda: self.driver.text('auth-status') == 'Signed out')
        self.touch()
        self.driver.click('sign-in')
        wait(self.hub)
        print('PASS: ' + scenario + '; correlated consume, C# protected identity, replay, persisted native session, sign-out')


if __name__ == '__main__':
    if os.environ.get('ROWND_RUN_E2E') != '1':
        sys.exit('Set ROWND_RUN_E2E=1 explicitly; no device command was sent')
    journey = None
    try:
        platform, scenario = sys.argv[1:]
        with open(os.environ['ROWND_E2E_CONFIG']) as file:
            config = json.load(file)
        driver = Appium(os.environ['ROWND_APPIUM_URL'], os.environ['ROWND_APPIUM_SESSION'], platform)
        journey = Journey(platform, config, driver)
        journey.run(scenario)
    except Exception:
        sys.exit('FAIL: ' + (journey.stage if journey else 'configuration') + '; secret-bearing details omitted')
