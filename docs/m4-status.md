# M4 implementation and evidence

Base: clean **1417a85**, including the user's universal iOS header-check fix and M3 Mac validation. Pins and those recorded results are preserved. **M4 runtime/exit gate remains open. No integration/E2E/device tests were run during this implementation.** The existing M2 simulator/emulator runtime evidence and M3 Mac builds apply to their recorded revisions, not these new artifacts.

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

1. **UNRUN:** every new Appium journey on both runtimes. Real Hub/WebView driver setup and platform behavior must be established on the user's Mac. Unit/mock checks do not satisfy phone authentication. Capture replaces provider delivery; no real SMS/tap requested.
2. **UNRUN:** physical signed Release custom-scheme/HTTPS/browser fallback, warm/cold handoff, native iOS presentation/resources, same-device-policy compatibility, active-Hub activity recreation and native terminal-subscription disposal. Automated recreation covers the authenticated Android host; physical iPhone external taps and actual browser fallback are documented manual gates.
3. **INPUTS:** custom HTTPS Hub/login hostname + hosting access, Android package ID and installed signing certificate SHA-256(s), iOS bundle ID and signed application-identifier prefix/team + Associated Domains provisioning. Also actual devices/UDIDs, device-reachable trusted API/Hub endpoints and selected same-device policy. Generation deploys nothing; forced app targeting cannot prove association.
4. **DEFERRED:** upstream iOS native release per user decision. Preserve the local pin; publish/update/rebuild only in a separately authorized phase. Native iOS fatal initialization error mapping remains the recorded M3 release gate. Concrete refresh/outage automation remains M5 (`refresh-recovery` fails explicitly as blocked).
5. Core image remains unpinned in the existing shared harness; record actual digest/code lifetime. Expiry driver must wait the actual lifetime plus margin. Dedicated fixture/default namespace, one runner at a time; no concurrent resets.

No subagent-spawn tool was available; no additional delegation occurred. No commits, pushes, publishing, domain deployment, integration tests or device commands were performed.
