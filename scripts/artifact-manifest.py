#!/usr/bin/env python3
"""Hash explicit build outputs; never inspect app storage, captures or credentials."""
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def manifest(paths):
    root = Path(__file__).resolve().parents[1]
    def git(*args):
        return subprocess.check_output(['git', *args], cwd=root).strip()
    def digest(path):
        value = hashlib.sha256()
        with path.open('rb') as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b''):
                value.update(chunk)
        return value.hexdigest()
    hashes = {}
    for path in paths:
        hashes[str(path)] = digest(path)
    sources = {}
    for name in sorted(set(git('ls-files', '-z', '--cached', '--others', '--exclude-standard').decode().split('\0'))):
        if name:
            path = root / name
            sources[name] = digest(path) if path.is_file() else 'missing'
    return {
        'revision': git('rev-parse', 'HEAD').decode(),
        'trackedDiffSha256': hashlib.sha256(git('diff', 'HEAD', '--binary')).hexdigest(),
        'worktreeDirty': bool(git('status', '--porcelain')),
        'sourceSnapshotSha256': hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest(),
        'pins': json.loads((root / 'eng/versions.json').read_text()),
        'artifacts': hashes,
        'runtimeAcceptance': 'UNRUN; hashes identify build outputs only',
    }


if __name__ == '__main__':
    paths = [Path(value) for value in sys.argv[1:]]
    if not paths or any(not path.is_file() or path.suffix not in ('.nupkg', '.apk', '.aab') for path in paths):
        sys.exit('Supply explicit nupkg/apk/aab build output paths')
    print(json.dumps(manifest(paths), indent=2))
