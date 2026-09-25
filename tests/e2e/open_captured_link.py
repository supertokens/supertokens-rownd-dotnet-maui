#!/usr/bin/env python3
"""Manual routing helper: exact captured callback, untargeted OS open, no URL logging."""
import argparse
import json
import os
import sys
import urllib.parse
from appium_smoke import request
from magic_links import Journey, callback, challenge


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--platform', choices=['android', 'ios'], required=True)
    parser.add_argument('--kind', choices=['scheme', 'https'], required=True)
    parser.add_argument('--contact', choices=['phone', 'email'], default='phone')
    args = parser.parse_args()
    if os.environ.get('ROWND_RUN_E2E') != '1':
        raise ValueError('Explicit E2E opt-in required')
    with open(os.environ['ROWND_E2E_CONFIG']) as file:
        config = json.load(file)
    key = 'phoneNumber' if args.contact == 'phone' else 'email'
    capture = request(config['harness-url'].rstrip('/') + '/captures/latest?' + urllib.parse.urlencode({key: config[args.contact]}))
    if capture.get(key) != config[args.contact]:
        raise ValueError('Identity mismatch')
    link = capture['urlWithLinkCode']
    challenge(link)
    if args.kind == 'https' and urllib.parse.urlsplit(link).scheme != 'https':
        raise ValueError('Capture is not HTTPS')
    Journey(args.platform, config, None).external_open(link if args.kind == 'https' else callback(link, config['link-scheme']))
    print('DISPATCHED: record OS destination and backend outcome separately; dispatch alone is not a pass')


if __name__ == '__main__':
    try:
        main()
    except Exception:
        sys.exit('FAIL: verify configuration/capture/device locally; secret-bearing details omitted')
