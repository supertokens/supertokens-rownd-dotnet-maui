# .NET MAUI SDK: focused passwordless implementation plan

Date: 2026-09-25. Status: M1 foundation implemented; native bindings and runtime acceptance pending. See [M1 evidence and gates](docs/m1-status.md).

**Approved M1 scope update (2026-09-25):** customer upgrades Rownd.Maui and targets stable .NET 10. Implement project/tooling and shared-fixture foundation plus unit/mock tests and integration/E2E scaffolding. Do not run integration/E2E/device tests in this phase; user runs on Mac. No Mac CI. Use captured Hub-created phone links, not real SMS delivery checks. Custom-subdomain association files await actual identifiers/signing. Public publishing and package reservation are postponed. Original later-stage acceptance below is retained as planning history; real SMS checks and publishing require a future explicit scope decision. M1's live-environment/device gates remain open, not passed by foundation tests.

## 1. Deliverable

Give a customer an installable NuGet package that authenticates users through the existing SuperTokens-backed Rownd native SDKs on Android and iOS.

The customer can configure the SDK, open passwordless sign-in, receive authenticated state, retrieve a usable access token, remain signed in across app launches, and sign out. The native SDKs own the Hub UI, token persistence, expiry handling and refresh.

**Build a thin C# binding. Keep the existing native authentication implementation.** No underlying SuperTokens SDK changes are planned. If the proof of concept exposes a missing API strictly necessary for this flow, add a small Rownd facade/public hook; do not turn it into a general native SDK redesign.

This replaces the earlier full-parity plan. Its HTTP transport, profile, migration and core-SDK requirements do not apply to this release.

## 2. Release scope

### Customer flow

1. Install the proposed `SuperTokens.Rownd.Maui` NuGet package.
2. Configure app key, SuperTokens API domain/base path, Hub URL and app link scheme.
3. Call `RequestSignIn()` to open the native Hub.
4. Complete email OTP, email magic-link or phone/SMS magic-link authentication.
5. Observe native-backed authenticated state and call `GetAccessTokenAsync()`.
6. Use that token in a customer-owned HTTP request to a protected API.
7. Relaunch the app and retrieve a refreshed token when necessary.
8. Call `SignOut()`; the native SDK clears the session using its existing semantics.

Email OTP, email magic links and a full phone/SMS magic-link flow are required acceptance targets on both platforms. The phone flow includes leaving the app, opening the delivered link, returning through OS link dispatch, and verifying the resulting native-backed session at the backend. SMS OTP is an additional fallback smoke when enabled. Use existing Hub/backend delivery; no separate C# authentication protocol is needed.

### Platform and backend assumptions

- Android and iOS only, one customer-compatible supported .NET/MAUI toolchain. Default candidate: .NET 10; confirm the customer's target and matching Xcode/workload in M1.
- Reuse an existing working Rownd-plugin/SuperTokens backend and the existing SuperTokens-backed Hub. Backend URL, app config and passwordless delivery are available before device validation.
- Configure the customer's app/Hub for passwordless-only sign-in and disable unrelated optional onboarding/automations for the acceptance fixture. No Apple/Google credentials are needed for this scope.
- In M1, enable email and phone passwordless in the shared test fixture (`EMAIL_OR_PHONE`, `USER_INPUT_CODE_AND_MAGIC_LINK`) and record the customer's production mode and same-device policy. Configure custom schemes and HTTPS app/universal links consistently with that backend/Hub flow.
- Keep the native dependency graph required to build and run the SDK. Removing unused native social libraries is not part of this work.

### Explicit release boundaries

No native-backed HttpClient transport, automatic HTTP interception/replay, profile editing/account-management API, social sign-in, guest conversion, separate email-verification workflow, desktop support, or comprehensive legacy C# API compatibility.

No silent migration of old MAUI credentials. Existing installations must sign in once with the new library. The new code does not read or import old `rownd_state` credentials or run the old C# auth stack. Native persistence handles subsequent launches. Document this requirement clearly if the first customer is upgrading from `Rownd.Maui`.

Account metadata fetched internally by the native SDK is unchanged; we do not expose a new C# profile subsystem. This is an authentication-focused replacement package, not a drop-in replacement for every legacy MAUI API.

## 3. Architecture and smallest useful API

The customer app calls a C# facade, which delegates through thin Android/iOS bindings to the existing native Rownd SDK. Native Rownd delegates to its existing SuperTokens integration and presents the existing Hub.

### C# surface

Proposed methods/types, finalized during the proof of concept:

- `ConfigureAsync(config)`: configure the single native instance and provide an explicit readiness/error outcome. Validate inputs before native configuration.
- `RequestSignIn()`: present the existing native Hub. Authentication completion comes through state/events rather than implying presentation itself authenticates the user.
- `GetAccessTokenAsync()`: call the native token getter, which owns expiry/refresh behavior. Preserve the distinction between no session and transient token retrieval failure.
- `SignOut()`: delegate to native sign-out. Observe local completion through native-backed state; do not promise remote revocation has completed synchronously.
- `State` and `StateChanged`: minimal ready/authenticated state and user identifier when available. Deliver updates on the MAUI UI thread; dispose native subscriptions correctly.

Internal lifecycle adapters forward URLs/intents to existing native handlers. They are plumbing, not another auth API.

Use simple facade signatures: strings, booleans, small DTOs and completion callbacks. Keep Kotlin coroutines/Flow and Swift async/publishers behind the native facade. Validate application configuration in C# and the facade; if a native fatal initialization path blocks basic customer error handling, resolve that narrowly in the Rownd layer during M2/M3.

### Android

- A small Kotlin/Java-friendly facade wraps native configure, sign-in, token retrieval, sign-out and state subscription.
- Use public `Rownd.handleIntent`/existing activity lifecycle hooks; no reflection into private APIs. Ensure links are delivered once if native activity registration already handles them.
- Bind the facade and package required AAR/JAR dependencies without duplicating MAUI-provided AndroidX classes.
- Present the native Hub using the MAUI host activity. The existing C# WebView/bottom sheet must not initialize.

### iOS

- A small explicitly Objective-C-compatible Swift facade wraps the same operations with Foundation-compatible values/callbacks.
- Package the facade and required native dependencies/resources as the selected XCFramework/binding arrangement.
- Forward URL/universal-link callbacks to `Rownd.handleSmartLink` through the MAUI app lifecycle.
- Use the existing native presenter over the MAUI host controller; retain/dispose callbacks and state subscriptions correctly.

### Deep-link feasibility and integration

**Yes: MAUI supports the required OS callbacks, and both native SDKs already accept passwordless deep links.** This is source-supported feasibility; successful MAUI bindings and physical-device routing remain milestone gates.

- **Custom scheme:** `<customer-scheme>://account/login?...#...`. Register the scheme in the Android manifest and iOS `CFBundleURLTypes`; match native configuration and the scheme generated by the Hub's browser fallback.
- **HTTPS:** `https://<configured-hub-domain>/account/login?...#...`. Use verified Android App Links and iOS Universal Links. Android needs a separate HTTPS intent filter with `android:autoVerify="true"` and domain-hosted `/.well-known/assetlinks.json` for the package/signing certificate. iOS needs the associated-domains entitlement/capability, matching provisioning, and `/.well-known/apple-app-site-association` for the application identifier and login path. Check the actual release signing identities.
- **Android delivery:** use MAUI `OnCreate` and `OnNewIntent` as needed, through the facade to public `Rownd.handleIntent`. Native Rownd already registers resume/new-intent listeners for supported hosts, so establish one forwarding owner. Keep an early launch intent until native initialization/host readiness; do not invoke an uninitialized handler or dispatch the same intent twice.
- **iOS delivery:** forward `OpenUrl`, cold-launch URL/user activity and `ContinueUserActivity` to `Rownd.handleSmartLink`; handle scene connection/open-URL/user-activity callbacks if the selected MAUI app uses scenes. Native iOS queues recognized links before configuration completes; validate that the customer scheme/config is available when recognition runs, and retain the URL in the adapter until it is if necessary.
- **URL fidelity:** preserve the original encoded query and fragment, including `preAuthSessionId`, the link code and `displayContext=mobile_app`. Pass the complete URI to native parsing. Route unrelated customer links back to their application handler when native reports unhandled.
- **Browser fallback:** if the HTTPS link opens in Safari/Chrome, the existing Hub must show its mobile “Open in app” action without consuming the code there. The action hands the intact callback to the app's configured custom scheme. Exercise the actual generated action rather than synthesizing the fallback only in test code.

Native handlers currently allow `/account/login` and `/account/verify-email`; this release uses the login route. General customer screen navigation remains with the host app. Scheme registration, HTTPS association and login-route acceptance are distinct checks: a direct native handler call or forced-target intent does not demonstrate automatic OS routing.

### HTTP usage

The customer uses their own HttpClient. Example usage, after successful initialization/sign-in:

```csharp
var token = await rownd.GetAccessTokenAsync();
if (string.IsNullOrEmpty(token))
{
    throw new InvalidOperationException("Sign in before calling this API.");
}

using var request = new HttpRequestMessage(HttpMethod.Get, protectedApiUrl);
request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
using var response = await httpClient.SendAsync(request);
```

Attach the token to requests for the customer's trusted backend. Retrieve a current token before each protected operation; do not cache it indefinitely in C#. No automatic response-header processing, 401 refresh/retry or global interception is advertised. The host application handles API errors. Native token retrieval/refresh is tested using a real protected endpoint.

## 4. Fork and project changes

Create `supertokens/supertokens-rownd-dotnet-maui` from `rownd/dotnet-maui`, retaining history and license. Set fork `origin` and read-only Rownd `upstream`; disable inherited publishing until it targets the new package. Proposed NuGet identity: `SuperTokens.Rownd.Maui`, subject to availability. Customers replace the old NuGet rather than installing both.

Minimal layout:

- `Rownd/`: focused C# config/facade/state types and platform lifecycle adapters.
- `native/android/`: small Gradle facade around the pinned native Rownd artifact.
- `native/ios/`: small Xcode facade around pinned native Rownd dependencies.
- `bindings/`: Android and iOS binding projects, including resource/dependency packaging.
- `samples/Passwordless/`: one MAUI customer-style app showing sign-in, token-backed API call and sign-out.
- `tests/`: focused facade tests and device smoke scenarios.
- `scripts/`: native build, NuGet pack and package-consumer smoke commands.

Change `RowndInstance`/initialization to use the native facade. Exclude legacy C# auth repositories, token persistence, automations and Hub presentation from the new execution path. Retain historical source in git rather than spending this project on broad cleanup or Redux compatibility adapters. Do not start old initialization alongside new native configuration.

Keep the package build simple: one public install, conditional platform binding dependencies as needed, and prebuilt native artifacts. Consumers need normal MAUI platform tooling, not our native source repositories or manually copied libraries. Reuse the existing native binary distribution mechanisms where practical; settle the exact packaging in M2.

## 5. Delivery milestones

Each milestone produces usable code and validation evidence. Estimates include that milestone's implementation and focused checks. The proof of concept becomes the shipped implementation; packaging starts early. M4 now includes required phone magic-link automation and verified OS handoff, adding **2–3 engineer-days** to the previous plan.

### M1 — Reproducible project and auth environment: 0.5–1 day

Dependencies: none.

**Implement**

1. Fork the repo with history/license intact; set remotes and prevent inherited workflows from publishing under the old identity.
2. Pin one .NET/MAUI toolchain and exact native Rownd releases. Record Android/JDK and Xcode requirements. Confirm the customer's target before changing frameworks.
3. Select one existing native harness/Hub/backend version set for both platforms. Enable email OTP plus email/phone magic links; use the Android/Hub harness's existing phone capture or extend the chosen harness equivalently. The current iOS harness discards SMS delivery. Identify a controlled test number and existing SMS delivery credentials for physical-phone validation.
4. Set app IDs, scheme, HTTPS link domain and same-device policy. Obtain Android/iOS physical-device and signing access; request association files now. Confirm the Hub generates the same custom scheme the app will register.
5. Establish a tiny sample with sign-in, protected-API and sign-out actions plus an auth-state label. Reserve the package identity and document configuration variables without secrets.

**Test / validate**

- Restore/build the starting sample for both selected targets; record any baseline/toolchain problem.
- Confirm the selected backend/Hub can complete the chosen passwordless flow independently of MAUI, preferably using the existing native sample.
- Start phone sign-in in the real Hub; verify the harness captures a phone-specific link with `displayContext=mobile_app`, `preAuthSessionId` and a link-code fragment. Record any delivery/path-rewrite requirement before wiring MAUI.
- Verify a protected endpoint rejects an unauthenticated request and returns a verified user ID for an authenticated request. Reuse the harness's endpoint rather than building a new business API.
- Check mobile network reachability: Android emulator loopback mapping, iOS simulator reachability and a device-accessible host. HTTPS links must target the intended domain.

**Exit gate / evidence:** fork + pinned config/build instructions; reachable working auth environment; app identities and signing/link setup identified. A broken backend must not be mistaken for a binding failure.

### M2 — Real passwordless login from C# on both platforms: 2–4 days

Dependencies: M1.

**Implement**

1. Add `native/android/` with a narrow Kotlin/Java-friendly facade for configure, native Hub sign-in, token getter, sign-out and auth-state subscription. Adapt coroutine/Flow results to callbacks.
2. Add `native/ios/` with explicitly Objective-C-compatible Swift entry points, Foundation values and completion callbacks. Hide Swift async/state publishers inside the facade.
3. Add .NET binding projects. Package native runtime dependencies/resources sufficiently to launch the real SDK; settle how those artifacts will be supplied by NuGet.
4. Wire a minimal `RowndInstance` through these bindings and present the native Hub over the MAUI host activity/controller. Disable the old C# auth and Hub initialization path from the first integration run.
5. Complete OTP authentication and have the sample call `GetAccessTokenAsync()` followed by a customer-style bearer request through ordinary HttpClient.
6. Pack a provisional NuGet and consume it from the sample as a package. Keep native sources and build scripts reproducible rather than relying on locally copied binaries.
7. Expose the native link handler through each facade and prove one captured callback reaches the native Hub from the MAUI host. Finish OS registration and phone-flow automation in M4.

**Test / validate**

- On both Android emulator and iOS simulator: launch signed out → open real Hub → enter a test email/OTP → observe C# auth state → request a token → call the protected endpoint.
- Assert the backend-verified ID belongs to the expected test user. Merely receiving a string or showing a signed-in label does not pass.
- Sign out and confirm another sign-in can start. Close/cancel the sheet and check the MAUI app remains interactive.
- Verify the provisional package resolves in a separate consumer directory and the selected iOS device/Android release build targets link.
- If a call fails, compare against the native sample using the same config: identify a binding/config/presentation issue before requesting native changes.

**Exit gate / evidence:** actual passwordless auth through C# on both platforms, initial package, recorded backend verification and build results. M1+M2 totals **2.5–5 engineer-days**. If presentation or native dependencies remain blocked, report the precise blocker and re-estimate before continuing. Add only a narrowly necessary Rownd facade hook; no general core SDK work.

### M3 — Customer-ready API and installable package: 4–7 days

Dependencies: M2. Inside this milestone, native packaging and C# facade work can proceed in parallel after the small bridge contract is fixed.

**Implement**

1. Finalize `ConfigureAsync`, `RequestSignIn`, `GetAccessTokenAsync`, `SignOut`, `State` and `StateChanged` in `Rownd/`. Validate config, return a clear readiness result, and distinguish no session from a transient native error.
2. Implement Task/callback mapping, main-thread state delivery and deterministic subscribe/unsubscribe. Keep state derived from native state; do not persist C# credentials or start a second session manager.
3. Complete Android dependency deduplication, callback/JNI preservation and resources. Complete iOS device/simulator framework slices, Objective-C binding declarations, resource bundles and callback retention.
4. Produce one documented public NuGet installation with platform dependencies as needed. Consumers must not need our native repo checkouts or manual binary copying.
5. Update `samples/Passwordless/` to use only the documented public package/API. Its API-call button retrieves the current native token each time and attaches it to a request-scoped Authorization header.

**Test / validate**

- Small C# tests using a fake native bridge: required config/defaults, callback-to-Task error/result mapping, no-session versus transient-error handling, state notification and disposal. Test a narrow injectable boundary; do not mock the actual mobile auth acceptance tests.
- In the device sample: repeat configuration/subscription as supported and verify there are no duplicate handlers or sheets; callbacks after disposal do not update abandoned UI.
- Restore a fresh consumer using the produced `.nupkg` and declared feeds/dependencies, with no project references to the SDK/native sources. Build and run Android Release and a signed iPhone Release using normal linker/AOT settings.
- On those package-only device builds run OTP → protected API → sign-out, checking native resources and callbacks survive release linking.

**Exit gate / evidence:** a usable prerelease artifact, stable minimal API, passing facade tests and real release-device results. Effort comprises bindings/package completion **3–5 days** plus C# facade/sample **1–2 days**; no double-counting of M2 work.

### M4 — Phone magic links, deep links and app lifecycle: 3–5 days

Dependencies: M3; host/link registration can be prepared earlier. Basic sheet presentation already works in M2.

**Implement**

1. Complete Android startup/new-intent and iOS launch/URL/user-activity forwarding described in section 3. Verify single delivery and readiness handling against the pinned native versions.
2. Finish scheme, HTTPS intent filters, entitlements and AASA/assetlinks setup for the sample/customer domains. Verify the backend-generated login URL and the Hub-generated fallback; preserve query/fragment through every handoff.
3. Add the phone capture reader to the MAUI smoke runner. Reuse the existing Android/Hub `/captures/latest?phoneNumber=...` facility with URL-encoded E.164 numbers, or extend the chosen shared harness's SMS sink. Keep one backend/version set for both platforms.
4. Adapt the existing native real-Hub E2E pattern to drive the MAUI sample: phone entry → captured SMS link → external OS dispatch → native Hub completion → C# token → protected API. Keep selectors/counters test-only and invoke the sample's public C# API for session operations.
5. Ensure host references and native state subscriptions survive background/resume or reattach appropriately. Keep only one native Hub presenter. Expose non-secret sample status and a post-login action so automation verifies both session readiness and host interactivity.

**Test / validate**

- Run the full phone magic-link scenario in section 6 on Android and iOS. Automate controlled SMS capture and custom-scheme cold/warm entry; also exercise link arrival during initialization.
- Verify HTTPS automatic handoff using real domain association and an untargeted OS open/external tap. Cover warm and terminated apps on physical Android and iPhone, with a fresh challenge/link per independent case.
- Exercise Safari/Chrome fallback on the phone: open the actual captured HTTPS URL in the browser, tap the actual “Open in app” action, and authenticate in the app. Confirm the browser did not consume the native-context link first.
- Repeat the email magic-link path as a regression. Replay a phone link and try an expired link; successful consume/completion stays single, the existing session is not replaced, and the host remains interactive. Native replay handling may briefly open/dismiss Hub; do not require zero presentation if that is the native contract.
- Cancel/dismiss Hub, background/resume, recreate the Android activity and reopen sign-in; check host touches and callbacks still work.
- Authenticate, kill the process without uninstalling, relaunch and make a protected call using a newly retrieved token. Old MAUI Preferences must not supply the session.
- When SMS OTP fallback is enabled, complete one “Use a code instead” attempt as well.

**Exit gate / evidence:** full phone magic-link E2E passes on both platforms; custom-scheme, verified HTTPS and browser-fallback results are recorded individually. Email regression and lifecycle checks pass. Indicative effort: harness/phone fixture **0.5–1 day**, lifecycle/domain wiring **1–2 days**, phone/link automation and device checks **1.5–2 days**. Association-file access delays add calendar time.

### M5 — Session validation and customer handoff: 2–3 days

Dependencies: M3/M4. Build/test scripts and a simple CI scaffold should begin during M2, rather than being postponed entirely to this milestone.

**Implement**

1. Reuse the selected existing native harness to provide test users, controlled email/SMS OTP/link delivery, successful-consume counters, a protected endpoint, short access-token expiry and a refresh-failure switch.
2. Add a small repeatable device smoke through the public C# API. Extend the sample's test mode or reuse existing mobile UI automation; do not build a general new E2E framework.
3. Add a CI job for facade tests, native/binding builds and package creation. Run mobile smoke on an available suitable runner or as a recorded local release check; make this distinction explicit.
4. Write a short README covering installation/config, sign-in, auth state, current-token retrieval, ordinary HttpClient usage, sign-out, link registration and one-time reauthentication for old MAUI installations.
5. Pack the release candidate, repeat the clean-consumer smoke on that exact artifact, then publish a prerelease for the customer.

**Test / validate**

- **Refresh:** run the explicit post-login refresh step in section 6 after OTP and phone magic-link authentication on both platforms. Confirm the old token is rejected after expiry, native refresh is observed, and `GetAccessTokenAsync()` supplies a token accepted for the same user/session without another sign-in. Use the native regression references below; do not fake refresh by editing JWTs or calling a separate C# token endpoint.
- **Outage/recovery:** expire the token, make native refresh temporarily return a network/server failure, and call the getter. Expect a recoverable error without a false signed-out event. Restore the backend and verify the next getter/API call succeeds without another login.
- **Relaunch:** perform a real process kill/restart, including with an expired token; verify restored native session and backend access.
- **Sign-out:** observe local signed-out state, no current token, and no restored old session after reopening Hub/relaunch. A new login succeeds. Do not claim synchronous revocation of previously issued access tokens beyond the native/backend contract.
- Rerun the focused acceptance checklist on the exact package. Verify reports identify platform, versions and scenario outcome without containing tokens, OTPs or magic-link secrets.
- On the exact package's physical Android/iPhone consumer builds, request an SMS to a controlled real number through the existing provider and tap it in Messages. Verify return to the app and a protected request; this checks delivery/linkification and installed-app routing beyond harness capture.
- Have the customer follow the README in their app; record passwordless success and a protected request, including phone magic-link handoff with their identities/domain when that is their configured mode.

**Exit gate / evidence:** exact NuGet, sample, reproducible commands, platform test results, documented manual checks and customer integration result. An unrun device check is pending, not passing.

### Schedule and estimate

- M1 **0.5–1**, M2 **2–4**, M3 **4–7**, M4 **3–5**, M5 **2–3** engineer-days: **11.5–20 total**.
- Allow **2–3 additional days** for dependency/toolchain integration; rounded planning budget **14–23 engineer-days**.
- One engineer familiar with our SDKs: approximately **3–5 working weeks**, assuming signing/backend/domain/SMS access is ready. Android and iOS work in parallel with two engineers: approximately **2–4 elapsed weeks**, subject to shared integration/release gates.
- First verified login on both platforms: end of M2, **2.5–5 engineer-days** into the project. Confirm the remaining estimate at that point.
- Dependency order: M1 → M2 → M3 → M4 → M5. Build scripts, CI scaffolding, domains and signing are prepared early; only final artifact/session validation waits until M5.

These are conditional estimates, not build-validated commitments. Packaging can still be difficult with a small public API. Signing/domain/toolchain access and customer feedback can add calendar time. The earlier full-parity estimate is superseded.

## 6. Focused acceptance checklist

Use the real native SDKs, real Hub and a compatible pinned SuperTokens/Rownd backend. Controlled email/SMS delivery from the existing harness is fine; a fabricated C# token or mocked native login is not evidence that auth works.

1. **Configure:** valid settings initialize; missing/invalid domain or app key produce an actionable error; one native instance and one auth UI path run.
2. **Email OTP:** new and returning users authenticate; invalid/expired codes show a usable error; cancellation permits another attempt.
3. **Token works:** retrieve a token through C# and send it to the protected backend; the backend verifies the expected user. A nonempty JWT alone is not a pass.
4. **Email magic links:** complete through native link handling and verify backend identity; retain the existing email regression alongside the required phone flow below.
5. **Expiry/refresh:** after real passwordless login, prove the saved token expires at the backend, observe native refresh, and verify `GetAccessTokenAsync()` returns a usable token for the same user/session without another login. C# performs no refresh request itself. Follow the explicit post-login step and native test references below.
6. **Temporary outage:** expire the access token while refresh is unavailable; native getter failure is surfaced rather than translated to logout. Restore connectivity; get a valid token without another sign-in.
7. **Restart:** authenticate, kill the app process without uninstalling, relaunch, and access the protected backend. The native store supplies the session; old MAUI Preferences are not consulted.
8. **Sign-out:** native-backed state becomes signed out; token getter reports no session; reopen sign-in and relaunch without reviving the previous session. Confirm repeat sign-in succeeds.
9. **Lifecycle/state:** present/dismiss repeatedly, background/resume, recreate the Android activity and dispose/recreate the C# subscription; no duplicate state handlers, stuck sheet or blocked host input.
10. **Distribution:** install the actual NuGet into a separate app, build Android release and signed iOS release, and run OTP and phone magic-link → protected API → sign-out on real devices. Consumer setup uses only documented config and package dependencies.
11. **Full phone magic link:** enter a phone number in the real Hub, capture the SMS callback, leave the app, open the link through the OS and establish a native session visible through C#. Verify expected phone-user identity, single successful completion, dismissed Hub and responsive host. Repeat with a cold app, warm app and link received during startup; replay/expiry do not create or replace a session.
12. **Deep-link routing:** verify custom scheme, associated HTTPS link and browser “Open in app” fallback on both platforms. Keep query/fragment intact; unrelated links remain available to the host app. Observe a real SMS tap on each physical platform using the release artifact.

Minimum automated coverage: small C# facade unit tests, builds/packaging in CI, OTP/session smoke, and full phone magic-link capture → OS custom-scheme open → C# token → protected API on both mobile runtimes, including warm/cold entry and replay. Record physical HTTPS routing, browser fallback and actual Messages delivery/tap as manual release checks when automation is impractical. These checks are required even when manual.

Use one existing harness implementation/version set for both platforms. Run relevant existing native refresh/Hub tests when needed, rather than rewriting native regression suites in C#. Document which checks ran automatically and which ran manually; no unrun checks count as passing.

### Existing E2E patterns and gaps

The following are **source observations, not newly executed test results**. Paths are relative to `repositories/`:

- **Android:** [`RealHubE2ETest.kt`](../repositories/supertokens-rownd-android/app/src/androidTest/java/io/rownd/rowndtestsandbox/RealHubE2ETest.kt), `magicLinkActionViewCompletesOnceAndReplayDoesNotReplaceSession`, starts real email sign-in, captures the link, preserves encoded query/fragment in a custom scheme, dispatches `ACTION_VIEW`, and checks one successful consume/completion, Hub dismissal, protected access and session stability on replay. Its `setPackage(...)` dispatch targets the app, so it does not prove verified HTTPS routing. Reuse its UI/assertion pattern with phone input and the MAUI public API.
- **iOS:** [`RowndRealHubAuthenticationUITests.swift`](../repositories/supertokens-rownd-ios/example/rownd_ios_exampleUITests/RowndRealHubAuthenticationUITests.swift), `testMagicLinkCompletesThroughCustomSchemeAndReplayDoesNotReplaceSession`, uses `app.open(deepLink)` after real email challenge creation, checks app foregrounding, auth state, one completion, WebView disappearance, protected access and stable session on replay. Reuse its native XCUITest approach against the MAUI sample; its custom-scheme check is not an AASA/Universal Link test.
- **Hub:** [`mobile_hub.spec.ts`](../repositories/supertokens-rownd-hub/test/e2e/mobile_hub.spec.ts) has `startPhoneSignIn`/`completePhoneSignIn`: capture by E.164 phone, then open the real link with mobile context. It tests phone OTP, native-channel messaging, browser “Open in app” fallback and same-device restrictions. Native channels are mocked in Playwright, so this covers the web/protocol side rather than an installed phone app/session.
- **Harness:** Android [`test-server/server.ts`](../repositories/supertokens-rownd-android/test-server/server.ts) already captures `phoneNumber`, `urlWithLinkCode` and `userInputCode` in `smsDelivery`, exposed by `/captures/latest`. iOS [`test-server/server.ts`](../repositories/supertokens-rownd-ios/test-server/server.ts) captures email only and its SMS sender is a no-op. Reuse the phone-capable harness for both platforms or extend the selected shared harness narrowly; do not assume iOS SMS capture exists.
- **Other wrappers:** inspected React Native Android harness tests exercise config/startup and targeted intent resolution, while the Flutter consumer smoke documents captured email links. They are useful setup references; the inspected coverage does not establish a full phone magic-link-to-native-session E2E.

### Full phone magic-link E2E

Run the same customer journey on Android and iOS:

1. Start with isolated signed-out app/harness state and a unique controlled E.164 number. Configure phone sign-in and the chosen same-device policy. Use the actual Hub phone selector/input through `RequestSignIn`; the test must start the challenge from UI, not mint a session through a test endpoint.
2. Submit the number and wait for the waiting-for-link UI/native challenge. Poll the harness SMS sink for that exact number/attempt. URL-encode the number (`+` must not become a space), and assert the callback retains the pre-auth session, link-code fragment and mobile context. Reset captures or correlate attempts so stale links cannot pass.
3. Background the app as a user would when switching to Messages. Open the actual captured HTTPS link for the verified-link case. For the isolated custom-scheme binding case, preserve encoded query/fragment when converting only the origin/path, as the native tests do. Invoke OS link dispatch from outside the app rather than calling the Rownd handler directly.
4. For browser fallback, load the captured URL in Safari/Chrome, verify the mobile blocked/open-app UI and no successful consume, then tap its actual “Open in app” action. Do not inject a native channel into the browser or bypass the configured same-device check. If the configured policy blocks this path, report it as a compatibility issue rather than changing policy to make the test pass.
5. Wait for the app to foreground and native authentication to settle. Assert one successful backend consume and one logical sign-in completion, resolved challenge, dismissed native Hub and a tappable MAUI action. Multiple `StateChanged` notifications can represent readiness/refresh; do not assert that the entire event stream has only one emission. Completion counters are test observability, not a new public API requirement.
6. Tap the sample's protected-request action, which calls `GetAccessTokenAsync()` and sends a bearer request through ordinary HttpClient. Assert the backend-verified user maps to the test phone identity. Do not use a browser cookie session, a native interceptor or just a decoded/nonempty JWT as the assertion.
7. Replay the same link. Assert no second successful consume/sign-in and the established session/identity remains stable; the app remains usable. Use backend session identity or non-secret test fingerprints rather than expecting an access token never to rotate. Also verify an expired link does not authenticate and a fresh attempt succeeds.
8. Repeat the initial handoff with the app process terminated after challenge creation, preserving app data, and with delayed initialization. The OS must launch the app from the link. For process death, compare backend observations across launches rather than an in-memory event count that resets.
9. **Confirm native access-token refresh:** configure a short real server-side access-token lifetime before login (longer than iOS's 60-second proactive refresh margin). Keep the initial token only in test memory and record the refresh/consume counters and session identity. Wait for actual expiry and verify the saved token receives 401 from the protected endpoint using a plain request without automatic refresh. Call `GetAccessTokenAsync()`, then send its result through the sample's ordinary HttpClient: expect 200 for the same user/session, an increased native `stRefresh` counter, no additional passwordless consume/sign-in and no reopened Hub. Exercise the M5 outage/recovery variant on the same login path: refresh failure faults the C# Task without signing out; restoring the backend lets the next getter/request recover. Run this shared check after OTP and phone magic-link login on both platforms; it need not be repeated for every link-routing variant.
10. Kill/relaunch and verify a protected request, including with an expired token, then sign out and repeat sign-in.

Physical-phone release check: with the same packaged app and production-shaped HTTPS associations, send through the existing SMS provider to a controlled number, open Messages and tap the delivered link on Android and iPhone. Record delivery, automatic handoff/fallback, app state and verified backend result separately. Harness capture validates authentication deterministically; this final tap validates SMS formatting, browser/OS behavior and domain/signing setup.

For HTTPS evidence, use untargeted Android `ACTION_VIEW` (no forced package/component) and inspect domain verification status; on iPhone tap from Messages/Notes or an external page on another domain. Entering a URL in Safari's address bar or directly invoking a native handler is not a Universal Link routing test. Test the selected release provisioning/association path, not only a debug development-domain override.

### Native refresh tests to reuse as references

- **Android — [`SessionRefreshFailureInstrumentedTest.kt`](../repositories/supertokens-rownd-android/android/src/androidTest/java/io/rownd/android/SessionRefreshFailureInstrumentedTest.kt):** `successfulRefreshSynchronizesAuthAndPreservesProfile` verifies real expiry, token rotation, unchanged session identity, protected-request success and `stRefresh`; `refresh503ThrowsRetryableErrorsAndPreservesCredentialsForRecovery` verifies retryable failures and recovery with preserved credentials. The same suite covers revoked sessions, concurrent token reads and a refresh response arriving after sign-out.
- **iOS device UI — [`RowndRealHubAuthenticationUITests.swift`](../repositories/supertokens-rownd-ios/example/rownd_ios_exampleUITests/RowndRealHubAuthenticationUITests.swift):** `testExpiredSessionRefreshesAfterColdRelaunch` and `testRefreshOutageDuringColdRelaunchPreservesLoginAndRecovers` use a real Core-issued 90-second session, process termination, refresh availability controls, stable session identity, refresh counters and a protected request. Their session is created by a test fixture; adapt the checks to the session established by the MAUI passwordless flow.
- **iOS unit — [`AuthTests.swift`](../repositories/supertokens-rownd-ios/Tests/RowndTests/AuthTests.swift):** `testGetValidTokenRefreshesExpiredSuperTokensAccessToken` and `testConcurrentRefreshTokenCallsShareRefreshTask` cover native delegation and shared refresh work through an injected bridge. Use them as focused behavior references, alongside the real-backend MAUI checks.

These references were inspected, not rerun for this plan. Validate refresh through the C# getter and plain bearer requests so a native HTTP interceptor cannot hide a binding failure. The check does not imply automatic 401 refresh/replay for customer HttpClient requests. This makes the existing M5 refresh requirement explicit; estimates are unchanged.

### How to run and record validation

Implement simple script entry points as part of the milestones. The following names/commands are proposed, not already available:

```sh
dotnet test tests/Rownd.UnitTests/Rownd.UnitTests.csproj -c Release
./scripts/pack.sh --configuration Release
./scripts/test-passwordless.sh --platform android --scenario smoke
./scripts/test-passwordless.sh --platform ios --scenario smoke
./scripts/test-passwordless.sh --platform android --scenario phone-magic-link
./scripts/test-passwordless.sh --platform ios --scenario phone-magic-link
./scripts/test-passwordless.sh --platform android --scenario refresh-recovery
./scripts/test-passwordless.sh --platform ios --scenario refresh-recovery
./scripts/verify-package.sh --source artifacts/packages
```

Keep orchestration small: choose an explicit device, start or connect to the pinned existing harness, install the sample, execute the selected flow, collect results and propagate failure through a nonzero exit code. Backend state and app data are reset between independent tests; restart scenarios deliberately keep native session data. Use condition waits and bounded timeouts for initialization/auth rather than long arbitrary sleeps. Retrieve test OTPs/links through test-only harness facilities; never ship those facilities in the customer package.

The smoke covers OTP, auth-state notification, token-backed protected request and sign-out. Phone-magic-link covers real phone challenge/SMS capture, external OS dispatch, warm/cold entry, native completion, C# protected access and replay. Both login paths run the shared post-login refresh check before sign-out. Record HTTPS/physical SMS/fallback checks alongside them; script success does not imply those manual checks ran. Refresh-recovery selects actual expiry and temporary refresh outage using the same authenticated session. Package verification creates a separate consumer and invokes platform restore/build checks; its device install/run step must be explicit in scripts or the release checklist, not implied by successful packing.

For each milestone record the git/native/Hub/backend versions, commands, device/OS, expected backend identity, scenario pass/fail, and any manual steps. Do not record raw credentials. If a test is blocked, state the missing prerequisite and keep the exit gate open.

## 7. Completion criteria

- A customer can install one documented NuGet and authenticate with email OTP, email magic links and phone/SMS magic links on Android and iOS.
- Custom-scheme and verified HTTPS auth links reach the native handlers through MAUI, with a tested browser fallback and real SMS tap on each physical platform.
- Their C# application receives auth state and can retrieve a token accepted by their backend.
- Expiry/refresh, relaunch and sign-out work through the existing native session implementation.
- Both platforms work from the packaged artifact, not only local project references.
- The sample and short README are sufficient to repeat configuration, sign-in, a protected API call and sign-out.
- One-time reauthentication for old MAUI installations and the absence of automatic HttpClient interception are stated accurately.

## 8. Source references and review scope

Reference baselines: MAUI `bc7291c` (1.2.4), native Rownd Android `cd08c866` (0.1.14), native Rownd iOS `0c89cac4` (0.2.4). Verify published availability and pin the actual artifacts selected in M1/M2; these are reviewed starting points, not floating dependencies.

- [MAUI upstream](https://github.com/rownd/dotnet-maui/tree/bc7291c).
- [Microsoft Native Library Interop](https://learn.microsoft.com/en-us/dotnet/communitytoolkit/maui/native-library-interop/).
- Existing React Native facades show native auth delegation; use current public native APIs rather than copying historical reflection workarounds.
- Native Android `Rownd.kt` and iOS `Rownd.swift` expose the relevant configure/sign-in/token/sign-out/lifecycle surface.
- Existing native `test-server/` and refresh/Hub regression tests provide the validation starting point.
- [MAUI Android App Links](https://learn.microsoft.com/en-us/dotnet/maui/android/app-links?view=net-maui-10.0), [Apple Universal Links](https://learn.microsoft.com/en-us/dotnet/maui/macios/universal-links?view=net-maui-10.0), and [platform lifecycle callbacks](https://learn.microsoft.com/en-us/dotnet/maui/fundamentals/app-lifecycle?view=net-maui-10.0).
- Android [`SignInLink.kt`](../repositories/supertokens-rownd-android/android/src/main/java/io/rownd/android/models/network/SignInLink.kt) and iOS [`SmartLinks.swift`](../repositories/supertokens-rownd-ios/Sources/Rownd/framework/SmartLinks.swift) implement URL recognition/remapping; the public entry points are `Rownd.handleIntent` and `Rownd.handleSmartLink` respectively.

The earlier subagent correctly identified gaps in the broader proposal. This scope removes the features that required new transport guarantees, profile mutation APIs and crash-safe cross-SDK migration. Its packaging and basic auth findings remain relevant. Any native defect that actually blocks the selected passwordless flow is reproduced during M2 and handled narrowly; unrelated hardening is not added to this release.
