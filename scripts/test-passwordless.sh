#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 4 || "$1" != --platform || "$3" != --scenario ]]; then
  echo 'Usage: test-passwordless.sh --platform android|ios --scenario smoke|phone-magic-link|delayed-startup|refresh-recovery' >&2
  exit 2
fi
case "$2" in android|ios) ;; *) exit 2 ;; esac
case "$4" in smoke|phone-magic-link|delayed-startup|refresh-recovery) ;; *) exit 2 ;; esac
if [[ "$4" != smoke && "$4" != phone-magic-link ]]; then
  echo 'BLOCKED: concrete delayed-startup and refresh/recovery drivers remain pending.' >&2
  exit 2
fi
[[ "${ROWND_RUN_E2E:-}" == 1 ]] || { echo 'Set ROWND_RUN_E2E=1 explicitly.' >&2; exit 2; }
exec python3 "$(dirname "$0")/../tests/e2e/appium_smoke.py" "$2" "$4"
