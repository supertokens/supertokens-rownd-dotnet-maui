# Testing on a Mac

**Current M4 link/lifecycle procedures:** [testing-m4.md](testing-m4.md), with [actual M4 evidence](m4-status.md). Its embedded startup config, observed shared harness and concrete Appium drivers supersede the older interactive-config/expected-ID/targeted-dispatch procedures below. Historical runtime evidence remains scoped to its recorded revisions. M3 combined-feed Mac build results are in [m3-status.md](m3-status.md); they do not establish M4 runtime results.

For current package-only Release validation, offline checker tests and physical-device evidence, follow the [M3 validation runbook](testing-m3.md).

**M2 runtime acceptance remains open.** Android Debug and Release email OTP have limited emulator evidence; other runtime gates remain.

### iOS Debug runtime verification — 2026-09-25

On checkout `778bcff` plus the fixes below, the source Debug sample passed computer-use checks on the iPhone 17 Pro iOS 26.3 simulator, using .NET/workload set 10.0.200, MAUI 10.0.20, iOS workload 26.2.10217 and Xcode 26.2 (17C52). The 73 managed tests, both native bridge XCTest cases, and shared fixture `environment` check passed. The two bridge XCTest cases only validate invalid-configuration rejection; the added Swift authentication regressions are described below.

Two confirmed problems were corrected:

- The sample had no launch-screen declaration. Its built manifest lacked `UILaunchStoryboardName`; previous Maestro logs reported a 320×480-point viewport, and simulator screenshots showed a letterboxed form. `EnableBlankMauiSplashScreen=true` generates `MauiSplash`; after a clean rebuild/reinstall the app fills the screen. Clean the sample's iOS intermediates when enabling this property: stale resizetizer stamps initially caused a missing `MauiInfo.plist` error.
- The managed iOS bridge passed `HubUrl.AbsoluteUri` with a trailing slash to native code, which concatenates `/mobile_app`. The actual Hub sheet displayed `Cannot GET //mobile_app`. Trimming trailing slashes at the iOS bridge boundary fixes the request; no fixture routing workaround was used.

Computer use exposed the MAUI automation IDs and filled the configuration with the fixture key and localhost URLs. The native Hub exposed little accessibility content, so its input/buttons were driven using fresh screenshots. Verify focus before typing and inspect the entered value: the first email-entry attempt dropped leading characters. The capture was retrieved for the exact synthetic address shown by the Hub. iOS also requested permission to paste the test configuration, which was explicitly approved. No black-screen failure recurred during this run; the original Maestro empty-tree/black-screen behavior is not proven fixed, and the Maestro/Appium scripts were not rerun.

Verified runtime sequence:

1. Configure, open native Hub, request email OTP, read the local capture, enter the six-digit code, and observe authenticated state.
2. Call the backend-protected API and observe its verified user ID matching the authenticated identity.
3. Terminate/relaunch the app process without reinstalling or clearing data, re-enter the same configuration, and observe authentication restored without another OTP. A second protected request returns the same user ID and session handle.
4. Sign out, observe `Signed out`, call the protected action and observe `No session`, then reopen the signed-out Hub.

Persistence evidence covers native session restoration after explicit reconfiguration; the sample does not persist its editable configuration and this does not establish automatic cold-start/deep-link behavior. After successful protected requests, the status label changed to `Authenticated: identity pending` despite the correct backend identity; this led to the native identity-state fix described below. Release/package-consumer runtime, physical devices, phone callbacks, expiry/recovery, and a repeatable unattended iOS driver remain open gates.

The shared Hub/Core/plugin fixture used localhost API 3137 and Hub 8787, Node v26.7.0, the locked Rownd plugin 0.3.0-beta.2, Postgres 14 and Core image digest `supertokens/supertokens-postgresql@sha256:8302ef1766b05c2b85cbed85de8d6e7fb38dedfe041918327e24e5b33d6f2590`. Local HTTP worked on this simulator without an ATS exception; this is not evidence for arbitrary hosts or physical devices. The image remains unpinned in fixture startup.

The first attempts from a restricted agent sandbox failed before tests ran (CoreSimulator connection errors and Swift cache writes denied). With approved elevated execution, both native tests passed. Those runner failures were not evidence of an application crash.

### Native identity-state fix

**Development status:** the upstream iOS SDK release is deferred. Continue .NET implementation without treating tests that depend on this unreleased fix as blocking; this does not waive unrelated test failures or mark deferred checks as passed. The current iOS commit pin is local and unreleased, while `version: 0.2.4` remains its base SDK version. After the SDK is released, update the commit/version in `eng/versions.json`, rebuild the native framework and managed consumer, and rerun the affected iOS checks before release acceptance.

The previous iOS SDK's authenticator cache does not observe profile actions that populate `auth.userId`. A subsequent token read or refresh could publish the older auth snapshot and erase the hydrated identity. The upstream iOS SDK fix makes the compatibility-state read, derivation, persistence and dispatch run together on the main actor using the current store. Same-session identity is preserved; replacement sessions still clear profile state and failed persistence does not publish changes. A second bug omitted `userId` from `AuthState.CodingKeys`: saving and reloading compatibility state erased the ID even with the cache fix. The SDK persists the optional `user_id` field; older saved states remain decodable and signed-out states retain no identity.

The fix and regression tests now live in `supertokens-rownd-ios`; the .NET build links the pinned sibling SDK directly. No iOS source overlay or patch is applied. The source pin currently selects the locally tested SDK commit pending publication of the next release. All 300 upstream package tests and both SDK-version tests passed; the direct-source XCFramework and clean Debug MAUI sample builds also passed. Rebuild the XCFramework before rebuilding or packaging the managed binding after updating the SDK. A normal incremental .NET build reused the old embedded framework during verification; clean the iOS consumer and its project references first (use the appropriate configuration/runtime for other consumers):

```sh
dotnet clean samples/Passwordless/Passwordless.csproj -c Debug \
  -p:RowndUsePackage=false \
  -p:RowndTargetFrameworks=net10.0-ios \
  -p:RowndApplicationId="$ROWND_APPLICATION_ID" -p:RuntimeIdentifier=iossimulator-arm64
```

Run the dedicated regression suite with an explicit simulator destination:

```sh
ROWND_IOS_TEST_DESTINATION='platform=iOS Simulator,id=SIMULATOR_UDID' \
  bash scripts/test-native-ios.sh
```

The suite covers profile hydration followed by token read and same-session refresh, replacement-session profile clearing, persistence failure, serialization/reload, legacy decoding and signed-out state. These use the actual Swift authenticator with a controlled session client, not C# mocks. All five regression tests (six cases, including both token read and refresh) pass with the SDK fix; the original source fails both identity-preservation cases (eight failed assertions). The existing 13 `AuthTests` also pass. After rebuilding both XCFramework slices and cleaning/rebuilding the Debug sample, computer use verified that the authenticated ID remains equal to the backend-verified ID after protected requests, including after process termination, relaunch and explicit reconfiguration. Sign-out clears authentication and the next protected action reports `No session`.

### Earlier iOS simulator check after 84fbfdf (Xcode 26.2, iOS 26.3)

On Apple Silicon with Xcode 26.2, `bash scripts/build-native-ios.sh` archives both slices and creates the XCFramework; reruns now replace the previously generated output. Both native bridge XCTest cases pass on an iOS 26.3 simulator (`xcodebuild test -project native/ios/RowndMauiBridge.xcodeproj -scheme RowndMauiBridge -destination 'platform=iOS Simulator,id=SIMULATOR_UDID' -derivedDataPath native/ios/build/test-derived CODE_SIGNING_ALLOWED=NO`). The shared Hub/Core/plugin fixture's `environment` integration check and 73 managed tests pass.

The earlier .NET 10.0.401 / iOS workload 26.5.10318 pin required Xcode 26.6; skipping its version check still failed because Xcode 26.2 lacks the iOS 26.5 SDK. The supported .NET 10.0.200 workload set instead supplies iOS 26.2.10217, which explicitly targets Xcode 26.2. With the matching SDK/workload set, the source Debug simulator app and isolated Release package consumer build **without Xcode validation or linker overrides**; the Android Debug sample also builds. Clean iOS intermediates when switching workload sets to avoid reusing native libraries from 26.5. The Debug iOS app installs, launches, and shows the configuration form on the iOS 26.3 simulator. A settled simulator screenshot shows the whole form with no keyboard, but Maestro 2.5.1 exposes only the app window in its accessibility tree. Coordinate-based text input sometimes leaves the simulator showing a black app window until the app is relaunched. iOS OTP, protected request, sign-out, and restart remain unverified.

Previously recorded Linux results: 72 managed unit/mock tests and 58 native JVM tests passed; Android native/binding builds, packaging, package inspection and isolated package-consumer Release build passed. See [M2 status](m2-status.md) for earlier evidence and warnings. On a Mac with .NET 10.0.401, JDK 21.0.12.1 and Xcode 26.2, 73 managed tests and 58 native JVM tests passed; Android Debug sample, packages and isolated Release consumer built. The shared Docker fixture's `environment` integration check passed against SuperTokens Core and a backend running `@supertokens-plugins/rownd-nodejs` (health, unauthenticated 401, and plugin-owned migration route). Source-built Android Release and Debug samples on an API 34 emulator completed email OTP through the native Hub, returned the expected user ID from the backend-protected API, signed out, received `No session` on another protected request, and reopened the native Hub. Appium drove native controls and direct WebView DevTools drove Hub controls; the full Appium script did not pass. The original Debug sample crashed after successful OTP consumption on both API 34 and 36.1 (Mono SIGSEGV in `mono_assembly_name_new`/`monodroid_load_assembly` on `DefaultDispatch`). The Android bridge now defers managed state notifications until after the native callback returns: three Debug OTP cycles (including one after process restart) completed without the crash. Disabling `UseInterpreter` alone did **not** fix it; a second run crashed identically. At that time, phone and iOS authentication runtime checks remained unrun; see the newer iOS evidence above.

## Tools and sibling checkouts

Build scripts require this layout; run MAUI commands from `supertokens-rownd-dotnet-maui` unless noted:

```text
rownd/
  supertokens-rownd-dotnet-maui/
  supertokens-rownd-android/
  supertokens-rownd-ios/
  supertokens-rownd-hub/
```

Exact pins from `eng/versions.json`:

| Component | Pin |
| --- | --- |
| .NET SDK / workload set | `10.0.200` (SDK roll-forward disabled) |
| MAUI | `10.0.20` |
| Android / iOS workload | `36.1.43` / `26.2.10217` |
| JDK | `21.0.12` |
| Android compile SDK | `36` for facade; sibling library also needs `35` |
| Android source | `cd08c866828232d130f32df3c1c47ee7fabe1a2c` (`0.1.14`) |
| iOS source | `95bd10b6c5bec1678fa6094e031a3e1cbf900901` (pending release; based on `0.2.4`) |
| Hub source | `086014e0f29c00722b260e69a9f28ff47512bf0f` |

Use the sibling Gradle wrapper (**8.11.1**, AGP **8.9.1**, Kotlin Android plugin **2.1.20**), not system Gradle. Install the pinned SDK/JDK, Android command-line tools, then on Mac:

```sh
export JAVA_HOME=$(/usr/libexec/java_home -v 21.0.12)
export ANDROID_HOME="$HOME/Library/Android/sdk"
export PATH="$JAVA_HOME/bin:$ANDROID_HOME/platform-tools:$ANDROID_HOME/cmdline-tools/latest/bin:$PATH"
java -version
dotnet --version
dotnet workload install maui --version 10.0.200
dotnet workload list
sdkmanager 'platforms;android-35' 'platforms;android-36' 'platform-tools'
sdkmanager --licenses
python3 scripts/check-native-sources.py
```

Also required: Python 3, Node **>=22** (Hub requirement), npm using each sibling's lockfile, Docker Desktop/running Docker daemon for Testcontainers, and Xcode 26.2/command-line tools/XcodeGen for iOS. There are no exact project toolchain pins for Node/npm/Python/Docker/Appium/drivers/Chromedriver/XcodeGen; record versions used. The pinned iOS workload **26.2.10217 targets Xcode 26.2**. The Linux `/home/dev/.config/rownd-android-tooling/env.sh` mentioned in earlier logs is not a Mac prerequisite.

The shared fixture uses Android's locked Rownd Node plugin **0.3.0-beta.2**, `EMAIL_OR_PHONE`, `USER_INPUT_CODE_AND_MAGIC_LINK`. Its images are `postgres:14` and **unpinned** `supertokens/supertokens-postgresql` (no tag/digest). The startup interface has no Core-image override. Record the actual pulled digest; exact Core reproducibility remains an open gate.

## Offline tests, builds and packages

No fixture/device required:

```sh
bash scripts/test-unit.sh --nologo -v quiet
dotnet build tests/Rownd.IntegrationTests/Rownd.IntegrationTests.csproj -c Release --nologo -v quiet
bash scripts/build-native-android.sh :android:testDebugUnitTest
```

The integration command is **compile-only**. The native build script prepares the MAUI initialization overlay and passes the extra JVM task to Gradle through `native/android/include.gradle`; running sibling Gradle without that init script omits MAUI regressions. It also exports AARs and prepares the binding runtime. JVM reports are in sibling `android/build/test-results/testDebugUnitTest/` and `android/build/reports/tests/testDebugUnitTest/`.

Android sample/package checks:

```sh
export ROWND_APPLICATION_ID=io.supertokens.maui.buildcheck
bash scripts/build-sample.sh android
bash scripts/pack.sh android
python3 scripts/check-android-package.py
bash scripts/verify-package.sh android
```

The buildcheck ID is for evaluation, not customer identity. `build-sample.sh` accepts only `android|ios` and does not forward extra MSBuild flags. `verify-package.sh` forwards arguments after the platform to restore/build. It copies the sample outside the checkout, disables source project references, restores into an isolated cache and builds Release. On Mac it uses `$TMPDIR`; if unset, set it to an existing writable temporary directory (fallback `/tmp/opencode` is environment-specific). These scripts do not install or launch anything.

Current packages target provisional `0.0.1-m3`: `SuperTokens.Rownd.Maui`, `SuperTokens.Rownd.Foundation`, and the platform binding. Feeds: `artifacts/packages/android` or `artifacts/packages/ios`, plus `https://api.nuget.org/v3/index.json`. `bash scripts/pack.sh all` on Mac builds the combined feed under `artifacts/packages/all`; use `ROWND_PACKAGE_SOURCE` with `verify-package.sh` to test that feed on both platforms. The sample now defaults to package references; source development explicitly uses `-p:RowndUsePackage=false` (set by `build-sample.sh`). No validated M3 combined customer package exists; publishing stays disabled. Repeat dependency/Dex checks if changing consumer AndroidX versions. M3 removes imported JNI copies from the binding-generated AAR; rebuilding and checking the package must confirm elimination of M2's duplicate native-library warnings. See [M3 status](m3-status.md) for current verification blockers.

### iOS build gate

After selecting compatible Xcode (`xcodebuild -version`, `xcode-select -p`) and installing XcodeGen:

```sh
bash scripts/build-native-ios.sh
export ROWND_APPLICATION_ID=io.supertokens.maui.buildcheck
bash scripts/pack.sh ios
bash scripts/verify-package.sh ios -p:RuntimeIdentifier=iossimulator-arm64 -p:CodesignKey=- -p:CodesignProvision=
```

Use `iossimulator-x64` on Intel. The native script archives unsigned device/simulator slices and creates `native/ios/build/RowndMauiBridge.xcframework`, using the sibling `Package.resolved`. The XCFramework, iOS packages, source Debug app, and isolated Release package consumer compile on Xcode 26.2 with the pinned SDK/workload set; source Debug authentication now has simulator evidence above; isolated Release package-consumer runtime linkage remains unverified. Verify Swift/ReSwift linkage, generated Objective-C selectors, resources (`Bundle.module`, GoogleSignIn) and Swift runtime embedding with a package-consumer app. Physical-device builds require your actual bundle ID, team/provisioning and signing settings.

Pinned iOS `Rownd.configure` can call **`fatalError`** on SuperTokens/keychain/installation bootstrap failure. The facade cannot turn process-fatal errors into failed C# Tasks. A throwing native initialization hook remains required; input validation does not close this gate.

## Start the shared fixture and Hub

Install sibling dependencies:

```sh
(cd ../supertokens-rownd-android && npm ci)
(cd ../supertokens-rownd-hub && npm ci)
```

Choose addresses **before startup**. Both native requests and the embedded Hub must reach the API/Hub; Python needs capture access too.

| Target | Device-visible Mac host | Runner on Mac |
| --- | --- | --- |
| Android emulator (with `adb reverse`) | `127.0.0.1` | `127.0.0.1` |
| iOS Simulator | `127.0.0.1` | `127.0.0.1` |
| Physical device | Reachable Mac LAN IP/hostname | `127.0.0.1` or LAN address |
| Remote device/Appium | Host reachable from device | Host reachable from Python runner |

On Android emulators and USB devices, run `adb -s "$ANDROID_SERIAL" reverse tcp:3137 tcp:3137` and `adb -s "$ANDROID_SERIAL" reverse tcp:8787 tcp:8787`, then configure the fixture and sample with device `127.0.0.1` URLs. `10.0.2.2` routes to the Mac but is not a secure WebView origin: the Hub's Web Crypto operations fail there. The development Android sample explicitly permits cleartext HTTP. Physical devices otherwise need a shared network and reachable ports. **The iOS sample has no ATS exception in `Info.plist`**: the table describes routing, not permission to load HTTP. Verify native/WKWebView transport policy on the selected OS; if blocked, use trusted HTTPS fixture/Hub endpoints or a deliberately local development ATS configuration before E2E. This repository supplies neither a TLS proxy nor an iOS ATS setup script. Production HTTPS associations/signing are separate gates.

In a dedicated terminal in **`supertokens-rownd-hub`**, use the existing test Hub server (serves `/mobile_app` and link routes):

```sh
npm run build
E2E_HUB_PORT=8787 node --import tsx ./test/e2e/harness/hub-server.ts
```

In another terminal in **`supertokens-rownd-android`**, with Docker running:

```sh
export ANDROID_HOST=127.0.0.1
export ANDROID_HARNESS_PORT=3137
export ANDROID_HUB_URL="http://$ANDROID_HOST:8787"
export ANDROID_PUBLIC_API_URL="http://$ANDROID_HOST:3137"
npm run test:integration:harness
```

Substitute the Mac LAN address for physical devices without `adb reverse`. Names remain `ANDROID_*` even for MAUI iOS. Startup prints host/android/public/Hub URLs. `GET http://127.0.0.1:3137/config` returns `appKey` (fixture `test_app_key`), `publicUrl`, `hubUrl` and `/auth` configuration. Check device reachability. API binds `0.0.0.0`; the test Hub listens on its configured port. Ctrl-C stops each server; harness shutdown stops its containers.

`ANDROID_PUBLIC_API_URL` controls API origin advertised in Hub app-config: changing only the sample entry is insufficient. `ANDROID_HUB_URL` takes precedence over `HUB_URL`, then default host/port. Standalone API defaults to **3137**, not the **3138** used by sibling instrumentation npm scripts.

Existing lifecycle alternative: from Android, `npx tsx test-server/with-harness.ts -- <command> [args...]` starts/stops the fixture around a child. `ANDROID_E2E_LOCAL_HUB=1` additionally builds/starts the same Hub server via `local-hub.ts`; `ANDROID_HUB_DIR`, `ANDROID_HUB_PORT`, `ANDROID_HOST` configure it. The child receives `HARNESS_URL`, `ANDROID_HARNESS_URL`, `ANDROID_API_URL`, `ANDROID_HUB_URL`, `ANDROID_APP_KEY`, **not** MAUI's `ROWND_*` variables. Standalone `npm run test:integration:harness` does **not** start Hub. Sibling `test:integration` / `test:e2e` run Android instrumentation, not MAUI. Hub `npm start` uses Wrangler/watch/proxy, not the test server above.

To run the MAUI environment check with automatic Hub, backend, Postgres and Core startup/cleanup, from the MAUI root:

```sh
(cd ../supertokens-rownd-android && \
  ANDROID_E2E_LOCAL_HUB=1 ANDROID_HOST=127.0.0.1 \
  ANDROID_PUBLIC_API_URL=http://127.0.0.1:3137 \
  npx tsx test-server/with-harness.ts -- sh -c \
  'ROWND_HARNESS_URL="$HARNESS_URL" ROWND_RUN_INTEGRATION=1 bash ../supertokens-rownd-dotnet-maui/scripts/test-integration.sh environment')
```

The backend initializes the locked `@supertokens-plugins/rownd-nodejs` **0.3.0-beta.2** with SuperTokens; its `/auth/plugin/rownd/app-config` route is overridden by the fixture for deterministic Hub config. The environment check instead calls the real plugin-owned `/auth/plugin/rownd/migrate` route without credentials and expects the plugin's missing-authorization error. This proves the plugin is handling requests, not that a native login completed.

## Opt-in integration checks

From the MAUI root with the fixture running:

```sh
export ROWND_HARNESS_URL=http://127.0.0.1:3137
ROWND_RUN_INTEGRATION=1 bash scripts/test-integration.sh environment
```

Asserts `/health` success, unauthenticated `/test/protected` **401**, and a real Rownd plugin migration-route response; no native login. For the second check, first request a fresh phone challenge in the **native Hub**, then:

```sh
ROWND_RUN_INTEGRATION=1 ROWND_TEST_PHONE='+12025550123' \
  bash scripts/test-integration.sh phone-capture
```

Checks an existing exact E.164 phone capture, including `preAuthSessionId`, `displayContext=mobile_app`, and code fragment. It does not create/consume a challenge. Fixture delivery is captured at `/captures/latest?email=...` or `/captures/latest?phoneNumber=...`: **real email/SMS delivery and providers are unnecessary**. Captures contain credentials; inspect locally rather than sharing raw output.

## Install the sample and create an Appium session

Use Debug for WebView inspection. The Android state-callback crash and the verified bridge change are described above. Android minimum API is 26. iOS sample minimum is 15, but this automation needs **iOS 16.4+** inspectable WKWebView support.

For Android, build as above, select the emulator/device via `ANDROID_SERIAL`, locate and install the actual signed APK:

```sh
find samples/Passwordless/bin/Debug/net10.0-android -name '*-Signed.apk'
export APK='/absolute/path/from-the-command-above.apk'
adb -s "$ANDROID_SERIAL" install -r "$APK"
```

`build-sample.sh android` embeds managed assemblies into the Debug APK so direct `adb install` can launch it without .NET Fast Deployment. Use `--no-incremental` with `adb install` if an incremental installation behaves unexpectedly.

For Apple Silicon simulator, **only after the iOS native build gate passes**:

```sh
dotnet build samples/Passwordless/Passwordless.csproj -c Debug \
  -p:RowndTargetFrameworks=net10.0-ios -p:RowndApplicationId="$ROWND_APPLICATION_ID" \
  -p:RuntimeIdentifier=iossimulator-arm64 -p:CodesignKey=- -p:CodesignProvision=
xcrun simctl list devices booted
xcrun simctl install booted samples/Passwordless/bin/Debug/net10.0-ios/iossimulator-arm64/Passwordless.app
```

Have one intended booted simulator or replace `booted` with its UDID. Use Xcode/device tooling and a correctly signed build for physical iPhone installation.

Install Appium/platform drivers in your chosen tooling environment; start the server explicitly in another terminal:

```sh
npm install -g appium
appium driver install uiautomator2
appium driver install xcuitest
appium driver list --installed
appium --address 127.0.0.1 --port 4723
```

Versions are not pinned here: choose compatible Appium/driver/Node/Xcode versions and record them. Android needs Chromedriver compatible with the device WebView. Physical iOS needs working WebDriverAgent signing. Inspect Hub before running the script: it picks the first `WEBVIEW*` context and does not provision drivers, scroll controls or recover missing contexts.

Create a W3C Android session (replace serial and Chromedriver path):

```sh
export ROWND_APPIUM_URL=http://127.0.0.1:4723
curl --fail-with-body -sS "$ROWND_APPIUM_URL/session" \
  -H 'Content-Type: application/json' -d "{
    \"capabilities\": {\"alwaysMatch\": {
      \"platformName\": \"Android\",
      \"appium:automationName\": \"UiAutomator2\",
      \"appium:udid\": \"$ANDROID_SERIAL\",
      \"appium:app\": \"$APK\",
      \"appium:noReset\": true,
      \"appium:newCommandTimeout\": 600,
      \"appium:chromedriverExecutable\": \"/absolute/path/to/compatible/chromedriver\"
    }, \"firstMatch\": [{}]}
  }"
```

Equivalent iOS Simulator body for `POST /session` after installation:

```json
{
  "capabilities": {
    "alwaysMatch": {
      "platformName": "iOS",
      "appium:automationName": "XCUITest",
      "appium:udid": "YOUR-BOOTED-SIMULATOR-UDID",
      "appium:bundleId": "io.supertokens.maui.buildcheck",
      "appium:noReset": true,
      "appium:newCommandTimeout": 600
    },
    "firstMatch": [{}]
  }
}
```

`platformName` is standard; Appium extensions require the `appium:` prefix. Set `ROWND_APPIUM_SESSION` to response **`value.sessionId`**, not device ID. Include any configured server base path in `ROWND_APPIUM_URL`. Capability paths are on the Appium server machine. Python uses standard-library HTTP and attaches to this existing session; it neither creates nor deletes it. Clean up with `DELETE $ROWND_APPIUM_URL/session/$ROWND_APPIUM_SESSION` when finished.

## E2E JSON, selectors and expected identity

Keep local JSON **outside the checkout**, e.g. `$HOME/.config/rownd-maui/e2e-android.json`, directory mode 700/file mode 600. No actual local config is supplied/tracked. Replace example identities/IDs:

```json
{
  "app-key": "test_app_key",
  "api-domain": "http://127.0.0.1:3137",
  "api-path": "/auth",
  "hub-url": "http://127.0.0.1:8787",
  "link-scheme": "rowndmauisample",
  "protected-url": "http://127.0.0.1:3137/test/protected",
  "harness-url": "http://127.0.0.1:3137",
  "application-id": "io.supertokens.maui.buildcheck",
  "email": "maui-otp-run-001@example.com",
  "phone": "+12025550123",
  "phone-selector": "#rph-sign-in-identifier-input",
  "expected-user-id": "REPLACE-WITH-BACKEND-VERIFIED-ID"
}
```

- First six fields populate sample entries by automation ID (Android resource ID, iOS accessibility ID). API/Hub/protected URLs are **device-visible**; `harness-url` is **runner-visible**. API origin excludes `/auth`; use `api-path`. `application-id` must match the installed package/bundle for deep links.
- `link-scheme` must match platform registration (`rowndmauisample` in sample) and Hub/native configuration. Callback is `rowndmauisample://account/login`.
- `email` is used by `smoke`; `phone`/`phone-selector` by `phone-magic-link`. Use separate configs when identities have different backend IDs.
- Pinned fixture enables a combined email/phone input. Its `phone-selector` can be `#rph-sign-in-identifier-input`: the driver's required preliminary click focuses it. If app config instead introduces phone navigation, use that UI's actual CSS selector; no universal phone-button test ID exists.
- Fixed Hub selectors: `#rph-sign-in-identifier-input`, `[data-testid="rownd-ui-login-continue-button"]`, `[data-testid="rownd-ui-passwordless-waiting-use-code"]`, `#rph-passwordless-code-input`, `[data-testid="rownd-ui-passwordless-code-submit"]`. Confirm them in the attached WebView. Native controls: `configure`, `auth-status`, `sign-in`, `protected-api`, `protected-result`, `sign-out`.

**Expected-ID chicken-and-egg:** the script reads JSON once and requires `expected-user-id`, but rejects any existing capture for its identity. A brand-new passwordless user has no known ID yet. Do not guess an ID, use `harness-user`, trust an unverified JWT claim, or copy the result of the run under test into its expectation.

With the existing interface:

1. Manually provision the intended email/phone through the real sample Hub on the running fixture. Complete login using its captured OTP/link; invoke **Call protected API**. Record that backend-verified `userId` in the corresponding JSON.
2. Sign out. On a **dedicated** fixture, `POST /reset` with `{"namespace":"default"}` clears captures/counters but retains Core users. The Appium script supplies no namespace headers; do not share its default namespace with concurrent tests.
3. Keep the harness/Core alive. Relaunch the sample process to restore unconfigured entries (Configure is once-per-process); ensure persisted native state is signed out. Recreate Appium session as needed. Confirm capture returns 404 before starting. Restarting the fixture creates new containers, so repeat provisioning instead of reusing old expected IDs.

After manual provisioning/sign-out, reset with:

```sh
curl --fail-with-body -sS -X POST http://127.0.0.1:3137/reset \
  -H 'Content-Type: application/json' -d '{"namespace":"default"}'
```

This makes the **challenge/capture fresh**, not the Core user. There is no automatic identity bootstrap in the driver; `/test/st-session` is not a general phone/passwordless seeder. The earlier `phone-capture` integration check also leaves an existing capture to reset before E2E.

## Warm email OTP and captured-phone-link E2E

From MAUI root, with a fresh unconfigured/signed-out sample and explicit existing session:

```sh
export ROWND_APPIUM_URL=http://127.0.0.1:4723
export ROWND_APPIUM_SESSION='SESSION-ID-FROM-APPIUM'
export ROWND_E2E_CONFIG="$HOME/.config/rownd-maui/e2e-android-email.json"
ROWND_RUN_E2E=1 bash scripts/test-passwordless.sh --platform android --scenario smoke
```

After sign-out, capture reset and process/session preparation, use phone identity config:

```sh
export ROWND_E2E_CONFIG="$HOME/.config/rownd-maui/e2e-android-phone.json"
ROWND_RUN_E2E=1 bash scripts/test-passwordless.sh --platform android --scenario phone-magic-link
```

After iOS build/inspection gates, use the iOS session and device-visible origins, preparing independently between these runs:

```sh
export ROWND_E2E_CONFIG="$HOME/.config/rownd-maui/e2e-ios-email.json"
ROWND_RUN_E2E=1 bash scripts/test-passwordless.sh --platform ios --scenario smoke
```

```sh
export ROWND_E2E_CONFIG="$HOME/.config/rownd-maui/e2e-ios-phone.json"
ROWND_RUN_E2E=1 bash scripts/test-passwordless.sh --platform ios --scenario phone-magic-link
```

Both configure, require signed-out state, open native Hub, create a challenge, read a capture, authenticate, assert protected API's exact expected `userId`, sign out, assert `No session`, then reopen Hub. The script finishes with Hub open: do not simply rerun in the configured process.

`smoke` enters email OTP. Phone mode validates mobile parameters, preserves encoded query/fragment, replaces the link prefix with the registered scheme, backgrounds the warm app and invokes Appium `mobile: deepLink` with `package` (Android) or `bundleId` (iOS). Driver support for that command is required. It does not tap real SMS, verify HTTPS associations or test browser fallback. **No real SMS is necessary.**

## Manual checks and unavailable coverage

Record device/OS, tool versions, source pins/Core digest, package source, scenario and observed backend identity (redact personal data). Keep OTPs/tokens/link URLs/raw Appium or capture logs out of commits and shared reports.

Manual acceptance still required:

- Configure completes once; signed-out state enables real Hub. Dismiss/cancel/reopen it; verify UI-thread state updates and error handling.
- Email OTP/warm phone callback produce backend-verified identity. Tokenless protected requests fail; sign-out yields `No session`; reopened Hub is signed out.
- Resume/background, persistence/relaunch with startup configuration, token expiry/native refresh, concurrent token requests and network recovery. A Release build is not runtime evidence.
- Android intent delivery occurs once: native ComponentActivity integration already owns forwarding. iOS must configure `RowndLinks` before URL/user-activity callbacks; verify both on a real build.
- Wrong/expired/replayed links and fixture consume counters. Exact successful callbacks are coalesced for two seconds; repeat after that for server replay checks. Router acceptance is not authentication; smoke does not assert consume counts.
- Install/launch package-consumer builds on both platforms and validate linkage/resources, not just source-project builds.

**Unavailable automation:** `delayed-startup` and `refresh-recovery` are recognized names but deliberately exit 2 as **BLOCKED**. Full phone replay/consume-count checks, cold launch/process death, verified HTTPS handoff, browser fallback and refresh/recovery have no concrete MAUI drivers. C# orchestration declarations are not device coverage. Editable sample configuration does not survive process death; production cold URL/scene startup and customer associations/signing remain pending. Email-verification links are outside this release and unhandled by the iOS login router. iOS fatal initialization errors, package-consumer linkage and runtime behavior remain gates even if a warm smoke eventually passes.
