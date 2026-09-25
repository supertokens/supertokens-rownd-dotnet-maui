using Foundation;
using UIKit;
using SuperTokens.Rownd.Maui;

namespace Passwordless;

[Register("AppDelegate")]
public sealed class AppDelegate : MauiUIApplicationDelegate
{
    protected override MauiApp CreateMauiApp() => MauiProgram.CreateMauiApp();

    public override bool OpenUrl(UIApplication application, NSUrl url, NSDictionary options) => RowndLinks.HandleUrl(url);

    public override bool ContinueUserActivity(UIApplication application, NSUserActivity userActivity,
        UIApplicationRestorationHandler completionHandler) =>
        userActivity.WebPageUrl is { } url && RowndLinks.HandleUrl(url);
}
