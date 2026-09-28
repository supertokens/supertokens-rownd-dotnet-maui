# Integrate the GitHub beta into a .NET MAUI app

This guide targets `SuperTokens.Rownd.Maui` **0.0.1-beta.1** for Android and iOS. Obtain the four matching NuGet package assets from the GitHub beta release supplied by the SDK maintainer. This guide does not imply that a release is already published or that the package is available on nuget.org.

The beta packages target native Android SDK **0.1.14** and iOS SDK **0.2.5**. Native SDKs handle Hub presentation, credential storage, and session refresh; the managed facade exposes initialization, authentication state, sign-in, token retrieval, and sign-out. You do not install the native SDKs separately.

## 1. Prepare the app and backend

Use a .NET MAUI app targeting `net10.0-android` and `net10.0-ios`. The repository's pinned build environment is .NET SDK/workload set **10.0.200**, MAUI **10.0.20**, Android workload **36.1.43**, JDK **21**, iOS workload **26.2.10217**, and Xcode **26.2**. Building iOS requires a Mac with Xcode and the matching workload; signed devices additionally require your Apple signing configuration. Minimum supported versions are Android API **26** and iOS **15**.

For an app dedicated to these supported platforms, use this property group in `MyApp.csproj` (merge it with the existing one):

```xml
<PropertyGroup>
  <TargetFrameworks>net10.0-android;net10.0-ios</TargetFrameworks>
  <UseMaui>true</UseMaui>
  <SingleProject>true</SingleProject>
  <MauiVersion>10.0.20</MauiVersion>
  <SupportedOSPlatformVersion Condition="$([MSBuild]::GetTargetPlatformIdentifier('$(TargetFramework)')) == 'android'">26.0</SupportedOSPlatformVersion>
  <SupportedOSPlatformVersion Condition="$([MSBuild]::GetTargetPlatformIdentifier('$(TargetFramework)')) == 'ios'">15.0</SupportedOSPlatformVersion>
</PropertyGroup>
```

Remove the template's Mac Catalyst and Windows target entries for this example: this SDK supports Android and iOS only. If your template references `Microsoft.Maui.Controls` through `$(MauiVersion)`, the property above pins it to 10.0.20; otherwise align the existing package reference explicitly.

Use your own Android application ID and iOS bundle ID. Package consumers do not need sibling SDK repositories, XcodeGen, or manually copied AAR/XCFramework files.

Before initializing the SDK, obtain these settings from your backend/Hub administrator:

| Setting | Meaning |
|---|---|
| `AppKey` | Client-facing Rownd app key; never use a backend API/admin secret |
| `ApiDomain` | HTTPS origin of your backend, without an API path, query, or credentials |
| `ApiBasePath` | SuperTokens API mount path on that backend, for example `/auth` |
| `HubUrl` | HTTPS base URL of the compatible Rownd Hub deployed for your app |
| `AppLinkScheme` | Your registered custom scheme, without `://` |
| Protected API URL | An endpoint on your trusted backend that verifies the session bearer token |

The backend must be configured with the compatible Rownd plugin and the authentication methods you want to offer. Configure the Hub/backend-generated mobile callback scheme to match the app registration below. This package does not provision your backend, enable email/SMS delivery, or deploy the Hub.

## 2. Download the four NuGet packages

Download these assets from the **same** GitHub beta release:

- `SuperTokens.Rownd.Maui.0.0.1-beta.1.nupkg`
- `SuperTokens.Rownd.Foundation.0.0.1-beta.1.nupkg`
- `SuperTokens.Rownd.Native.Android.0.0.1-beta.1.nupkg`
- `SuperTokens.Rownd.Native.iOS.0.0.1-beta.1.nupkg`

If the release supplies a `SHA256SUMS` asset, download it alongside the packages and verify the files before installation. From that download directory on macOS:

```sh
shasum -a 256 -c SHA256SUMS
```

On Linux, use `sha256sum -c SHA256SUMS`. Every listed package must report `OK`; stop if a checksum differs or a required package is missing. Use the checksum asset from the same release, rather than generating a new manifest from your downloads.

Keep the downloaded `.nupkg` files intact. Place them in this layout alongside your solution:

```text
MySolution/
  NuGet.Config
  packages/
    rownd-beta/
      SuperTokens.Rownd.Maui.0.0.1-beta.1.nupkg
      SuperTokens.Rownd.Foundation.0.0.1-beta.1.nupkg
      SuperTokens.Rownd.Native.Android.0.0.1-beta.1.nupkg
      SuperTokens.Rownd.Native.iOS.0.0.1-beta.1.nupkg
  MyApp/
    MyApp.csproj
```

Create `NuGet.Config` at the solution root. Its local path is relative to this configuration file:

```xml
<?xml version="1.0" encoding="utf-8"?>
<configuration>
  <packageSources>
    <clear />
    <add key="rownd-beta" value="./packages/rownd-beta" />
    <add key="nuget.org" value="https://api.nuget.org/v3/index.json" />
  </packageSources>
</configuration>
```

If your solution needs other private feeds, include them as additional sources. Add only the public facade to `MyApp.csproj`; its dependencies select the correct platform package automatically:

```xml
<ItemGroup>
  <PackageReference Include="SuperTokens.Rownd.Maui" Version="0.0.1-beta.1" />
</ItemGroup>
```

Then restore from the solution root:

```sh
dotnet restore MyApp/MyApp.csproj --configfile NuGet.Config
```

For an existing legacy integration, remove the old `Rownd.Maui` package and its old initialization/Hub handlers before adding this package. Do not initialize both SDKs. Legacy `rownd_state` is not migrated: existing customers must sign in once after upgrading.

## 3. Define one configuration for the process

The examples use namespace `MyApp`. Replace it with your app's namespace throughout. Add `AuthBootstrap.cs` to the shared project:

```csharp
using SuperTokens.Rownd.Foundation;
using SuperTokens.Rownd.Maui;
using NativeRownd = SuperTokens.Rownd.Maui.Rownd;

namespace MyApp;

internal static class AuthBootstrap
{
    // Replace these placeholders with your application's non-secret settings.
    internal const string AppLinkScheme = "com.example.myapp.auth";
    internal static readonly RowndConfiguration Configuration = new(
        appKey: "YOUR_CLIENT_APP_KEY",
        apiDomain: "https://api.your-domain.example",
        apiBasePath: "/auth",
        hubUrl: "https://hub.your-domain.example",
        appLinkScheme: AppLinkScheme);

    private static readonly object Gate = new();
    private static Task? initialization;

    // Called early by the platform delegates, before they forward incoming URLs.
    internal static void PrepareLinks() => RowndLinks.Configure(Configuration);

    // Call only once a MAUI Activity/window exists, such as from OnAppearing.
    internal static Task InitializeAsync()
    {
        lock (Gate)
            return initialization ??= NativeRownd.Current.ConfigureAsync(Configuration);
    }
}
```

The `.example` URLs above are placeholders, not service endpoints. Use your real HTTPS deployment. Do not copy the development sample's localhost addresses or cleartext-traffic configuration into your app.

`ConfigureAsync` may be invoked only once per process, including when initialization fails. Keep its Task as above; correct the configuration and restart the process after a failure. Do not call it each time you navigate to an authentication screen. Configuration must be available at startup after process death so a cold-start login link can be queued before the UI appears.

## 4. Register and forward Android links

Adapt `Platforms/Android/MainActivity.cs`. Keep your existing application-specific activity settings and other intent handling. The important ordering is to capture a login intent **before** calling the base implementation and store the sanitized result:

```csharp
using Android.App;
using Android.Content;
using Android.Content.PM;
using Android.OS;
using SuperTokens.Rownd.Maui;

namespace MyApp;

[Activity(
    Theme = "@style/Maui.MainTheme.NoActionBar",
    MainLauncher = true,
    Exported = true,
    LaunchMode = LaunchMode.SingleTask,
    ConfigurationChanges = ConfigChanges.ScreenSize | ConfigChanges.Orientation |
        ConfigChanges.UiMode | ConfigChanges.ScreenLayout |
        ConfigChanges.SmallestScreenSize | ConfigChanges.Density)]
[IntentFilter([Intent.ActionView],
    Categories = [Intent.CategoryDefault, Intent.CategoryBrowsable],
    DataScheme = AuthBootstrap.AppLinkScheme,
    DataHost = "account", DataPath = "/login")]
public class MainActivity : MauiAppCompatActivity
{
    protected override void OnCreate(Bundle? savedInstanceState)
    {
        AuthBootstrap.PrepareLinks();
        RowndLinks.Suspend();
        Intent = RowndLinks.CaptureIntent(Intent);
        base.OnCreate(savedInstanceState);
    }

    protected override void OnNewIntent(Intent? intent)
    {
        var sanitized = RowndLinks.CaptureIntent(intent);
        Intent = sanitized;
        base.OnNewIntent(sanitized);
    }

    protected override void OnPause()
    {
        RowndLinks.Suspend();
        base.OnPause();
    }

    protected override void OnPostResume()
    {
        base.OnPostResume();
        RowndLinks.Resume();
    }
}
```

Ensure `Platforms/Android/AndroidManifest.xml` contains the internet permission:

```xml
<uses-permission android:name="android.permission.INTERNET" />
```

The attribute registers URLs shaped like `com.example.myapp.auth://account/login?...`. Replace the scheme with your own. Do not forward the same auth intent through a second native listener: `CaptureIntent` is the forwarding owner and sanitizes recognized login data before native base listeners see it. Unrelated intents continue through the base implementation.

## 5. Register and forward iOS links

Add the scheme to the existing dictionary in `Platforms/iOS/Info.plist`, merging with any URL types your app already uses:

```xml
<key>CFBundleURLTypes</key>
<array>
  <dict>
    <key>CFBundleURLName</key>
    <string>com.example.myapp.authentication</string>
    <key>CFBundleURLSchemes</key>
    <array>
      <string>com.example.myapp.auth</string>
    </array>
  </dict>
</array>
```

For a MAUI app using the non-scene `UIApplicationDelegate` lifecycle, adapt `Platforms/iOS/AppDelegate.cs`:

```csharp
using Foundation;
using UIKit;
using SuperTokens.Rownd.Maui;

namespace MyApp;

[Register("AppDelegate")]
public class AppDelegate : MauiUIApplicationDelegate
{
    protected override MauiApp CreateMauiApp() => MauiProgram.CreateMauiApp();

    public override bool FinishedLaunching(
        UIApplication application, NSDictionary launchOptions)
    {
        AuthBootstrap.PrepareLinks();
        RowndLinks.Suspend();
        if (launchOptions?[UIApplication.LaunchOptionsUrlKey] is NSUrl url)
            RowndLinks.HandleUrl(url);
        if (launchOptions?[UIApplication.LaunchOptionsUserActivityDictionaryKey]
            is NSDictionary activities)
            foreach (var value in activities.Values)
                if (value is NSUserActivity activity && activity.WebPageUrl is { } page)
                    RowndLinks.HandleUrl(page);
        return base.FinishedLaunching(application, launchOptions);
    }

    public override void OnActivated(UIApplication application)
    {
        base.OnActivated(application);
        RowndLinks.Resume();
    }

    public override void OnResignActivation(UIApplication application)
    {
        RowndLinks.Suspend();
        base.OnResignActivation(application);
    }

    public override bool OpenUrl(
        UIApplication application, NSUrl url, NSDictionary options) =>
        RowndLinks.HandleUrl(url) || base.OpenUrl(application, url, options);

    public override bool ContinueUserActivity(
        UIApplication application, NSUserActivity userActivity,
        UIApplicationRestorationHandler completionHandler) =>
        (userActivity.WebPageUrl is { } url && RowndLinks.HandleUrl(url)) ||
        base.ContinueUserActivity(application, userActivity, completionHandler);
}
```

Scene-based apps need forwarding from their actual scene callbacks; that lifecycle is not covered by this recipe or fully validated for the beta. Do not install multiple owners for the same callback.

The managed adapter accepts login URLs only: the configured custom scheme's `://account/login`, or HTTPS `/account/login` on the configured Hub origin. It preserves the original query and fragment. HTTPS App Links/Universal Links also require your domain association files, Android signing fingerprints, iOS team/bundle identifiers, and entitlements; the custom-scheme setup above does not establish those associations. Other callback types are outside this login adapter's contract.

## 6. Initialize, observe state, and open sign-in

Initialize from an already displayed page. For example, adapt the following members into your page's code-behind, with a `Label` named `AuthStatus`. The page handlers below are examples to connect to your own buttons; enable authentication buttons only after initialization succeeds.

```csharp
using SuperTokens.Rownd.Foundation;
using NativeRownd = SuperTokens.Rownd.Maui.Rownd;

// Members inside your ContentPage class:
private bool authUiVisible;

protected override async void OnAppearing()
{
    base.OnAppearing();
    authUiVisible = true;
    NativeRownd.Current.StateChanged -= OnAuthStateChanged;
    NativeRownd.Current.StateChanged += OnAuthStateChanged;
    try
    {
        await AuthBootstrap.InitializeAsync();
        if (authUiVisible)
            RenderAuthState(NativeRownd.Current.State);
        // Enable your sign-in, token-request, and sign-out controls here.
    }
    catch
    {
        if (authUiVisible)
            AuthStatus.Text = "Initialization failed. Check configuration and restart.";
    }
}

protected override void OnDisappearing()
{
    authUiVisible = false;
    NativeRownd.Current.StateChanged -= OnAuthStateChanged;
    base.OnDisappearing();
}

private void OnAuthStateChanged(object? sender, RowndState state) => RenderAuthState(state);

private void RenderAuthState(RowndState state) =>
    AuthStatus.Text = state.IsAuthenticated ? "Signed in" : "Signed out";

private void OnSignInClicked(object? sender, EventArgs e) =>
    NativeRownd.Current.RequestSignIn();

private void OnSignOutClicked(object? sender, EventArgs e) =>
    NativeRownd.Current.SignOut();
```

`RequestSignIn()` opens the native Hub. Observe `StateChanged` for completion; the method does not return an authentication result. `RowndState` contains `IsReady`, `IsAuthenticated`, and `UserId`. State changes are delivered on the MAUI UI thread. Update a newly opened screen from `Current.State` as well as subscribing to future changes.

The native SDK handles persisted sessions after app restart. Run normal initialization again in the new process; do not copy tokens into your own preferences or re-create a session from a cached user ID.

## 7. Retrieve a token for each protected request

Use one reusable `HttpClient`, but set the bearer token on each individual request:

```csharp
using System.Net.Http.Headers;
using NativeRownd = SuperTokens.Rownd.Maui.Rownd;

// Members inside a service or page; call only after initialization succeeded.
private static readonly HttpClient Api = new();

private async Task CallProtectedApiAsync()
{
    var token = await NativeRownd.Current.GetAccessTokenAsync();
    if (token is null)
        throw new InvalidOperationException("Sign in before making this request.");

    using var request = new HttpRequestMessage(
        HttpMethod.Get, "https://api.your-domain.example/protected");
    request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
    using var response = await Api.SendAsync(request);
    response.EnsureSuccessStatusCode();
    // Read and handle your backend's response here. Do not log the token.
}
```

A `null` result means there is no session. An exception means token retrieval failed, including temporary network/refresh failures; it does not by itself mean the user signed out. Show a retryable error and allow a later operation to retrieve a token again after recovery. Request a current token for every protected operation instead of retaining one indefinitely.

The facade does not attach headers globally, intercept requests, or replay an API call after a 401. Handle a protected endpoint's errors explicitly in your app. Send tokens only to your trusted backend, not to arbitrary URLs or third-party services.

## 8. Sign-out and lifetime

`SignOut()` dispatches native sign-out; observe the resulting state rather than treating its return as remote revocation completion. Local state completion and remote revocation are distinct; revocation is asynchronous.

Unsubscribe page event handlers when their view disappears. Do **not** dispose `Rownd.Current` for navigation or ordinary sign-out. Disposing this process-wide singleton is terminal: it cancels pending managed operations and closes the managed/native bridge and link router, but does not perform native sign-out. It cannot be configured or reused afterward in the same process.

The link router retains only the latest pending login callback for up to two minutes while initialization or host activation is pending. Its acceptance result is not proof of successful authentication; use state and an actual protected request to verify login.

## Beta limitations and your acceptance check

This is a limited beta, not a claim that every customer lifecycle and deployment combination is verified:

- Native iOS fatal initialization failures cannot currently be converted into a failed managed Task. Validate configuration before release; ordinary C# exception handling cannot recover from a native process termination.
- Disposal while native callbacks are queued and Android recreation while the Hub is actively presented are not fully validated. Ordinary page navigation should detach UI handlers while leaving the singleton alive.
- The unmodified Hub used for this beta has a known limitation with access-token lifetimes of **five minutes or less**; the local reproduction used a 90-second lifetime. A local Hub fix is not included in this beta. Use a longer lifetime for beta evaluation or coordinate a corrected Hub before testing short lifetimes. This describes the tested Hub, not the version currently deployed in your environment; installing these packages alone does not update your Hub.
- On Android, an immediate force-stop just after creating a challenge can occur before WebView local storage commits the originating attempt to disk. The attempt can then be lost, and the Hub requires confirmation as a safety measure because it cannot establish the same-device match. This remains a beta limitation; do not count accepting that prompt as a successful automatic same-device cold-start test. Ordinary background-and-callback behavior is being validated separately and should be checked in your app.
- Physical-device Release behavior, HTTPS association routing, scene-based iOS hosts, and your backend's enabled authentication methods require your own acceptance testing.

Before distributing your app, test sign-in, one protected request, process termination/relaunch with the same session, and sign-out followed by another relaunch. Test links while the app is open, closed, and initializing; separately confirm that a link created on another device keeps the intended cross-device policy. Exercise a temporary backend outage and recovery without interpreting token exceptions as sign-out. Use your own signed Release builds for final acceptance.

For repository validation details rather than customer setup, see [M5 testing](testing-m5.md), [M5 status](m5-status.md), and the [sample host implementation](../samples/Passwordless).
