#!/usr/bin/env python3
"""Package Gradle's native graph, with NuGet owning its existing Maven modules."""
import json
import re
import xml.etree.ElementTree as ET
from pathlib import Path

root = Path(__file__).resolve().parent.parent
assets = json.loads((root / 'bindings/Rownd.Android/obj/project.assets.json').read_text())
provided = set()
for library in assets['libraries'].values():
    if library['type'] != 'package':
        continue
    for folder in assets['packageFolders']:
        for spec in (Path(folder) / library['path']).glob('*.nuspec'):
            text = spec.read_text()
            provided.update(re.findall(r'\bartifact=([^\s<]+)', text))

project = ET.Element('Project')
items = ET.SubElement(project, 'ItemGroup')
report = []
for artifact in json.loads((root / 'native/android/build/runtime.json').read_text()):
    coordinate = artifact['group'] + ':' + artifact['name']
    # Kotlin multiplatform Android/JVM variants are the same module in NuGet tags.
    aliases = {coordinate, re.sub(r'-(android|jvm)$', '', coordinate)}
    owner = 'NuGet' if provided & aliases else 'embedded'
    report.append(dict(artifact, owner=owner))
    if owner == 'embedded':
        ET.SubElement(items, 'AndroidLibrary', Include='$(MSBuildThisFileDirectory)runtime/' + artifact['file'], Bind='false')
ET.indent(project)
ET.ElementTree(project).write(root / 'native/android/build/runtime-libraries.props', encoding='unicode')
(root / 'native/android/build/packaging-inventory.json').write_text(json.dumps(report, indent=2) + '\n')
print(f'Runtime packaging: {sum(a["owner"] == "embedded" for a in report)} embedded, '
      f'{sum(a["owner"] == "NuGet" for a in report)} supplied by declared NuGet dependencies')
