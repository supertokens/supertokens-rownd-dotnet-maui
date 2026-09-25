#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
[[ $(uname -s) == Darwin ]] || { echo 'Requires macOS, Xcode and xcodegen' >&2; exit 2; }
python3 "$root/scripts/check-native-sources.py"
cd "$root/native/ios"
xcodegen generate
mkdir -p RowndMauiBridge.xcodeproj/project.xcworkspace/xcshareddata/swiftpm
cp ../../../supertokens-rownd-ios/Package.resolved RowndMauiBridge.xcodeproj/project.xcworkspace/xcshareddata/swiftpm/Package.resolved
for platform in iphoneos iphonesimulator; do
  xcodebuild archive -project RowndMauiBridge.xcodeproj -scheme RowndMauiBridge \
    -sdk "$platform" -archivePath "build/$platform.xcarchive" \
    -derivedDataPath "build/$platform" -onlyUsePackageVersionsFromResolvedFile \
    CODE_SIGNING_ALLOWED=NO SKIP_INSTALL=NO
  # SwiftPM Bundle.module resolves resources alongside the aggregate framework.
  find "build/$platform/Build" -type d -name '*.bundle' -prune \
    -exec cp -R '{}' "build/$platform.xcarchive/Products/Library/Frameworks/RowndMauiBridge.framework/" \;
done
rm -rf build/RowndMauiBridge.xcframework
xcodebuild -create-xcframework \
  -framework build/iphoneos.xcarchive/Products/Library/Frameworks/RowndMauiBridge.framework \
  -framework build/iphonesimulator.xcarchive/Products/Library/Frameworks/RowndMauiBridge.framework \
  -output build/RowndMauiBridge.xcframework
python3 "$root/scripts/check-ios-framework.py"
