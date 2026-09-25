# Device scenarios — runtime validation pending

M2 adds an opt-in Appium driver for the **initial** email OTP and warm captured-phone-link smoke, backed by the real native sample. It has never been run. See [driver setup and exact limits](../../docs/m2-status.md). `scripts/test-passwordless.sh` requires `ROWND_RUN_E2E=1`; delayed-startup and refresh-recovery still exit **2 (blocked)**.
`PasswordlessScenarios.cs` compiles the fuller email OTP, phone warm/cold/replay, delayed initialization and refresh/recovery orchestration below. Its richer device-driver interfaces still have no concrete mobile implementation. The initial Appium driver does not satisfy those complete contracts. Offline unit tests use recording/scripted doubles to validate the runner's decisions, not authentication.
The sample's stable action IDs are `sign-in`, `auth-status`, `protected-api`, `sign-out`.
No integration or device scenario was executed during M1 or M2 implementation.

## smoke (Android and iOS)

1. Reset isolated harness/app state, then launch the actual MAUI app signed out.
2. Tap sign-in; create an email OTP challenge in the real Hub. Read captured code from shared Android harness.
3. Complete OTP in Hub, wait for native-backed C# authenticated state.
4. Tap protected-api; retrieve the token through the C# native facade and send request-scoped bearer header.
5. Assert HTTP 200 and backend-verified expected user, dismissed Hub, responsive host.
6. Run real-expiry refresh assertions below, sign out, relaunch and assert no session.

## phone-magic-link (Android and iOS)

1. Reset captures/counters in an isolated fixture; use a unique E.164 number per case.
2. Create the challenge through real Hub phone UI. No session-minting endpoint.
3. Use `HarnessClient.ReadPhoneLinkAsync` to read that exact phone's callback. A capture alone is not a login.
4. Background app; dispatch captured callback via OS. For custom scheme, replace only origin/path and preserve original encoded query/fragment.
5. Assert app foreground, one successful consume/completion, native C# session, Hub dismissed, protected API verifies phone user's identity.
6. Replay callback; assert no second successful consume, same session and responsive host.
7. Repeat with a fresh challenge for warm, terminated (retain data), and delayed-startup cases. Expired callback must not authenticate.
8. Run refresh assertions, then process kill/relaunch and protected request. Sign out and repeat sign-in.

## refresh-recovery (after both OTP and phone login)

Use genuine Core-issued expiry longer than iOS's 60-second refresh margin. Save old token only in memory.
After expiry, plain bearer request with old token must return 401. Native C# getter must obtain a token accepted for the same user/session, with increased `stRefresh` and no new consume or Hub presentation.
Repeat expiry with `/test/refresh-availability` unavailable: getter faults recoverably, no false logout. Restore backend, retry getter and verify protected access.

Implemented contract: `IRefreshDeviceDriver` retains the native token only in memory, waits for actual Core expiry, makes a plain old-token request, controls fixture availability, invokes the sample getter and reports session/refresh/sign-out observations. `RefreshRecoveryAsync` asserts 401, increased refresh counters, stable user/session/consume state, a recoverable outage result and protected access after recovery. Availability restoration runs in `finally` with a separate bounded cleanup token, including on cancellation. Supplying this driver to `PasswordlessScenarios` composes the check before sign-out after either login path; omitting it does not establish refresh coverage.

## delayed-startup

`PhoneMagicLinkDuringStartupAsync` creates/captures the real challenge, terminates the process, holds native initialization on the next launch, opens the exact callback externally, and asserts zero successful consumes before releasing initialization. It then verifies the protected identity and replay behavior. `IDelayedStartupDeviceDriver` must implement a real startup gate and backend counter observation; the runner releases the gate in `finally`, including cancellation. This gate is test instrumentation, not a production auth API.

Driver implementations must honor cancellation, use bounded condition waits, derive observations from actual UI/native/backend state, and fail rather than fabricate values. Refresh/session observations are non-secret; saved token bytes must never enter logs or reports. Startup-delay, refresh and OS-dispatch contracts remain unimplemented at the mobile boundary. Verified HTTPS/browser-fallback and lifecycle extensions below still require concrete automation.

## Separate physical routing gates

After customer identifiers/domain/signing are known, generate domain association files.
Check untargeted HTTPS OS open on Android and external link tap on iPhone; forced-package dispatch does not prove association.
Open actual captured HTTPS callback in browser, tap actual Hub “Open in app”, verify no browser consume and subsequent native protected access.
Use captured Hub links only: no real SMS delivery checks in this scope.
Record platform/OS, pinned commits, scenario outcome, verified non-secret identity and counters; never tokens, codes or callback URLs.
