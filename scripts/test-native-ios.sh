#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
: "${ROWND_IOS_TEST_DESTINATION:?Set an explicit iOS Simulator destination}"
python3 "$root/scripts/check-native-sources.py"
cd "$root/../supertokens-rownd-ios"
xcodebuild test -scheme Rownd \
  -destination "$ROWND_IOS_TEST_DESTINATION" \
  -derivedDataPath "$root/native/ios/build/auth-tests" \
  -only-testing:RowndTests/AuthIdentityPersistenceTests \
  -parallel-testing-enabled NO CODE_SIGNING_ALLOWED=NO "$@"
