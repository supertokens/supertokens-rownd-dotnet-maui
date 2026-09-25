using SuperTokens.Rownd.Foundation;

namespace SuperTokens.Rownd.Maui;

// Native handlers expose submission, not consumption. Their deferred single URL
// slot cannot support a FIFO contract: keep only the latest waiting callback.
internal sealed class LoginLinkRouter(
    Func<string, bool> submit,
    TimeProvider? timeProvider = null,
    Action<Action>? schedule = null) : IDisposable
{
    internal const int PendingLimit = 1;
    internal const int RecentLimit = 32;
    internal static readonly TimeSpan CallbackWindow = TimeSpan.FromSeconds(2);
    internal static readonly TimeSpan PendingLifetime = TimeSpan.FromMinutes(2);
    private readonly object gate = new();
    private readonly TimeProvider clock = timeProvider ?? TimeProvider.System;
    private readonly Action<Action> dispatch = schedule ?? (action => action());
    private readonly Dictionary<string, long> recent = new(StringComparer.Ordinal);
    private (string Value, long Created)? pending;
    private string? submitting;
    private bool scheduled;
    private string? appLinkScheme;
    private Uri? hubUrl;
    private bool ready;
    private bool hostReady = true;
    private bool disposed;

    public void Configure(RowndConfiguration config)
    {
        lock (gate)
        {
            if (disposed) return;
            appLinkScheme = config.AppLinkScheme;
            hubUrl = config.HubUrl;
        }
    }

    // True means managed acceptance/coalescing, never native consumption.
    public bool Handle(string value)
    {
        lock (gate)
        {
            if (disposed || value.Length > 16384 || !Recognizes(value)) return false;
            ExpirePending();
            ExpireRecent();
            if (pending?.Value == value || submitting == value || recent.ContainsKey(value)) return true;
            pending = (value, clock.GetTimestamp());
        }

        Schedule();
        return true;
    }

    public void NativeReady()
    {
        lock (gate)
        {
            if (disposed) return;
            ready = true;
        }

        Schedule();
    }

    public void Suspend()
    {
        lock (gate) hostReady = false;
    }

    public void Resume()
    {
        lock (gate)
        {
            if (disposed) return;
            hostReady = true;
        }

        Schedule();
    }

    private void Schedule()
    {
        lock (gate)
        {
            ExpirePending();
            if (disposed || !ready || !hostReady || pending is null || scheduled || submitting is not null) return;
            scheduled = true;
        }

        try
        {
            dispatch(SubmitLatest);
        }
        catch
        {
            lock (gate) scheduled = false;
            throw;
        }
    }

    private void SubmitLatest()
    {
        lock (gate)
        {
            scheduled = false;
            ExpirePending();
            if (disposed || !ready || !hostReady || pending is not { } item) return;
            pending = null;
            submitting = item.Value;
            try
            {
                // Keep the exact encoded string; success acknowledges submission only.
                if (submit(item.Value) && !disposed)
                {
                    ExpireRecent();
                    if (recent.Count >= RecentLimit) recent.Remove(recent.MinBy(entry => entry.Value).Key);
                    recent[item.Value] = clock.GetTimestamp();
                }
            }
            catch (Exception)
            {
                // A transient rejection/throw does not poison a subsequent OS retry.
            }
            finally
            {
                submitting = null;
            }
        }

        Schedule();
    }

    public bool Recognizes(string value)
    {
        lock (gate)
        {
            if (appLinkScheme is null || hubUrl is null ||
                !Uri.TryCreate(value, UriKind.Absolute, out var uri) || uri.UserInfo.Length != 0) return false;
            return (uri.Scheme.Equals(appLinkScheme, StringComparison.OrdinalIgnoreCase)
                    && uri.Host == "account" && uri.Port == -1 && uri.AbsolutePath == "/login")
                || (uri.Scheme == "https" && uri.Host == hubUrl.Host && uri.Port == hubUrl.Port
                    && uri.AbsolutePath == "/account/login");
        }
    }

    // Inputs come from java.net.URI, the parser used by pinned SignInLinkApi.
    // Ownership intentionally ignores credentials/port and includes native aliases;
    // acceptance above does not. Keep these rules after disposal to prevent bypass.
    internal bool OwnsAndroidLogin(string? scheme, string? host, string? rawPath)
    {
        lock (gate)
        {
            if (appLinkScheme is null || hubUrl is null || host is null) return false;
            if (scheme == appLinkScheme)
                return host.Trim('/') == "account" && rawPath?.Trim('/') == "login";
            return scheme == "https" && rawPath == "/account/login" &&
                (host == hubUrl.Host || host == "rownd-hub.supertokens.com" ||
                 host.EndsWith(".rownd-hub.supertokens.com", StringComparison.Ordinal) ||
                 host is "staging.supertokens-rownd-hub.pages.dev" or "supertokens-rownd-hub.pages.dev");
        }
    }

    private void ExpirePending()
    {
        if (pending is { } item && clock.GetElapsedTime(item.Created) >= PendingLifetime) pending = null;
    }

    private void ExpireRecent()
    {
        var now = clock.GetTimestamp();
        foreach (var value in recent.Where(entry => clock.GetElapsedTime(entry.Value, now) >= CallbackWindow)
                     .Select(entry => entry.Key).ToArray())
            recent.Remove(value);
    }

    public void Dispose()
    {
        lock (gate)
        {
            disposed = true;
            ready = false;
            pending = null;
            recent.Clear();
        }
    }
}
