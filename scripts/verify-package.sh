#!/usr/bin/env bash
set -euo pipefail
root="$(cd "$(dirname "$0")/.." && pwd)"
version="$(python3 -c 'import sys, xml.etree.ElementTree as ET; print(ET.parse(sys.argv[1]).findtext("./PropertyGroup/RowndPackageVersion"))' "$root/Rownd.Package.props")"
platform="${1:-android}"
[[ "$platform" == android || "$platform" == ios ]] || exit 2
consumer="$(mktemp -d "${TMPDIR:-/tmp/opencode}/rownd-consumer.XXXXXX")"
cp -R "$root/samples/Passwordless/Platforms" "$consumer/Platforms"
cp "$root"/samples/Passwordless/*.cs "$root/samples/Passwordless/Passwordless.csproj" "$consumer/"
cp "$root/global.json" "$root/Rownd.Package.props" "$consumer/"
# RowndUsePackage disables every source ProjectReference; an isolated package cache
# prevents a previous local prerelease with the same version satisfying this check.
dotnet restore "$consumer/Passwordless.csproj" -p:RowndUsePackage=true \
  -p:RowndTargetFrameworks="net10.0-$platform" -p:RowndApplicationId="${ROWND_APPLICATION_ID:?Set a build application ID}" \
  --packages "$consumer/packages" --source "${ROWND_PACKAGE_SOURCE:-$root/artifacts/packages/$platform/$version}" --source https://api.nuget.org/v3/index.json "${@:2}"
dotnet build "$consumer/Passwordless.csproj" -c Release --no-restore \
  -p:RowndUsePackage=true -p:RowndTargetFrameworks="net10.0-$platform" \
  -p:RowndApplicationId="$ROWND_APPLICATION_ID" -p:RestorePackagesPath="$consumer/packages" "${@:2}"
echo "Package-only build completed: $consumer. No install or launch performed."
