# M1 status — 2026-09-25

## Approved acceptance scope

M1 is a reproducible project/configuration foundation with meaningful unit/mock tests and opt-in integration/E2E scaffolding. Native login belongs to M2. All integration, E2E and device execution is deferred to the user on Mac; no real SMS tests. Public publishing postponed. Customer upgrades `Rownd.Maui` and targets .NET 10.

Implemented: exact SDK/workload and native source pins; isolated config validator; minimal Android/iOS MAUI sample; fixture health/401 and captured-phone-link assertions; phone challenge/replay, email OTP, delayed-startup and refresh/recovery orchestration awaiting real device drivers; Linux unit-only CI and compile-only integration check; disabled inherited release hooks.

## Shared fixture

Use sibling `supertokens-rownd-android/test-server` for **both platforms**, at the commit in `eng/versions.json`. It already configures `EMAIL_OR_PHONE` / `USER_INPUT_CODE_AND_MAGIC_LINK`; its SMS sink captures `phoneNumber`, `urlWithLinkCode`, and `userInputCode`. Do not use the iOS harness's no-op SMS sink.

After reviewing/installing pinned sibling npm dependencies, the user can start it with `npm run test:integration:harness` from the Android repository. Supply `ANDROID_HUB_URL` for the pinned Hub server, `ANDROID_PUBLIC_API_URL` for device-visible backend routing, and `ANDROID_HOST` as appropriate. This command starts Docker-backed Core/Postgres; it was not run here. The sibling `test-server/local-hub.ts` documents building/serving the pinned Hub. Backend dependencies come from that Android commit's package-lock, including Rownd plugin 0.3.0-beta.2.

**Reproducibility gap:** the pinned harness still names an unversioned Core image (`supertokens/supertokens-postgresql`). Select and record a tested image digest before treating the auth environment as reproducible. No new Core version or Docker digest has been invented. Native release numbers are source pins, not verified published binary artifacts.

Use a unique test phone and reset isolated captures before a Hub-created challenge. `phone-capture` reads `/captures/latest?phoneNumber=<encoded E.164>`, verifies exact phone and mobile query/fragment, never prints links/codes. Standalone capture checks depend on that operator freshness step; E2E orchestration rejects an existing capture before creating its challenge. A real protected call from a native token remains an M2 gate.

Android emulator reaches host via `10.0.2.2`; iOS simulator ordinarily uses `localhost`. Physical devices require a reachable host/custom HTTPS subdomain. Confirm the actual host mapping on the user's network. Fixture endpoints are test-only and must not be deployed publicly without access controls.

## Configuration to obtain

- Actual Android application ID/iOS bundle ID (`ROWND_APPLICATION_ID`), signing identities and provisioning.
- App key, API origin/base path, Hub URL, custom scheme, HTTPS subdomain and production same-device policy.
- Generate assetlinks/AASA only after identifiers/signing are known. Verify actual Hub fallback scheme before lifecycle wiring.
- Matching Xcode for pinned iOS workload 26.5.10318; Mac build and device access remain pending.

The build-only identifier `io.supertokens.maui.buildcheck` was used locally to compile Android. It is not a customer identity, link registration or signing configuration.

## Evidence

- Unit tests after focused review: **48 passed, 0 failed, 0 skipped**, all offline/in-memory HTTP and recording/scripted driver doubles. The 25 added orchestrator cases cover stale captures, cancellation, byte-preserving URL forwarding, invalid session/UI observations, replay consumes/session replacement, delayed-startup ordering/cleanup, and refresh/expiry/outage/recovery assertions. These are unit tests of runner logic, not executed integration/E2E scenarios or native evidence.
- Android Debug sample built with .NET 10.0.401 / MAUI 10.0.20 / Android workload 36.1.69. No install or launch.
- Integration project compiled only. Its runtime requires explicit opt-in.
- Final Android and integration builds: **0 warnings, 0 errors**.
- Focused review reran the unit project and compiled the integration/scenario project only (0 warnings/errors); Android evidence above is from the initial M1 build, since no sample code changed in review.
- `python3 scripts/check-native-sources.py`: Android, iOS and Hub pinned commits matched with no tracked modifications.
- `bash -n scripts/build-sample.sh scripts/test-unit.sh scripts/test-integration.sh scripts/test-passwordless.sh` and `git diff --check`: passed.
- iOS build not attempted: Linux host, no Mac/Xcode.
- Integration, E2E, phone capture, backend health/auth, device routing, refresh and native package checks: **not run**.

An initial Android command used global `TargetFrameworks`, which propagated into the foundation reference and failed restore targeting. The corrected build script uses sample-specific `RowndTargetFrameworks`; Android build then succeeded.

Final executable checks (after sourcing `/home/dev/.config/rownd-android-tooling/env.sh`):

```sh
./scripts/test-unit.sh --nologo -v quiet
dotnet build tests/Rownd.IntegrationTests/Rownd.IntegrationTests.csproj -c Release --nologo -v quiet
ROWND_APPLICATION_ID=io.supertokens.maui.buildcheck ./scripts/build-sample.sh android
python3 scripts/check-native-sources.py
bash -n scripts/build-sample.sh scripts/test-unit.sh scripts/test-integration.sh scripts/test-passwordless.sh
git diff --check
```

## Open gates

M1 runtime environment gate remains open: pinned Core digest, customer config/same-device policy, network reachability, fresh real-Hub capture, protected backend identity and iOS build. M2 must supply native facades/bindings, native resources, lifecycle adapters and real automation drivers before the sample's auth buttons are enabled. Refresh/recovery and delayed-startup runner logic now exist, with offline unit tests of scripted observations, but all concrete mobile drivers remain absent. Verified HTTPS/browser routing and further lifecycle orchestration remain future work. A Mac alone cannot run unfinished M2-dependent automation; E2E CLI remains nonzero and cannot load unit doubles as a substitute.

Existing git history is intact at baseline `bc7291c`. Origin already points to the SuperTokens fork; no remote writes performed. No top-level license file existed in this checkout; inherited files/headers were retained, license provenance needs confirmation before distribution. No package identity reservation, NuGet pack/publish, commit, push or signing changes were performed.
