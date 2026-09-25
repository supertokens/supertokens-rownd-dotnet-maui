#if IOS
using SuperTokens.Rownd.Foundation;
using SuperTokens.Rownd.Native.iOS;

namespace SuperTokens.Rownd.Maui;

internal sealed class PlatformBridge : INativeBridge
{
    internal static PlatformBridge? Active { get; private set; }
    private readonly RowndBridge native = new();
    public event Action<RowndState>? StateChanged;
    public PlatformBridge() { Active = this; }
    public void Configure(RowndConfiguration config, Action<string?> completion)
    {
        RowndLinks.Configure(config);
        native.SetStateListener((ready, authenticated, userId) => StateChanged?.Invoke(new(ready, authenticated, userId)));
        native.Configure(config.AppKey, config.ApiDomain.AbsoluteUri.TrimEnd('/'), config.ApiBasePath,
            config.HubUrl.AbsoluteUri, config.AppLinkScheme, error =>
            {
                if (error is null) RowndLinks.NativeReady();
                completion(error);
            });
    }
    public void RequestSignIn() => native.RequestSignIn();
    public void SignOut() => native.SignOut();
    public void GetAccessToken(Action<string?, string?> completion) => native.GetAccessToken(completion);
    internal bool HandleUrl(global::Foundation.NSUrl url) => native.HandleUrl(url);
    public void Dispose() { RowndLinks.Dispose(); native.Close(); native.Dispose(); Active = null; }
}
#endif
