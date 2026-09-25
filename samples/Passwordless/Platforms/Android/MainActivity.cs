using Android.App;
using Android.Content.PM;
using Android.Content;
using Android.OS;
using SuperTokens.Rownd.Maui;

namespace Passwordless;

[Activity(
    Name = "io.supertokens.maui.PasswordlessActivity",
    Theme = "@style/Maui.MainTheme.NoActionBar",
    MainLauncher = true,
    LaunchMode = LaunchMode.SingleTask,
    ConfigurationChanges = ConfigChanges.ScreenSize | ConfigChanges.Orientation | ConfigChanges.UiMode |
        ConfigChanges.ScreenLayout | ConfigChanges.SmallestScreenSize | ConfigChanges.Density)]
[IntentFilter([Intent.ActionView], Categories = [Intent.CategoryDefault, Intent.CategoryBrowsable],
    DataScheme = "rowndmauisample", DataHost = "account", DataPath = "/login")]
public sealed class MainActivity : MauiAppCompatActivity
{
    protected override void OnCreate(Bundle? savedInstanceState)
    {
        App.ActivityGeneration++;
        StartupSettings.PrepareLinks();
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
