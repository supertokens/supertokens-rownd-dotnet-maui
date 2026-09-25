#if IOS
using SuperTokens.Rownd.Foundation;
using SuperTokens.Rownd.Native.iOS;

namespace SuperTokens.Rownd.Maui;

internal sealed class PlatformBridge : INativeBridge
{
    internal static PlatformBridge? Active { get; private set; }
    private readonly RowndBridge native = new();
    private bool disposed;
    private Action<bool, bool, string?>? stateListener;
    public event Action<RowndState>? StateChanged;
    public PlatformBridge() { Active = this; }
    public void Configure(RowndConfiguration config, Action<string?> completion)
    {
        RowndLinks.Configure(config);
        stateListener = (ready, authenticated, userId) =>
        {
            if (!disposed) StateChanged?.Invoke(new(ready, authenticated, userId));
        };
        native.SetStateListener(stateListener);
        native.Configure(config.AppKey, config.ApiDomain.AbsoluteUri.TrimEnd('/'), config.ApiBasePath,
            config.HubUrl.AbsoluteUri.TrimEnd('/'), config.AppLinkScheme, error =>
            {
                if (disposed) return;
                if (error is null) RowndLinks.NativeReady();
                completion(error);
            });
    }
    public void RequestSignIn() => native.RequestSignIn();
    public void SignOut() => native.SignOut();
    public void GetAccessToken(Action<string?, string?> completion) => native.GetAccessToken(completion);
    internal bool HandleUrl(global::Foundation.NSUrl url) => native.HandleUrl(url);
    public void Dispose()
    {
        if (disposed) return;
        disposed = true;
        StateChanged = null;
        RowndLinks.Dispose();
        native.Close();
        stateListener = null;
        native.Dispose();
        Active = null;
    }
}
#endif
