#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
platform="${1:-android}"
case "$platform" in
  android) binding=Rownd.Android ;;
  ios) binding=Rownd.iOS ;;
  all) binding=all ;;
  *) echo 'Usage: pack.sh android|ios|all' >&2; exit 2 ;;
esac
if [[ "$platform" != android && "$(uname -s)" != Darwin ]]; then
  echo 'iOS/combined packaging requires macOS and the pinned iOS workload/Xcode.' >&2
  exit 2
fi
out="$root/artifacts/packages/$platform"
dotnet pack src/Rownd.Foundation/Rownd.Foundation.csproj -c Release -o "$out"
if [[ "$platform" == all ]]; then
  dotnet pack bindings/Rownd.Android/Rownd.Android.csproj -c Release -o "$out"
  dotnet pack bindings/Rownd.iOS/Rownd.iOS.csproj -c Release -o "$out"
  dotnet pack src/Rownd.Maui/Rownd.Maui.csproj -c Release -o "$out"
  python3 scripts/check-package-dependencies.py "$out"
else
  dotnet pack "bindings/$binding/$binding.csproj" -c Release -o "$out"
  dotnet pack src/Rownd.Maui/Rownd.Maui.csproj -c Release -p:RowndTargetFrameworks="net10.0-$platform" -o "$out"
fi
echo "Provisional packages ($platform): $out (no runtime acceptance claimed)"
