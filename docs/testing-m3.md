# M3 validation runbook

Run from the repository root. **M3 release acceptance remains open.** This is a procedure, not a report of completed runs. Record each gate as **PASS**, **FAIL**, **BLOCKED** (with reason), or **UNRUN**, against an exact revision and artifact hash. See [M3 status](m3-status.md) for current evidence and [testing.md](testing.md) for fixture setup, tool installation and earlier runtime results. Earlier source Debug/emulator results do not validate M3 package-only Release apps.

## 1. Preconditions and offline tests

Use `eng/versions.json` and `global.json`: .NET SDK/workload set 10.0.200, MAUI 10.0.20, Android workload 36.1.43, iOS workload 26.2.10217, JDK 21.0.12; Mac builds require Xcode 26.2 and XcodeGen. Record `dotnet --info`, `dotnet workload list`, Java/Xcode versions and sibling revisions. The Linux verification host's pinned Android workload repair and package-only Release build passed; see [M3 status](m3-status.md) for evidence. Check these prerequisites independently on each new host.

```sh
python3 scripts/check-native-sources.py
bash scripts/test-unit.sh --nologo -v quiet
python3 -m unittest discover -s tests/package_checkers -p 'test_*.py' -v
```

The Python tests use synthetic archives/headers; they test the checkers, not real packages. Source validation checks **all** siblings, including when called by the Android native wrapper. If the pinned iOS sibling is unavailable, record that blocker; do not substitute an older commit to obtain a green result.

The iOS pin `95bd10b6c5bec1678fa6094e031a3e1cbf900901` is local/unreleased; `0.2.4` is its base version. Preserve the pin. Upstream release is deferred: dependent checks may be deferred for development, but are not passed. After publication, update commit/version, rebuild the XCFramework and clean/rebuild consumers before rerunning affected checks. Native iOS process-fatal initialization (`fatalError`) remains a separate release gate.

## 2. Android package-only Release

With source checks and workloads ready:

```sh
bash scripts/build-native-android.sh :android:testDebugUnitTest
bash scripts/pack.sh android
python3 scripts/check-android-package.py
export ROWND_APPLICATION_ID=io.supertokens.maui.buildcheck
bash scripts/verify-package.sh android
```

Use an existing writable `TMPDIR` if the verifier's `/tmp/opencode` fallback is unavailable. The verifier copies the sample outside the checkout, restores an isolated package cache with `RowndUsePackage=true`, and builds **Release**; it prints the consumer directory and does not install/launch. Preserve that directory and build log. Confirm no source project references, no XA4301 duplicate-native-library warnings, and no linker/AOT overrides hiding callback issues. Strict package inspection must find no repeated JNI paths and retain datastore/graphics libraries across all four supported ABIs. A successful pack alone is insufficient.

After changing JNI packaging, clean the binding/facade `bin` and `obj` directories and regenerate affected local `.nupkg` files before verifying; a stale same-version package survived incremental packing during M3 verification. Preserve earlier evidence before replacing outputs. The binding-only checker does not detect JNI libraries re-embedded by the facade package: inspect all AARs across the feed and require a consumer build without XA4301 warnings. If cleaning native Gradle outputs, run clean before `prepare-android-source.py` regenerates the overlay under `native/android/build`.

## 3. Mac iOS and combined feed

Rebuild native artifacts at the pinned sources. Clean managed iOS binding/facade/consumer intermediates when replacing embedded frameworks or switching workloads; incremental reuse of an older framework has occurred before. See the clean example in [testing.md](testing.md#native-identity-state-fix).

```sh
bash scripts/build-native-ios.sh
python3 scripts/check-ios-framework.py native/ios/build/RowndMauiBridge.xcframework
bash scripts/pack.sh ios
export ROWND_APPLICATION_ID=io.supertokens.maui.buildcheck
bash scripts/verify-package.sh ios \
  -p:RuntimeIdentifier=iossimulator-arm64 -p:CodesignKey=- -p:CodesignProvision=

bash scripts/build-native-android.sh
bash scripts/pack.sh all
python3 scripts/check-package-dependencies.py artifacts/packages/all
python3 scripts/check-android-package.py \
  artifacts/packages/all/SuperTokens.Rownd.Native.Android.0.0.1-m3.nupkg
export ROWND_PACKAGE_SOURCE="$PWD/artifacts/packages/all"
bash scripts/verify-package.sh android
bash scripts/verify-package.sh ios \
  -p:RuntimeIdentifier=iossimulator-arm64 -p:CodesignKey=- -p:CodesignProvision=
```

`build-native-ios.sh` already runs the framework checker; the explicit command is useful for retained artifacts. It checks device/simulator arm64 slices, binding selectors and Rownd/GoogleSignIn bundles, not runtime linkage or Intel simulator support. `pack.sh all` already checks conditional dependency groups. Verify both consumers against the same combined feed, containing facade, foundation and both native packages. Inspect runtime Swift/ReSwift linkage, Swift runtime embedding and resource loading on device; static checks cannot establish those results.

## 4. Signed physical Release authentication

Use an actual provisioned application ID and customer/test signing settings, not the buildcheck ID. Build from the combined feed with `verify-package.sh`; it forwards arguments after the platform to restore/build. For an iPhone, for example:

```sh
export ROWND_APPLICATION_ID='YOUR.PROVISIONED.BUNDLE.ID'
ROWND_PACKAGE_SOURCE="$PWD/artifacts/packages/all" \
  bash scripts/verify-package.sh ios -p:RuntimeIdentifier=ios-arm64 \
  -p:CodesignKey="$IOS_CODESIGN_KEY" -p:CodesignProvision="$IOS_PROVISION_PROFILE"
```

Use your Android Release signing properties similarly. Install the actual signed artifacts from the printed consumer directory using device tooling; record artifact hashes and signing identity (no private keys/passwords). Keep normal Release trimming/AOT. Set up the shared Hub/Core/plugin fixture using [testing.md](testing.md#start-the-shared-fixture-and-hub): device-reachable URLs, matching registered `rowndmauisample` scheme, trusted HTTPS where transport policy requires it. Captured delivery needs no real email/SMS provider.

On **each physical platform**, record:

- [ ] Configure once; dismiss/reopen native Hub without crash or duplicate presentation.
- [ ] Request a fresh email OTP in the Hub; retrieve the exact identity's local capture, enter its code, and observe authenticated state.
- [ ] Call the protected API; backend-verified `userId` equals facade identity. Repeat token/protected requests; identity must not regress to `identity pending`.
- [ ] Background/resume; terminate/relaunch without clearing data, explicitly re-enter configuration, and verify persisted authentication plus the same backend identity/session. This does not prove automatic cold-start configuration.
- [ ] Sign out; facade becomes signed out, protected action says `No session`, and reopened Hub is signed out.
- [ ] In a separate signed-out run, request a fresh E.164 phone challenge in the Hub. Inspect its capture locally: `preAuthSessionId`, `displayContext=mobile_app`, and code fragment must exist. Preserve encoded query/fragment when replacing the link prefix with the registered scheme. Background the warm app and open that callback; confirm backend identity, then sign out and check `No session`.

For capture/config preparation and optional drivers, follow [warm OTP/phone E2E](testing.md#warm-email-otp-and-captured-phone-link-e2e). Actual CLI scenarios are `ROWND_RUN_E2E=1 bash scripts/test-passwordless.sh --platform android --scenario smoke` and `--scenario phone-magic-link` (use `--platform ios` for iOS). They require an existing Appium session, external `ROWND_E2E_CONFIG`, a fresh capture and an independently provisioned backend-verified expected ID. Full automation remains unproven; Release WebView inspection may be unavailable, so record manual device evidence when used.

Phone acceptance is tracked in M4/M5; record it separately rather than silently treating it as an M3 pass. Warm custom-scheme handoff does not prove HTTPS associations, SMS delivery, browser fallback, cold launch or replay protection. `delayed-startup` and `refresh-recovery` deliberately exit 2 as BLOCKED. Wrong/expired/replayed links, consume counts, HTTPS and refresh/recovery remain separate checks.

## 5. Reconfiguration, subscriptions and disposal

Use a package-only diagnostic consumer/debugger for cases the sample UI cannot trigger (Configure disables itself; there is no disposal/navigation test button). Keep the tested Release package and record any consumer instrumentation.

- [ ] A second `ConfigureAsync` on the same instance throws, including after a managed configuration failure; no second native initialization occurs. Restart the process for a fresh singleton.
- [ ] Repeated page appear/disappear and Hub open/close cycles do not accumulate subscriptions. Each changed state reaches the active subscriber once on the UI thread; an unsubscribed page receives no queued update.
- [ ] Dispose while configuration/token completion or state delivery is pending. Pending managed operations cancel, late callbacks do not publish state or revive the instance, and no crash occurs. Repeated disposal is harmless; subsequent operations reject terminal use.
- [ ] Disposal releases subscribers/callback roots; it is not sign-out. Verify sign-out separately. Android delivers each intent once (native ComponentActivity owns forwarding); iOS configures `RowndLinks` before URL/user-activity delivery.

Managed unit tests cover controlled lifecycle regressions; they do not prove native callback preservation under physical-device Release linking/AOT.

## Evidence to retain

- [ ] Gate/scenario, outcome, date, exact MAUI/sibling revisions and any local changes; explicitly list unrun/deferred/blocked checks.
- [ ] Host/tool/workload versions, device model/OS, actual Core image digest and locked plugin version; the fixture's Core image is currently unpinned.
- [ ] Package version/feed, SHA-256 of every tested package and installed app, isolated consumer path, build/signing configuration, warnings and checker/test summaries.
- [ ] Redacted runtime sequence, backend identity comparison, callback/subscription observations, screenshots and crash/device logs where relevant.
- [ ] Keep OTPs, tokens, full callback URLs, raw captures and private signing material out of commits/shared reports.

Publishing remains disabled. Passing builds, offline tests or historical simulator checks must not be reported as signed physical Release acceptance.
