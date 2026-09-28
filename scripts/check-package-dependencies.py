#!/usr/bin/env python3
"""Validate the combined public package's conditional native dependencies."""
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

root = Path(__file__).resolve().parent.parent
version = ET.parse(root / 'Rownd.Package.props').findtext('./PropertyGroup/RowndPackageVersion')
assert version, 'Missing centralized package version'
feed = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'artifacts/packages/all' / version
with zipfile.ZipFile(feed / f'SuperTokens.Rownd.Maui.{version}.nupkg') as package:
    spec = ET.fromstring(package.read('SuperTokens.Rownd.Maui.nuspec'))
    groups = spec.findall('.//{*}dependencies/{*}group')
    for platform, binding in [('android', 'Android'), ('ios', 'iOS')]:
        group = [g for g in groups if platform in g.attrib['targetFramework'].lower()]
        assert len(group) == 1, f'Missing or ambiguous {platform} dependency group'
        dependencies = {d.attrib['id'] for d in group[0]}
        native = {d for d in dependencies if d.startswith('SuperTokens.Rownd.Native.')}
        assert native == {f'SuperTokens.Rownd.Native.{binding}'}, native
        assert 'SuperTokens.Rownd.Foundation' in dependencies
        for dependency in group[0]:
            if dependency.attrib['id'].startswith('SuperTokens.Rownd.'):
                assert dependency.attrib['version'] in (version, f'[{version}]', f'[{version}, )'), dependency.attrib
        assert (feed / f'SuperTokens.Rownd.Native.{binding}.{version}.nupkg').is_file()
        assert any(n.startswith('lib/') and platform in n.lower() and n.endswith('.dll')
                   for n in package.namelist()), f'Missing {platform} managed assembly'
assert (feed / f'SuperTokens.Rownd.Foundation.{version}.nupkg').is_file()
print('PASS: one public package with both platform assemblies and conditional native dependencies')
