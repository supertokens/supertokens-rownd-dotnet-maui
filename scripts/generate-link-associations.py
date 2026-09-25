#!/usr/bin/env python3
"""Generate association and sample platform files; never deploy them."""
import argparse
import json
from pathlib import Path
import plistlib
import re
import xml.etree.ElementTree as ET


def generate(domain, package, certificates, prefix, bundle, output):
    label = r'[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?'
    if len(domain) > 253 or not re.fullmatch(rf'(?:{label}\.)+{label}', domain):
        raise ValueError('Supply the actual HTTPS hostname, without scheme/path/port')
    if not re.fullmatch(r'[A-Za-z][A-Za-z0-9_]*(?:\.[A-Za-z][A-Za-z0-9_]*)+', package):
        raise ValueError('Invalid Android application identifier')
    if not re.fullmatch(r'[A-Za-z0-9-]+(?:\.[A-Za-z0-9-]+)+', bundle):
        raise ValueError('Invalid iOS bundle identifier')
    if not re.fullmatch(r'[A-Z0-9]{10}', prefix):
        raise ValueError('Supply the signed application-identifier prefix (usually Team ID)')
    if not certificates or any(not re.fullmatch(r'(?:[0-9A-Fa-f]{2}:){31}[0-9A-Fa-f]{2}', c) for c in certificates):
        raise ValueError('Supply SHA-256 signing fingerprints as 32 colon-separated bytes')
    well_known = output / '.well-known'
    well_known.mkdir(parents=True, exist_ok=True)
    assets = [{'relation': ['delegate_permission/common.handle_all_urls'], 'target': {
        'namespace': 'android_app', 'package_name': package,
        'sha256_cert_fingerprints': [c.upper() for c in certificates]}}]
    aasa = {'applinks': {'apps': [], 'details': [{'appID': prefix + '.' + bundle, 'paths': ['/account/login']}]}}
    (well_known / 'assetlinks.json').write_text(json.dumps(assets, indent=2) + '\n')
    (well_known / 'apple-app-site-association').write_text(json.dumps(aasa, indent=2) + '\n')
    with (output / 'Entitlements.plist').open('wb') as file:
        plistlib.dump({'com.apple.developer.associated-domains': ['applinks:' + domain]}, file)
    ns = 'http://schemas.android.com/apk/res/android'
    tools = 'http://schemas.android.com/tools'
    ET.register_namespace('android', ns)
    ET.register_namespace('tools', tools)
    root = ET.Element('manifest')
    ET.SubElement(root, 'uses-permission', {f'{{{ns}}}name': 'android.permission.INTERNET'})
    app = ET.SubElement(root, 'application', {f'{{{ns}}}allowBackup': 'false', f'{{{ns}}}usesCleartextTraffic': 'true',
                                           f'{{{tools}}}replace': 'android:allowBackup'})
    activity = ET.SubElement(app, 'activity', {f'{{{ns}}}name': 'io.supertokens.maui.PasswordlessActivity'})
    intent = ET.SubElement(activity, 'intent-filter', {f'{{{ns}}}autoVerify': 'true'})
    ET.SubElement(intent, 'action', {f'{{{ns}}}name': 'android.intent.action.VIEW'})
    for category in ('DEFAULT', 'BROWSABLE'):
        ET.SubElement(intent, 'category', {f'{{{ns}}}name': 'android.intent.category.' + category})
    ET.SubElement(intent, 'data', {f'{{{ns}}}scheme': 'https', f'{{{ns}}}host': domain, f'{{{ns}}}path': '/account/login'})
    ET.indent(root)
    ET.ElementTree(root).write(output / 'AndroidManifest.xml', encoding='utf-8', xml_declaration=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ('domain', 'android-package', 'ios-prefix', 'ios-bundle', 'output'):
        parser.add_argument('--' + name, required=True)
    parser.add_argument('--android-sha256', action='append', required=True)
    args = parser.parse_args()
    generate(args.domain, args.android_package, args.android_sha256, args.ios_prefix, args.ios_bundle, Path(args.output))
    print('Generated local files. Hosting, signing and OS verification are still required.')


if __name__ == '__main__':
    main()
