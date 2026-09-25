using SuperTokens.Rownd.Foundation;

namespace Passwordless;

public static class MauiProgram
{
    public static MauiApp CreateMauiApp() => MauiApp.CreateBuilder().UseMauiApp<App>().Build();
}

public sealed class App : Application
{
    protected override Window CreateWindow(IActivationState? activationState) => new(new FoundationPage());
}

public sealed class FoundationPage : ContentPage
{
    public FoundationPage()
    {
        var appKey = new Entry { Placeholder = "App key", IsPassword = true };
        var api = new Entry { Placeholder = "SuperTokens API origin" };
        var path = new Entry { Placeholder = "API base path", Text = "/auth" };
        var hub = new Entry { Placeholder = "Hub URL" };
        var scheme = new Entry { Placeholder = "Custom app scheme (no ://)" };
        var status = new Label { Text = "Native bindings pending M2. Auth state unavailable.", AutomationId = "auth-status" };
        var validate = new Button { Text = "Validate configuration", AutomationId = "validate-config" };
        validate.Clicked += (_, _) =>
        {
            try
            {
                _ = new RowndConfiguration(appKey.Text, api.Text, path.Text, hub.Text, scheme.Text);
                status.Text = "Configuration valid. Native initialization remains unavailable (M2).";
            }
            catch (ArgumentException error)
            {
                status.Text = error.Message;
            }
        };
        Content = new ScrollView
        {
            Content = new VerticalStackLayout
            {
                Padding = 24, Spacing = 12,
                Children =
                {
                    new Label { Text = "Passwordless — M1 foundation", FontSize = 24 },
                    status, appKey, api, path, hub, scheme, validate,
                    new Button { Text = "Sign in (M2)", IsEnabled = false, AutomationId = "sign-in" },
                    new Button { Text = "Call protected API (M2)", IsEnabled = false, AutomationId = "protected-api" },
                    new Button { Text = "Sign out (M2)", IsEnabled = false, AutomationId = "sign-out" },
                },
            },
        };
    }
}
