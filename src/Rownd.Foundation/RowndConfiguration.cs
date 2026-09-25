namespace SuperTokens.Rownd.Foundation;

// Configuration only: native initialization is introduced in M2.
public sealed class RowndConfiguration
{
    public RowndConfiguration(string appKey, string apiDomain, string apiBasePath, string hubUrl, string appLinkScheme)
    {
        ArgumentException.ThrowIfNullOrWhiteSpace(appKey);
        ApiDomain = HttpUri(apiDomain, nameof(apiDomain));
        if (ApiDomain.AbsolutePath != "/" || ApiDomain.Query.Length != 0)
            throw new ArgumentException("API domain must be an origin without a path or query.", nameof(apiDomain));
        HubUrl = HttpUri(hubUrl, nameof(hubUrl));
        if (string.IsNullOrWhiteSpace(apiBasePath) || !apiBasePath.StartsWith('/') ||
            apiBasePath.Contains('?') || apiBasePath.Contains('#') || apiBasePath.Contains('\\') ||
            apiBasePath.Contains("//") || apiBasePath.Split('/').Any(s => s is "." or "..") ||
            apiBasePath.Any(char.IsWhiteSpace) || apiBasePath.Contains('%'))
            throw new ArgumentException("API base path must be an absolute, unescaped path.", nameof(apiBasePath));
        if (!Uri.CheckSchemeName(appLinkScheme) || appLinkScheme.Equals("http", StringComparison.OrdinalIgnoreCase) ||
            appLinkScheme.Equals("https", StringComparison.OrdinalIgnoreCase))
            throw new ArgumentException("Use a custom app link scheme without ://.", nameof(appLinkScheme));
        AppKey = appKey;
        ApiBasePath = apiBasePath;
        AppLinkScheme = appLinkScheme;
    }

    public string AppKey { get; }
    public Uri ApiDomain { get; }
    public string ApiBasePath { get; }
    public Uri HubUrl { get; }
    public string AppLinkScheme { get; }

    private static Uri HttpUri(string value, string name)
    {
        if (!Uri.TryCreate(value, UriKind.Absolute, out var uri) ||
            (uri.Scheme != "http" && uri.Scheme != "https") ||
            uri.UserInfo.Length != 0 || uri.Fragment.Length != 0 || string.IsNullOrEmpty(uri.Host))
            throw new ArgumentException("Provide an HTTP(S) URL without credentials or fragment.", name);
        return uri;
    }
}
