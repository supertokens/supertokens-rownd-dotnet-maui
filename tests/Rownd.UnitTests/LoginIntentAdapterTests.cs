using SuperTokens.Rownd.Foundation;
using SuperTokens.Rownd.Maui;
using Xunit;

namespace Rownd.UnitTests;

public sealed class LoginIntentAdapterTests
{
    private static readonly RowndConfiguration Config = new("key", "https://api.example.test", "/auth", "https://hub.example.test", "testapp");

    // Parsed fields are java.net.URI outputs, verified against the pinned parser
    // and native toHubUrl in MauiLoginOwnershipTest (no Android runtime needed).
    [Theory]
    [InlineData("testapp://user@account/login", "testapp", "account", "/login")]
    [InlineData("testapp://account:444/login", "testapp", "account", "/login")]
    [InlineData("testapp://account///login///", "testapp", "account", "///login///")]
    [InlineData("https://user@hub.example.test/account/login", "https", "hub.example.test", "/account/login")]
    [InlineData("https://hub.example.test:444/account/login", "https", "hub.example.test", "/account/login")]
    [InlineData("https://rownd-hub.supertokens.com/account/login", "https", "rownd-hub.supertokens.com", "/account/login")]
    [InlineData("https://tenant.rownd-hub.supertokens.com/account/login", "https", "tenant.rownd-hub.supertokens.com", "/account/login")]
    [InlineData("https://staging.supertokens-rownd-hub.pages.dev/account/login", "https", "staging.supertokens-rownd-hub.pages.dev", "/account/login")]
    [InlineData("https://supertokens-rownd-hub.pages.dev/account/login", "https", "supertokens-rownd-hub.pages.dev", "/account/login")]
    public void NativeOwnedButRejectedLoginCannotReachBaseBeforeReadyWhileSuspendedOrAfterDisposal(
        string value, string scheme, string host, string path)
    {
        var submissions = new List<string>();
        using var router = new LoginLinkRouter(url =>
        {
            submissions.Add(url);
            return true;
        });
        router.Configure(Config);
        var intent = new TestIntent(value, "view", "host-extra");
        var adapter = Adapter(router, _ => router.OwnsAndroidLogin(scheme, host, path));
        Assert.False(router.Recognizes(value));
        AssertSanitized(adapter.Capture(intent), intent);
        router.Suspend();
        router.NativeReady();
        AssertSanitized(adapter.Capture(intent), intent);
        router.Resume();
        Assert.Empty(submissions);
        router.Dispose();
        AssertSanitized(adapter.Capture(intent), intent);
        router.NativeReady();
        router.Resume();
        Assert.Empty(submissions);
    }

    [Theory]
    [InlineData("https", "other.example.test", "/account/login")]
    [InlineData("https", "evilrownd-hub.supertokens.com", "/account/login")]
    [InlineData("https", "rownd-hub.supertokens.com.evil.test", "/account/login")]
    [InlineData("http", "hub.example.test", "/account/login")]
    [InlineData("otherapp", "account", "/login")]
    [InlineData("testapp", "elsewhere", "/login")]
    [InlineData("testapp", "account", "/verify-email")]
    [InlineData("https", "hub.example.test", "/account/verify-email")]
    [InlineData("testapp", "account", "/%6cogin")]
    public void UnrelatedHostAndNonLoginIntentsKeepTheirOriginalIdentityAndData(string scheme, string host, string path)
    {
        using var router = new LoginLinkRouter(_ => throw new Exception("Must not submit"));
        router.Configure(Config);
        var intent = new TestIntent($"{scheme}://{host}{path}", "view", "host-extra");
        var adapter = Adapter(router, _ => router.OwnsAndroidLogin(scheme, host, path));
        Assert.Same(intent, adapter.Capture(intent));
        router.Dispose();
        Assert.Same(intent, adapter.Capture(intent));
    }

    [Fact]
    public void AcceptedOwnedCallbackIsSanitizedImmediatelyAndDeliveredExactlyOnceAfterBothGates()
    {
        const string value = "testapp://account/login?code=%2f%2B#x=%252F+";
        var submissions = new List<string>();
        using var router = new LoginLinkRouter(url =>
        {
            submissions.Add(url);
            return true;
        });
        router.Configure(Config);
        var adapter = Adapter(router, _ => router.OwnsAndroidLogin("testapp", "account", "/login"));
        var intent = new TestIntent(value, "view", "host-extra");
        router.Suspend();
        AssertSanitized(adapter.Capture(intent), intent);
        AssertSanitized(adapter.Capture(intent), intent);
        router.NativeReady();
        Assert.Empty(submissions);
        router.Resume();
        Assert.Equal(new[] { value }, submissions);
        var edit = intent with { Action = "edit" };
        Assert.Same(edit, adapter.Capture(edit));
    }

    [Fact]
    public void OversizeAndDisposedAcceptedCallbacksStillCannotReachBase()
    {
        using var router = new LoginLinkRouter(_ => throw new Exception("Must not submit"));
        router.Configure(Config);
        var adapter = Adapter(router, _ => router.OwnsAndroidLogin("testapp", "account", "/login"));
        var oversized = new TestIntent("testapp://account/login?code=" + new string('x', 16384), "view", "extra");
        AssertSanitized(adapter.Capture(oversized), oversized);
        router.Dispose();
        var valid = oversized with { Data = "testapp://account/login" };
        AssertSanitized(adapter.Capture(valid), valid);
        Assert.Null(adapter.Capture(null));
    }

    private static LoginIntentAdapter<TestIntent> Adapter(LoginLinkRouter router, Func<string, bool> owns) =>
        new(router, intent => intent.Action == "view" ? intent.Data : null, owns, intent => intent with { Data = null });

    private static void AssertSanitized(TestIntent? captured, TestIntent original)
    {
        Assert.NotNull(captured);
        Assert.NotSame(original, captured);
        Assert.Null(captured.Data);
        Assert.NotNull(original.Data);
        Assert.Equal(original.Action, captured.Action);
        Assert.Equal(original.Extra, captured.Extra);
    }

    private sealed record TestIntent(string? Data, string Action, string Extra);
}
