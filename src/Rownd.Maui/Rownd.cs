using SuperTokens.Rownd.Foundation;

namespace SuperTokens.Rownd.Maui;

public static class Rownd
{
    private static readonly Lazy<RowndInstance> Instance = new(() =>
        new RowndInstance(new PlatformBridge(), MainThread.BeginInvokeOnMainThread));

    public static RowndInstance Current => Instance.Value;
}
