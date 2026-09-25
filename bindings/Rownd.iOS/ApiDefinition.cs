using Foundation;
using ObjCRuntime;

namespace SuperTokens.Rownd.Native.iOS;

[BaseType(typeof(NSObject), Name = "RWNRowndBridge")]
interface RowndBridge
{
    [Export("configureWithAppKey:apiDomain:apiBasePath:hubURL:scheme:completion:")]
    void Configure(string appKey, string apiDomain, string apiBasePath, string hubUrl, string scheme, Action<string?> completion);
    [Export("setStateListener:")]
    void SetStateListener([NullAllowed] Action<bool, bool, string?> listener);
    [Export("requestSignIn")]
    void RequestSignIn();
    [Export("signOut")]
    void SignOut();
    [Export("getAccessToken:")]
    void GetAccessToken(Action<string?, string?> completion);
    [Export("handleURL:")]
    bool HandleUrl(NSUrl url);
    [Export("dispose")]
    void Close();
}
