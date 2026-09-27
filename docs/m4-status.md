# M4 implementation and evidence

Base: clean **1417a85**, including the user's universal iOS header-check fix and M3 Mac validation. Pins and those recorded results are preserved. **M4 runtime/exit gate remains open. The implementation-time evidence below is historical; subsequent Mac builds and runtime results are recorded in [Mac validation](#mac-validation--2026-09-25-to-2026-09-27).** The existing M2 simulator/emulator runtime evidence and M3 Mac builds apply to their recorded revisions, not these new artifacts.

## Implemented

- Embedded non-secret sample startup config (`RowndStartupConfig`), automatic configure-once, bounded Debug startup delay and native-session restoration without managed credential persistence. Startup JSON uses source-generated serialization for trimming.
- Android cold/warm intent adapter captures exact `DataString`, sanitizes the intent before MAUI/native listeners, then forwards through the bound native handler after both initialization and host resume. Recreated activities retain one native presenter and process singleton. Rejected/oversized/disposed owned callbacks cannot fall through into the native listener. Other intents retain base handling.
- iOS launch URL/user-activity dictionary plus OpenUrl/ContinueUserActivity; activation gates delivery and unhandled callbacks fall back to base. Selected sample uses the non-scene UIApplicationDelegate lifecycle, not dual scene/app-delegate forwarding. Scene-enabled customer hosts need their own selected callback wiring and validation.
- Shared router: **one latest pending link**, 16 KiB maximum, two-minute lifetime, deferred main-thread submission after initialization/resume, exact encoded suffixes and bounded two-second submission coalescing. This deliberately replaces the proposed distinct-link FIFO: native submission is synchronous but URL consumption is deferred through a single slot with no public correlated completion acknowledgment. Newer links may supersede older unconsumed submissions; neither return value nor cache entry proves consumption/authentication. See [routing policy and tradeoff](testing-m4.md#lifecycle-ownership). Both native facades disable clipboard auto-consume to prevent readiness bypass.
- Sample exposes only verified identity, hashed native-session fingerprint, request sequence, process/activity/page IDs, logical authenticated transitions and touch counts. Protected calls use the public C# token getter and ordinary cookie-free/no-redirect HttpClient; no token/payload output. UI subscriptions detach on disappearance/handler removal; sample requests cancel with page lifetime. Rebinding and Debug Android `Activity.Recreate()` are concrete sample actions.
- Concrete opt-in Appium journeys in `tests/e2e/magic_links.py` (also used by the older smoke entry point): real Hub phone/email entry, fresh exact-identity captures, warm/cold/startup external OS callback, replay, real expiry/recovery, OTP/SMS-OTP, process persistence, sign-out, presenter cancellation and host touches. Android uses untargeted adb ACTION_VIEW; iOS automated external dispatch uses explicit Simulator simctl openurl. They attach to real existing Appium sessions and never mint native sessions.
- Shared pinned Android harness observation overlay for **both** platforms, generated under ignored `artifacts/m4-harness`. Correlates decoded preAuthSessionId hashes with actual JSON consume status/user ID; HTTP 200 is insufficient. Protected identity/session fingerprints come from `verifySession`. Existing SMS/email delivery and same-device policy are retained; sibling sources are not edited.
- Parameterized AASA/assetlinks + Android HTTPS manifest/iOS entitlement generator. No real domain/team/certificate selected, no deployment. Exact setup, OS handoff, actual Hub browser-fallback action and manual physical gates: [testing-m4.md](testing-m4.md).

## High-finding follow-up

- **Ownership fixed:** Android ownership is independent of strict acceptance, uses actual `java.net.URI` parsing and tracks pinned native `SignInLinkApi.toHubUrl` login mapping. User-info/ports, native production/staging aliases and slash-trimmed custom paths cannot bypass the adapter through base hooks. Only accepted configured routes enter the slot; unrelated host intents and verification routes retain base handling. Ownership retains only scheme/Hub origin after disposal, not the app key.
- **Handoff contract corrected:** bounded latest-link-wins replaces the unsafe FIFO. Both platform adapters defer submission to the main queue; readiness/disposal is rechecked there. Earlier submitted callbacks can still be superseded by later arrivals before native consumption; this is explicit policy, not serialized consumption. Exact strings, duplicate/replay window and transient rejection retry are retained. No auth protocol was added.
- **PASS:** **111 managed unit/mock cases** (84 baseline + 27). New adapter-level tests exercise sanitization before ready, while suspended and after disposal, accepted/oversized links, untouched unrelated intents and exact strings. A deferred single-slot native double proves startup/warm bursts submit only the latest once, and explicitly demonstrates later-arrival supersession rather than falsely claiming FIFO consumption. The integration assembly is compiled as a dependency, never run.
- **PASS:** **60 native JVM tests**, re-executed (58 baseline + two new native ownership/vector cases). The actual pinned `SignInLinkApi.toHubUrl` and `java.net.URI` confirm that rejected managed inputs would otherwise reach native login, while lookalike hosts/encoded paths do not. Native facade/runtime export passed; no production native code changed in this follow-up. Android/Hub tracked pins and clean tracked source checked first; iOS missing-pin restriction is unchanged.
- **PASS:** Android `pack.sh android`, strict package checker, and a fresh package-only Release consumer with normal trimming/profiled AOT: **zero warnings/errors**, no XA4301. Consumer: `/home/dev/.cache/rownd-m4/rownd-consumer.byId9v`; no install/launch. This supersedes earlier routing build evidence below. Pack retains existing analyzer/binding warnings; JVM build retains Gradle deprecation warnings.
- Logs: `/tmp/opencode/rownd-m4-review-managed.log`, `rownd-m4-review-native.log`, `rownd-m4-review-pack.log`, `rownd-m4-review-consumer.log`. The shell initially lacked dotnet/JAVA_HOME; checks above used the existing `/home/dev/.dotnet` SDK and JDK `21.0.12.1+1`, without changing pins.
- Follow-up hashes: `/tmp/opencode/rownd-m4-review-hashes.json`; MAUI package `ff8fed43237bd8b806b3a9c958f06f69a4baffdc7146aa017853c4b477b7a0c8`, consumer APK `5be4e1340ec8b69f590d0b4e03c5d0443f03a36ef1142051d416a1619b3977ec`. Consumer restore contains exactly the expected three Rownd packages and zero project libraries.
- **UNRUN/BLOCKED:** iOS compilation on Linux, missing pinned iOS sibling commit, and all runtime/integration/E2E/device checks. The local iOS source/public facade was inspected; it is not evidence of a build at the absent pin.

## Earlier checks on this Linux host

- **PASS:** 84 managed unit/mock tests (78 prior + six router cases). Covers readiness/resume ordering, queue expiry/capacity, ownership after disposal/oversize, origin/user-info checks, exact forwarding and existing disposal/async regressions. Integration project is compiled as a test dependency, not executed.
- **PASS:** 26 Python unit checks, including the user's universal-header regressions, AASA/assetlinks identity propagation, stale/wrong-phone capture rejection, unchanged encoded suffix, explicit untargeted external dispatch with mocked subprocess, stale/replaced protected-session rejection and unsupported-scenario rejection before any device action. These are offline boundary tests, not authentication results.
- **PASS:** pinned harness overlay generation and `tsc --noEmit -p artifacts/m4-harness/test-server/tsconfig.json` using the Android lockfile dependencies (Node 22.23.2). No harness, Docker containers or Hub were started.
- **PASS (intermediate M4 revision):** Android source Debug sample build with embedded startup JSON, SDK 10.0.200 / MAUI 10.0.20 / Android workload 36.1.43. This precedes the final ownership/disposal/clipboard refinements; final code is checked by the Release consumer below. No app installed/launched. Debug source build reported analyzer warnings and four XA4301 imported-JNI duplicate warnings; these are not a clean package-only acceptance result.
- **PASS:** final Android native facade build/runtime export in 45 seconds, including compiled clipboard opt-out. Inventory: 118 embedded artifacts, 64 supplied by declared NuGet dependencies. Gradle reported `:android:testDebugUnitTest UP-TO-DATE`; retained XML has **58 passed, zero failures/errors/skips**, but these JVM tests were **not re-executed**. Native build retains upstream deprecation/SDK warnings.
- **PASS:** final `bash scripts/pack.sh android` and strict Android package checker. Whole current-version feed inspection finds **eight distinct required JNI paths with no duplicates** across packages; compiled packaged facade contains `setEnableSmartLinkPasteBehavior`. Historical m2-version packages remain in the feed and are excluded from this current-version inspection.
- **PASS:** final package-only Android Release consumer **outside the checkout**, `/home/dev/.cache/rownd-m4/rownd-consumer.tTa1m7`, normal trimming/profiled AOT, **zero warnings/errors**, no XA4301. Restore contains the expected three Rownd packages and **no project libraries/references**. APK has 206 unique native-library paths. Its embedded non-secret local fixture configuration has a Debug delay which is ignored in Release. No install/launch occurred.
- **PASS:** Python/shell syntax checks and `git diff --check`.
- **BLOCKED here:** full native source check: Android/Hub pins match; local iOS sibling lacks pinned `95bd10b6c5bec1678fa6094e031a3e1cbf900901`. No Mac/Xcode/iOS workload. Android native steps are run separately only after checking its and Hub's tracked pins; the iOS pin is not replaced. Hub has an unrelated untracked `plan.md`, retained.

### Build recovery and retained evidence

Initial source Debug builds failed at D8 with duplicate Compose classes from stale Debug binding AARs (`runtime-annotation.aar` beside older `runtime-release.aar`). Removed only generated Debug intermediates and retained old binding binaries at `artifacts/m4-prior-binding-debug`. Attempting to copy intermediates into `/tmp/opencode` hit its quota; removed those reproducible partial copies, retaining bin outputs/logs. A subsequent cold build exceeded the 120-second command limit; the incremental 600-second build passed. This did not require pin/dependency changes.

Prior package feed retained at `artifacts/m4-prior-packages/android`. Consumer first built under `artifacts/rownd-consumer.tTa1m7`, then moved to `/home/dev/.cache/rownd-m4/rownd-consumer.tTa1m7` to stay outside the checkout without filling `/tmp`. Its isolated cache is refreshed for changed same-version packages. No native source substitution or rebuild of an unrelated iOS revision occurred.

Logs: `/tmp/opencode/rownd-m4-android-build*.log`, `rownd-m4-pack*.log`, `rownd-m4-package-consumer.log`, `rownd-m4-consumer-final.log`, `rownd-m4-native-android.log`. Artifact version remains provisional **0.0.1-m3**; identify M4 artifacts by revision/local changes and SHA-256, not version alone.

The all-platform native wrapper is blocked by the missing iOS pin here. After explicit Android/Hub tracked-pin checks, its Android-only steps were run directly:

```sh
export ROWND_MAUI_ROOT="$PWD"
python3 scripts/prepare-android-source.py
../supertokens-rownd-android/gradlew -p ../supertokens-rownd-android --no-daemon \
  -I "$PWD/native/android/include.gradle" :mauiFacade:exportRuntime :android:testDebugUnitTest
dotnet restore bindings/Rownd.Android/Rownd.Android.csproj
python3 scripts/prepare-android-runtime.py
bash scripts/pack.sh android
python3 scripts/check-android-package.py
```

Final consumer restore used its own `packages` directory, `RowndUsePackage=true`, `RowndTargetFrameworks=net10.0-android`, `RowndApplicationId=io.supertokens.maui.buildcheck` and `RowndStartupConfig=/tmp/opencode/rownd-m4-startup-build.json`, with the local Android feed plus nuget.org. Build used `-c Release --no-restore` and the same properties plus `RestorePackagesPath`. Only that disposable consumer's updated same-version facade/native-package cache entries were refreshed. Current repeatable fresh-consumer command is in [testing-m4.md](testing-m4.md); set `TMPDIR` to a writable directory **outside the checkout**.

### Pre-follow-up Android artifact SHA-256 (historical)

| Artifact | SHA-256 |
| --- | --- |
| `SuperTokens.Rownd.Foundation.0.0.1-m3.nupkg` | `fd0db8dd749538e01c872e10176dd951dd67bae1636c540a9aef7aae99eef6e6` |
| `SuperTokens.Rownd.Maui.0.0.1-m3.nupkg` | `699b1fde538215cb910516138b159831ddbed0d52f4db0abc96e1903fbd6cefa` |
| `SuperTokens.Rownd.Native.Android.0.0.1-m3.nupkg` | `8c6fd8babb153d918c938715d1163ae905c22b1a04411ed128a47d1e0f980a5a` |
| Package-consumer `io.supertokens.maui.buildcheck-Signed.apk` | `8c5a3eddd963cbfbc8ca3901a08dab8deae321c33e3586be97212f3e09fbda86` |

Full paths/hashes: `/tmp/opencode/rownd-m4-artifact-hashes.json`. These identify the earlier artifacts, not the follow-up rebuild. This is build signing, not customer physical-device signing or runtime acceptance.

## Open gates / necessary inputs

1. **PARTIALLY VALIDATED:** see the Mac journey matrix below. Android cold/startup handoff failures keep the exit gate open. Capture replaces provider delivery; no real SMS was sent.
2. **UNRUN:** physical signed Release custom-scheme/HTTPS/browser fallback, warm/cold handoff, native iOS presentation/resources, same-device-policy compatibility, active-Hub activity recreation and native terminal-subscription disposal. Automated recreation covers the authenticated Android host; physical iPhone external taps and actual browser fallback are documented manual gates.
3. **INPUTS:** custom HTTPS Hub/login hostname + hosting access, Android package ID and installed signing certificate SHA-256(s), iOS bundle ID and signed application-identifier prefix/team + Associated Domains provisioning. Also actual devices/UDIDs, device-reachable trusted API/Hub endpoints and selected same-device policy. Generation deploys nothing; forced app targeting cannot prove association.
4. **DEFERRED:** upstream iOS native release per user decision. Preserve the local pin; publish/update/rebuild only in a separately authorized phase. Native iOS fatal initialization error mapping remains the recorded M3 release gate. Concrete refresh/outage automation remains M5 (`refresh-recovery` fails explicitly as blocked).
5. Core image remains unpinned in the existing shared harness; record actual digest/code lifetime. Expiry driver must wait the actual lifetime plus margin. Dedicated fixture/default namespace, one runner at a time; no concurrent resets.

During the original Linux implementation, no additional delegation, commits, pushes, publishing, domain deployment, integration tests or device commands were performed. Subsequent Mac validation follows.

## Mac validation — 2026-09-25 to 2026-09-27

Tested .NET revision `6c29807` plus local E2E driver corrections and regression tests. No production SDK/facade changes were made. This is simulator/emulator Debug runtime evidence and package-only Release build evidence, not signed physical-device acceptance.

### Build and offline checks

- **PASS:** all native source pins. Android `cd08c866828232d130f32df3c1c47ee7fabe1a2c`, iOS `95bd10b6c5bec1678fa6094e031a3e1cbf900901` (still local/unreleased), Hub `086014e0f29c00722b260e69a9f28ff47512bf0f`.
- **PASS:** 111 managed tests; 40 Python checker/tool tests after driver regressions; observed harness preparation and TypeScript type check.
- **PASS:** rebuilt Android facade/runtime and 60 native JVM tests; rebuilt iOS device/simulator XCFramework and static slice/selector/resource checks.
- **PASS:** both startup-configured source Debug samples, combined `0.0.1-m3` feed, conditional dependency inspection, Android required JNI inspection. Whole feed has eight distinct JNI paths and no duplicates.
- **PASS:** isolated package-only Android Release build, zero warnings/errors. Output is a signed AAB, not an installed APK. Consumer: `/private/var/folders/5r/6bl83v_92vg_zgq58303jlc00000gn/T/rownd-consumer.fCWAsi`.
- **PASS with warning:** isolated package-only iOS Release simulator build, one CS8765 warning for `AppDelegate.FinishedLaunching`'s non-nullable `launchOptions`; zero errors. Consumer: `/private/var/folders/5r/6bl83v_92vg_zgq58303jlc00000gn/T/rownd-consumer.hc9qah`.
- Both consumers restored only the three appropriate Rownd packages from isolated caches with no project libraries. Normal Release optimization was retained. Debug Android retains analyzer/binding warnings and XA4301 source-project duplicate-JNI warnings; these were absent from the package-only Release build. Debug iOS retains analyzer/platform/nullability warnings.

### Runtime setup and limitations

Android: Pixel 8 API 34 emulator (`emulator-5554`). iOS: iPhone 17 Pro simulator, iOS 26.3 (`A2E2A30F-15BE-45E3-ACF4-E89F35FF3200`). App ID: `io.supertokens.maui.buildcheck`. Automatic embedded startup config uses a ten-second Debug delay, API `http://127.0.0.1:3139`, Hub `http://127.0.0.1:8787`, and the registered `rowndmauisample` scheme. Android ports are reversed. Initialization delay is ignored by Release. No app data was cleared between successful journeys or persistence/replay checks.

Toolchain: .NET/workload set 10.0.200, MAUI 10.0.20, Android 36.1.43, iOS 26.2.10217, Xcode 26.2 (17C52), JDK 21.0.12.1, Node 26.7.0. Appium 3.8.0, UiAutomator2 8.7.0, XCUITest 12.13.2; Android WebView 113.0.5672.136 with Chromedriver 113.0.5672.63. Drivers were installed in `/private/tmp/rownd-m4-appium`; sessions explicitly attach to the named devices.

One dedicated M4 observation overlay/fixture was used sequentially for both platforms, with the locked Rownd plugin 0.3.0-beta.2 and Postgres 14. Actual Core digest: `supertokens/supertokens-postgresql@sha256:8302ef1766b05c2b85cbed85de8d6e7fb38dedfe041918327e24e5b33d6f2590`. Running Core uses its unoverridden 900000-ms passwordless code lifetime; expiry scenarios wait 901 seconds. Fixture app-config omits `enforce_same_device_passwordless_sign_in`; the pinned Hub evaluates that as false. This unchanged fixture policy does not prove stricter same-device-policy compatibility. Captured delivery used synthetic identities and no real SMS/email provider.

### Journey results

A PASS means the whole driver's assertions completed: a fresh exact-identity capture, one initial correlated JSON OK consume in a bounded observation window, matching facade/backend user and session fingerprint, interactive host, replay without another successful consume, process restart with the same verified session, subscription rebind, sign-out and signed-out restart. Android passes also include authenticated-host activity recreation. Backend observation windows do not prove exactly-once native dispatch or rule out all later attempts.

| Journey | Android | iOS |
| --- | --- | --- |
| `phone-magic-link` | PASS | PASS |
| `cold-phone-magic-link` | FAIL | PASS |
| `delayed-startup` | FAIL | PASS |
| `email-magic-link` | PASS | PASS |
| `smoke` | PASS | PASS |
| `sms-otp` | PASS | PASS |
| `expired-link` | PASS | PASS |

Android cold-phone and delayed-startup were retried and timed out in `Journey.complete` waiting for authenticated state after untargeted external dispatch. Warm phone/email links and both OTP flows pass. The Android cold/readiness handoff remains a runtime failure to investigate; no root cause or SDK fix is claimed.

### Driver corrections and initial failures

The original driver required `.rph-close[aria-label="close"]`, but the pinned Hub explicitly disables that control in mobile-app context. Cancellation now uses bounded native Back attempts on Android (accounting for the keyboard), and a tap on the exposed native backdrop computed from the iOS WebView rectangle. A fixed screen-coordinate swipe failed when the keyboard moved the sheet and was replaced. Host-touch assertions remain mandatory.

The iOS driver now accepts only the exact sample-specific OS `Open in “Passwordless foundation”?` confirmation after untargeted `simctl openurl`; unrelated alerts are rejected. An unrelated Apple Account prompt was manually dismissed with Not Now; no credentials were entered. A simulator restart without data erasure recovered inspection setup. The first iOS protected request permits an absent empty result label (404), while retaining request-sequence, backend-user and session assertions. Regression tests cover these boundaries. No native authentication calls, session seeding, URL-targeting shortcuts or policy bypasses were added.

Initial Android startup and presenter attempts and iOS inspection/presenter/result-label attempts failed; they are not counted as passes. Later complete runs supersede those setup failures only for the scenarios shown as PASS. The original cold/startup failures remain recorded. Raw driver/server logs and captures stay local; no OTP, token or complete callback URL is included here.

### Open acceptance gates

- **BLOCKED on inputs/hardware:** physical signed Release Android/iPhone journeys, verified HTTPS associations and real browser fallback. Required custom hostname/hosting, installed signing identities, iOS Associated Domains provisioning and physical-device targets were not supplied. Nothing was deployed or published.
- **UNRUN:** active-Hub Android recreation, terminal native disposal with queued callbacks, scene-based iOS hosts, and package-only Release runtime linkage/authentication. Debug host recreation/rebind is not terminal-disposal evidence.
- **DEFERRED:** upstream iOS publication; pins were preserved. Native iOS fatal initialization error mapping and M5 refresh/outage remain separate open gates.

### Evidence

Artifact SHA-256 values are recorded below. Full paths and sorted per-file iOS manifests are retained under `/Users/bogdan/Documents/Codex/2026-09-25/anal/outputs`. iOS app hashes identify those manifests, not IPAs. Logs are retained under `/Users/bogdan/Documents/Codex/2026-09-25/anal/work/m4-*.log`. Prior generated binding/facade/sample/feed outputs were preserved at `/private/tmp/rownd-m4-prior-xl2hkxhi` before rebuilding to avoid stale same-version packages. No commit, push or release was performed by this validation run.

### Mac artifact SHA-256

| Artifact | SHA-256 |
| --- | --- |
| `SuperTokens.Rownd.Foundation.0.0.1-m3.nupkg` | `eb1952a7ad114b7fce682f3026064e716d807ddcef6eefb9358f2a7e27c704e3` |
| `SuperTokens.Rownd.Maui.0.0.1-m3.nupkg` | `e7ca19c6213935d5f5da5c7068467b624f75b3ebd2d79c9c5648c16a619c101d` |
| `SuperTokens.Rownd.Native.Android.0.0.1-m3.nupkg` | `c1fd7aecd52e1f686484296374d649b4e97fe7366a8d8f4f79e0486d6b5a88b3` |
| `SuperTokens.Rownd.Native.iOS.0.0.1-m3.nupkg` | `300433f32a58e64f27ee556a1caade6c74b24d8b0178eec2eee753199e9ffe2e` |
| `io.supertokens.maui.buildcheck-Signed.apk` | `4338cba4882967913ff8a1c4247e25c93c3092a5256d2f1fa5468a4e90911d2c` |
| `io.supertokens.maui.buildcheck-Signed.aab` | `81045da219e0bb6ce9fd1f946df7a3c7a9a34ba8f0d6de1245daab4246194c2f` |
| `m4-debug-ios-manifest.txt` | `0336f8868713746559585498e5a2b1f63107d20732c89effd98010543c17db22` |
| `m4-release-ios-manifest.txt` | `588007a41c5844b38b9250245ab3ec1129b165aa18f338685afb33d335b2aa7d` |
