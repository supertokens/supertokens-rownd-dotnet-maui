# SuperTokens Rownd MAUI — native bridge preview

.NET 10 Android/iOS authentication replacement for customers upgrading `Rownd.Maui`.
See the [integration guide](docs/beta-integration.md) for setup and usage, [beta status](docs/beta-status.md) for validated behavior and known limitations, and [release guide](docs/github-releases.md) for GitHub publication.

Native Rownd owns Hub UI, token persistence, expiry and refresh. The C# facade does not initialize legacy authentication, import old `rownd_state`, or intercept HTTP requests. Existing customers must sign in once after replacing the old package.

## Build and local package

Pinned SDK/workload set: **10.0.200**, MAUI **10.0.20**, JDK **21.0.12**, Xcode **26.2**. Source pins and open Core-image requirements are in `eng/versions.json`. Builders need the pinned sibling repositories; package consumers do not.

Current beta candidate build and smoke results are recorded in [beta validation](docs/beta-status.md); older milestone reports below remain historical evidence.

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

These commands build/pack without installing or launching a device. `io.supertokens.maui.buildcheck` is a build-only identifier, not the customer's identity. The beta candidate for GitHub distribution is `SuperTokens.Rownd.Maui` version `0.0.1-beta.1`; it has not been published to GitHub or NuGet.org. See the [beta integration guide](docs/beta-integration.md) for local-feed setup and limitations. Platform-only development packs use separate feeds under `artifacts/packages/<platform>/<version>`.

On Mac with the matching workloads, Xcode and XcodeGen, build both native frameworks then run `bash scripts/pack.sh all`. This creates one public multi-target package and its transitive foundation/platform packages in `artifacts/packages/all/0.0.1-beta.1`. The script checks conditional native dependency groups. See [beta status](docs/beta-status.md) for the exact package build and runtime validation scope.

## Package installation

After producing the combined feed, add its absolute path and nuget.org as NuGet sources. Install only:

```xml
<PackageReference Include="SuperTokens.Rownd.Maui" Version="0.0.1-beta.1" />
```

NuGet selects the Android or iOS native dependency for the application's target framework. Distribute all four packages together; consumers need no sibling checkout or manually copied native binary. Target .NET 10 Android API 26+ or iOS 15+, with MAUI 10.0.20.

`samples/Passwordless` uses the package by default. Restore it with the local feed plus nuget.org and your `RowndApplicationId`. `scripts/build-sample.sh` explicitly opts into source references for SDK development. To verify the combined feed in isolated Release consumers:

```sh
ROWND_PACKAGE_SOURCE="$PWD/artifacts/packages/all/0.0.1-beta.1" \
  ROWND_APPLICATION_ID=io.supertokens.maui.buildcheck bash scripts/verify-package.sh android
ROWND_PACKAGE_SOURCE="$PWD/artifacts/packages/all/0.0.1-beta.1" \
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

The [passwordless sample](samples/Passwordless) demonstrates native sign-in, authentication state, request-scoped bearer tokens and sign-out. Configure your own app key, API origin/path, Hub URL and callback scheme. The development sample uses `rowndmauisample`; customer apps must register their own scheme.

Start beta link testing with a custom scheme. The [deep-linking section](docs/beta-integration.md#6-deep-linking-app-configuration-and-details-to-send-us) explains `AppLinkScheme`, Android/iOS callback forwarding, and the app/signing details needed later for verified HTTPS links.

The adapter accepts login callbacks at the configured scheme's `://account/login` and the configured Hub origin's HTTPS `/account/login`. Configure link handling before forwarding OS callbacks. A callback accepted by the router is not proof of authentication; verify the resulting state and a protected API request.

See [beta status](docs/beta-status.md) for simulator/emulator results and the remaining physical-device, initialization and lifecycle limitations. Historical `Rownd/`, `examples/` and `Rownd.sln` are excluded from the new build path.

## GitHub beta releases

Run `npm run release` for an offline check of the prepared beta assets. After committing and pushing the release target, `npm run release -- --publish` creates a GitHub prerelease and uploads the validated packages and tutorial. It does not publish to NuGet.org. See [the release guide](docs/github-releases.md) for prerequisites, artifact layout and recovery.
