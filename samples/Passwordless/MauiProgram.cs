using System.Net.Http.Headers;
using SuperTokens.Rownd.Foundation;
using NativeRownd = SuperTokens.Rownd.Maui.Rownd;

namespace Passwordless;

public static class MauiProgram
{
    public static MauiApp CreateMauiApp() => MauiApp.CreateBuilder().UseMauiApp<App>().Build();
}

public sealed class App : Application
{
    protected override Window CreateWindow(IActivationState? activationState) => new(new PasswordlessPage());
}

public sealed class PasswordlessPage : ContentPage
{
    private readonly Label status = new() { Text = "Not configured", AutomationId = "auth-status" };
    private readonly HttpClient http = new(new HttpClientHandler { AllowAutoRedirect = false, UseCookies = false });
    private readonly RowndInstance rownd = NativeRownd.Current;

    public PasswordlessPage()
    {
        var appKey = new Entry { Placeholder = "App key", IsPassword = true, AutomationId = "app-key" };
        var api = new Entry { Placeholder = "SuperTokens API origin", AutomationId = "api-domain" };
        var path = new Entry { Text = "/auth", AutomationId = "api-path" };
        var hub = new Entry { Placeholder = "Hub URL", AutomationId = "hub-url" };
        var scheme = new Entry { Text = "rowndmauisample", Placeholder = "Registered custom scheme", AutomationId = "link-scheme" };
        var endpoint = new Entry { Placeholder = "Trusted protected API URL", AutomationId = "protected-url" };
        var result = new Label { AutomationId = "protected-result" };
        var configure = new Button { Text = "Configure", AutomationId = "configure" };
        var signIn = new Button { Text = "Sign in", IsEnabled = false, AutomationId = "sign-in" };
        var signOut = new Button { Text = "Sign out", IsEnabled = false, AutomationId = "sign-out" };
        var protectedApi = new Button { Text = "Call protected API", IsEnabled = false, AutomationId = "protected-api" };
        configure.Clicked += async (_, _) =>
        {
            try
            {
                var config = new RowndConfiguration(appKey.Text, api.Text, path.Text, hub.Text, scheme.Text);
                configure.IsEnabled = false;
                await rownd.ConfigureAsync(config);
                signIn.IsEnabled = signOut.IsEnabled = protectedApi.IsEnabled = true;
                UpdateState(rownd.State);
            }
            catch (Exception error) { status.Text = error.Message; }
        };
        signIn.Clicked += (_, _) => rownd.RequestSignIn();
        signOut.Clicked += (_, _) => rownd.SignOut();
        protectedApi.Clicked += async (_, _) =>
        {
            try
            {
                var token = await rownd.GetAccessTokenAsync();
                if (token is null) { result.Text = "No session"; return; }
                using var request = new HttpRequestMessage(HttpMethod.Get, endpoint.Text);
                request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
                using var response = await http.SendAsync(request);
                response.EnsureSuccessStatusCode();
                // The selected fixture returns only verified user/session identity here.
                result.Text = await response.Content.ReadAsStringAsync();
            }
            catch { result.Text = "Protected request failed"; }
        };
        Content = new ScrollView
        {
            Content = new VerticalStackLayout
            {
                Padding = 24, Spacing = 12,
                Children = { status, appKey, api, path, hub, scheme, endpoint, configure, signIn, protectedApi, signOut, result },
            },
        };
    }

    protected override void OnAppearing()
    {
        base.OnAppearing();
        rownd.StateChanged -= StateChanged;
        rownd.StateChanged += StateChanged;
        UpdateState(rownd.State);
    }

    protected override void OnDisappearing()
    {
        rownd.StateChanged -= StateChanged;
        base.OnDisappearing();
    }

    private void StateChanged(object? sender, RowndState state) => UpdateState(state);
    private void UpdateState(RowndState state) => status.Text = state.IsAuthenticated
        ? $"Authenticated: {state.UserId ?? "identity pending"}" : state.IsReady ? "Signed out" : "Initializing";
}
