"""Offline platform identifier validation and generated association identity."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

SCRIPT = Path(__file__).resolve().parents[2] / 'scripts/generate-link-associations.py'
spec = importlib.util.spec_from_file_location('associations', SCRIPT)
associations = importlib.util.module_from_spec(spec)
spec.loader.exec_module(associations)


class PlatformIdentifierTests(unittest.TestCase):
    def generate(self, output, package='com.example.android_app', bundle='com.example.ios-app', prefix='AB12345678'):
        associations.generate('auth.example.test', package, [':'.join(['ab'] * 32)], prefix, bundle, output)

    def test_ios_hyphen_android_underscore_and_signed_prefix_preserved(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            self.generate(output)
            aasa = json.loads((output / '.well-known/apple-app-site-association').read_text())
            self.assertEqual(aasa['applinks']['details'][0]['appID'], 'AB12345678.com.example.ios-app')
            assets = json.loads((output / '.well-known/assetlinks.json').read_text())
            self.assertEqual(assets[0]['target']['package_name'], 'com.example.android_app')

    def test_invalid_platform_identifiers_fail_before_writing(self):
        cases = [{'bundle': value} for value in ('com.example.ios_app', 'com..app', 'com.example.app/', '*.app')]
        cases += [{'package': value} for value in ('com.example.android-app', 'com.1app', 'com..app', 'app')]
        cases += [{'prefix': value} for value in ('AB123', 'ab12345678', 'AB12345678.com')]
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'generated'
            for case in cases:
                with self.subTest(case=case), self.assertRaises(ValueError):
                    self.generate(output, **case)
                self.assertFalse(output.exists())


if __name__ == '__main__':
    unittest.main()
