"""Release validation and publication sequencing, without network mutations."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch
import zipfile
import hashlib

SPEC = importlib.util.spec_from_file_location('release', Path(__file__).resolve().parents[2] / 'scripts/release-github.py')
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.version = '0.0.1-beta.1'
        self.folder = self.root / 'artifacts/releases' / self.version
        self.folder.mkdir(parents=True)
        self.archive = self.folder.parent / f'SuperTokens.Rownd.{self.version}.zip'
        self.sha = 'a' * 40
        self.manifest = {'revision': self.sha, 'pins': {}, 'worktreeDirty': True,
                         'runtimeAcceptance': {'android': 'PASS Debug', 'ios': 'PASS simulator Release'}, 'artifacts': {}}
        for name in release.IDS:
            path = self.folder / f'{name}.{self.version}.nupkg'
            with zipfile.ZipFile(path, 'w') as z:
                z.writestr(name + '.nuspec', f'<package><metadata><id>{name}</id><version>{self.version}</version></metadata></package>')
            self.manifest['artifacts'][path.name] = hashlib.sha256(path.read_bytes()).hexdigest()
        (self.folder / 'manifest.json').write_text(json.dumps(self.manifest))
        (self.folder / 'SHA256SUMS').write_text(''.join(f'{h}  {n}\n' for n, h in self.manifest['artifacts'].items()))
        (self.folder / 'VALIDATION.md').write_text('Limited beta; smoke checked, production gates open.')
        (self.folder / 'beta-integration.md').write_text('Install all four packages.')
        self.props = f'<Project><PropertyGroup><RowndPackageVersion>{self.version}</RowndPackageVersion></PropertyGroup></Project>'
        (self.root / 'Rownd.Package.props').write_text(self.props)
        self.bundle()

    def bundle(self):
        with zipfile.ZipFile(self.archive, 'w') as z:
            for p in self.folder.iterdir():
                z.write(p, p.name)

    def validate(self):
        return release.validate(self.folder, self.archive, self.version)

    def test_valid_bundle_and_github_remote(self):
        self.assertEqual(len(self.validate()[1]), 9)
        self.assertEqual(release.remote_repo('git@github.com:owner/repo.git'), 'owner/repo')
        self.assertEqual(release.remote_repo('https://github.com/owner/repo.git'), 'owner/repo')
        with self.assertRaises(ValueError):
            release.remote_repo('https://example.com/owner/repo')

    def test_changed_package_is_rejected(self):
        next(self.folder.glob('*.nupkg')).write_bytes(b'changed')
        with self.assertRaisesRegex(ValueError, 'Checksum mismatch'):
            self.validate()

    def test_stale_zip_is_rejected(self):
        (self.folder / 'beta-integration.md').write_text('Different guide')
        with self.assertRaisesRegex(ValueError, 'ZIP/asset mismatch'):
            self.validate()

    def test_unexpected_package_is_rejected(self):
        (self.folder / 'old.nupkg').touch()
        with self.assertRaisesRegex(ValueError, 'exactly four'):
            self.validate()

    def test_unrun_smoke_is_rejected(self):
        self.manifest['runtimeAcceptance'] = 'UNRUN'
        (self.folder / 'manifest.json').write_text(json.dumps(self.manifest))
        self.bundle()
        with self.assertRaisesRegex(ValueError, 'Both platform'):
            self.validate()

    def test_stable_release_is_rejected(self):
        with self.assertRaisesRegex(ValueError, 'Only prerelease'):
            release.validate(self.folder, self.archive, '1.0.0')

    def exercise(self, publish=False, fail_upload=False, existing=False, wrong_tag=False):
        calls = []
        def fake(*args, **kwargs):
            calls.append(args)
            if args[:2] == ('git', 'rev-parse'): return self.sha
            if args[:3] == ('git', 'remote', 'get-url'): return 'git@github.com:owner/repo.git'
            if args[:2] == ('git', 'show'):
                return self.props if args[2].endswith('Rownd.Package.props') else '{}'
            if args[:2] == ('git', 'ls-remote'):
                return ('b' * 40 + '\trefs/tags/v' + self.version) if wrong_tag else ''
            if args[:2] in [('git', 'status'), ('gh', 'auth')]: return ''
            if args[:2] == ('gh', 'api'):
                if '--paginate' in args: return 'v' + self.version if existing else ''
                return json.dumps({'sha': self.sha})
            if args[:3] == ('gh', 'release', 'create'):
                if fail_upload: raise subprocess.CalledProcessError(1, args)
                return ''
            if args[:3] == ('gh', 'release', 'view'):
                if 'assets,isDraft,isPrerelease' in args:
                    assets = list(self.folder.iterdir()) + [self.archive]
                    return json.dumps({'isDraft': True, 'isPrerelease': True,
                                       'assets': [{'name': p.name, 'size': p.stat().st_size} for p in assets]})
                return 'https://github.com/owner/repo/releases/tag/v' + self.version
            if args[:3] == ('gh', 'release', 'edit'): return ''
            raise AssertionError(args)
        argv = ['release'] + (['--publish'] if publish else [])
        with patch.object(release, 'ROOT', self.root), patch.object(release, 'run', side_effect=fake), \
             patch.object(release.subprocess, 'run', return_value=subprocess.CompletedProcess([], 0)), \
             patch('sys.argv', argv), contextlib.redirect_stdout(io.StringIO()):
            try:
                release.main()
            except (ValueError, subprocess.CalledProcessError):
                if not (fail_upload or existing or wrong_tag): raise
        return calls

    def test_default_dry_run_never_contacts_github(self):
        self.assertFalse(any(c[0] == 'gh' for c in self.exercise()))

    def test_publish_uploads_draft_before_publishing(self):
        calls = self.exercise(publish=True)
        create = next(c for c in calls if c[:3] == ('gh', 'release', 'create'))
        edit = next(c for c in calls if c[:3] == ('gh', 'release', 'edit'))
        self.assertIn('--draft', create)
        self.assertIn('--prerelease', create)
        self.assertIn('--draft=false', edit)
        self.assertLess(calls.index(create), calls.index(edit))

    def test_failed_upload_never_publishes(self):
        calls = self.exercise(publish=True, fail_upload=True)
        self.assertFalse(any(c[:3] == ('gh', 'release', 'edit') for c in calls))

    def test_conflicting_tag_is_not_moved(self):
        calls = self.exercise(publish=True, wrong_tag=True)
        self.assertFalse(any(c[:3] == ('gh', 'release', 'create') for c in calls))

    def test_existing_release_is_not_overwritten(self):
        calls = self.exercise(publish=True, existing=True)
        self.assertFalse(any(c[:3] == ('gh', 'release', 'create') for c in calls))


if __name__ == '__main__':
    unittest.main()
