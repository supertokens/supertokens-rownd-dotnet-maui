using Foundation;
using UIKit;
using SuperTokens.Rownd.Maui;

namespace Passwordless;

[Register("AppDelegate")]
public sealed class AppDelegate : MauiUIApplicationDelegate
{
    protected override MauiApp CreateMauiApp() => MauiProgram.CreateMauiApp();

    public override bool FinishedLaunching(UIApplication application, NSDictionary launchOptions)
    {
        StartupSettings.PrepareLinks();
        RowndLinks.Suspend();
        if (launchOptions?[UIApplication.LaunchOptionsUrlKey] is NSUrl url) RowndLinks.HandleUrl(url);
        if (launchOptions?[UIApplication.LaunchOptionsUserActivityDictionaryKey] is NSDictionary activities)
            foreach (var value in activities.Values)
                if (value is NSUserActivity activity && activity.WebPageUrl is { } page) RowndLinks.HandleUrl(page);
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

    public override bool OpenUrl(UIApplication application, NSUrl url, NSDictionary options) =>
        RowndLinks.HandleUrl(url) || base.OpenUrl(application, url, options);

    public override bool ContinueUserActivity(UIApplication application, NSUserActivity userActivity,
        UIApplicationRestorationHandler completionHandler) =>
        (userActivity.WebPageUrl is { } url && RowndLinks.HandleUrl(url)) ||
        base.ContinueUserActivity(application, userActivity, completionHandler);
}
