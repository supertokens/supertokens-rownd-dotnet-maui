#if ANDROID
using Android.Content;
using SuperTokens.Rownd.Foundation;

namespace SuperTokens.Rownd.Maui;

public static class RowndLinks
{
    private static readonly Android.OS.Handler MainHandler = new(Android.OS.Looper.MainLooper!);
    private static readonly LoginLinkRouter Router = new(value =>
    {
        using var uri = Android.Net.Uri.Parse(value);
        using var intent = new Intent(Intent.ActionView, uri);
        return PlatformBridge.Active?.HandleIntent(intent) == true;
    }, schedule: action => MainHandler.Post(action));

    private static readonly LoginIntentAdapter<Intent> Adapter = new(Router,
        intent => intent.Action == Intent.ActionView ? intent.DataString : null,
        value =>
        {
            try
            {
                using var uri = new Java.Net.URI(value);
                return Router.OwnsAndroidLogin(uri.Scheme, uri.Host, uri.RawPath);
            }
            catch (Java.Net.URISyntaxException) { return false; }
        },
        intent =>
        {
            var sanitized = new Intent(intent);
            sanitized.SetData(null);
            return sanitized;
        });

    public static void Configure(RowndConfiguration config) => Router.Configure(config);
    public static void Suspend() => Router.Suspend();
    public static void Resume() => Router.Resume();

    // Call BEFORE base.OnCreate/base.OnNewIntent and store the returned intent on
    // the activity. Native ComponentActivity listeners see only the sanitized copy;
    // this adapter is the sole auth-link owner when explicitly installed by a host.
    public static Intent? CaptureIntent(Intent? intent) => Adapter.Capture(intent);

    internal static void NativeReady() => Router.NativeReady();
    internal static void Dispose() => Router.Dispose();
}
#endif
