# M4 phone links and lifecycle runbook

These are **commands for the user's Mac/device run**, not runtime evidence. See [m4-status.md](m4-status.md). No integration, E2E, emulator, simulator or device tests were run during implementation. Keep [M3's recorded Mac results](m3-status.md) attached to their original revisions/artifact hashes.

## Toolchain and offline checks

Keep `global.json` / `eng/versions.json`: .NET/workload set **10.0.200**, MAUI **10.0.20**, Android **36.1.43**, iOS **26.2.10217**, Xcode **26.2**, JDK **21.0.12**. iOS source **95bd10b6c5bec1678fa6094e031a3e1cbf900901** remains local/unreleased; its release is deferred. Do not substitute published 0.2.4. Preserve the universal Swift-header checker fix in `1417a85`.

```sh
python3 scripts/check-native-sources.py
bash scripts/test-unit.sh --nologo -v quiet
python3 -m unittest discover -s tests/package_checkers -p 'test_*.py' -v
python3 scripts/prepare-m4-harness.py
artifacts/m4-harness/node_modules/.bin/tsc --noEmit \
  -p artifacts/m4-harness/test-server/tsconfig.json
```

The TypeScript check requires the Android sibling's locked `npm ci` dependencies. Preparation copies its clean pinned `test-server` to ignored `artifacts/m4-harness`, applies narrowly scoped observations and links its `node_modules`. It neither starts a server nor changes the sibling. Source-shape drift fails preparation. Python tests mock subprocess/HTTP boundaries; passing them is not mobile coverage.

## Startup configuration and builds

The sample can embed a **non-secret** JSON file with `-p:RowndStartupConfig=/absolute/path/startup.json`. It reads configuration before OS callbacks, configures automatically on first appearance, and reuses the one native singleton across activity/page recreation. It does not persist managed credentials. With no file, the older interactive form remains available, but does not establish automatic cold-start acceptance.

Store outside the checkout; use real device-visible origins from the fixture. Example for the existing local fixture with Android port reversal / iOS Simulator:

```json
{
  "AppKey": "test_app_key",
  "ApiDomain": "http://127.0.0.1:3137",
  "ApiBasePath": "/auth",
  "HubUrl": "http://127.0.0.1:8787",
  "AppLinkScheme": "rowndmauisample",
  "ProtectedUrl": "http://127.0.0.1:3137/test/protected",
  "InitializationDelayMs": 10000
}
```

Use `InitializationDelayMs: 0` normally; **10000–30000 in Debug** for `delayed-startup`. Delay is bounded at 30 seconds and ignored in Release. Public app key / API / Hub settings are compiled into the app; never place backend secrets or tokens here. The sample registers `rowndmauisample`; changing the JSON scheme alone does not change platform registrations. Source-generated JSON metadata supports trimming.

```sh
export ROWND_APPLICATION_ID='YOUR.ACTUAL.APPLICATION.ID'
export ROWND_STARTUP_CONFIG='/absolute/path/startup.json'
dotnet build samples/Passwordless/Passwordless.csproj -c Debug \
  -p:RowndUsePackage=false -p:RowndTargetFrameworks=net10.0-android \
  -p:RowndApplicationId="$ROWND_APPLICATION_ID" \
  -p:RowndStartupConfig="$ROWND_STARTUP_CONFIG" -p:EmbedAssembliesIntoApk=true
```

On Mac, with the pinned native iOS checkout and an up-to-date XCFramework:

```sh
bash scripts/build-native-ios.sh
dotnet build samples/Passwordless/Passwordless.csproj -c Debug \
  -p:RowndUsePackage=false -p:RowndTargetFrameworks=net10.0-ios \
  -p:RowndApplicationId="$ROWND_APPLICATION_ID" \
  -p:RowndStartupConfig="$ROWND_STARTUP_CONFIG" \
  -p:RuntimeIdentifier=iossimulator-arm64 -p:CodesignKey=- -p:CodesignProvision=
```

Clean managed iOS intermediates when replacing the framework, as in [testing.md](testing.md). For package acceptance, rebuild/pack the changed facade with `bash scripts/pack.sh all` on Mac, then use `verify-package.sh` with `-p:RowndStartupConfig=...` and platform signing properties. It copies the current sample; the external config must remain accessible. Current provisional package version remains `0.0.1-m3`; retain artifact hashes and use an isolated package cache to avoid old same-version packages. Do not install historical M3 packages and expect the new `RowndLinks` lifecycle surface.

```sh
ROWND_PACKAGE_SOURCE="$PWD/artifacts/packages/all" \
  bash scripts/verify-package.sh android -p:RowndStartupConfig="$ROWND_STARTUP_CONFIG"
ROWND_PACKAGE_SOURCE="$PWD/artifacts/packages/all" \
  bash scripts/verify-package.sh ios -p:RowndStartupConfig="$ROWND_STARTUP_CONFIG" \
  -p:RuntimeIdentifier=iossimulator-arm64 -p:CodesignKey=- -p:CodesignProvision=
```

Use an existing writable `TMPDIR` outside the checkout; the verifier prints its new consumer directory. Linux platform-only builds use `artifacts/packages/android` instead of the combined feed.

Install the resulting APK/app and create an explicit Appium session using [testing.md](testing.md#install-the-sample-and-create-an-appium-session). No driver creates/deletes a session. Use the same device UDID/serial in Appium and runner JSON. Drivers require inspectable native Hub WebViews (Debug; iOS 16.4+), matching Chromedriver on Android, and an Appium server on the same host as `adb`/`xcrun`. Release inspection may be unavailable; repeat those checks manually on package-only signed Release builds.

## Lifecycle ownership

- **Android ownership:** configure `RowndLinks` before capturing callbacks. `MainActivity.OnCreate` and `OnNewIntent` capture original `DataString` before calling base, then store/pass a copy with data removed for every login callback the pinned native listener could consume. Ownership uses the same `java.net.URI` parser as native, including user-info/ports, slash-trimmed custom paths, configured Hub host, `rownd-hub.supertokens.com` and its subdomains, and the two native staging/Pages hosts. **Ownership is not acceptance:** only configured custom-scheme `account/login` without user-info/port, or configured HTTPS origin `/account/login` without user-info, enters the managed slot. Native aliases and malformed-route variants are sanitized and dropped, including before readiness, while suspended, oversized and after disposal. Verification/non-login routes, unrelated hosts and non-view intents keep base handling. `RowndLinks` is the sole login-link owner **when this adapter is installed**; do not also call native `handleIntent` or register another login listener.
- **Readiness and deliberate latest-link-wins policy:** retain **one latest** waiting encoded URL, at most 16 KiB, expiring after two minutes. A newer accepted distinct callback replaces that waiting URL. Dispatch needs native initialization and an active/resumed host, rechecked on a deferred main-thread turn; startup/suspended/warm same-turn bursts produce one native submission. Disposal/initialization failure clears waiting work. Exact encoded strings are neither decoded nor rebuilt. Duplicate submissions coalesce for a fixed two seconds in a bounded 32-entry cache; native rejection/throw does not cache success, allowing a subsequent OS retry. `HandleUrl == true` means managed acceptance/coalescing, **not native consumption or authentication**.
- **Policy tradeoff:** the native public handlers return synchronously after scheduling presentation and provide no URL-consumption/presentation-completion acknowledgment to this facade. Android writes one `pendingHubDeepLinkUrl` which the Hub reads later; draining a managed FIFO would overwrite earlier callbacks and request multiple presentations. This adapter therefore does **not** promise preservation of all distinct links. A newer callback arriving after a previous submission may also supersede its unread native slot and request another native presentation. No artificial delay or synchronous boolean is treated as consumption acknowledgment. Native/backend replay handling remains authoritative after the two-second coalescing window. FIFO delivery would require an upstream, correlated completion/cancellation contract on both platforms; it is not claimed here.
- **iOS:** prepare link recognition in `FinishedLaunching`, queue launch URL / user-activity dictionary, forward `OpenUrl` and `ContinueUserActivity`, fall back to base for unhandled URLs. `OnActivated` drains after native readiness; `OnResignActivation` pauses delivery. Original `NSUrl.AbsoluteString` is retained through the router. **This sample selects MAUI 10's UIApplicationDelegate single-window lifecycle:** no `UIApplicationSceneManifest`, no scene delegate and no second scene forwarding owner. Scene-based customer hosts must wire their selected MAUI scene connection/open-URL/user-activity callbacks into the same router instead of registering both owners; this sample does not claim scene-host validation.
- Native Rownd remains the sole presenter/session store. Android's pinned lifecycle listener uses weak activity references, registers once per ComponentActivity, removes per-activity new-intent listeners on destruction and obtains a new host/viewmodel on recreation. C# state subscriptions attach once per appearance and detach on disappearance; `Rebind page subscription` exercises unsubscribe/re-add. Pending sample HTTP requests cancel when the page disappears. Disposal of the SDK instance is terminal and is not sign-out; use M3's diagnostic-consumer disposal gate.
- Both thin native facades disable optional clipboard auto-consume before configuration; otherwise pasted callbacks could bypass the chosen readiness/forwarding owner. OS URL dispatch and the Hub's actual fallback action remain the supported entry paths.

## One shared observed fixture for both platforms

Use the Hub setup/reachability instructions in [testing.md](testing.md#start-the-shared-fixture-and-hub). Start the pinned Hub separately. For **M4**, replace the old standalone backend command with this prepared overlay:

```sh
(cd ../supertokens-rownd-android && npm ci)
python3 scripts/prepare-m4-harness.py
export ANDROID_HOST=127.0.0.1
export ANDROID_HARNESS_PORT=3137
export ANDROID_HUB_URL=http://127.0.0.1:8787
export ANDROID_PUBLIC_API_URL=http://127.0.0.1:3137
node --import ./artifacts/m4-harness/node_modules/tsx/dist/loader.mjs \
  artifacts/m4-harness/test-server/run-harness.ts
```

Alternatively run `node --import tsx test-server/run-harness.ts` with working directory `artifacts/m4-harness`. Docker must be running. Both platforms use the Android harness's real passwordless recipes, existing email/SMS capture and locked Rownd plugin. The overlay adds capture timestamps, SHA-256 challenge-correlated consume **JSON statuses/user IDs**, `/test/m4/observations`, and a SHA-256 session fingerprint on the verified protected response. It does not mint sessions, alter native auth, bypass same-device policy, or change code expiry. HTTP 200 alone is not considered consume success. Use a **dedicated fixture, one runner at a time**; native requests use the default namespace. `/reset` resets observations/captures; don't reset during a journey.

Core's image is still unpinned upstream; record its actual digest and passwordless code lifetime. For physical HTTPS testing, set `ANDROID_HUB_URL` and advertised API origin to reachable trusted HTTPS endpoints **before starting**. The iOS sample has no ATS bypass. Hosted Hub config must keep the intended same-device policy. Local capture replaces real SMS delivery for this approved scope.

## Concrete Appium journeys

External runner JSON (`ROWND_E2E_CONFIG`), distinct from embedded startup JSON:

```json
{
  "harness-url": "http://127.0.0.1:3137",
  "application-id": "YOUR.ACTUAL.APPLICATION.ID",
  "device-id": "EXPLICIT_ADB_SERIAL_OR_SIMULATOR_UDID",
  "ios-device-kind": "simulator",
  "link-scheme": "rowndmauisample",
  "phone": "+12025550123",
  "email": "maui-m4-run-001@example.com",
  "phone-selector": "#rph-sign-in-identifier-input",
  "debug-lifecycle": true,
  "https-handoff": "warm",
  "expiry-wait-seconds": 901
}
```

Choose controlled test identities, actual app ID/device ID, and **actual code lifetime plus a margin** for expiry (901 is only appropriate for a 900-second lifetime). `debug-lifecycle` invokes the sample's Debug Android `Activity.Recreate()` button; set false for Release/iOS and record that gate separately. `https-handoff: cold` tests terminated HTTPS entry with a fresh challenge. Optional `hub-close-selector` overrides the pinned `.rph-close[aria-label="close"]`; inspect the real Hub before overriding. `expected-user-id` provisioning is no longer required: the real successful consume for the exact captured challenge establishes expected identity, independently compared with C# state and the bearer-protected backend result.

```sh
export ROWND_APPIUM_URL=http://127.0.0.1:4723
export ROWND_APPIUM_SESSION='EXISTING_SESSION_ID'
export ROWND_E2E_CONFIG='/absolute/path/e2e-android.json'
ROWND_RUN_E2E=1 bash scripts/test-passwordless.sh --platform android --scenario phone-magic-link
ROWND_RUN_E2E=1 bash scripts/test-passwordless.sh --platform android --scenario cold-phone-magic-link
ROWND_RUN_E2E=1 bash scripts/test-passwordless.sh --platform android --scenario delayed-startup
ROWND_RUN_E2E=1 bash scripts/test-passwordless.sh --platform android --scenario email-magic-link
ROWND_RUN_E2E=1 bash scripts/test-passwordless.sh --platform android --scenario expired-link
ROWND_RUN_E2E=1 bash scripts/test-passwordless.sh --platform android --scenario smoke
ROWND_RUN_E2E=1 bash scripts/test-passwordless.sh --platform android --scenario sms-otp
```

Repeat each with `--platform ios`, iOS runner JSON and its existing Appium session. Automated iOS external dispatch currently uses **explicit Simulator `simctl openurl`**; physical iPhone external taps are manual below, not replaced with a targeted Appium `bundleId` command.

Each run terminates/relaunches without clearing data, signs out, cancels/reopens the real Hub, enters the real contact UI, rejects stale captures by challenge fingerprint, and uses external OS dispatch. `smoke` enters captured email OTP; `sms-otp` enters captured phone OTP through **Use a code instead**. Link cases background, terminate, or observe `Initializing` before dispatch. Android uses untargeted `ACTION_VIEW` with no package/component; iOS uses untargeted `simctl openurl`. Query/fragment bytes are unchanged when converting only the prefix to the sample scheme.

Assertions: exactly one correlated JSON `OK` consume; matching native/C# and backend user; a fresh C# `GetAccessTokenAsync` → ordinary cookie-free, non-redirecting `HttpClient` request; stable session fingerprint; host touch counter changes (sheet no longer blocks touches). Replay occurs after adapter coalescing; a brief native reopen/dismiss is allowed. A real process restart must change the non-secret process ID, then return the same verified native session. Rebinding and optional Android activity recreation remain interactive. Sign-out yields `No session` and survives another process restart; Hub reopens. The expiry case waits real elapsed time with Appium keepalives, requires explicit expired/restart-flow rejection, verifies no session after restart, then completes a fresh challenge.

Drivers print only milestones/outcomes. Exceptions, capture responses, URL subprocess output and WebDriver responses are not printed because they may contain credentials. Driver/server debug logs and raw captures remain local. A timeout/failure is not a skipped pass. `refresh-recovery` remains explicitly blocked for M5. These runnable drivers have **not yet been run on either runtime**.

## HTTPS registration: required inputs and generated files

Obtain:

1. Actual custom Hub/login HTTPS hostname and hosting access for `/.well-known/` on that host.
2. Android package ID plus SHA-256 fingerprints for installed signing certificates (Play App Signing certificate when applicable, not merely upload certificate).
3. iOS bundle ID plus the **application-identifier prefix** from the signed entitlement (usually Team ID); provisioning with Associated Domains capability.

No identity/domain/certificate is invented and nothing is deployed by this command:

```sh
python3 scripts/generate-link-associations.py \
  --domain "$ROWND_LINK_DOMAIN" --android-package "$ANDROID_APPLICATION_ID" \
  --android-sha256 "$ANDROID_SIGNING_SHA256" \
  --ios-prefix "$IOS_APPLICATION_IDENTIFIER_PREFIX" --ios-bundle "$IOS_BUNDLE_ID" \
  --output "$HOME/.config/rownd-maui/associations"
```

Repeat `--android-sha256` for additional actually installed signers. Output: `.well-known/assetlinks.json`, `.well-known/apple-app-site-association` (no extension), `AndroidManifest.xml`, `Entitlements.plist`. Only `/account/login` is associated. Host JSON over public trusted HTTPS, no redirects/auth, correct JSON content type. Inspect responses after **you** deploy; Apple CDN caching can delay AASA propagation.

Build Android with `-p:RowndAndroidManifest=/absolute/path/associations/AndroidManifest.xml`; it augments the explicitly named sample activity with a separate autoVerify HTTPS filter. Scheme registration still comes from its attribute. Build/sign iOS with `-p:CodesignEntitlements=/absolute/path/associations/Entitlements.plist` plus actual signing settings. Configured Hub URL and captured link host must match this domain. Verify merged APK manifest and signed iOS entitlements, not just generated files. The generated Android manifest retains the sample's development HTTP permission; production transport policy is host-owned.

## Actual OS routing and browser fallback gates

For each warm and cold physical platform case, start a **fresh real Hub challenge** with the selected policy and capture. Keep app data for cold termination. No real provider/Message delivery is required in this phase.

Android:

```sh
adb -s "$ANDROID_SERIAL" shell pm verify-app-links --re-verify "$ANDROID_APPLICATION_ID"
adb -s "$ANDROID_SERIAL" shell pm get-app-links "$ANDROID_APPLICATION_ID"
ROWND_RUN_E2E=1 bash scripts/test-passwordless.sh --platform android --scenario https-magic-link
```

Record domain verification, installed signer, foreground destination and backend outcome. Repeat with runner JSON `https-handoff: cold`. Do not use `set-app-links`, `am start -n`, `-p`, or a targeted Appium deepLink to claim association success.

For manual Android or iOS Simulator dispatch of a fresh challenge already created in the Hub:

```sh
ROWND_RUN_E2E=1 python3 tests/e2e/open_captured_link.py --platform android --kind https
# Use --platform ios for explicit Simulator; --kind scheme for the isolated scheme gate.
```

Physical iPhone: place the **actual captured HTTPS URL** in Notes or an external HTTPS page on another domain, background/terminate the app, then tap the link. Record automatic app opening vs Safari, C# state, one correlated success and matching protected identity/session. Entering the URL in Safari's address bar is not Universal Link verification. Reinstall with correct entitlement/provisioning and allow association refresh when needed; record any user preference to stay in the browser.

**Browser fallback, both platforms:** use another fresh native-context challenge. Load its actual captured HTTPS URL in Safari/Chrome (address-bar navigation is appropriate for this separate fallback gate). Before any action, require zero `OK` observations for that challenge and the Hub's mobile blocked / **Open in app** UI. Tap the actual rendered action; inspect locally that its destination keeps the original query/fragment and registered scheme. Confirm native foregrounding, exactly one correlated successful consume, dismissed Hub, host touch and C# protected request. Do not synthesize a scheme callback for this gate, inject a native channel into the browser, or relax same-device policy. If the selected policy prevents fallback/cold handoff, record **FAIL/BLOCKED compatibility** with observed reason, not a pass with policy changed.

## Remaining manual lifecycle/distribution gates

- Cancel by native dismissal/back/swipe as well as Hub close, background/resume while a challenge is active, recreate Android activity while Hub is active, then complete the original challenge and reopen sign-in. Check one presenter and no stuck overlay. Automated recreation currently exercises the authenticated host.
- Dispose a diagnostic consumer's C# instance with state/config/token callbacks queued; verify no abandoned UI callbacks, no crash, subscriptions released, and persisted native state remains until explicit sign-out. Repeated sample rebind is not terminal native-disposal evidence.
- Repeat custom scheme, HTTPS, fallback and persistence on actual package-only signed physical Release artifacts with normal trimming/AOT. Run iOS framework/linkage/resource gates with the preserved native pin on Mac.
- Record exact revisions/local changes, package/app SHA-256, tool versions, Core digest, device/OS, same-device policy, signer and each independent gate as PASS/FAIL/BLOCKED/UNRUN. Keep refresh/outage/M5 and deferred iOS publication separate. No public publishing or real SMS provider/tap is part of this phase.
