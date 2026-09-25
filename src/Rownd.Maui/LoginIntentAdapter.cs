namespace SuperTokens.Rownd.Maui;

// Keep the ownership/sanitization boundary testable without an Android runtime.
internal sealed class LoginIntentAdapter<T>(
    LoginLinkRouter router,
    Func<T, string?> viewUrl,
    Func<string, bool> nativeOwnsLogin,
    Func<T, T> withoutData)
    where T : class
{
    internal T? Capture(T? intent)
    {
        if (intent is null || viewUrl(intent) is not { } value || !nativeOwnsLogin(value)) return intent;

        // Sanitize even when validation, size, readiness or disposal rejects delivery.
        var sanitized = withoutData(intent);
        router.Handle(value);
        return sanitized;
    }
}
