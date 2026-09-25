#!/usr/bin/env bash
set -euo pipefail
if [[ $# != 4 || "$1" != --platform || "$3" != --scenario ]]; then
  echo 'Usage: test-passwordless.sh --platform android|ios --scenario smoke|sms-otp|phone-magic-link|cold-phone-magic-link|delayed-startup|email-magic-link|expired-link|https-magic-link|refresh-recovery' >&2
  exit 2
fi
case "$2" in android|ios) ;; *) exit 2 ;; esac
case "$4" in smoke|sms-otp|phone-magic-link|cold-phone-magic-link|delayed-startup|email-magic-link|expired-link|https-magic-link|refresh-recovery) ;; *) exit 2 ;; esac
if [[ "$4" == refresh-recovery ]]; then
  echo 'BLOCKED: concrete refresh/recovery driver remains M5 work.' >&2
  exit 2
fi
[[ "${ROWND_RUN_E2E:-}" == 1 ]] || { echo 'Set ROWND_RUN_E2E=1 explicitly.' >&2; exit 2; }
exec python3 "$(dirname "$0")/../tests/e2e/magic_links.py" "$2" "$4"
