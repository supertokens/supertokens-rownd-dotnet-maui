#!/usr/bin/env bash
set -euo pipefail
export ROWND_MAUI_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
python3 "$ROWND_MAUI_ROOT/scripts/check-native-sources.py"
python3 "$ROWND_MAUI_ROOT/scripts/prepare-android-source.py"
native="${ROWND_ANDROID_SOURCE:-$ROWND_MAUI_ROOT/../supertokens-rownd-android}"
cd "$native"
./gradlew --no-daemon -I "$ROWND_MAUI_ROOT/native/android/include.gradle" :mauiFacade:exportRuntime "$@"
cd "$ROWND_MAUI_ROOT"
dotnet restore bindings/Rownd.Android/Rownd.Android.csproj
python3 scripts/prepare-android-runtime.py
