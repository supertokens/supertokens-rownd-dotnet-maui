# SuperTokens Rownd MAUI — native bridge preview

.NET 10 Android/iOS authentication replacement for customers upgrading `Rownd.Maui`.
**M2 runtime acceptance is pending. iOS implementation is uncompiled.** See [implementation, checks and blockers](docs/m2-status.md).

Native Rownd owns Hub UI, token persistence, expiry and refresh. The C# facade does not initialize legacy authentication, import old `rownd_state`, or intercept HTTP requests. Existing customers must sign in once after replacing the old package.

## Build and local package

Pinned SDK/workload set: **10.0.401**, MAUI **10.0.20**, JDK **21.0.12**. Source pins and open Xcode/Core-image requirements are in `eng/versions.json`. Builders need the pinned sibling repositories; package consumers do not.

```sh
source /home/dev/.config/rownd-android-tooling/env.sh # this Linux environment
python3 scripts/check-native-sources.py
bash scripts/build-native-android.sh
./scripts/test-unit.sh --nologo -v quiet
ROWND_APPLICATION_ID=io.supertokens.maui.buildcheck ./scripts/build-sample.sh android
bash scripts/pack.sh android
python3 scripts/check-android-package.py
ROWND_APPLICATION_ID=io.supertokens.maui.buildcheck bash scripts/verify-package.sh android
```

These commands build/pack without installing or launching a device. `io.supertokens.maui.buildcheck` is a build-only identifier, not the customer's identity. Local NuGet identity `SuperTokens.Rownd.Maui` version `0.0.1-m2` is provisional, unreserved and unpublished. Android and iOS packs use separate feeds under `artifacts/packages/<platform>`; a combined customer artifact awaits Mac validation.

On Mac with the matching .NET iOS workload, Xcode and XcodeGen: run `bash scripts/build-native-ios.sh`, `bash scripts/pack.sh ios`, then package-consumer verification with actual signing/identity settings. This path is written but has not been compiled or executed here.

## Minimal API

Reference `SuperTokens.Rownd.Maui` from the local platform feed plus nuget.org. Configure once after the host activity/window exists:

```csharp
using SuperTokens.Rownd.Foundation;
using NativeRownd = SuperTokens.Rownd.Maui.Rownd;

var rownd = NativeRownd.Current;
rownd.StateChanged += (_, state) => UpdateAuthLabel(state.IsAuthenticated);
await rownd.ConfigureAsync(new RowndConfiguration(
    appKey, apiDomain, "/auth", hubUrl, "your-registeredscheme"));
rownd.RequestSignIn(); // Completion is observed through native-backed state.

var token = await rownd.GetAccessTokenAsync(); // null = no session; failures fault.
if (token is not null)
{
    using var request = new HttpRequestMessage(HttpMethod.Get, trustedProtectedUrl);
    request.Headers.Authorization = new("Bearer", token);
    using var response = await httpClient.SendAsync(request);
    response.EnsureSuccessStatusCode();
}
rownd.SignOut(); // Local completion is observed through state; remote revocation is async.
```

Retrieve a current token per protected operation. No automatic 401 retry or global authorization header is provided. Unsubscribe UI handlers when leaving the screen; disposing the process singleton is terminal and stops observations/pending managed operations, not a native sign-out.

## Sample and links

See [Testing on a Mac](docs/testing.md) for pinned tools, offline tests, native/package builds, shared fixture setup, and opt-in existing-session Appium instructions. Runtime and iOS validation remain pending.

`samples/Passwordless` has real native actions and an ordinary bearer request. Enter fixture configuration, then Configure. The development scheme **`rowndmauisample`** is registered on both platforms; the Hub must use that same scheme. Customer apps must substitute their registration. Native Android owns ComponentActivity intent forwarding: do not duplicate `OnNewIntent` delivery. iOS `AppDelegate` forwards warm URL/user-activity callbacks through `RowndLinks` to native smart-link handling. Production cold-launch/scene configuration, HTTPS associations and physical routing remain pending.

iOS forwarding is **login-only**: the configured scheme's `://account/login` and the configured Hub host's HTTPS `/account/login`. Email-verification links are outside this release and remain unhandled. `RowndLinks.Configure(config)` must precede callbacks. Exact encoded URLs are deduplicated while queued/in flight (eight distinct outstanding links maximum) and for two seconds after a successful native handoff (32 recent entries maximum, oldest evicted). Suppressed duplicates return `true`; duplicates do not extend that window. Failed native handoffs can retry immediately; replay testing can retry after two seconds. Disposal clears the router and is terminal. This is callback coalescing, not proof of authentication or server-side replay protection.

See [M1 shared fixture](docs/m1-status.md) and [M2 E2E driver prerequisites](docs/m2-status.md). Appium email OTP/warm captured-phone-link drivers are implemented but **not run**. They require explicit opt-in and a real native WebView automation setup. Full replay/cold-start/refresh drivers and runtime results remain open; no real SMS delivery is needed.

Historical `Rownd/`, `examples/` and `Rownd.sln` are excluded from the new execution/build path. Publishing stays disabled. Nothing has been committed, pushed or published for M2.
