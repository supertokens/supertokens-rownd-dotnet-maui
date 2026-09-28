# SuperTokens Rownd MAUI — native bridge preview

.NET 10 Android/iOS authentication replacement for customers upgrading `Rownd.Maui`.
**M5 session automation is implemented; exact-candidate runtime and customer acceptance remain open.** See [M5 runbook](docs/testing-m5.md), [M5 evidence and final matrix](docs/m5-status.md), [M4 status](docs/m4-status.md) and [user-recorded runtime results](docs/testing.md).

Native Rownd owns Hub UI, token persistence, expiry and refresh. The C# facade does not initialize legacy authentication, import old `rownd_state`, or intercept HTTP requests. Existing customers must sign in once after replacing the old package.

## Build and local package

Pinned SDK/workload set: **10.0.200**, MAUI **10.0.20**, JDK **21.0.12**, Xcode **26.2**. Source pins and open Core-image requirements are in `eng/versions.json`. Builders need the pinned sibling repositories; package consumers do not.

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

These commands build/pack without installing or launching a device. `io.supertokens.maui.buildcheck` is a build-only identifier, not the customer's identity. Local NuGet identity `SuperTokens.Rownd.Maui` version `0.0.1-m3` is provisional, unreserved and unpublished. Platform-only development packs use separate feeds under `artifacts/packages/<platform>`.

On Mac with the matching workloads, Xcode and XcodeGen, build both native frameworks then run `bash scripts/pack.sh all`. This creates one public multi-target package and its transitive foundation/platform packages in `artifacts/packages/all`. The script checks conditional native dependency groups. M3 combined packaging and isolated Android/iOS Release builds have user-recorded Mac evidence in `docs/m3-status.md`; the changed M4 artifacts require their own verification.

## Package installation

After producing the combined feed, add its absolute path and nuget.org as NuGet sources. Install only:

```xml
<PackageReference Include="SuperTokens.Rownd.Maui" Version="0.0.1-m3" />
```

NuGet selects the Android or iOS native dependency for the application's target framework. Distribute all four packages together; consumers need no sibling checkout or manually copied native binary. Target .NET 10 Android API 26+ or iOS 15+, with MAUI 10.0.20.

`samples/Passwordless` uses the package by default. Restore it with the local feed plus nuget.org and your `RowndApplicationId`. `scripts/build-sample.sh` explicitly opts into source references for SDK development. To verify the combined feed in isolated Release consumers:

```sh
ROWND_PACKAGE_SOURCE="$PWD/artifacts/packages/all" \
  ROWND_APPLICATION_ID=io.supertokens.maui.buildcheck bash scripts/verify-package.sh android
ROWND_PACKAGE_SOURCE="$PWD/artifacts/packages/all" \
  ROWND_APPLICATION_ID=io.supertokens.maui.buildcheck bash scripts/verify-package.sh ios \
  -p:RuntimeIdentifier=iossimulator-arm64
```

These checks build only. Signed physical-device Release installation and authentication remain separate acceptance gates.

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

Retrieve a current token per protected operation. No automatic 401 retry or global authorization header is provided. Configure exactly once per process, including after failure; repeated calls throw. Await readiness before other operations. Native callbacks map to Tasks with asynchronous continuations; null token means no session, native errors fault the Task without inventing a signed-out state. State is a native snapshot; changed snapshots are delivered on the MAUI UI thread. Unsubscribe UI handlers when leaving the screen; disposing the process singleton is terminal and cancels pending managed operations, not a native sign-out. iOS native fatal initialization failures cannot currently be translated to failed Tasks.

If token retrieval fails during a temporary outage, show a retryable error. After connectivity returns, a later user operation can call the getter again; do not equate an exception with a signed-out state. Handle a protected API's 401 as an API error: this package does not replay that request. Keep bearer tokens request-scoped and send them only to your trusted backend. Use native state changes to update sign-in/sign-out UI.

## Sample and links

See the [M3 validation runbook](docs/testing-m3.md) for package-only Release checks and physical-device acceptance. [Testing on a Mac](docs/testing.md) covers pinned tools, shared fixture setup, user-recorded simulator results and runtime driver prerequisites.

`samples/Passwordless` has real native actions and an ordinary bearer request. Embed non-secret startup JSON with `-p:RowndStartupConfig=/absolute/path/startup.json` for automatic configuration after process death; see the [M4 runbook](docs/testing-m4.md). Without it, enter configuration manually. The development scheme **`rowndmauisample`** is registered on both platforms; the Hub must use that same scheme. Customer apps must substitute their registration. The sample Android adapter captures auth URLs before base callbacks and sanitizes the intent seen by native ComponentActivity listeners, establishing one forwarding owner. iOS uses launch URL/activity, OpenUrl and ContinueUserActivity callbacks in its selected non-scene UIApplicationDelegate lifecycle. Both adapters wait for native readiness and an active host. Physical routing remains unrun; parameterized association-file generation awaits actual domain/signing inputs.

The adapter recognizes **login-only** URLs: the configured scheme's `://account/login` and configured Hub origin's HTTPS `/account/login`. `RowndLinks.Configure(config)` must precede callbacks. It retains **one latest pending link**, with a 16 KiB limit and two-minute lifetime, and coalesces exact duplicates for two seconds after native submission (32 recent entries). Pause/resume gates presentation readiness. Disposal clears the router and is terminal. Native submission is not an authentication acknowledgment. See the [M4 ownership/queue contract](docs/testing-m4.md#lifecycle-ownership) before adapting the sample host.

Concrete Appium OTP/link/lifecycle journeys have [revision-specific Mac evidence](docs/m4-status.md#mac-validation--2026-09-25-to-2026-09-27). Run [M5 refresh/recovery](docs/testing-m5.md) separately after rebuilding the exact candidate; no M5 runtime pass is claimed. Captured generated links replace SMS delivery for this scope. Signed physical Release, HTTPS associations, browser fallback and customer integration remain distinct gates. Debug-only session probes are sample code and are excluded from Release and the SDK packages.

Historical `Rownd/`, `examples/` and `Rownd.sln` are excluded from the new execution/build path. Publishing stays disabled.
