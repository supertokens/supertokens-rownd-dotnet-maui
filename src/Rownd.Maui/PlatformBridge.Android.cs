#if ANDROID
using SuperTokens.Rownd.Foundation;
using SuperTokens.Rownd.Native.Android;

namespace SuperTokens.Rownd.Maui;

internal sealed class PlatformBridge : Java.Lang.Object, INativeBridge, IStateListener
{
    private readonly RowndBridge native = new();
    private readonly Android.OS.Handler mainHandler = new(Android.OS.Looper.MainLooper);
    // JNI callbacks must survive GC until the native async operation completes.
    private readonly HashSet<Java.Lang.Object> callbacks = [];
    public event Action<RowndState>? StateChanged;

    public void Configure(RowndConfiguration config, Action<string?> completion)
    {
        var activity = Platform.CurrentActivity as AndroidX.Fragment.App.FragmentActivity
            ?? throw new InvalidOperationException("Configure after the MAUI activity has been created.");
        native.SetStateListener(this);
        CompletionCallback? callback = null;
        callback = new(error => { callbacks.Remove(callback!); completion(error); });
        callbacks.Add(callback);
        native.Configure(activity, config.AppKey, config.ApiDomain.AbsoluteUri.TrimEnd('/'),
            config.ApiBasePath, config.HubUrl.AbsoluteUri, config.AppLinkScheme, callback);
    }

    public void Changed(bool ready, bool authenticated, string? userId)
    {
        // Leave the native state collector before notifying MAUI; reentrant JNI callbacks can crash Mono.
        mainHandler.Post(() => StateChanged?.Invoke(new(ready, authenticated, userId)));
    }
    public void RequestSignIn() => native.RequestSignIn();
    public void SignOut() => native.SignOut();
    public void GetAccessToken(Action<string?, string?> completion)
    {
        TokenCallback? callback = null;
        callback = new((token, error) => { callbacks.Remove(callback!); completion(token, error); });
        callbacks.Add(callback);
        native.GetAccessToken(callback);
    }
    void IDisposable.Dispose()
    {
        native.SetStateListener(null);
        native.Close();
        native.Dispose();
        mainHandler.Dispose();
        callbacks.Clear();
        base.Dispose();
    }

    private sealed class CompletionCallback(Action<string?> callback) : Java.Lang.Object, ICompletion
    {
        public void Complete(string? error) => callback(error);
    }
    private sealed class TokenCallback(Action<string?, string?> callback) : Java.Lang.Object, ITokenCompletion
    {
        public void Complete(string? token, string? error) => callback(token, error);
    }
}
#endif
