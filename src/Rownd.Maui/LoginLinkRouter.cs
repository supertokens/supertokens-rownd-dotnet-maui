using SuperTokens.Rownd.Foundation;

namespace SuperTokens.Rownd.Maui;

internal sealed class LoginLinkRouter(Func<string, bool> forward, TimeProvider? timeProvider = null) : IDisposable
{
    internal const int PendingLimit = 8;
    internal const int RecentLimit = 32;
    internal static readonly TimeSpan CallbackWindow = TimeSpan.FromSeconds(2);
    private readonly object gate = new();
    private readonly TimeProvider clock = timeProvider ?? TimeProvider.System;
    private readonly Queue<string> pending = new();
    private readonly HashSet<string> inFlight = new(StringComparer.Ordinal);
    private readonly Dictionary<string, long> recent = new(StringComparer.Ordinal);
    private RowndConfiguration? configuration;
    private bool ready;
    private bool disposed;

    public void Configure(RowndConfiguration config)
    {
        lock (gate)
        {
            if (!disposed) configuration = config;
        }
    }

    public bool Handle(string value)
    {
        lock (gate)
        {
            if (disposed || !Recognizes(value)) return false;
            ExpireRecent();
            if (pending.Contains(value) || inFlight.Contains(value) || recent.ContainsKey(value)) return true;
            if (pending.Count + inFlight.Count >= PendingLimit) return false;
            if (!ready)
            {
                pending.Enqueue(value);
                return true;
            }

            inFlight.Add(value);
        }

        return Forward(value);
    }

    public void NativeReady()
    {
        lock (gate)
        {
            if (disposed) return;
            ready = true;
        }

        while (true)
        {
            string value;
            lock (gate)
            {
                if (disposed || !pending.TryDequeue(out value!)) return;
                inFlight.Add(value);
            }

            Forward(value);
        }
    }

    private bool Forward(string value)
    {
        var accepted = false;
        try
        {
            // Keep the original encoded string through both deduplication and dispatch.
            accepted = forward(value);
            return accepted;
        }
        catch (Exception)
        {
            // A failed native handoff must neither poison dedup nor stop queue draining.
            return false;
        }
        finally
        {
            lock (gate)
            {
                inFlight.Remove(value);
                if (accepted && !disposed)
                {
                    ExpireRecent();
                    if (recent.Count >= RecentLimit) recent.Remove(recent.MinBy(entry => entry.Value).Key);
                    recent[value] = clock.GetTimestamp();
                }
            }
        }
    }

    private bool Recognizes(string value)
    {
        if (configuration is null || !Uri.TryCreate(value, UriKind.Absolute, out var uri)) return false;
        return (uri.Scheme.Equals(configuration.AppLinkScheme, StringComparison.OrdinalIgnoreCase)
                && uri.Host == "account" && uri.AbsolutePath == "/login")
            || (uri.Scheme == "https" && uri.Host == configuration.HubUrl.Host
                && uri.AbsolutePath == "/account/login");
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
            configuration = null;
            pending.Clear();
            inFlight.Clear();
            recent.Clear();
        }
    }
}
