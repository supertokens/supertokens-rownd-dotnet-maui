#!/usr/bin/env python3
"""Static native payload check; never installs/launches a consumer."""
import hashlib
import io
import sys
import zipfile
from collections import defaultdict
from pathlib import Path

# Input contract for the unrestricted Android binding and its JNI dependencies.
# Never infer supported ABIs from the package being checked: omission must fail.
SUPPORTED_ABIS = ('armeabi-v7a', 'arm64-v8a', 'x86', 'x86_64')
REQUIRED_LIBRARIES = ('libdatastore_shared_counter.so', 'libandroidx.graphics.path.so')


def check_package(path, supported_abis=SUPPORTED_ABIS):
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
        for entry in package.infolist():
            if not entry.filename.endswith('.aar'):
                continue
            with zipfile.ZipFile(io.BytesIO(package.read(entry))) as aar:
                for library in aar.infolist():
                    if library.filename.endswith('.so'):
                        native[library.filename].add(hashlib.sha256(aar.read(library)).hexdigest())
                        counts[library.filename] += 1
        assert all(len(hashes) == 1 for hashes in native.values()), 'Conflicting copies of native shared libraries'
        assert all(count == 1 for count in counts.values()), 'Repeated native shared libraries'
        for abi in supported_abis:
            for library in REQUIRED_LIBRARIES:
                expected = f'jni/{abi}/{library}'
                assert counts[expected] == 1, f'Missing native shared library: {expected}'


def main():
    root = Path(__file__).resolve().parent.parent
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else root / 'artifacts/packages/android/SuperTokens.Rownd.Native.Android.0.0.1-m3.nupkg'
    check_package(path)
    print('PASS: real facade/native classes and resources present; required JNI libraries unique for every supported ABI')


if __name__ == '__main__':
    main()
