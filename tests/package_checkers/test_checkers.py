"""Offline unit tests using synthetic archives/headers, not platform builds."""
import importlib.util
import io
import plistlib
import tempfile
import unittest
import warnings
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def load_checker(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


android = load_checker('check-android-package')
ios = load_checker('check-ios-framework')


def archive(entries):
    data = io.BytesIO()
    with zipfile.ZipFile(data, 'w') as result:
        with warnings.catch_warnings():
            warnings.filterwarnings('ignore', message='Duplicate name:', category=UserWarning)
            for name, content in entries:
                result.writestr(name, content)
    return data.getvalue()


def package(libraries, extra_aars=()):
    facade = archive([
        ('AndroidManifest.xml', '<manifest/>'),
        ('classes.jar', archive([('io/supertokens/rownd/maui/RowndBridge.class', b'class')]))])
    native = archive([
        ('AndroidManifest.xml', '<manifest/>'),
        ('classes.jar', archive([('io/rownd/android/RowndClient.class', b'class')])),
        ('res/values/strings.xml', '<resources/>')])
    return io.BytesIO(archive([
        ('lib/net10.0-android/mauiFacade-release.aar', facade),
        ('lib/net10.0-android/android-release.aar', native),
        ('lib/net10.0-android/runtime.aar', archive(libraries)),
        *extra_aars]))


class AndroidPackageTests(unittest.TestCase):
    def setUp(self):
        # Deliberately independent of the checker's constants: contract shrinkage
        # must not silently shrink the negative fixtures as well.
        self.libraries = [
            (f'jni/{abi}/{library}', b'ELF fixture')
            for abi in ('armeabi-v7a', 'arm64-v8a', 'x86', 'x86_64')
            for library in ('libdatastore_shared_counter.so', 'libandroidx.graphics.path.so')]

    def test_complete_package(self):
        android.check_package(package(self.libraries))

    def test_only_arm64_missing(self):
        libraries = [(name, data) for name, data in self.libraries if '/arm64-v8a/' not in name]
        with self.assertRaisesRegex(AssertionError, 'jni/arm64-v8a/'):
            android.check_package(package(libraries))

    def test_each_required_library_in_each_abi(self):
        for missing, _ in self.libraries:
            with self.subTest(missing=missing), self.assertRaisesRegex(AssertionError, 'Missing native shared library'):
                android.check_package(package([(n, d) for n, d in self.libraries if n != missing]))

    def test_incorrect_path_or_name(self):
        original, content = self.libraries[2]
        for replacement in (original.replace('jni/', 'assets/jni/'),
                            original.replace('jni/', 'lib/'),
                            original.replace('.so', '.so.backup.so')):
            with self.subTest(replacement=replacement), self.assertRaisesRegex(AssertionError, 'Missing native shared library'):
                android.check_package(package([(replacement if n == original else n, d) for n, d in self.libraries]))

    def test_duplicate_in_one_aar(self):
        with self.assertRaisesRegex(AssertionError, 'Repeated native shared libraries'):
            android.check_package(package([*self.libraries, self.libraries[2]]))

    def test_duplicate_across_aars(self):
        with self.assertRaisesRegex(AssertionError, 'Repeated native shared libraries'):
            android.check_package(package(self.libraries, [('runtime/copy.aar', archive([self.libraries[2]]))]))

    def test_conflicting_duplicate_in_one_aar(self):
        with self.assertRaisesRegex(AssertionError, 'Conflicting copies'):
            android.check_package(package([*self.libraries, (self.libraries[2][0], b'different ELF')]))


class IosFrameworkTests(unittest.TestCase):
    def setUp(self):
        self.header = (Path(__file__).parent / 'fixtures/RowndMauiBridge-Swift.h').read_text()
        self.api = (ROOT / 'bindings/Rownd.iOS/ApiDefinition.cs').read_text()

    def test_full_selectors(self):
        ios.check_selectors(self.header, self.api)

    def test_renamed_hub_url(self):
        with self.assertRaisesRegex(AssertionError, 'configureWithAppKey:apiDomain:apiBasePath:hubURL:scheme:completion:'):
            ios.check_selectors(self.header.replace('hubURL:', 'hubUrl:'), self.api)

    def test_sign_in_with_options_is_not_no_arg_selector(self):
        with self.assertRaisesRegex(AssertionError, 'requestSignIn'):
            ios.check_selectors(self.header.replace('requestSignIn;', 'requestSignInWithOptions:(NSDictionary *)options;'), self.api)

    def test_selector_in_other_class_or_comment_does_not_count(self):
        header = self.header.replace('- (void)requestSignIn;', '// - (void)requestSignIn;')
        header += '\n@interface AnotherBridge : NSObject\n- (void)requestSignIn;\n@end\n'
        with self.assertRaisesRegex(AssertionError, 'requestSignIn'):
            ios.check_selectors(header, self.api)

    def test_class_method_does_not_satisfy_instance_binding(self):
        with self.assertRaisesRegex(AssertionError, 'requestSignIn'):
            ios.check_selectors(self.header.replace('- (void)requestSignIn;', '+ (void)requestSignIn;'), self.api)

    def test_missing_bridge_declaration(self):
        with self.assertRaisesRegex(AssertionError, 'Missing or repeated RWNRowndBridge'):
            ios.check_selectors(self.header.replace('RWNRowndBridge', 'AnotherBridge'), self.api)

    def test_exports_come_from_binding(self):
        api = self.api.replace('[Export("dispose")]', '[Export("close")]')
        with self.assertRaisesRegex(AssertionError, 'close'):
            ios.check_selectors(self.header, api)

    def test_synthetic_xcframework_checks_each_slice(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            slices = []
            for identifier, variant in [('ios-arm64', None), ('ios-arm64-simulator', 'simulator')]:
                entry = dict(LibraryIdentifier=identifier, LibraryPath='RowndMauiBridge.framework',
                             SupportedPlatform='ios', SupportedArchitectures=['arm64'])
                if variant:
                    entry['SupportedPlatformVariant'] = variant
                slices.append(entry)
                framework = root / identifier / entry['LibraryPath']
                (framework / 'Headers').mkdir(parents=True)
                (framework / 'Headers/RowndMauiBridge-Swift.h').write_text(self.header)
                (framework / 'RowndMauiBridge').write_bytes(b'synthetic binary placeholder')
                (framework / 'Rownd_Rownd.bundle').mkdir()
                (framework / 'GoogleSignIn_GoogleSignIn.bundle').mkdir()
            (root / 'Info.plist').write_bytes(plistlib.dumps(dict(AvailableLibraries=slices)))
            ios.check_framework(root, self.api)
            simulator_header = root / 'ios-arm64-simulator/RowndMauiBridge.framework/Headers/RowndMauiBridge-Swift.h'
            simulator_header.write_text(self.header.replace('hubURL:', 'hubUrl:'))
            with self.assertRaisesRegex(AssertionError, 'hubURL:'):
                ios.check_framework(root, self.api)


if __name__ == '__main__':
    unittest.main()
