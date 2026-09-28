#if DEBUG
using System.Net.Http.Headers;
using System.Security.Cryptography;
using System.Text;
using System.Text.Json;
using SuperTokens.Rownd.Foundation;

namespace Passwordless;

// Sample-only observations. Credentials never leave this process or enter UI/log output.
internal sealed class SessionProbe
{
    private static readonly HttpClient Http = new(new HttpClientHandler { AllowAutoRedirect = false, UseCookies = false });
    private readonly RowndInstance rownd;
    private string? savedToken;
    private string? candidateToken;
    private int signedOutTransitions;
    private int operations;
    private int credentialEpoch;
    private bool authenticated;
    internal static SessionProbe Current { get; } = new(SuperTokens.Rownd.Maui.Rownd.Current);

    private SessionProbe(RowndInstance rownd)
    {
        this.rownd = rownd;
        authenticated = rownd.State.IsAuthenticated;
        rownd.StateChanged += (_, state) =>
        {
            if (authenticated && !state.IsAuthenticated) signedOutTransitions++;
            authenticated = state.IsAuthenticated;
            if (!authenticated) Clear();
        };
    }

    private void Clear()
    {
        credentialEpoch++;
        savedToken = candidateToken = null;
    }

    internal View CreateControls(Func<string> endpoint)
    {
        var result = new Label { Text = "Idle", AutomationId = "session-probe-result", FontSize = 10 };

        // Individual buttons keep platform automation independent of Picker implementations.
        var layout = new VerticalStackLayout { Spacing = 0 };
        var buttons = new HorizontalStackLayout { Spacing = 0 };
        foreach (var action in new[] { "save", "saved-request", "getter", "candidate-request", "state", "clear" })
        {
            var button = new Button { Text = action, AutomationId = "session-probe-" + action, HeightRequest = 40, WidthRequest = 85, FontSize = 10, Padding = 0 };
            button.Clicked += async (_, _) =>
            {
                result.Text = "Pending";
                button.IsEnabled = false;
                try
                {
                    result.Text = $"{++operations};{await Run(action, endpoint())}";
                }
                catch
                {
                    result.Text = "Probe failed";
                }
                finally
                {
                    button.IsEnabled = true;
                }
            };
            if (action == "candidate-request")
            {
                layout.Children.Add(buttons);
                buttons = new HorizontalStackLayout { Spacing = 0 };
            }
            buttons.Children.Add(button);
        }

        layout.Children.Add(buttons);
        layout.Children.Add(result);
        return layout;
    }

    private async Task<string> Run(string action, string endpoint)
    {
        string outcome;
        if (action == "clear")
        {
            Clear();
            outcome = "Cleared";
        }
        else if (action == "state")
        {
            outcome = "State";
        }
        else if (action is "saved-request" or "candidate-request")
        {
            var token = action == "saved-request" ? savedToken : candidateToken;
            // A candidate is single-use, including failed HTTP/identity observations.
            if (action == "candidate-request") candidateToken = null;
            if (token is null)
            {
                outcome = "Missing token";
            }
            else
            {
                using var request = new HttpRequestMessage(HttpMethod.Get, endpoint);
                request.Headers.Authorization = new AuthenticationHeaderValue("Bearer", token);
                using var response = await Http.SendAsync(request);
                outcome = "HTTP " + (int)response.StatusCode;
                if (action == "candidate-request" && response.StatusCode == System.Net.HttpStatusCode.OK)
                {
                    using var body = JsonDocument.Parse(await response.Content.ReadAsStringAsync());
                    var root = body.RootElement;
                    var session = root.TryGetProperty("sessionFingerprint", out var fingerprint) ? fingerprint.GetString() : null;
                    if (session is null && root.TryGetProperty("accessTokenPayload", out var payload) &&
                        payload.TryGetProperty("sessionHandle", out var handle))
                        session = Convert.ToHexString(SHA256.HashData(Encoding.UTF8.GetBytes(handle.GetString()!)));
                    outcome += " " + JsonSerializer.Serialize(
                        new ProtectedObservation(root.GetProperty("userId").GetString(), session, operations),
                        SampleJsonContext.Default.ProtectedObservation);
                }
            }
        }
        else
        {
            candidateToken = null;
            if (action == "save") savedToken = null;
            var epoch = credentialEpoch;
            try
            {
                var token = await rownd.GetAccessTokenAsync();
                // Do not retain credentials from a getter that crossed sign-out.
                if (authenticated && epoch == credentialEpoch)
                {
                    if (action == "save") savedToken = token;
                    else candidateToken = token;
                }
                outcome = token is null ? "No session" : "Token available";
            }
            catch
            {
                outcome = "Getter error";
            }
        }

        return $"{outcome};authenticated={rownd.State.IsAuthenticated};signedOut={signedOutTransitions}";
    }
}
#endif
