using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using SuperTokens.Rownd.Foundation;
using NativeRownd = SuperTokens.Rownd.Maui.Rownd;

namespace Passwordless;

public static class MauiProgram
{
    public static MauiApp CreateMauiApp()
    {
        StartupSettings.PrepareLinks();
        return MauiApp.CreateBuilder().UseMauiApp<App>().Build();
    }
}

public sealed class App : Application
{
    internal static int ActivityGeneration { get; set; }
    protected override Window CreateWindow(IActivationState? activationState) => new(new PasswordlessPage());
}

public sealed class PasswordlessPage : ContentPage
{
    private static Task? initialization;
    private static readonly string ProcessId = Guid.NewGuid().ToString("N");
    private static bool previouslyAuthenticated;
    private static int authenticationTransitions;
    private static readonly HttpClient Http = new(new HttpClientHandler { AllowAutoRedirect = false, UseCookies = false });
    private readonly Label status = new() { Text = "Not configured", AutomationId = "auth-status" };
    private readonly Label completions = new() { Text = "0", AutomationId = "auth-completions", FontSize = 10 };
    private readonly RowndInstance rownd = NativeRownd.Current;
    private readonly Button signIn = new() { Text = "Sign in", IsEnabled = false, AutomationId = "sign-in" };
    private readonly Button signOut = new() { Text = "Sign out", IsEnabled = false, AutomationId = "sign-out" };
    private readonly Button protectedApi = new() { Text = "Call protected API", IsEnabled = false, AutomationId = "protected-api" };
    private CancellationTokenSource? visible;
    private int requests;
    private int touches;

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
        configure.Clicked += async (_, _) =>
        {
            try
            {
                var config = new RowndConfiguration(appKey.Text, api.Text, path.Text, hub.Text, scheme.Text);
                configure.IsEnabled = false;
                initialization ??= rownd.ConfigureAsync(config);
                await initialization;
                signIn.IsEnabled = signOut.IsEnabled = protectedApi.IsEnabled = true;
                UpdateState(rownd.State);
            }
            catch (Exception error) { status.Text = error.Message; }
        };
        signIn.Clicked += (_, _) => rownd.RequestSignIn();
        signOut.Clicked += (_, _) => rownd.SignOut();
        protectedApi.Clicked += async (_, _) =>
        {
            var cancellation = visible?.Token ?? new CancellationToken(true);
            var sequence = ++requests;
            result.Text = "Requesting";
            try
            {
                var token = await rownd.GetAccessTokenAsync();
                cancellation.ThrowIfCancellationRequested();
                if (token is null) { result.Text = "No session"; return; }
                using var request = new HttpRequestMessage(HttpMethod.Get, endpoint.Text);
                request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
                using var response = await Http.SendAsync(request, cancellation);
                response.EnsureSuccessStatusCode();
                using var body = JsonDocument.Parse(await response.Content.ReadAsStringAsync(cancellation));
                var root = body.RootElement;
                var session = root.TryGetProperty("sessionFingerprint", out var fingerprint) ? fingerprint.GetString() : null;
                if (session is null && root.TryGetProperty("accessTokenPayload", out var payload) &&
                    payload.TryGetProperty("sessionHandle", out var handle))
                    session = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(handle.GetString()!)));
                // Expose verified identity plus a non-secret session fingerprint, never token payloads.
                result.Text = JsonSerializer.Serialize(new ProtectedObservation(root.GetProperty("userId").GetString(), session, sequence),
                    SampleJsonContext.Default.ProtectedObservation);
            }
            catch (OperationCanceledException) { }
            catch { if (!cancellation.IsCancellationRequested) result.Text = "Protected request failed"; }
        };
        var touch = new Button { Text = "Check host", AutomationId = "host-touch" };
        var observation = new Label { Text = "0", AutomationId = "host-touches" };
        var process = new Label { Text = ProcessId, AutomationId = "process-id", FontSize = 10 };
        var page = new Label { Text = Guid.NewGuid().ToString("N"), AutomationId = "page-id", FontSize = 10 };
        var generation = new Label { Text = App.ActivityGeneration.ToString(), AutomationId = "activity-generation", FontSize = 10 };
        var recreate = new Button { Text = "Recreate activity (Debug)", AutomationId = "recreate-activity", IsVisible = false };
#if ANDROID && DEBUG
        recreate.IsVisible = true;
        recreate.Clicked += (_, _) => Platform.CurrentActivity?.Recreate();
#endif
        touch.Clicked += (_, _) =>
        {
            observation.Text = (++touches).ToString();
            generation.Text = App.ActivityGeneration.ToString();
        };
        var rebind = new Button { Text = "Rebind page subscription", AutomationId = "rebind-subscription" };
        rebind.Clicked += (_, _) =>
        {
            rownd.StateChanged -= StateChanged;
            rownd.StateChanged += StateChanged;
            UpdateState(rownd.State);
        };
        var settings = StartupSettings.Current;
        if (settings is not null)
        {
            endpoint.Text = settings.ProtectedUrl;
            foreach (var entry in new[] { appKey, api, path, hub, scheme, endpoint }) entry.IsVisible = false;
            configure.IsVisible = false;
        }
        Content = new ScrollView
        {
            Content = new VerticalStackLayout
            {
                Padding = 16, Spacing = 4,
                Children = { status, signIn, protectedApi, signOut, result, touch, observation, completions, process, page, generation, rebind, recreate,
                    appKey, api, path, hub, scheme, endpoint, configure },
            },
        };
    }

    protected override async void OnAppearing()
    {
        base.OnAppearing();
        visible?.Cancel();
        visible?.Dispose();
        visible = new();
        var appearance = visible;
        rownd.StateChanged -= StateChanged;
        rownd.StateChanged += StateChanged;
        UpdateState(rownd.State);
        if (StartupSettings.Current is { } settings)
        {
            try
            {
                initialization ??= Initialize(settings);
                await initialization;
                if (ReferenceEquals(visible, appearance) && !appearance.IsCancellationRequested) UpdateState(rownd.State);
            }
            catch
            {
                if (ReferenceEquals(visible, appearance) && !appearance.IsCancellationRequested)
                    status.Text = "Initialization failed; restart after correcting configuration";
            }
        }
    }

    protected override void OnDisappearing()
    {
        rownd.StateChanged -= StateChanged;
        visible?.Cancel();
        base.OnDisappearing();
    }

    protected override void OnHandlerChanged()
    {
        base.OnHandlerChanged();
        rownd.StateChanged -= StateChanged;
        if (Handler is not null)
        {
            visible ??= new();
            rownd.StateChanged += StateChanged;
            UpdateState(rownd.State);
        }
        else
        {
            visible?.Cancel();
            visible?.Dispose();
            visible = null;
        }
    }

    private void StateChanged(object? sender, RowndState state) => UpdateState(state);
    private static async Task Initialize(StartupSettings settings)
    {
        await Task.Delay(settings.Delay);
        await NativeRownd.Current.ConfigureAsync(settings.Configuration);
    }

    private void UpdateState(RowndState state)
    {
        if (state.IsAuthenticated && !previouslyAuthenticated) authenticationTransitions++;
        previouslyAuthenticated = state.IsAuthenticated;
        completions.Text = authenticationTransitions.ToString();
        signIn.IsEnabled = signOut.IsEnabled = protectedApi.IsEnabled = state.IsReady;
        status.Text = state.IsAuthenticated
            ? $"Authenticated: {state.UserId ?? "identity pending"}" : state.IsReady ? "Signed out" : "Initializing";
    }
}
