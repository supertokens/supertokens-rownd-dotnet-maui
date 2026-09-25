#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 4 || "$1" != --platform || "$3" != --scenario ]]; then
  echo 'Usage: test-passwordless.sh --platform android|ios --scenario smoke|phone-magic-link|delayed-startup|refresh-recovery' >&2
  exit 2
fi
case "$2" in android|ios) ;; *) exit 2 ;; esac
case "$4" in smoke|phone-magic-link|delayed-startup|refresh-recovery) ;; *) exit 2 ;; esac
echo "BLOCKED: $2/$4 has no concrete mobile driver or M2 native bindings. A Mac alone cannot run unfinished automation. See tests/e2e/scenarios.md. No auth test ran." >&2
exit 2
