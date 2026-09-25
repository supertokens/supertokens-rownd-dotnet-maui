using SuperTokens.Rownd.Foundation;
using SuperTokens.Rownd.Maui;
using Xunit;

namespace Rownd.UnitTests;

public sealed class LoginLinkSchedulingTests
{
    private const string First = "testapp://account/login?code=first%2f#token=%252B+";
    private const string Latest = "testapp://account/login?code=latest%2F#token=%252b+";

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public async Task DelayedSingleSlotNativeGetsOnlyLatestCallbackAndOnePresentation(bool warm)
    {
        var turns = new Queue<Action>();
        var native = new DeferredSingleSlotNative();
        using var router = Create(native.Submit, turns.Enqueue);
        if (warm) router.NativeReady();
        Assert.True(router.Handle(First));
        Assert.True(router.Handle(Latest));
        Assert.True(router.Handle(Latest));
        router.NativeReady();
        Assert.Single(turns);
        Assert.Empty(native.Read);
        turns.Dequeue()();
        Assert.Equal(1, native.Presentations);
        Assert.Empty(native.Read);

        // Native reads later, after managed submission has already returned true.
        await native.ReadSlotAsync();
        Assert.Equal(new[] { Latest }, native.Read);
        Assert.Empty(turns);
    }

    [Fact]
    public async Task NewCallbackAfterSubmissionCanSupersedeUnreadNativeSlotByExplicitPolicy()
    {
        var turns = new Queue<Action>();
        var native = new DeferredSingleSlotNative();
        using var router = Create(native.Submit, turns.Enqueue);
        router.NativeReady();
        Assert.True(router.Handle(First));
        turns.Dequeue()();
        Assert.True(router.Handle(Latest));
        turns.Dequeue()();
        await native.ReadSlotAsync();
        Assert.Equal(new[] { Latest }, native.Read);
        Assert.Equal(2, native.Presentations);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void DeferredDispatchRechecksSuspensionAndDisposal(bool dispose)
    {
        var turns = new Queue<Action>();
        var native = new DeferredSingleSlotNative();
        using var router = Create(native.Submit, turns.Enqueue);
        router.NativeReady();
        router.Handle(First);
        if (dispose) router.Dispose(); else router.Suspend();
        turns.Dequeue()();
        Assert.Equal(0, native.Presentations);
        router.Resume();
        if (dispose)
        {
            Assert.Empty(turns);
        }
        else
        {
            turns.Dequeue()();
            Assert.Equal(1, native.Presentations);
        }
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void AsynchronousNativeRejectionOrThrowAllowsImmediateExactRetry(bool throws)
    {
        var turns = new Queue<Action>();
        var calls = 0;
        using var router = Create(
            _ =>
            {
                if (++calls > 1) return true;
                if (throws) throw new InvalidOperationException();
                return false;
            },
            turns.Enqueue);
        router.NativeReady();
        Assert.True(router.Handle(First));
        turns.Dequeue()();
        Assert.True(router.Handle(First));
        turns.Dequeue()();
        Assert.True(router.Handle(First));
        Assert.Equal(2, calls);
        Assert.Empty(turns);
    }

    private static LoginLinkRouter Create(Func<string, bool> submit, Action<Action> schedule)
    {
        var router = new LoginLinkRouter(submit, schedule: schedule);
        router.Configure(new RowndConfiguration("key", "https://api.example.test", "/auth", "https://hub.example.test", "testapp"));
        return router;
    }

    private sealed class DeferredSingleSlotNative
    {
        private string? slot;
        public int Presentations { get; private set; }
        public List<string> Read { get; } = new();
        public bool Submit(string value)
        {
            slot = value;
            Presentations++;
            return true;
        }

        public async Task ReadSlotAsync()
        {
            await Task.Yield();
            if (slot is { } value) Read.Add(value);
            slot = null;
        }
    }
}
