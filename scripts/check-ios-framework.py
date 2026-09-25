#!/usr/bin/env python3
"""Check distributable slices/resources; does not establish runtime linkage."""
import plistlib
import re
import sys
from pathlib import Path


def without_comments(text):
    return re.sub(r'/\*.*?\*/|//[^\n]*', '', text, flags=re.S)


def binding_selectors(api_definition):
    text = without_comments(api_definition)
    bridge = re.search(r'\binterface\s+RowndBridge\s*\{([^}]+)\}', text, re.S)
    assert bridge, 'Missing RowndBridge binding interface'
    selectors = set(re.findall(r'\[Export\("([^"]+)"\)\]', bridge[1]))
    assert selectors, 'Missing RowndBridge binding exports'
    return selectors


def objc_selectors(header):
    text = without_comments(header)
    declarations = re.findall(r'@interface\s+RWNRowndBridge\s*:\s*[^\n]+(.*?)@end', text, re.S)
    assert len(declarations) == 1, 'Missing or repeated RWNRowndBridge declaration'
    selectors = set()
    for method in re.findall(r'^\s*-\s*\([^\n]+?\)\s*([^;]+);', declarations[0], re.M):
        # Parameter types can contain block signatures. Selector components only
        # occur before colons; types and Swift-name attributes do not contribute.
        method = re.split(r'\b(?:SWIFT_\w+|NS_\w+|__attribute__)\s*\(', method)[0]
        components = re.findall(r'\b([A-Za-z_]\w*)\s*:', method)
        if components:
            selectors.add(''.join(component + ':' for component in components))
        else:
            name = re.match(r'([A-Za-z_]\w*)\b', method)
            if name:
                selectors.add(name[1])
    return selectors


def check_selectors(header, api_definition):
    missing = binding_selectors(api_definition) - objc_selectors(header)
    assert not missing, f'Missing Objective-C selectors on RWNRowndBridge: {sorted(missing)}'


def check_framework(framework, api_definition):
    framework = Path(framework)
    info = plistlib.loads((framework / 'Info.plist').read_bytes())
    slices = info['AvailableLibraries']
    assert any(s['SupportedPlatform'] == 'ios' and not s.get('SupportedPlatformVariant')
               and 'arm64' in s['SupportedArchitectures'] for s in slices), 'Missing iPhone arm64 slice'
    assert any(s['SupportedPlatform'] == 'ios' and s.get('SupportedPlatformVariant') == 'simulator'
               and 'arm64' in s['SupportedArchitectures'] for s in slices), 'Missing Apple Silicon simulator slice'
    for s in slices:
        path = framework / s['LibraryIdentifier'] / s['LibraryPath']
        assert (path / 'RowndMauiBridge').is_file(), f'Missing binary: {path}'
        header = (path / 'Headers/RowndMauiBridge-Swift.h').read_text()
        check_selectors(header, api_definition)
        assert any(path.glob('*Rownd*.bundle')), f'Missing Rownd SwiftPM resources: {path}'
        assert any(path.glob('*GoogleSignIn*.bundle')), f'Missing GoogleSignIn resources: {path}'


def main():
    root = Path(__file__).resolve().parent.parent
    framework = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'native/ios/build/RowndMauiBridge.xcframework'
    check_framework(framework, (root / 'bindings/Rownd.iOS/ApiDefinition.cs').read_text())
    print('PASS: iPhone/simulator slices, Objective-C selectors and resource bundles (static only)')


if __name__ == '__main__':
    main()
