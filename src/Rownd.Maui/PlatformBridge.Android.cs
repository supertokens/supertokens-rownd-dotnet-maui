#if ANDROID
using SuperTokens.Rownd.Foundation;
using SuperTokens.Rownd.Native.Android;

namespace SuperTokens.Rownd.Maui;

[Android.Runtime.Preserve(AllMembers = true)]
internal sealed class PlatformBridge : Java.Lang.Object, INativeBridge, IStateListener
{
    internal static PlatformBridge? Active { get; private set; }
    public PlatformBridge() { Active = this; }
    private readonly RowndBridge native = new();
    private readonly Android.OS.Handler mainHandler = new(Android.OS.Looper.MainLooper);
    // JNI callbacks must survive GC until the native async operation completes.
    private readonly HashSet<Java.Lang.Object> callbacks = [];
    private readonly object callbackGate = new();
    private bool disposed;
    public event Action<RowndState>? StateChanged;

    public void Configure(RowndConfiguration config, Action<string?> completion)
    {
        RowndLinks.Configure(config);
        var activity = Platform.CurrentActivity as AndroidX.Fragment.App.FragmentActivity
            ?? throw new InvalidOperationException("Configure after the MAUI activity has been created.");
        native.SetStateListener(this);
        CompletionCallback? callback = null;
        callback = new(error => Post(() =>
        {
            callbacks.Remove(callback!);
            if (error is null) RowndLinks.NativeReady();
            else RowndLinks.Dispose();
            completion(error);
        }));
        callbacks.Add(callback);
        try
        {
            native.Configure(activity, config.AppKey, config.ApiDomain.AbsoluteUri.TrimEnd('/'),
                config.ApiBasePath, config.HubUrl.AbsoluteUri, config.AppLinkScheme, callback);
        }
        catch { callbacks.Remove(callback); throw; }
    }

    public void Changed(bool ready, bool authenticated, string? userId)
    {
        // Leave the native state collector before notifying MAUI; reentrant JNI callbacks can crash Mono.
        Post(() => StateChanged?.Invoke(new(ready, authenticated, userId)));
    }
    private void Post(Action action)
    {
        lock (callbackGate)
        {
            if (disposed) return;
            mainHandler.Post(() => { if (!disposed) action(); });
        }
    }
    public void RequestSignIn() => native.RequestSignIn();
    public void SignOut() => native.SignOut();
    internal bool HandleIntent(Android.Content.Intent intent) => native.HandleIntent(intent);
    public void GetAccessToken(Action<string?, string?> completion)
    {
        TokenCallback? callback = null;
        callback = new((token, error) => Post(() => { callbacks.Remove(callback!); completion(token, error); }));
        callbacks.Add(callback);
        try { native.GetAccessToken(callback); }
        catch { callbacks.Remove(callback); throw; }
    }
    void IDisposable.Dispose()
    {
        lock (callbackGate)
        {
            if (disposed) return;
            disposed = true;
            mainHandler.RemoveCallbacksAndMessages(null);
            mainHandler.Dispose();
        }
        StateChanged = null;
        RowndLinks.Dispose();
        Active = null;
        native.SetStateListener(null);
        native.Close();
        native.Dispose();
        callbacks.Clear();
        base.Dispose();
    }

    [Android.Runtime.Preserve(AllMembers = true)]
    private sealed class CompletionCallback(Action<string?> callback) : Java.Lang.Object, ICompletion
    {
        public void Complete(string? error) => callback(error);
    }
    [Android.Runtime.Preserve(AllMembers = true)]
    private sealed class TokenCallback(Action<string?, string?> callback) : Java.Lang.Object, ITokenCompletion
    {
        public void Complete(string? token, string? error) => callback(token, error);
    }
}
#endif
