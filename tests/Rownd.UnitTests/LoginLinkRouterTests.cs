using SuperTokens.Rownd.Foundation;
using SuperTokens.Rownd.Maui;
using Xunit;

namespace Rownd.UnitTests;

public sealed class LoginLinkRouterTests
{
    private const string Link = "testapp://account/login?code=a%2Fb%2Bc&next=%252F#token=%2f+%3D";
    private static readonly RowndConfiguration Config = new("key", "https://api.example.test", "/auth", "https://hub.example.test", "testapp");

    [Fact]
    public void QueuedDuplicatesCoalesceAndLatestDistinctLinkWinsWithExactEncoding()
    {
        var forwarded = new List<string>();
        using var router = Create(value =>
        {
            forwarded.Add(value);
            return true;
        });
        var distinct = Link.Replace("%2f", "%2F", StringComparison.Ordinal);
        for (var i = 0; i < 20; i++) Assert.True(router.Handle(Link));
        Assert.True(router.Handle(distinct));
        Assert.Empty(forwarded);
        router.Configure(Config);
        router.NativeReady();
        router.NativeReady();
        Assert.True(router.Handle(distinct));
        Assert.Equal(new[] { distinct }, forwarded);
    }

    [Fact]
    public void SuccessfulCallbacksHaveFixedNonSlidingExpiryAllowingReplay()
    {
        var clock = new Clock();
        var calls = 0;
        using var router = Create(
            _ =>
            {
                calls++;
                return true;
            },
            clock);
        router.NativeReady();
        Assert.True(router.Handle(Link));
        clock.Advance(TimeSpan.FromMilliseconds(1900));
        Assert.True(router.Handle(Link));
        Assert.Equal(1, calls);
        clock.Advance(TimeSpan.FromMilliseconds(100));
        Assert.True(router.Handle(Link));
        Assert.Equal(2, calls);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void InflightDuplicateIsRecognizedWithoutNativeReentryEvenAfterWindow(bool queued)
    {
        var clock = new Clock();
        var calls = 0;
        LoginLinkRouter router = null!;
        using (router = Create(
            value =>
            {
                calls++;
                clock.Advance(TimeSpan.FromMinutes(1));
                Assert.True(router.Handle(value));
                return true;
            },
            clock))
        {
            if (queued) Assert.True(router.Handle(Link));
            router.NativeReady();
            Assert.True(router.Handle(Link));
            Assert.True(router.Handle(Link));
            Assert.Equal(1, calls);
        }
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void FailedHandoffCanRetryImmediately(bool throws)
    {
        var calls = 0;
        using var router = Create(_ =>
        {
            if (++calls > 1) return true;
            if (throws) throw new InvalidOperationException("native handoff failed");
            return false;
        });
        router.NativeReady();
        Assert.True(router.Handle(Link));
        Assert.True(router.Handle(Link));
        Assert.True(router.Handle(Link));
        Assert.Equal(2, calls);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public void FailedLatestQueuedSubmissionDoesNotPoisonRetry(bool throws)
    {
        var forwarded = new List<string>();
        using var router = Create(value =>
        {
            forwarded.Add(value);
            if (forwarded.Count > 1) return true;
            if (throws) throw new InvalidOperationException("native handoff failed");
            return false;
        });
        Assert.True(router.Handle(Link));
        Assert.True(router.Handle(Link + "other"));
        router.NativeReady();
        Assert.True(router.Handle(Link));
        Assert.Equal(new[] { Link + "other", Link }, forwarded);
    }

    [Fact]
    public void QueueCapacityIsOneAndNewDistinctCallbackReplacesOlder()
    {
        var calls = 0;
        using var router = Create(_ =>
        {
            calls++;
            return true;
        });
        for (var i = 0; i < LoginLinkRouter.PendingLimit; i++) Assert.True(router.Handle(Link + i));
        Assert.True(router.Handle(Link + 0));
        Assert.True(router.Handle(Link + "overflow"));
        router.NativeReady();
        Assert.Equal(LoginLinkRouter.PendingLimit, calls);
        Assert.True(router.Handle(Link + "overflow"));
        Assert.Equal(1, calls);
    }

    [Fact]
    public void RecentCacheIsBoundedAndEvictsOldestSuccess()
    {
        var clock = new Clock();
        var calls = 0;
        using var router = Create(
            _ =>
            {
                calls++;
                return true;
            },
            clock);
        router.NativeReady();
        for (var i = 0; i <= LoginLinkRouter.RecentLimit; i++)
        {
            Assert.True(router.Handle(Link + i));
            clock.Advance(TimeSpan.FromMilliseconds(1));
        }

        Assert.True(router.Handle(Link + 1));
        Assert.Equal(LoginLinkRouter.RecentLimit + 1, calls);
        Assert.True(router.Handle(Link + 0));
        Assert.Equal(LoginLinkRouter.RecentLimit + 2, calls);
    }

    [Theory]
    [InlineData("testapp://account/verify-email?token=secret")]
    [InlineData("https://hub.example.test/account/verify-email?token=secret")]
    [InlineData("https://unrelated.example.test/account/login")]
    [InlineData("otherapp://account/login")]
    [InlineData("testapp://elsewhere/login")]
    [InlineData("testapp://account/logout")]
    [InlineData("not a URI")]
    public void UnrelatedAndEmailVerificationLinksRemainUnhandled(string value)
    {
        var calls = 0;
        using var router = Create(_ =>
        {
            calls++;
            return true;
        });
        Assert.False(router.Handle(value));
        Assert.Equal(0, calls);
        router.NativeReady();
        Assert.False(router.Handle(value));
        Assert.Equal(0, calls);
    }

    [Fact]
    public void HttpsLoginPreservesEncodedString()
    {
        var forwarded = new List<string>();
        using var router = Create(value =>
        {
            forwarded.Add(value);
            return true;
        });
        router.NativeReady();
        var value = Link.Replace("testapp://account", "https://hub.example.test/account", StringComparison.Ordinal);
        Assert.True(router.Handle(value));
        Assert.True(router.Handle(value));
        Assert.Equal(new[] { value }, forwarded);
    }

    [Fact]
    public void UnconfiguredAndDisposedRouterRejectCallbacksAndNeverDrainOldQueue()
    {
        var calls = 0;
        using var router = new LoginLinkRouter(_ =>
        {
            calls++;
            return true;
        });
        Assert.False(router.Handle(Link));
        router.Configure(Config);
        Assert.True(router.Handle(Link));
        router.Dispose();
        router.Configure(Config);
        router.NativeReady();
        Assert.False(router.Handle(Link));
        Assert.Equal(0, calls);
    }

    [Fact]
    public void DisposalDuringHandoffIsTerminalEvenAfterLateSuccess()
    {
        var calls = 0;
        LoginLinkRouter router = null!;
        using (router = Create(_ =>
        {
            calls++;
            router.Dispose();
            return true;
        }))
        {
            router.NativeReady();
            Assert.True(router.Handle(Link));
            router.Configure(Config);
            router.NativeReady();
            Assert.False(router.Handle(Link));
            Assert.Equal(1, calls);
        }
    }

    private static LoginLinkRouter Create(Func<string, bool> forward, TimeProvider? clock = null)
    {
        var router = new LoginLinkRouter(forward, clock);
        router.Configure(Config);
        return router;
    }

    [Fact]
    public void InitializationAndHostResumeMustBothCompleteBeforeDelivery()
    {
        var forwarded = new List<string>();
        using var router = Create(value => { forwarded.Add(value); return true; });
        router.Suspend();
        Assert.True(router.Handle(Link));
        router.NativeReady();
        Assert.Empty(forwarded);
        router.Resume();
        router.Resume();
        Assert.Equal(new[] { Link }, forwarded);
        router.Suspend();
        Assert.True(router.Handle(Link + "new"));
        Assert.Single(forwarded);
        router.Resume();
        Assert.Equal(2, forwarded.Count);
    }

    [Fact]
    public void ExpiredStartupQueueIsDroppedAndCapacityRecovered()
    {
        var clock = new Clock();
        var forwarded = new List<string>();
        using var router = Create(value => { forwarded.Add(value); return true; }, clock);
        for (var i = 0; i < LoginLinkRouter.PendingLimit; i++) Assert.True(router.Handle(Link + i));
        clock.Advance(LoginLinkRouter.PendingLifetime);
        Assert.True(router.Handle(Link + "fresh"));
        router.NativeReady();
        Assert.Equal(new[] { Link + "fresh" }, forwarded);
    }

    [Theory]
    [InlineData("https://hub.example.test:8443/account/login")]
    [InlineData("https://user@hub.example.test/account/login")]
    [InlineData("testapp://user@account/login")]
    public void OtherOriginsAndUserInfoRemainUnhandled(string value)
    {
        using var router = Create(_ => throw new Exception("Must not forward"));
        Assert.False(router.Handle(value));
    }

    [Fact]
    public void OversizedLinkCannotOccupyReadinessQueue()
    {
        using var router = Create(_ => true);
        var oversized = Link + new string('x', 16384);
        Assert.True(router.Recognizes(oversized));
        Assert.False(router.Handle(oversized));
        router.Dispose();
        Assert.True(router.Recognizes(Link));
        Assert.False(router.Handle(Link));
    }

    private sealed class Clock : TimeProvider
    {
        private long timestamp;
        public override long TimestampFrequency => TimeSpan.TicksPerSecond;
        public override long GetTimestamp() => timestamp;
        public void Advance(TimeSpan elapsed) => timestamp += elapsed.Ticks;
    }
}
