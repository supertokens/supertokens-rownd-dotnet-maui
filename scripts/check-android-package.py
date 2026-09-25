#!/usr/bin/env python3
"""Static native payload check; never installs/launches a consumer."""
import hashlib
import io
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

root = Path(__file__).resolve().parent.parent
path = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'artifacts/packages/android/SuperTokens.Rownd.Native.Android.0.0.1-m2.nupkg'
with zipfile.ZipFile(path) as package:
    entries = package.namelist()
    for filename, expected in [
        ('mauiFacade-release.aar', 'io/supertokens/rownd/maui/RowndBridge.class'),
        ('android-release.aar', 'io/rownd/android/RowndClient.class'),
    ]:
        matches = [name for name in entries if name.endswith('/' + filename)]
        assert len(matches) == 1, f'Missing or repeated {filename}'
        with zipfile.ZipFile(io.BytesIO(package.read(matches[0]))) as aar:
            assert 'AndroidManifest.xml' in aar.namelist(), filename
            with zipfile.ZipFile(io.BytesIO(aar.read('classes.jar'))) as classes:
                assert expected in classes.namelist(), f'Missing real native class: {expected}'
            if filename == 'android-release.aar':
                assert any(name.startswith('res/') for name in aar.namelist()), 'Missing Rownd native resources'
    native = defaultdict(set)
    counts = defaultdict(int)
    for name in entries:
        if not name.endswith('.aar'):
            continue
        with zipfile.ZipFile(io.BytesIO(package.read(name))) as aar:
            for entry in aar.namelist():
                if entry.endswith('.so'):
                    native[entry].add(hashlib.sha256(aar.read(entry)).hexdigest())
                    counts[entry] += 1
    assert all(len(hashes) == 1 for hashes in native.values()), 'Conflicting copies of native shared libraries'
print(f'PASS: real facade/native classes and resources present; {sum(c > 1 for c in counts.values())} byte-identical duplicate native paths')
