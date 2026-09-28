# M5 implementation, checks and final acceptance matrix

M5 implementation commit **b502245**, based on **95df80857f2bf91328328f92283433f80071233b**. The Linux implementation/build evidence below is historical; subsequent Mac validation is recorded separately. **Mac validation: all four full M5 Debug journeys passed (Android/iOS, source/package), after fixing the Hub short-token handoff.** Customer/release acceptance remains distinct from local test results. No package publication or pin changes.

## Implemented

- `refresh-recovery` is a concrete Appium journey on both platforms, using the existing real-Hub login/capture/external-dispatch driver. Each invocation covers real email OTP and phone magic-link authentication, real expiry, saved-token 401, native-getter refresh, protected same-user/session 200, native refresh counters, temporary 503 failure/recovery, current/expired process relaunch, sign-out persistence and fresh real login.
- Debug-only `samples/Passwordless/SessionProbe.cs` retains separate expiry and one-use getter-candidate tokens only in test-process memory; plain cookie-free/non-redirecting HttpClient has no getter/refresh/retry behavior. Both normal refresh and outage recovery check `stRefresh` immediately after the explicit getter, then require **that exact returned candidate** to produce HTTP 200 with the expected user/session fingerprint. A second getter cannot repair a stale candidate and create a false pass. Sign-out/final cleanup clear references; in-flight getters cannot repopulate after clear. Getter errors and auth transition counts are non-secret UI observations. No SDK/public API, native auth protocol or managed credential persistence was added. Release excludes these controls.
- The disposable shared Android harness overlay configures real Core access-token validity (90 seconds by default; strictly above the iOS 60-second margin) and reports fixture settings. Existing native refresh counter/503 switch and phone capture serve **both platforms**. Same-device checks are retained. No acceptance session uses fixture token-creation endpoints.
- 18 Python M5 mock/control/source-contract tests cover stale operation results, false signed-out events, failure-vs-no-session, visible Hub rejection, additional consume rejection, lifetime validation, failure-control acknowledgment/cleanup (including an assertion during an outage), both login paths, first-getter-stale/second-getter-refresh rejection, refreshed-counter-but-stale-candidate rejection, exact candidate identity, counter ordering and separate Debug memory/HTTP contracts. These tests are offline evidence only.
- CI now includes Python offline tests alongside managed tests/integration compilation. An opt-in provisioned Linux Android runner job builds native/bindings, packs, checks and builds a fresh consumer. It remains unexecuted; there is no Mac CI promise.
- Pack writes artifact hashes and source metadata. README corrects stale lifecycle claims and documents token/error handling; [M5 runbook](testing-m5.md) provides exact Mac commands and acceptance boundaries.

## Executed offline/build checks — Linux, 2026-09-28

Tool environment: `/home/dev/.config/rownd-android-tooling/env.sh`; existing .NET/workload **10.0.200**, MAUI **10.0.20**, Android **36.1.43**, JDK **21.0.12.1+1**. Type checking used existing **Node 22.23.2**.

| Check | Result |
| --- | --- |
| `bash scripts/test-unit.sh --nologo -v quiet` | **111 passed**, 0 failed/skipped; integration dependency compiled, never executed. Existing analyzer warnings. |
| `python3 -m unittest discover -s tests/package_checkers -p 'test_*.py' -v` | **62 passed** (44 existing + 18 M5), rerun after P1 correction. Python 3.14 emits existing HTTPError cleanup ResourceWarnings. |
| `python3 scripts/prepare-m4-harness.py` | PASS, clean pinned test-server copied; no server started. |
| Overlay `tsc --noEmit -p artifacts/m4-harness/test-server/tsconfig.json` | PASS with Node 22. Initial invocation could not find `node`; rerun used its existing installation, no dependency changes. |
| Source pin check | Android/Hub PASS; iOS BLOCKED. `git cat-file` independently confirms pinned iOS commit absent. |
| Android native facade/runtime export | PASS: Gradle build successful, 1 task executed / 61 up-to-date; 118 embedded runtime artifacts, 64 supplied by NuGet dependencies. No native JVM/device test rerun. Existing Gradle deprecations. |
| Final source Android Debug sample | PASS, **47 warnings, 0 errors**, including existing source-project XA4301 duplicate-JNI warnings. New probe has no analyzer warnings. No install/launch. |
| `bash scripts/pack.sh android` and strict Android package checker | PASS, fresh provisional `0.0.1-m3` feed. Existing analyzer/binding/readme warnings. |
| Isolated package-only Android Release consumer | PASS, **0 warnings/errors**, normal trimming/profiled AOT. Exactly 3 Rownd packages and **0 project libraries** in restore. No install/launch. |
| Python compilation, shell syntax, `git diff --check` | PASS. |

Because the all-platform native wrapper requires the absent iOS source, Android was built directly **after Android/Hub pin verification**, using the established `prepare-android-source.py` → `:mauiFacade:exportRuntime` → binding restore → `prepare-android-runtime.py` steps. No sibling tracked source or pin was changed. The native export largely reused valid pinned build intermediates; this is not a clean-room/source-reproducibility pass.

The previous Android package feed, including historical m2/m3 outputs, was preserved under ignored `artifacts/m5-prior-packages.*` before packing a fresh feed. Consumer: `/home/dev/.cache/rownd-m5/rownd-consumer.NNj4fd`, with its own package cache. Logs: `/tmp/opencode/rownd-m5-{managed,python,native-build,pack,consumer}.log`, `rownd-m5-debug-final.log`. An initial Debug build had 57 warnings; formatting the new probe removed its analyzer warnings before the final 47-warning build.

### Exact local artifact SHA-256

These are build-only baseline-pin artifacts, **not** the user's coordinated Android/Hub persistence candidate. Version `0.0.1-m3` alone does not identify them.

| Artifact | SHA-256 |
| --- | --- |
| `SuperTokens.Rownd.Foundation.0.0.1-m3.nupkg` | `b1dca2ade475b948920f1623ca7c7808b48c0461fc5e5c0a2e7e66a4dbf7ba68` |
| `SuperTokens.Rownd.Maui.0.0.1-m3.nupkg` | `20cecc34d7ce62da53ab7446069c6077bf7403bc69f17e0e2c14181d8d7a92dc` |
| `SuperTokens.Rownd.Native.Android.0.0.1-m3.nupkg` | `d178dba6ab8368a8e6ff67ff5e58e730ebcce0ff7c875d591bf84d80d3d0afb5` |
| P1-corrected source Debug `io.supertokens.maui.buildcheck-Signed.apk` | `04dcbbca8b8aa27b8430782bbdb651ab7c4c51cc4482fc7217d22db700640f36` |
| Isolated package Release `io.supertokens.maui.buildcheck-Signed.apk` | `d912c30581ec269b69b64c8749a014c78345ff89136ae1abde726a2d962c8b37` |

Packages live under `artifacts/packages/android`. Debug APK lives under `samples/Passwordless/bin/Debug/net10.0-android`; Release APK under the isolated consumer's `bin/Release/net10.0-android`. These app identities/signatures are build fixtures, not customer device-signing acceptance. Final metadata/hash collection is retained at `/tmp/opencode/rownd-m5-artifacts.json`; no credential/capture files are included.

## Historical Linux acceptance matrix

P1 correction verification (2026-09-28): **111 managed unit tests**, **62 Python offline tests**, Python compilation and whitespace checks passed; Android source Debug sample rebuilt with **47 existing warnings, 0 errors**. Logs: `/tmp/opencode/rownd-m5-p1-{managed,python,debug}.log`. The old Debug hash `c92c23b23e7da874abb3cdc8d2bcd7770b7e257948113b8204ddfc8fa0b1e796` and its entry in `/tmp/opencode/rownd-m5-artifacts.json` are **superseded**, not hashes of the corrected sample. Package and isolated Release hashes above remain historical build results; they were not rebuilt for this Debug-only probe correction. No integration/E2E/device/services ran.

Historical Mac evidence is retained in [M4 status](m4-status.md); it is not reassigned to M5 outputs.

| Gate | Android | iOS | Required next evidence |
| --- | --- | --- | --- |
| Managed API/error/lifecycle unit coverage | PASS, shared | PASS, shared | 111 offline cases; native runtime separate |
| Current source Debug sample compile | PASS | BLOCKED here | Mac + preserved missing iOS pin |
| Provisional package/isolated Release build | PASS baseline pins | UNRUN M5 | Rebuild combined exact-candidate feed on Mac |
| Real OTP and phone-link → C# protected API | Historical M4 candidate PASS | Historical M4 revision PASS | Rerun on identified M5 package/app bytes |
| Email magic-link regression, link replay/expiry and presenter cancellation | Historical M4 evidence; candidate expiry not rerun | Historical M4 evidence | Repeat M4 journeys on exact candidate; retain initial failures |
| Saved-token expiry401 → getter refresh → same-session200 after **both** methods | UNRUN | UNRUN | `refresh-recovery` per platform |
| 503 getter fault, no false sign-out, next getter recovery | UNRUN | UNRUN | Same scenario, counter/state assertions |
| Current and expired-token process relaunch | UNRUN M5 | UNRUN M5 | Same scenario; real process ID change |
| Sign-out survives relaunch; new real login | UNRUN M5 | UNRUN M5 | Same scenario |
| Same-device cold/startup + cross-device negative control | Local Mac candidate evidence only | Candidate rerun pending | Available exact Android/Hub coordinated source + preserved iOS source |
| Signed physical package-only Release auth/session checks | UNRUN | UNRUN | Devices, actual signing/provisioning, install/run |
| Verified HTTPS warm/cold + real browser Open-in-app fallback | BLOCKED inputs | BLOCKED inputs | Domain hosting, signing IDs, associated-domain entitlement, physical targets |
| Active-Hub recreation / terminal native disposal | UNRUN | UNRUN | Existing manual M4/M3 gates; rebind is insufficient |
| Legacy MAUI upgrade / one-time reauthentication | DOCUMENTED | DOCUMENTED | Customer upgrade check; no managed credential migration |
| Customer follows README with own identity/backend | PENDING | PENDING | Customer integration result |
| Source reproducibility / distribution | OPEN | OPEN | Exact candidate source, Core digest, native build provenance; deferred iOS release |
| Publication / provider SMS | DEFERRED | DEFERRED | Separate authorization; not part of M5 |

## Historical Linux blockers and requested Mac work

1. The coordinated M4 Android/Hub persistence fix exists only on the user's Mac and was not fetched here. Preserve its local source and [recorded strict runs](m4-status.md#local-coordinated-fix-and-strict-reruns). Current pins stay unchanged. Baseline packages above cannot claim candidate behavior. Full-source pin checks deliberately reject dirty/unavailable candidates; record candidate revisions and local diff hashes rather than disguising that result. Candidate source availability blocks exact-candidate runtime validation, **not this implemented automation**.
2. iOS pin **95bd10b6c5bec1678fa6094e031a3e1cbf900901** is absent locally, and Linux has no Xcode/iOS toolchain. Never substitute published 0.2.4 or a nearby commit. Native fatal-initialization error mapping and deferred upstream iOS publication remain release gates.
3. Core image remains unpinned; record the actual digest. Physical HTTPS/signing/device inputs and package-only runtime evidence remain outstanding. No existing M4 result closes these M5 gates.
4. On Mac: rebuild the exact native candidate; prepare/type-check the overlay; start the shared 90-second fixture/Hub; build/install startup-configured Debug apps; run `refresh-recovery` for Android then iOS with explicit Appium sessions. Preserve failed runs as failures. Repack the exact candidate, use isolated consumers/caches, hash outputs, rerun package-only and signed Release/manual gates. Commands and config are in [testing-m5.md](testing-m5.md).

## Mac candidate validation — 2026-09-28

Pulled `main` to `b502245`. The coordinated native candidate is Android `f7f4a5f921ca8f44ab6902ce2754ac84578f3a90`, iOS `95bd10b6c5bec1678fa6094e031a3e1cbf900901`, and Hub `d2c0619ff661200fe4f404f3d8d2d82fa590c165` plus the short-lived-token fix described below (committed as `17f98e8`). Declared pins and package versions remain unchanged; these are candidate results, not an all-pin source-check pass.

### Issues found and changes

- The Hub used a five-minute early-refresh threshold as its authentication/expiry predicate. With M5's real 90-second tokens, successful backend login never sent credentials to either native SDK. Both responsive device runs reproduced the consume-success/host-signed-out failure. The Hub now distinguishes actual finite JWT expiry for authentication/handoff from the five-minute proactive legacy-migration refresh window. Short-token native-handoff and expiry-boundary regression tests were added. No Android or iOS SDK source change was needed for this fix.
- The M5 runner could replace the original test failure with a secondary cleanup error. Cleanup now attempts both required controls, preserves an existing failure, and still fails an otherwise successful run if cleanup fails. Three regression tests cover this behavior.
- Initial Android device/ADB responsiveness failed after incremental installation. Preserving disk state, cold-booting our emulator, and reinstalling the exact APK with non-incremental installation restored responsiveness. No product crash signature was captured; the initial failure remains recorded.
- Two initial iOS attempts were blocked by an Apple Account verification dialog. Simulator computer-use inspection showed the overlay although Appium exposed the underlying host controls. Dismissing the unrelated prompt allowed real login to proceed and expose the separate Hub issue.
- Initial package Debug invocations from the projectless working directory selected an unpinned SDK. Those generated outputs were rejected/preserved. Both consumers were rebuilt from their own directories with `global.json` selecting SDK/workload `10.0.200`; no bypass flags were used.

### Build and fixture evidence

- .NET/workload set `10.0.200`, Xcode `26.2`; MAUI 10.0.20, Android workload 36.1.43, iOS workload 26.2.10217 and JDK 21.0.12.1 were retained.
- Shared local fixture: API `127.0.0.1:3139`, Hub `127.0.0.1:8787`, actual Core access-token validity **90 seconds**, failure switch **503**, embedded initialization delay **0**. Journeys are sequential; no session fabrication, JWT editing, confirmation click, or policy relaxation. The pinned app configuration leaves `enforce_same_device_passwordless_sign_in` unset, retaining Hub defaults; any same-device confirmation chooser remains a test failure.
- Core image: `supertokens/supertokens-postgresql@sha256:8302ef1766b05c2b85cbed85de8d6e7fb38dedfe041918327e24e5b33d6f2590`.
- The stock harness preparation correctly rejects the newer Android HEAD. For this run, the exact pinned `test-server` was exported from `cd08c866828232d130f32df3c1c47ee7fabe1a2c` and transformed using the current M5 overlay function. The candidate test-server and dependency files were verified unchanged from that pin. Overlay TypeScript check passed; the sibling was not checked out or modified.
- Native Android facade/runtime export passed. Clean iOS device/simulator archives, XCFramework checker and **2/2 bridge XCTest cases** passed. Native iOS source remained clean. Previous generated outputs/feed were preserved.
- Source Debug builds passed: Android **51 warnings, 0 errors**; iOS **37 warnings, 0 errors**. Fresh combined package feed and strict Android payload/dependency checks passed; all **119** packaged iOS framework files match the rebuilt framework.
- Isolated package-only Release and Debug consumers passed on both platforms. Android **0 warnings/errors**; iOS **1 existing nullability warning, 0 errors**. Each restore contains exactly **3 Rownd packages, 0 project libraries**, in a fresh private cache.
- Offline validation: **111 managed tests**, **65 Python tests**, and corrected Hub **313 unit tests passed / 1 skipped**, type checks/build passed. The opt-in live integration environment check passed.

### Runtime results

| Runtime check | Source Debug | Package-only Debug |
| --- | --- | --- |
| Android full `refresh-recovery` | **PASS**, corrected Hub, run 3 | **PASS**, first attempt |
| iOS full `refresh-recovery` | **PASS**, corrected Hub, run 4 | **PASS**, first attempt |
| Live managed fixture/environment and fresh phone capture | **PASS** | Shared fixture checks |

Each complete journey covers both real email OTP and untargeted external phone links; saved-token 200 then real-expiry 401; first explicit getter/counter/exact-candidate same-user/session 200; 503 fault without false sign-out and subsequent recovery; current and expired-token process restart; sign-out persistence; and fresh login with a different session. Source Android run 3, source iOS run 4, and the first package-only run on each platform completed successfully with all assertions and final cleanup. Each completed 25 probe operations in addition to real login, protected identity and process/OS dispatch assertions. Approximate durations: Android source 809 seconds, Android package 839 seconds, iOS source 660 seconds, iOS package 654 seconds. Initial failed attempts remain recorded; they are not reassigned to the corrected candidate.

The dedicated M5 fixture and its test containers were stopped after all four successful journeys and cleanup; the test apps remain signed out with probe memory cleared.

### Remaining acceptance boundaries

The M4-only replay/expired-link, delayed-startup, cross-device and presenter-cancellation matrix was not rerun against this new Hub patch; its older results remain historical. Signed physical Release runtime, verified HTTPS/app associations and real-browser fallback, customer-owned backend/signing integration, legacy upgrade checks, and the previously documented native disposal/active-Hub recreation gates remain separate. Local simulator/emulator results do not close those gates. No package publication, provider SMS or push was performed for this validation.

### Tested artifact identities

All packages are provisional `0.0.1-m3`; version alone does not identify these bytes. Android hashes are SHA-256 of APKs. The source iOS value hashes the canonical sorted relative-file/hash map; package iOS values hash the saved sorted per-file manifest JSON. Neither iOS value is a signature/provisioning claim.

| Artifact | SHA-256 |
| --- | --- |
| `SuperTokens.Rownd.Foundation.0.0.1-m3.nupkg` | `19bc258c86e6b5c1a60752eaf3f27c539cf44f1376d8de95cf58bc4a193c2483` |
| `SuperTokens.Rownd.Maui.0.0.1-m3.nupkg` | `42dace3a3d57c795577c6baf67311dcc1b5a61c102f247f9fff60c1499556967` |
| `SuperTokens.Rownd.Native.Android.0.0.1-m3.nupkg` | `1e351f3a2f6c5cf94d76b877b54b5168aba0b44d6537000e351991a49a2c5e76` |
| `SuperTokens.Rownd.Native.iOS.0.0.1-m3.nupkg` | `b0bbf83e1313aba8089cf95c400ae6d51fde6bc398d9b17b1e2e4e97fa9d3023` |
| `Package Android Debug APK` | `ca2f9119e67f7db040df0cd796785329f0ca3a3de83a5fdcfb6971adaba542cc` |
| `Package Android Release APK` | `42c3d51a99a7c3855e74b327bc62ada43570acff105a6a6589f7256112e04024` |
| Source Android Debug APK | `63957167c135b6025ba4f510b9cf393eb9a77a60e08783504a18f7807eef7934` |
| Source iOS Debug file map | `264b47d6df3f1e3e0cb9e68ccbd1fe1dd8bf504735c9c3ffa86a78ba7ac1de5f` |
| Package iOS Debug file manifest | `11aa821d80300454423c519123bb1c8105a7177a9d940cbe99070d0a9314e785` |
| Package iOS Release file manifest | `6152d058b726880aaeb9876659449424ff6c60180632c78074504a406529a52a` |

The iOS XCFramework has a 119-file hash manifest; all 119 packaged framework files match the rebuild. Candidate source, local patch, file manifests and logs are retained in the local M5 evidence set. Raw backend/Appium/device logs remain private because they may contain synthetic credentials.
