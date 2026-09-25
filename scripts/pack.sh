#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
cd "$root"
platform="${1:-android}"
case "$platform" in
  android) binding=Rownd.Android ;;
  ios) binding=Rownd.iOS ;;
  *) echo 'Usage: pack.sh android|ios' >&2; exit 2 ;;
esac
out="$root/artifacts/packages/$platform"
dotnet pack src/Rownd.Foundation/Rownd.Foundation.csproj -c Release -o "$out"
dotnet pack "bindings/$binding/$binding.csproj" -c Release -o "$out"
dotnet pack src/Rownd.Maui/Rownd.Maui.csproj -c Release -p:RowndTargetFrameworks="net10.0-$platform" -o "$out"
echo "Provisional $platform-only packages: $out (no runtime acceptance claimed)"
