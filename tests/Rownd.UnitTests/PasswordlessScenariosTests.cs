using System.Net;
using System.Text.Json;
using Rownd.Harness;
using Rownd.IntegrationTests;
using Xunit;

namespace Rownd.UnitTests;

// Scripted observations test orchestration only, never native authentication.
public sealed class PasswordlessScenariosTests
{
    private const string Phone = "+15555550123";
    private const string Link = "https://hub.example.com/account/login?preAuthSessionId=a%2Fb&displayContext=mobile_app#c%2Bd";
    private static readonly SessionObservation Valid = new("user", "session", 1, false, true);

    [Fact]
    public async Task StaleCaptureStopsBeforeCreatingChallenge()
    {
        using var fixture = new Fixture(stale: true);
        await Assert.ThrowsAsync<InvalidOperationException>(() => fixture.RunAsync());
        Assert.Equal(new[] { "reset" }, fixture.Driver.Calls);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public async Task ForwardsExactEncodedLinkOnInitialOpenAndReplay(bool cold)
    {
        using var fixture = new Fixture();
        await fixture.Scenarios.PhoneMagicLinkAsync(Phone, "user", cold, CancellationToken.None);
        Assert.Equal(new[] { Link, Link }, fixture.Driver.Links);
        Assert.Equal(new[] { "reset", "phone", cold ? "terminate" : "background", "open", "protected", "open", "protected", "signout" }, fixture.Driver.Calls);
    }

    [Fact]
    public async Task PreCancelledScenarioHasNoEffects()
    {
        using var fixture = new Fixture();
        using var cancellation = new CancellationTokenSource();
        cancellation.Cancel();
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => fixture.RunAsync(cancellation.Token));
        Assert.Empty(fixture.Driver.Calls);
        Assert.Equal(0, fixture.Requests);
    }

    [Fact]
    public async Task CancellationWhileWaitingForCaptureStopsBeforeDispatch()
    {
        using var cancellation = new CancellationTokenSource();
        using var fixture = new Fixture(onPoll: cancellation.Cancel);
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => fixture.RunAsync(cancellation.Token));
        Assert.Equal(new[] { "reset", "phone" }, fixture.Driver.Calls);
        Assert.Empty(fixture.Driver.Links);
    }

    public static TheoryData<SessionObservation> InvalidSessions => new()
    {
        Valid with { UserId = "other" },
        Valid with { HubVisible = true },
        Valid with { HostResponsive = false },
        Valid with { SuccessfulConsumes = 2 },
        Valid with { SessionId = "" },
    };

    [Theory]
    [MemberData(nameof(InvalidSessions))]
    public async Task RejectsInvalidInitialSession(SessionObservation observation)
    {
        using var fixture = new Fixture();
        fixture.Driver.Sessions.Enqueue(observation);
        await Assert.ThrowsAsync<InvalidOperationException>(() => fixture.RunAsync());
        Assert.Single(fixture.Driver.Links);
        Assert.DoesNotContain("signout", fixture.Driver.Calls);
    }

    [Theory]
    [InlineData(2, "session")]
    [InlineData(1, "replacement")]
    public async Task RejectsReplayConsumeOrSessionReplacement(int consumes, string session)
    {
        using var fixture = new Fixture();
        fixture.Driver.Sessions.Enqueue(Valid);
        fixture.Driver.Sessions.Enqueue(Valid with { SuccessfulConsumes = consumes, SessionId = session });
        await Assert.ThrowsAsync<InvalidOperationException>(() => fixture.RunAsync());
        Assert.Equal(2, fixture.Driver.Links.Count);
        Assert.DoesNotContain("signout", fixture.Driver.Calls);
    }

    [Fact]
    public async Task EmailOtpUsesVerifiedIdentityBeforeSignOut()
    {
        using var fixture = new Fixture();
        await fixture.Scenarios.EmailOtpAsync("test@example.com", "user", CancellationToken.None);
        Assert.Equal(new[] { "reset", "otp", "protected", "signout" }, fixture.Driver.Calls);
        Assert.Equal(0, fixture.Requests);
    }

    [Fact]
    public async Task DelayedStartupDispatchesBeforeReleaseAndVerifiesAfterward()
    {
        using var fixture = new Fixture();
        await fixture.Scenarios.PhoneMagicLinkDuringStartupAsync(Phone, "user", fixture.Driver, CancellationToken.None);
        Assert.Equal(new[] { "reset", "phone", "terminate", "hold", "open", "held-consumes", "release", "protected", "open", "protected", "signout" }, fixture.Driver.Calls);
    }

    [Fact]
    public async Task PrematureConsumeFailsButReleasesStartupGate()
    {
        using var fixture = new Fixture();
        fixture.Driver.HeldConsumes = 1;
        await Assert.ThrowsAsync<InvalidOperationException>(() => fixture.Scenarios.PhoneMagicLinkDuringStartupAsync(Phone, "user", fixture.Driver, CancellationToken.None));
        Assert.Equal("release", fixture.Driver.Calls.Last());
        Assert.DoesNotContain("protected", fixture.Driver.Calls);
    }

    [Fact]
    public async Task CancelledStartupStillReleasesGateWithFreshToken()
    {
        using var cancellation = new CancellationTokenSource();
        using var fixture = new Fixture();
        fixture.Driver.OnHold = cancellation.Cancel;
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => fixture.Scenarios.PhoneMagicLinkDuringStartupAsync(Phone, "user", fixture.Driver, cancellation.Token));
        Assert.Equal("release", fixture.Driver.Calls.Last());
        Assert.Empty(fixture.Driver.Links);
    }

    [Theory]
    [InlineData(false)]
    [InlineData(true)]
    public async Task ComposesRefreshBeforeSignOutAfterEitherLogin(bool phone)
    {
        var refresh = new RefreshDriver();
        using var fixture = new Fixture(refresh: refresh);
        fixture.Driver.OnSignOut = () =>
        {
            Assert.Equal(3, refresh.Calls.Count(call => call == "read"));
            Assert.Equal("observe", refresh.Calls.Last());
        };
        if (phone)
        {
            await fixture.RunAsync();
        }
        else
        {
            await fixture.Scenarios.EmailOtpAsync("test@example.com", "user", CancellationToken.None);
        }

        Assert.Equal("signout", fixture.Driver.Calls.Last());
    }

    [Fact]
    public async Task RefreshRequiresExpiryNativeRefreshAndRecoveryInSameSession()
    {
        var driver = new RefreshDriver();
        await PasswordlessScenarios.RefreshRecoveryAsync(driver, "user", CancellationToken.None);
        Assert.Equal(new[] { "observe", "save", "expiry", "old-token", "read", "protected", "observe", "observe", "save", "outage-on", "expiry", "old-token", "read", "observe", "outage-off", "read", "protected", "observe" }, driver.Calls);
    }

    [Theory]
    [InlineData("not-expired")]
    [InlineData("no-refresh")]
    [InlineData("logout")]
    [InlineData("replacement")]
    [InlineData("outage-no-session")]
    public async Task RejectsInvalidRefreshEvidence(string fault)
    {
        var driver = new RefreshDriver { Fault = fault };
        await Assert.ThrowsAsync<InvalidOperationException>(() => PasswordlessScenarios.RefreshRecoveryAsync(driver, "user", CancellationToken.None));
        if (driver.Calls.Contains("outage-on")) Assert.Contains("outage-off", driver.Calls);
    }

    [Fact]
    public async Task CancellationDuringOutageRestoresBackendWithFreshCleanupToken()
    {
        using var cancellation = new CancellationTokenSource();
        var driver = new RefreshDriver { OnOutage = cancellation.Cancel };
        await Assert.ThrowsAnyAsync<OperationCanceledException>(() => PasswordlessScenarios.RefreshRecoveryAsync(driver, "user", cancellation.Token));
        Assert.Equal("outage-off", driver.Calls.Last());
    }

    private sealed class Fixture : IDisposable
    {
        private readonly HttpClient http;
        public Fixture(bool stale = false, Action? onPoll = null, IRefreshDeviceDriver? refresh = null)
        {
            http = new HttpClient(new ScriptedHttp(request =>
            {
                Requests++;
                Assert.Equal("?phoneNumber=%2B15555550123", request.RequestUri!.Query);
                if (Requests == 1 && !stale) return new(HttpStatusCode.NotFound);
                if (onPoll is not null)
                {
                    onPoll();
                    return new(HttpStatusCode.NotFound);
                }

                return new(HttpStatusCode.OK)
                {
                    Content = new StringContent(JsonSerializer.Serialize(new { phoneNumber = Phone, urlWithLinkCode = Link })),
                };
            })) { BaseAddress = new Uri("http://fixture.invalid/") };
            Scenarios = new PasswordlessScenarios(new HarnessClient(http), Driver, refresh);
        }

        public int Requests { get; private set; }
        public RecordingDriver Driver { get; } = new();
        public PasswordlessScenarios Scenarios { get; }
        public Task RunAsync(CancellationToken cancellationToken = default) => Scenarios.PhoneMagicLinkAsync(Phone, "user", false, cancellationToken);
        public void Dispose() => http.Dispose();
    }

    private sealed class ScriptedHttp(Func<HttpRequestMessage, HttpResponseMessage> response) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken)
        {
            cancellationToken.ThrowIfCancellationRequested();
            return Task.FromResult(response(request));
        }
    }

    private sealed class RecordingDriver : IPasswordlessDeviceDriver, IDelayedStartupDeviceDriver
    {
        public List<string> Calls { get; } = new();
        public List<string> Links { get; } = new();
        public Queue<SessionObservation> Sessions { get; } = new();
        public int HeldConsumes { get; set; }
        public Action? OnHold { get; set; }
        public Action? OnSignOut { get; set; }
        public Task ResetAsync(CancellationToken token) => Record("reset", token);
        public Task StartPhoneChallengeInHubAsync(string phone, CancellationToken token) => Record("phone", token);
        public Task CompleteEmailOtpInHubAsync(string email, CancellationToken token) => Record("otp", token);
        public Task BackgroundAsync(bool terminateProcess, CancellationToken token) => Record(terminateProcess ? "terminate" : "background", token);
        public async Task SignOutFromSampleAndAssertNoSessionAsync(CancellationToken token)
        {
            await Record("signout", token);
            OnSignOut?.Invoke();
        }

        public async Task HoldInitializationOnNextLaunchAsync(CancellationToken token)
        {
            await Record("hold", token);
            OnHold?.Invoke();
        }

        public Task ReleaseInitializationAsync(CancellationToken token) => Record("release", token);

        public async Task OpenExternalLinkAsync(string link, CancellationToken token)
        {
            await Record("open", token);
            Links.Add(link);
        }

        public async Task<SessionObservation> CallProtectedApiFromSampleAsync(CancellationToken token)
        {
            await Record("protected", token);
            return Sessions.Count > 0 ? Sessions.Dequeue() : Valid;
        }

        public async Task<int> ReadSuccessfulConsumesWhileInitializationHeldAsync(CancellationToken token)
        {
            await Record("held-consumes", token);
            return HeldConsumes;
        }

        private Task Record(string call, CancellationToken token)
        {
            token.ThrowIfCancellationRequested();
            Calls.Add(call);
            return Task.CompletedTask;
        }
    }

    private sealed class RefreshDriver : IRefreshDeviceDriver
    {
        private int reads;
        private bool outage;
        public List<string> Calls { get; } = new();
        public string? Fault { get; init; }
        public Action? OnOutage { get; init; }
        public Task SaveCurrentNativeTokenAsync(CancellationToken token) => Record("save", token);
        public Task WaitForSavedTokenExpiryAsync(CancellationToken token) => Record("expiry", token);

        public async Task<RefreshObservation> ObserveAsync(CancellationToken token)
        {
            await Record("observe", token);
            var session = Fault == "replacement" && reads > 0 ? Valid with { SessionId = "other" } : Valid;
            return new(session, Fault == "no-refresh" ? 0 : Math.Min(reads, 1) + (reads >= 3 ? 1 : 0), Fault == "logout" && outage ? 1 : 0);
        }

        public async Task<int> RequestWithSavedTokenWithoutRefreshAsync(CancellationToken token)
        {
            await Record("old-token", token);
            return Fault == "not-expired" ? 200 : 401;
        }

        public async Task SetRefreshUnavailableAsync(bool unavailable, CancellationToken token)
        {
            await Record(unavailable ? "outage-on" : "outage-off", token);
            outage = unavailable;
            if (unavailable) OnOutage?.Invoke();
        }

        public async Task<TokenReadOutcome> ReadTokenThroughSampleAsync(CancellationToken token)
        {
            await Record("read", token);
            reads++;
            return outage ? (Fault == "outage-no-session" ? TokenReadOutcome.NoSession : TokenReadOutcome.RetryableFailure) : TokenReadOutcome.Success;
        }

        public async Task<SessionObservation> CallProtectedApiFromSampleAsync(CancellationToken token)
        {
            await Record("protected", token);
            return Valid;
        }

        private Task Record(string call, CancellationToken token)
        {
            token.ThrowIfCancellationRequested();
            Calls.Add(call);
            return Task.CompletedTask;
        }
    }
}
