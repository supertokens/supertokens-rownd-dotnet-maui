#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
: "${ROWND_IOS_TEST_DESTINATION:?Set an explicit iOS Simulator destination}"
python3 "$root/scripts/prepare-ios-source.py"
cd "$root/native/ios/build/patched-native"
xcodebuild test -scheme Rownd \
  -destination "$ROWND_IOS_TEST_DESTINATION" \
  -derivedDataPath "$root/native/ios/build/auth-tests" \
  -only-testing:RowndTests/MauiAuthIdentityTests \
  -parallel-testing-enabled NO CODE_SIGNING_ALLOWED=NO "$@"
