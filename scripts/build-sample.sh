#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
platform="${1:-}"
case "$platform" in
  android|ios) ;;
  *) echo 'Usage: build-sample.sh android|ios (ROWND_APPLICATION_ID required)' >&2; exit 2 ;;
esac
: "${ROWND_APPLICATION_ID:?Set the sample application identifier explicitly}"
if [[ "$platform" == ios && "$(uname -s)" != Darwin ]]; then
  echo 'iOS build requires macOS and matching Xcode. No iOS build performed.' >&2
  exit 2
fi
dotnet build samples/Passwordless/Passwordless.csproj -c Debug \
  -p:RowndTargetFrameworks="net10.0-$platform" -p:RowndApplicationId="$ROWND_APPLICATION_ID"
