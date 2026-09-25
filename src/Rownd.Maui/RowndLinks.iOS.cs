#if IOS
using SuperTokens.Rownd.Foundation;

namespace SuperTokens.Rownd.Maui;

public static class RowndLinks
{
    private static readonly LoginLinkRouter Router = new(value =>
    {
        using var url = new global::Foundation.NSUrl(value);
        return PlatformBridge.Active?.HandleUrl(url) == true;
    }, schedule: action => CoreFoundation.DispatchQueue.MainQueue.DispatchAsync(action));

    // Call at app startup before forwarding OS callbacks, with the same config used
    // for ConfigureAsync. Queue encoded strings, never reconstruct query/fragment.
    public static void Configure(RowndConfiguration config) => Router.Configure(config);
    public static void Suspend() => Router.Suspend();
    public static void Resume() => Router.Resume();

    public static bool HandleUrl(global::Foundation.NSUrl url) => Router.Handle(url.AbsoluteString);

    internal static void NativeReady() => Router.NativeReady();

    internal static void Dispose() => Router.Dispose();
}
#endif
