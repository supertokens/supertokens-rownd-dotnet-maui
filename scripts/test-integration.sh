#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
case "${1:-}" in
  environment|phone-capture) ;;
  *) echo 'Usage: test-integration.sh environment|phone-capture' >&2; exit 2 ;;
esac
if [[ "${ROWND_RUN_INTEGRATION:-}" != 1 ]]; then
  echo 'Set ROWND_RUN_INTEGRATION=1 to opt in. These checks contact the fixture.' >&2
  exit 2
fi
dotnet run --project tests/Rownd.IntegrationTests/Rownd.IntegrationTests.csproj -c Release -- "$1"
