using System.Text.Json;
using System.Text.Json.Serialization;
using SuperTokens.Rownd.Foundation;
using SuperTokens.Rownd.Maui;

namespace Passwordless;

internal sealed record StartupSettings(string AppKey, string ApiDomain, string ApiBasePath,
    string HubUrl, string AppLinkScheme, string ProtectedUrl, int InitializationDelayMs = 0)
{
    private static readonly Lazy<StartupSettings?> Settings = new(() =>
    {
        using var stream = typeof(StartupSettings).Assembly.GetManifestResourceStream("Passwordless.Startup.json");
        return stream is null ? null : JsonSerializer.Deserialize(stream, SampleJsonContext.Default.StartupSettings);
    });
    internal static StartupSettings? Current => Settings.Value;
    internal RowndConfiguration Configuration => new(AppKey, ApiDomain, ApiBasePath, HubUrl, AppLinkScheme);
    internal static void PrepareLinks()
    {
        if (Current is { } settings) RowndLinks.Configure(settings.Configuration);
    }

    internal int Delay
    {
        get
        {
#if DEBUG
            return Math.Clamp(InitializationDelayMs, 0, 30000);
#else
            return 0;
#endif
        }
    }
}

internal sealed record ProtectedObservation(
    [property: JsonPropertyName("userId")] string? UserId,
    [property: JsonPropertyName("sessionFingerprint")] string? SessionFingerprint,
    [property: JsonPropertyName("request")] int Request);

[JsonSerializable(typeof(StartupSettings))]
[JsonSerializable(typeof(ProtectedObservation))]
internal partial class SampleJsonContext : JsonSerializerContext;
