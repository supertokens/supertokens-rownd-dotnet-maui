#!/usr/bin/env python3
"""Validate and publish an existing beta bundle. Default: offline dry run."""
import argparse
import hashlib
import json
from pathlib import Path
import re
import subprocess
import tempfile
import xml.etree.ElementTree as ET
import zipfile

ROOT = Path(__file__).resolve().parents[1]
IDS = ['SuperTokens.Rownd.' + name for name in ('Foundation', 'Maui', 'Native.Android', 'Native.iOS')]


def require(condition, message):
    if not condition:
        raise ValueError(message)


def run(*args, cwd=ROOT):
    return subprocess.check_output(args, cwd=cwd, text=True).strip()


def validate(folder, archive, version):
    require(re.fullmatch(r'\d+\.\d+\.\d+-[0-9A-Za-z.-]+', version), 'Only prerelease versions are supported')
    names = {f'{name}.{version}.nupkg' for name in IDS}
    require({p.name for p in folder.glob('*.nupkg')} == names, 'Expected exactly four matching packages')
    sums = {}
    for line in (folder / 'SHA256SUMS').read_text().splitlines():
        digest, name = line.split(maxsplit=1)
        name = name.lstrip('*')
        require(name not in sums and name in names, 'Unexpected or duplicate checksum entry')
        sums[name] = digest
    require(set(sums) == names, 'Missing package checksums')
    manifest = json.loads((folder / 'manifest.json').read_text())
    require(manifest.get('artifacts') == sums, 'Manifest/checksum mismatch')
    for name, digest in sums.items():
        path = folder / name
        require(hashlib.sha256(path.read_bytes()).hexdigest() == digest, f'Checksum mismatch: {name}')
        with zipfile.ZipFile(path) as package:
            specs = [n for n in package.namelist() if n.endswith('.nuspec')]
            require(len(specs) == 1, f'Expected one nuspec: {name}')
            spec = ET.fromstring(package.read(specs[0]))
            package_id = spec.findtext('.//{*}metadata/{*}id')
            require(package_id in IDS and name == f'{package_id}.{version}.nupkg', f'Wrong package ID: {name}')
            require(spec.findtext('.//{*}metadata/{*}version') == version, f'Wrong version: {name}')
    members = names | {'SHA256SUMS', 'manifest.json', 'VALIDATION.md', 'beta-integration.md'}
    with zipfile.ZipFile(archive) as bundle:
        require(len(bundle.namelist()) == len(members) and set(bundle.namelist()) == members,
                'ZIP must contain exactly the packages, checksums, manifest, tutorial and validation notes')
        for name in members:
            require(bundle.read(name) == (folder / name).read_bytes(), f'ZIP/asset mismatch: {name}')
    acceptance = manifest.get('runtimeAcceptance')
    require(isinstance(acceptance, dict) and all(str(acceptance.get(p, '')).startswith('PASS')
            for p in ('android', 'ios')), 'Both platform smoke results must be recorded as PASS')
    return manifest, [folder / name for name in sorted(members)] + [archive]


def remote_repo(remote):
    match = re.fullmatch(r'(?:git@github\.com:|https://github\.com/)([\w.-]+/[\w.-]+?)(?:\.git)?', remote)
    require(match, 'origin must be a GitHub SSH or HTTPS repository URL')
    return match.group(1)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_mutually_exclusive_group()
    modes.add_argument('--publish', action='store_true', help='Create and publish the GitHub prerelease')
    modes.add_argument('--dry-run', action='store_true', help='Offline validation only (default)')
    parser.add_argument('--assets', type=Path, help='Directory containing the validated individual assets')
    parser.add_argument('--zip', dest='archive', type=Path, help='Matching convenience ZIP')
    parser.add_argument('--target', default='HEAD', help='Committed release target, defaults to HEAD')
    args = parser.parse_args()
    version = ET.parse(ROOT / 'Rownd.Package.props').findtext('./PropertyGroup/RowndPackageVersion')
    require(version, 'Missing centralized package version')
    folder = (args.assets or ROOT / 'artifacts/releases' / version).resolve()
    archive = (args.archive or folder.parent / f'SuperTokens.Rownd.{version}.zip').resolve()
    manifest, assets = validate(folder, archive, version)
    target = run('git', 'rev-parse', '--verify', args.target + '^{commit}')
    repo = remote_repo(run('git', 'remote', 'get-url', 'origin'))
    tag = 'v' + version
    # Check release metadata against the target, not merely the current working files.
    target_props = ET.fromstring(run('git', 'show', f'{target}:Rownd.Package.props'))
    require(target_props.findtext('./PropertyGroup/RowndPackageVersion') == version, 'Target commit has another package version')
    pins = json.loads(run('git', 'show', f'{target}:eng/versions.json'))
    require(pins == manifest.get('pins'), 'Target pins do not match the build manifest')
    base = manifest.get('revision', '')
    require(re.fullmatch('[0-9a-f]{40}', base), 'Invalid manifest build revision')
    require(subprocess.run(['git', 'merge-base', '--is-ancestor', base, target], cwd=ROOT).returncode == 0,
            'Build base is not an ancestor of the release target')
    # Keep the original pre-commit build provenance. Never relabel it as a clean build.
    provenance = (f'Build base: `{base}`; release target: `{target}`. '
                  f'Build working tree dirty: `{bool(manifest.get("worktreeDirty"))}`. '
                  'The attached manifest preserves the original source snapshot and package hashes; '
                  'the release target is not a claim that these packages were rebuilt from that clean commit.')
    notes = (f'# SuperTokens Rownd MAUI {version}\n\n'
             'Download the ZIP for all four packages and the integration guide, or download individual assets. '
             'Use a local NuGet feed; these packages are not published to NuGet.org.\n\n'
             + (folder / 'VALIDATION.md').read_text() + '\n\n## Build provenance\n\n' + provenance + '\n')
    print(f'{repo}: {tag} -> {target}\nValidated {len(assets)} assets; Android and iOS smoke evidence present.')
    print(provenance)
    if not args.publish:
        print('DRY RUN: no network calls, tag creation, uploads or publication. Use --publish after committing/pushing changes.')
        return
    require(not run('git', 'status', '--porcelain'), 'Commit working-tree changes before publishing')
    # Authentication, target reachability and conflicts are read before the first mutation.
    run('gh', 'auth', 'status', '--hostname', 'github.com')
    remote_commit = json.loads(run('gh', 'api', f'repos/{repo}/commits/{target}'))
    require(remote_commit.get('sha') == target, 'Push the target commit to GitHub first')
    releases = run('gh', 'api', '--paginate', f'repos/{repo}/releases', '--jq', '.[].tag_name').splitlines()
    require(tag not in releases, f'Release {tag} already exists; refusing to replace it (including drafts)')
    refs = run('git', 'ls-remote', '--tags', 'origin', f'refs/tags/{tag}', f'refs/tags/{tag}^{{}}')
    if refs:
        values = dict(line.split()[::-1] for line in refs.splitlines())
        require(values.get(f'refs/tags/{tag}^{{}}', values.get(f'refs/tags/{tag}')) == target,
                'Remote tag points to another commit; refusing to move it')
    with tempfile.TemporaryDirectory(prefix='rownd-release-') as temporary:
        notes_file = Path(temporary) / 'notes.md'
        notes_file.write_text(notes)
        # Upload to a draft first: a failed upload must not expose a partial public release.
        command = ['gh', 'release', 'create', tag, '--repo', repo, '--target', target,
                   '--title', f'SuperTokens Rownd MAUI {version}', '--prerelease', '--draft',
                   '--latest=false', '--notes-file', str(notes_file)]
        if refs:
            command.append('--verify-tag')
        command.extend(str(asset) for asset in assets)
        try:
            run(*command)
            state = json.loads(run('gh', 'release', 'view', tag, '--repo', repo, '--json', 'assets,isDraft,isPrerelease'))
            actual = {a['name']: a['size'] for a in state['assets']}
            require(state['isDraft'] and state['isPrerelease'] and
                    actual == {a.name: a.stat().st_size for a in assets}, 'Draft asset verification failed')
            run('gh', 'release', 'edit', tag, '--repo', repo, '--draft=false', '--prerelease', '--latest=false')
        except (subprocess.CalledProcessError, ValueError):
            print(f'Publication did not complete. Inspect {repo} release {tag}; a draft may remain. No automatic overwrite or cleanup.')
            raise
    print(run('gh', 'release', 'view', tag, '--repo', repo, '--json', 'url', '--jq', '.url'))


if __name__ == '__main__':
    try:
        main()
    except (ValueError, OSError, KeyError, ET.ParseError, zipfile.BadZipFile, subprocess.CalledProcessError) as error:
        raise SystemExit(f'Release failed: {error}')
