#!/usr/bin/env python3
"""Minimal Appium HTTP transport and backwards-compatible opt-in smoke entry point."""
import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request


def request(url, data=None, method=None, timeout=20):
    body = None if data is None else json.dumps(data).encode()
    with urllib.request.urlopen(urllib.request.Request(url, body,
            {'Content-Type': 'application/json'}, method=method), timeout=timeout) as response:
        return json.load(response)


class Appium:
    def __init__(self, endpoint, session, platform):
        self.base = endpoint.rstrip('/') + '/session/' + session
        self.native_locator = 'id' if platform == 'android' else 'accessibility id'

    def call(self, path, data=None):
        value = request(self.base + path, data, timeout=90)['value']
        if isinstance(value, dict) and 'error' in value:
            raise RuntimeError('WebDriver command failed')
        return value

    def find(self, value, web=False):
        result = self.call('/element', {'using': 'css selector' if web else self.native_locator, 'value': value})
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
    from magic_links import Journey
    with open(os.environ['ROWND_E2E_CONFIG']) as file:
        config = json.load(file)
    driver = Appium(os.environ['ROWND_APPIUM_URL'], os.environ['ROWND_APPIUM_SESSION'], platform)
    Journey(platform, config, driver).run(scenario)


if __name__ == '__main__':
    if os.environ.get('ROWND_RUN_E2E') != '1':
        sys.exit('Set ROWND_RUN_E2E=1 explicitly; no device command was sent')
    try:
        run(sys.argv[1], sys.argv[2])
    except Exception:
        # WebDriver and delivery responses can contain OTPs, tokens and callback URLs.
        sys.exit('FAIL: native smoke did not complete; inspect device locally (secrets omitted)')
