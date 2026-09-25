#!/usr/bin/env python3
"""Validate the combined public package's conditional native dependencies."""
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
feed = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'artifacts/packages/all'
with zipfile.ZipFile(feed / 'SuperTokens.Rownd.Maui.0.0.1-m3.nupkg') as package:
    spec = ET.fromstring(package.read('SuperTokens.Rownd.Maui.nuspec'))
    groups = spec.findall('.//{*}dependencies/{*}group')
    for platform, binding in [('android', 'Android'), ('ios', 'iOS')]:
        group = [g for g in groups if platform in g.attrib['targetFramework'].lower()]
        assert len(group) == 1, f'Missing or ambiguous {platform} dependency group'
        dependencies = {d.attrib['id'] for d in group[0]}
        native = {d for d in dependencies if d.startswith('SuperTokens.Rownd.Native.')}
        assert native == {f'SuperTokens.Rownd.Native.{binding}'}, native
        assert 'SuperTokens.Rownd.Foundation' in dependencies
        assert (feed / f'SuperTokens.Rownd.Native.{binding}.0.0.1-m3.nupkg').is_file()
        assert any(n.startswith('lib/') and platform in n.lower() and n.endswith('.dll')
                   for n in package.namelist()), f'Missing {platform} managed assembly'
assert (feed / 'SuperTokens.Rownd.Foundation.0.0.1-m3.nupkg').is_file()
print('PASS: one public package with both platform assemblies and conditional native dependencies')
