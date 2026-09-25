using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using System.Text.RegularExpressions;

namespace Rownd.Harness;

public sealed class HarnessClient(HttpClient http)
{
    public async Task VerifyEnvironmentAsync(CancellationToken cancellationToken = default)
    {
        using var health = await http.GetAsync("health", cancellationToken);
        health.EnsureSuccessStatusCode();
        using var response = await http.GetAsync("test/protected", cancellationToken);
        if (response.StatusCode != HttpStatusCode.Unauthorized)
            throw new InvalidOperationException("Protected endpoint must reject unauthenticated requests with 401.");
    }

    public async Task<string?> ReadPhoneLinkAsync(string phone, CancellationToken cancellationToken = default)
    {
        if (!Regex.IsMatch(phone, @"^\+[1-9][0-9]{6,14}$"))
            throw new ArgumentException("Use an E.164 test phone number.", nameof(phone));
        using var response = await http.GetAsync("captures/latest?phoneNumber=" + Uri.EscapeDataString(phone), cancellationToken);
        if (response.StatusCode == HttpStatusCode.NotFound) return null;
        response.EnsureSuccessStatusCode();
        using var capture = await response.Content.ReadFromJsonAsync<JsonDocument>(cancellationToken);
        var root = capture!.RootElement;
        if (root.GetProperty("phoneNumber").GetString() != phone)
            throw new InvalidOperationException("Capture belongs to another phone number.");
        var link = root.GetProperty("urlWithLinkCode").GetString()!;
        ValidateMobileLink(link);
        return link;
    }

    public static void ValidateMobileLink(string link)
    {
        if (!Uri.TryCreate(link, UriKind.Absolute, out var uri) ||
            (uri.Scheme != "http" && uri.Scheme != "https") || uri.UserInfo.Length != 0 || uri.Fragment.Length < 2)
            throw new InvalidOperationException("Capture must contain an HTTP(S) link with a code fragment.");
        var query = uri.Query.TrimStart('?').Split('&').Select(part => part.Split('=', 2)).ToArray();
        bool Has(string key, Func<string, bool> valid) => query.Count(p => Uri.UnescapeDataString(p[0]) == key) == 1 &&
            query.Any(p => p.Length == 2 && Uri.UnescapeDataString(p[0]) == key && valid(Uri.UnescapeDataString(p[1])));
        if (!Has("preAuthSessionId", value => !string.IsNullOrWhiteSpace(value)) ||
            !Has("displayContext", value => value == "mobile_app"))
            throw new InvalidOperationException("Capture must retain pre-auth session and mobile context.");
    }
}
