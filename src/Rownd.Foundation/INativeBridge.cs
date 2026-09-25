namespace SuperTokens.Rownd.Foundation;

public sealed record RowndState(bool IsReady, bool IsAuthenticated, string? UserId);

// Platform adapters implement this boundary; credentials never enter C# persistence.
public interface INativeBridge : IDisposable
{
    event Action<RowndState>? StateChanged;
    void Configure(RowndConfiguration configuration, Action<string?> completion);
    void RequestSignIn();
    void GetAccessToken(Action<string?, string?> completion);
    void SignOut();
}
