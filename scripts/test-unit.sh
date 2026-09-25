#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
dotnet test tests/Rownd.UnitTests/Rownd.UnitTests.csproj -c Release "$@"
