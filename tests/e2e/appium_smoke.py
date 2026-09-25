#!/usr/bin/env python3
"""Opt-in real native MAUI smoke. Requires an existing Appium session; never creates a session implicitly."""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def request(url, data=None, method=None):
    body = None if data is None else json.dumps(data).encode()
    with urllib.request.urlopen(urllib.request.Request(url, body,
            {'Content-Type': 'application/json'}, method=method), timeout=20) as response:
        return json.load(response)


class Appium:
    def __init__(self, endpoint, session):
        self.base = endpoint.rstrip('/') + '/session/' + session

    def call(self, path, data=None):
        value = request(self.base + path, data)['value']
        if isinstance(value, dict) and 'error' in value:
            raise RuntimeError('WebDriver command failed')
        return value

    def find(self, value, web=False):
        result = self.call('/element', {'using': 'css selector' if web else 'accessibility id', 'value': value})
        return result['element-6066-11e4-a52e-4f735466cecf']

    def click(self, value, web=False):
        self.call('/element/' + self.find(value, web) + '/click', {})

    def fill(self, value, text, web=False):
        element = self.find(value, web)
        self.call('/element/' + element + '/clear', {})
        self.call('/element/' + element + '/value', {'text': text})

    def text(self, value):
        return self.call('/element/' + self.find(value) + '/text')

    def context(self, name):
        self.call('/context', {'name': name})

    def webview(self):
        contexts = self.call('/contexts')
        web = next((c for c in contexts if c.startswith('WEBVIEW')), None)
        if web:
            self.context(web)
        return web


def wait(check):
    deadline = time.monotonic() + 60
    while time.monotonic() < deadline:
        try:
            value = check()
            if value:
                return value
        except (urllib.error.HTTPError, RuntimeError, KeyError):
            pass
        time.sleep(0.25)
    raise TimeoutError('Condition did not settle')


def run(platform, scenario):
    config = json.loads(open(os.environ['ROWND_E2E_CONFIG']).read())
    driver = Appium(os.environ['ROWND_APPIUM_URL'], os.environ['ROWND_APPIUM_SESSION'])
    driver.context('NATIVE_APP')
    for field in ['app-key', 'api-domain', 'api-path', 'hub-url', 'link-scheme', 'protected-url']:
        driver.fill(field, config[field])
    driver.click('configure')
    wait(lambda: driver.text('auth-status') == 'Signed out')
    identifier = config['email' if scenario == 'smoke' else 'phone']
    key = 'email' if scenario == 'smoke' else 'phoneNumber'
    capture_url = config['harness-url'].rstrip('/') + '/captures/latest?' + urllib.parse.urlencode({key: identifier})
    try:
        request(capture_url)
    except urllib.error.HTTPError as error:
        if error.code != 404:
            raise
    else:
        raise RuntimeError('Use a fresh identity/capture namespace')
    driver.click('sign-in')
    wait(driver.webview)
    if scenario != 'smoke':
        # Selector is explicit because Hub phone navigation depends on app config.
        driver.click(config['phone-selector'], web=True)
    driver.fill('#rph-sign-in-identifier-input', identifier, web=True)
    driver.click('[data-testid="rownd-ui-login-continue-button"]', web=True)
    capture = wait(lambda: request(capture_url))
    if capture.get(key) != identifier:
        raise RuntimeError('Capture identity mismatch')
    if scenario == 'smoke':
        driver.click('[data-testid="rownd-ui-passwordless-waiting-use-code"]', web=True)
        driver.fill('#rph-passwordless-code-input', capture['userInputCode'], web=True)
        driver.click('[data-testid="rownd-ui-passwordless-code-submit"]', web=True)
    else:
        link = capture['urlWithLinkCode']
        uri = urllib.parse.urlsplit(link)
        query = urllib.parse.parse_qs(uri.query)
        if query.get('displayContext') != ['mobile_app'] or not query.get('preAuthSessionId') or not uri.fragment:
            raise RuntimeError('Capture lacks mobile challenge/code')
        # Preserve the encoded suffix byte-for-byte. This is custom-scheme evidence,
        # not verified HTTPS association or browser fallback evidence.
        link = config['link-scheme'] + '://account/login' + link[link.index('?'):]
        driver.context('NATIVE_APP')
        driver.call('/appium/app/background', {'seconds': -1})
        args = {'url': link}
        args['package' if platform == 'android' else 'bundleId'] = config['application-id']
        driver.call('/execute/sync', {'script': 'mobile: deepLink', 'args': [args]})
    driver.context('NATIVE_APP')
    wait(lambda: driver.text('auth-status').startswith('Authenticated:'))
    driver.click('protected-api')
    def verified():
        try:
            result = json.loads(driver.text('protected-result'))
            return result.get('userId') == config['expected-user-id']
        except json.JSONDecodeError:
            return False
    wait(verified)
    driver.click('sign-out')
    wait(lambda: driver.text('auth-status') == 'Signed out')
    driver.click('protected-api')
    wait(lambda: driver.text('protected-result') == 'No session')
    driver.click('sign-in')
    wait(driver.webview)
    print('PASS: native login, backend-verified expected user, sign-out and reopened Hub; other milestone gates remain pending')


if __name__ == '__main__':
    if os.environ.get('ROWND_RUN_E2E') != '1':
        sys.exit('Set ROWND_RUN_E2E=1 explicitly; no device command was sent')
    try:
        run(sys.argv[1], sys.argv[2])
    except Exception:
        # WebDriver and delivery responses can contain OTPs, tokens and callback URLs.
        sys.exit('FAIL: native smoke did not complete; inspect device locally (secrets omitted)')
