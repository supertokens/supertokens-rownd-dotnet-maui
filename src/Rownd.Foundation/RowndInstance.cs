namespace SuperTokens.Rownd.Foundation;

public sealed class RowndInstance : IDisposable
{
    private readonly INativeBridge bridge;
    private readonly Action<Action> dispatch;
    private readonly CancellationTokenSource lifetime = new();
    private readonly object gate = new();
    private Task? configuration;
    private volatile bool disposed;

    public RowndInstance(INativeBridge bridge, Action<Action> dispatch)
    {
        this.bridge = bridge ?? throw new ArgumentNullException(nameof(bridge));
        this.dispatch = dispatch ?? throw new ArgumentNullException(nameof(dispatch));
        bridge.StateChanged += OnStateChanged;
    }

    public RowndState State { get; private set; } = new(false, false, null);
    public event EventHandler<RowndState>? StateChanged;

    public Task ConfigureAsync(RowndConfiguration config)
    {
        ArgumentNullException.ThrowIfNull(config);
        lock (gate)
        {
            ObjectDisposedException.ThrowIf(disposed, this);
            if (configuration != null)
                throw new InvalidOperationException("Configure once per process. Native reconfiguration is unsupported.");
            configuration = InvokeAsync<bool>(done => bridge.Configure(config, error => done(true, error)));
            return configuration;
        }
    }

    public void RequestSignIn()
    {
        RequireReady();
        DispatchOperation(bridge.RequestSignIn);
    }

    public void SignOut()
    {
        RequireReady();
        DispatchOperation(bridge.SignOut);
    }

    public Task<string?> GetAccessTokenAsync()
    {
        RequireReady();
        return InvokeAsync<string?>(bridge.GetAccessToken);
    }

    private void RequireReady()
    {
        ObjectDisposedException.ThrowIf(disposed, this);
        if (configuration?.IsCompletedSuccessfully != true)
            throw new InvalidOperationException("Await ConfigureAsync before invoking authentication.");
    }

    private void DispatchOperation(Action action) => dispatch(() =>
    {
        if (!disposed) action();
    });

    private Task<T> InvokeAsync<T>(Action<Action<T, string?>> invoke)
    {
        var completion = new TaskCompletionSource<T>(TaskCreationOptions.RunContinuationsAsynchronously);
        dispatch(() =>
        {
            if (disposed) return;
            try
            {
                invoke((value, error) =>
                {
                    if (error is null) completion.TrySetResult(value);
                    else completion.TrySetException(new InvalidOperationException($"Native Rownd operation failed: {error}"));
                });
            }
            catch (Exception error)
            {
                completion.TrySetException(error);
            }
        });
        return completion.Task.WaitAsync(lifetime.Token);
    }

    private void OnStateChanged(RowndState state) => dispatch(() =>
    {
        if (disposed || state == State) return;
        State = state;
        StateChanged?.Invoke(this, state);
    });

    public void Dispose()
    {
        lock (gate)
        {
            if (disposed) return;
            disposed = true;
            bridge.StateChanged -= OnStateChanged;
            lifetime.Cancel();
        }

        dispatch(bridge.Dispose);
    }
}
