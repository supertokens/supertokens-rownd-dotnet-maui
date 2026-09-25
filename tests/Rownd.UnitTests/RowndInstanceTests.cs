using SuperTokens.Rownd.Foundation;
using Xunit;

namespace Rownd.UnitTests;

public sealed class RowndInstanceTests
{
    private static readonly RowndConfiguration Config = new("key", "https://api.example.test", "/auth", "https://hub.example.test", "testapp");

    [Fact]
    public async Task NoSessionAndRetryableFailureRemainDifferent()
    {
        var bridge = new Bridge();
        using var instance = new RowndInstance(bridge, action => action());
        await instance.ConfigureAsync(Config);
        bridge.Emit(new(true, true, "user"));
        bridge.TokenError = "network";
        await Assert.ThrowsAsync<InvalidOperationException>(() => instance.GetAccessTokenAsync());
        Assert.True(instance.State.IsAuthenticated);
        bridge.TokenError = null;
        Assert.Null(await instance.GetAccessTokenAsync());
    }

    [Fact]
    public async Task NativeConfigurationFailurePreventsPresentationAndReconfiguration()
    {
        var bridge = new Bridge { ConfigurationError = "bootstrap" };
        using var instance = new RowndInstance(bridge, action => action());
        await Assert.ThrowsAsync<InvalidOperationException>(() => instance.ConfigureAsync(Config));
        Assert.Throws<InvalidOperationException>(instance.RequestSignIn);
        await Assert.ThrowsAsync<InvalidOperationException>(() => instance.ConfigureAsync(Config));
        Assert.Equal(0, bridge.SignIns);
    }

    [Fact]
    public async Task DisposalCancelsPendingTokenAndIgnoresQueuedState()
    {
        var queue = new Queue<Action>();
        var bridge = new Bridge { DelayToken = true };
        var instance = new RowndInstance(bridge, queue.Enqueue);
        var configure = instance.ConfigureAsync(Config);
        queue.Dequeue()();
        await configure;
        var token = instance.GetAccessTokenAsync();
        queue.Dequeue()();
        bridge.Emit(new(true, true, "user"));
        instance.Dispose();
        while (queue.TryDequeue(out var action)) action();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => token);
        Assert.False(instance.State.IsAuthenticated);
        Assert.True(bridge.Disposed);
    }

    [Fact]
    public async Task StateIsDispatchedAndDeduplicatedAndSignOutWaitsForNativeState()
    {
        var queue = new Queue<Action>();
        var bridge = new Bridge();
        using var instance = new RowndInstance(bridge, queue.Enqueue);
        var configure = instance.ConfigureAsync(Config);
        queue.Dequeue()();
        await configure;
        var notifications = 0;
        instance.StateChanged += (_, _) => notifications++;
        bridge.Emit(new(true, true, "user"));
        Assert.False(instance.State.IsAuthenticated);
        queue.Dequeue()();
        bridge.Emit(new(true, true, "user"));
        queue.Dequeue()();
        instance.SignOut();
        queue.Dequeue()();
        Assert.True(instance.State.IsAuthenticated);
        Assert.Equal(1, notifications);
        bridge.Emit(new(true, false, null));
        queue.Dequeue()();
        Assert.False(instance.State.IsAuthenticated);
    }

    [Fact]
    public async Task FirstCallbackWinsAndErrorsDoNotBecomeTokens()
    {
        var bridge = new Bridge { DelayToken = true };
        using var instance = new RowndInstance(bridge, action => action());
        await instance.ConfigureAsync(Config);
        var token = instance.GetAccessTokenAsync();
        bridge.TokenCompletion!("must-not-leak", "network");
        bridge.TokenCompletion!("late-token", null);
        await Assert.ThrowsAsync<InvalidOperationException>(() => token);
        var retry = instance.GetAccessTokenAsync();
        bridge.TokenCompletion!("current-token", null);
        Assert.Equal("current-token", await retry);
    }

    [Fact]
    public async Task DisposalBeforeDispatchCancelsConfigurationWithoutCallingNative()
    {
        var queue = new Queue<Action>();
        var bridge = new Bridge();
        var instance = new RowndInstance(bridge, queue.Enqueue);
        var configure = instance.ConfigureAsync(Config);
        instance.Dispose();
        instance.Dispose();
        while (queue.TryDequeue(out var action)) action();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => configure);
        Assert.Equal(0, bridge.Configurations);
        Assert.Equal(1, bridge.Disposals);
        await Assert.ThrowsAsync<ObjectDisposedException>(() => instance.GetAccessTokenAsync());
    }

    [Fact]
    public async Task LateCompletionAfterDisposalCannotReviveOperation()
    {
        var bridge = new Bridge { DelayToken = true };
        var instance = new RowndInstance(bridge, action => action());
        await instance.ConfigureAsync(Config);
        var token = instance.GetAccessTokenAsync();
        instance.Dispose();
        bridge.TokenCompletion!("late-token", null);
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => token);
    }

    [Fact]
    public async Task DispatchFailureFaultsConfigurationAndStillPreventsRetry()
    {
        var reject = true;
        using var instance = new RowndInstance(new Bridge(), action =>
        {
            if (reject) throw new InvalidOperationException("dispatcher unavailable");
            action();
        });
        var configure = instance.ConfigureAsync(Config);
        await Assert.ThrowsAsync<InvalidOperationException>(() => configure);
        reject = false;
        await Assert.ThrowsAsync<InvalidOperationException>(() => instance.ConfigureAsync(Config));
    }

    [Fact]
    public async Task UnsubscribedUiDoesNotReceiveQueuedNotification()
    {
        var queue = new Queue<Action>();
        var bridge = new Bridge();
        using var instance = new RowndInstance(bridge, queue.Enqueue);
        var configure = instance.ConfigureAsync(Config);
        queue.Dequeue()();
        await configure;
        var notifications = 0;
        EventHandler<RowndState> handler = (_, _) => notifications++;
        instance.StateChanged += handler;
        bridge.Emit(new(true, true, "user"));
        instance.StateChanged -= handler;
        queue.Dequeue()();
        Assert.Equal(0, notifications);
        Assert.Equal("user", instance.State.UserId);
    }

    private sealed class Bridge : INativeBridge
    {
        public string? ConfigurationError { get; init; }
        public string? TokenError { get; set; }
        public bool DelayToken { get; init; }
        public int SignIns { get; private set; }
        public bool Disposed { get; private set; }
        public int Configurations { get; private set; }
        public int Disposals { get; private set; }
        public Action<string?, string?>? TokenCompletion { get; private set; }
        public event Action<RowndState>? StateChanged;
        public void Emit(RowndState state) => StateChanged?.Invoke(state);
        public void Configure(RowndConfiguration config, Action<string?> completion)
        {
            Configurations++;
            completion(ConfigurationError);
        }

        public void RequestSignIn() => SignIns++;
        public void GetAccessToken(Action<string?, string?> completion)
        {
            TokenCompletion = completion;
            if (!DelayToken) completion(null, TokenError);
        }

        public void SignOut() { }
        public void Dispose()
        {
            Disposals++;
            Disposed = true;
        }
    }
}
