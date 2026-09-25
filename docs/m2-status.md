# M2 implementation and remaining gates

M2 runtime gate is **open**. No integration, E2E, simulator or device test has been run. iOS code is uncompiled on this Linux host. Local packages are provisional, platform-specific, not published customer releases.

## Implementation

- `native/android`: Java-friendly Kotlin callback facade delegates configuration, Hub presentation, native token retrieval, sign-out and StateFlow observation to the pinned Android source. Built as an extra Gradle module through an init script; sibling tracked sources are untouched. Native lifecycle registration owns MAUI ComponentActivity startup/resume/new-intent dispatch; do not also forward `OnNewIntent`. Explicit `handleIntent` is available for other hosts.
- `native/ios`: Objective-C-visible Swift facade, ReSwift subscription, async token/configuration completion and native smart-link forwarding. XcodeGen/build script archives device/simulator aggregate framework slices and copies SwiftPM resource bundles. Actual Swift compilation, linker/resource validation and Swift runtime embedding need a Mac.
- `bindings`: generated Android JNI bindings plus explicit iOS Objective-C selectors. Native Android dependencies/resources are embedded except Maven modules already provided by declared NuGet dependencies. `native/android/build/packaging-inventory.json` records ownership. No Java class stripping is used.
- `src/Rownd.Foundation`: thin callback-to-Task `RowndInstance`, native-derived state, dispatched notifications, no-session/error distinction and disposal cancellation. It stores no credentials. `src/Rownd.Maui` supplies real platform adapters and process singleton. Configure once; failed native initialization is not retried in-process.
- `samples/Passwordless`: real Configure/sign-in/sign-out/current-token bearer request actions. Legacy `Rownd/` is outside all project references. Development-only `rowndmauisample://account/login` registration is included; configure the Hub with the same scheme. HTTPS associations wait for customer identifiers.
- `scripts/pack.sh android|ios`: local platform-specific prereleases and their binding/foundation dependencies. `verify-package.sh` copies the sample outside the repository and restores into an isolated cache with package references only, then builds Release without installing/running.

## Runtime/API limitations requiring follow-up

### Android readiness

The facade now waits up to 30 seconds for native bootstrap, cache hydration, usable app configuration, legacy migration and native session reconciliation before publishing readiness or subscribing to state. Signed-out success is distinct from transient reconciliation failure. Failed configuration cannot be retried in-process.

The pinned source is compiled through a reproducible build-local overlay: `scripts/prepare-android-source.py` applies `native/android/initialization.patch` with zero fuzz, preserving a swallowed bootstrap exception; an additive native hook calls the existing reconciliation authority. All 73 overlay files reproduced byte-for-byte in final verification. Android/iOS/Hub pins and tracked sibling files remain unchanged. See [Android initialization contract](android-initialization.md).

Caveats: cached usable app configuration can satisfy readiness; app-config failure may surface only as timeout; swallowed migration errors cannot always retain their original cause, so unresolved legacy authentication is rejected conservatively. Coroutine timeout cannot immediately interrupt synchronous native work. Readiness does not establish backend identity or subsequent network availability. The preceding native build passed **58 JVM tests**, including **six readiness regressions**, with no failures/errors/skips; these controlled boundary tests are not device/runtime acceptance.

### iOS callback idempotency follow-up

`RowndLinks` now uses the platform-independent `LoginLinkRouter`, compiled directly into the unit project for offline testing. Routing remains login-only: configured custom scheme `://account/login` or configured Hub host HTTPS `/account/login`. Email verification is explicitly outside this release; verification and unrelated links return unhandled.

The router preserves exact encoded URL strings, coalesces queued/in-flight duplicates, and remembers successful native handoffs for a fixed **two seconds** (not extended by duplicate callbacks). Suppressed duplicates return recognized/`true`. At most eight distinct links are queued/in flight; overflow returns `false`. The recent cache holds at most 32 successes, evicting the oldest. A rejected or throwing native handoff is removed immediately so a new callback can retry; queue draining continues past failures. There is no automatic retry. Repeat a successful URL after two seconds for replay testing. Disposal clears routing state and is terminal, matching singleton disposal. Native acceptance is not authentication completion or server-side replay protection.

Final verification: **72 unit/mock tests passed**, zero failures/skips, including **20 new routing cases** using a fake monotonic clock and native-forward delegate. Coverage includes pre/post-ready duplicates, encoded/distinct URLs, reentrant in-flight duplicates during immediate forwarding and queue draining, queue/recent bounds, expiry, immediate failure recovery, login-only recognition and disposal. **iOS adapter/native code remains uncompiled on Linux; integration/E2E/device execution remains unrun.**

### Remaining gates

1. Pinned iOS `Rownd.configure` calls `fatalError` on SuperTokens/keychain/installation bootstrap failures. Input validation avoids common invalid settings, but an external facade cannot translate those fatal errors into a C# Task failure. A narrow throwing native configure hook remains required for reliable initialization errors. No sibling change or invented success stub was added.
2. iOS XCFramework aggregation is written but uncompiled. Confirm ReSwift visibility, binary dependency embedding, GoogleSignIn resources, SwiftPM `Bundle.module` lookup and Objective-C generated header selectors on the customer's Mac. Exact Xcode compatibility remains unverified.
3. The editable sample is warm-session oriented: configure using its entries before opening sign-in. Production hosts must load nonsecret app configuration at startup. On iOS, call `RowndLinks.Configure(config)` before forwarding callbacks; matching links can queue until native configuration completes. Cold launch URL/user-activity/scene integration and process-relaunch automation still need M4 work. The sample does not pretend manual configuration survives process death.
4. Android resources/Dex/link checks do not establish Hub presentation, persistence, native refresh, cancellation or callback survival on a device. Package-only Release build is also not runtime evidence.
5. Shared Core image remains unpinned; no digest was invented. Production app IDs, signing, same-device policy and custom-domain association files remain pending. Upgrade from `Rownd.Maui` requires one new sign-in; no old C# `rownd_state` import or initialization runs.
6. Native runtime ownership is resolved against the declared MAUI 10.0.20 graph. Changing a consumer's AndroidX versions requires repeating dependency/Dex/runtime checks. Third-party license inventory and original repository license provenance still need review before distribution beyond local evaluation.

## E2E driver (written, never run here)

`tests/e2e/appium_smoke.py` drives an **existing explicit Appium session** against the real MAUI/native Hub. It fills sample config, starts a fresh Hub challenge, reads the shared Android fixture capture, enters email OTP or dispatches the captured phone callback via OS custom scheme, invokes the sample bearer request and asserts the backend's expected `userId`, signs out and reopens Hub. No mock device fallback exists.

Prerequisites: Appium UiAutomator2/XCUITest driver; installed sample; Android debuggable app/compatible Chromedriver or iOS 16.4+ inspectable WebView; reachable pinned Hub/backend; a fresh unique identifier; known backend user ID. Native sources enable inspection under those conditions, but Appium attachment has not been validated. Driver requires `ROWND_RUN_E2E=1`, `ROWND_APPIUM_URL`, `ROWND_APPIUM_SESSION`, `ROWND_E2E_CONFIG` (path to a local JSON file). Fields:

```json
{
  "app-key": "fixture app key",
  "api-domain": "device-visible API origin",
  "api-path": "/auth",
  "hub-url": "device-visible pinned Hub URL",
  "link-scheme": "rowndmauisample",
  "protected-url": "device-visible API origin/test/protected",
  "harness-url": "runner-visible API origin",
  "application-id": "actual installed package/bundle ID",
  "email": "fresh fixture identity",
  "phone": "+15550000000",
  "phone-selector": "CSS selector for configured Hub phone action",
  "expected-user-id": "backend expected user ID"
}
```

The phone mode is an initial warm-link smoke, **not** the complete M4 phone scenario. Replay/consume counters, cold launch, delayed initialization, actual browser fallback, verified HTTPS handoff and refresh/recovery drivers remain pending. Existing C# orchestration for these scenarios still has no concrete driver. No real SMS provider/tap check is required in approved scope.

## Verification

Final verification executed on Linux after sourcing `/home/dev/.config/rownd-android-tooling/env.sh` (native AAR/build and 58 JVM tests had already passed in the readiness follow-up):

```sh
./scripts/test-unit.sh --nologo -v quiet
dotnet build tests/Rownd.IntegrationTests/Rownd.IntegrationTests.csproj -c Release --nologo -v quiet
bash scripts/pack.sh android
python3 scripts/check-android-package.py
ROWND_APPLICATION_ID=io.supertokens.maui.buildcheck bash scripts/verify-package.sh android
python3 scripts/prepare-android-source.py # reproduced the existing overlay byte-for-byte
python3 -m py_compile scripts/prepare-android-source.py scripts/prepare-android-runtime.py tests/e2e/appium_smoke.py
bash -n scripts/build-native-android.sh scripts/build-native-ios.sh scripts/pack.sh scripts/verify-package.sh scripts/test-passwordless.sh
python3 scripts/check-native-sources.py
git diff --check
```

- **72 unit/mock tests passed**, zero failures/skips (139 ms test duration). Coverage includes the four native boundary cases and 20 login-link routing cases. These do not prove native auth.
- Integration project **compiled only**, zero warnings/errors, 1.77s. Python drivers/scripts compile; shell syntax and diff whitespace checks pass.
- Native Android Release AAR and generated .NET binding build successfully. Binding generator reports Kotlin synthetic `$` accessor exclusions (BG8605/BG8606); resolution report lists only compiler-generated accessors, not public bridge methods. Generated binding code is excluded from StyleCop analysis.
- Local Android `SuperTokens.Rownd.Maui`, `SuperTokens.Rownd.Foundation` and `SuperTokens.Rownd.Native.Android` packages were repacked under `artifacts/packages/android`. Package IDs/version remain provisional. Pack succeeded with eight StyleCop warnings in `PlatformBridge.Android.cs` and missing-readme notices for the native/Maui packages.
- Package-content checker passes: real native/facade classes and resources, eight byte-identical duplicate native-library paths. Both packaged AARs match current build outputs byte-for-byte. Class payload inspection confirms the bridge's `awaitMauiSessionReady` invocation, `MauiInitializationKt` hook and sticky `initializationFailure` field are present in the actual NuGet.
- The isolated consumer restored byte-identical copies of all three current NuGets; its assets contain no project dependencies.
- Separate consumer Android Release build succeeds with normal trimming/AOT. **Eight XA4301 warnings** report duplicate `libdatastore_shared_counter.so` / `libandroidx.graphics.path.so` for arm64-v8a and x86_64 from two extracted library directories. Package ZIP/SHA-256 inspection confirms all duplicate copies are byte-identical across all four packaged ABIs. No class-stripping/dummy library workaround was used; eliminating redundant native copies remains packaging cleanup.
- Android/iOS/Hub pinned commits and clean tracked sibling sources pass the source check. No native source pin changed. No commit/push/publication occurred.
- **iOS native/binding/sample/build/test execution: unrun**, no Mac/Xcode. Swift validation unit-test source and XcodeGen test target are included. **All integration/E2E/device execution: unrun**, by user constraint. Actual OTP, captured-link handoff, verified backend identity and M2 runtime gate remain pending.

Initial dependency exploration selected too-new Fragment NuGet 1.8.9.2 and duplicated Compose runtime annotation classes. The final binding pins MAUI-compatible Fragment 1.8.8.1, keeps the native Compose graph, and derives runtime exclusions from declared NuGet Maven coordinates. The source-pin set remains unchanged.

Preceding readiness native build/JVM run: **1m22s**, 58 passing tests (existing XML totals rechecked during final verification). Current inventory: 118 embedded Maven artifacts / 64 supplied by declared NuGet dependencies, plus source-built Rownd and facade AARs. Native logs: `/tmp/opencode/rownd-android-initialization-{build,binding}.log`.

Final package-only consumer: `/tmp/opencode/rownd-consumer.riLwB8`, Android Release with trimming/AOT, **2m16.92s, 8 warnings, 0 errors**, script exit 0 (restore: 2.13s). Current verification logs: `/tmp/opencode/rownd-m2-{unit,integration-compile,pack,consumer}-current.log` on this development machine.

SHA-256 of the final local artifacts (uncommitted M2 working tree based on M1 `2bb1111`):

```text
776bfd99565a923c122026780a7626fa5a867ad13e109303bf15b77e6e94afe1  SuperTokens.Rownd.Foundation.0.0.1-m2.nupkg
05082362c5d9a82d240fd525ca1bc5ba82151e683d5b8c4c9874124639cd867d  SuperTokens.Rownd.Maui.0.0.1-m2.nupkg
d1e4613e4ef83470df78f05416600efeb6b4a63985b0550adedf8e1ad77703c8  SuperTokens.Rownd.Native.Android.0.0.1-m2.nupkg
0341c0bfea20272d2732ea7119b6738c294a9ffc7bfaf30820ec7630afe19f98  mauiFacade-release.aar (embedded)
be6766c6d6c529f4a0cc17db98d91fadeb1d55918b8299ab2ae6f0aba5d6cca9  android-release.aar (embedded)
```
