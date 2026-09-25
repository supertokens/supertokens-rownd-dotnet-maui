using Rownd.Harness;

namespace Rownd.IntegrationTests;

public sealed record SessionObservation(string UserId, string SessionId, int SuccessfulConsumes, bool HubVisible, bool HostResponsive);

public enum TokenReadOutcome
{
    Success,
    RetryableFailure,
    NoSession,
}

public sealed record RefreshObservation(SessionObservation Session, int NativeRefreshes, int SignOutEvents);

public interface IRefreshDeviceDriver
{
    Task<RefreshObservation> ObserveAsync(CancellationToken cancellationToken);

    // Keep the actual token only in driver memory; expiry must be Core-issued, not edited JWT claims.
    Task SaveCurrentNativeTokenAsync(CancellationToken cancellationToken);
    Task WaitForSavedTokenExpiryAsync(CancellationToken cancellationToken);
    Task<int> RequestWithSavedTokenWithoutRefreshAsync(CancellationToken cancellationToken);
    Task SetRefreshUnavailableAsync(bool unavailable, CancellationToken cancellationToken);
    Task<TokenReadOutcome> ReadTokenThroughSampleAsync(CancellationToken cancellationToken);
    Task<SessionObservation> CallProtectedApiFromSampleAsync(CancellationToken cancellationToken);
}

public interface IDelayedStartupDeviceDriver
{
    Task HoldInitializationOnNextLaunchAsync(CancellationToken cancellationToken);
    Task<int> ReadSuccessfulConsumesWhileInitializationHeldAsync(CancellationToken cancellationToken);
    Task ReleaseInitializationAsync(CancellationToken cancellationToken);
}

// Implement with native UI automation against the MAUI sample in M2, not a mock auth provider.
public interface IPasswordlessDeviceDriver
{
    Task ResetAsync(CancellationToken cancellationToken);
    Task StartPhoneChallengeInHubAsync(string phone, CancellationToken cancellationToken);
    Task CompleteEmailOtpInHubAsync(string email, CancellationToken cancellationToken);
    Task BackgroundAsync(bool terminateProcess, CancellationToken cancellationToken);
    Task OpenExternalLinkAsync(string originalCapturedLink, CancellationToken cancellationToken);
    Task<SessionObservation> CallProtectedApiFromSampleAsync(CancellationToken cancellationToken);
    Task SignOutFromSampleAndAssertNoSessionAsync(CancellationToken cancellationToken);
}

public sealed class PasswordlessScenarios(HarnessClient harness, IPasswordlessDeviceDriver device, IRefreshDeviceDriver? refreshDriver = null)
{
    public async Task EmailOtpAsync(string email, string expectedUserId, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        await device.ResetAsync(cancellationToken);
        await device.CompleteEmailOtpInHubAsync(email, cancellationToken);
        AssertSession(await device.CallProtectedApiFromSampleAsync(cancellationToken), expectedUserId);
        if (refreshDriver is not null)
            await RefreshRecoveryAsync(refreshDriver, expectedUserId, cancellationToken);
        await device.SignOutFromSampleAndAssertNoSessionAsync(cancellationToken);
    }

    public async Task PhoneMagicLinkAsync(string uniquePhone, string expectedUserId, bool coldLaunch, CancellationToken cancellationToken)
        => await PhoneMagicLinkCoreAsync(uniquePhone, expectedUserId, coldLaunch, null, cancellationToken);

    public async Task PhoneMagicLinkDuringStartupAsync(string uniquePhone, string expectedUserId, IDelayedStartupDeviceDriver startup, CancellationToken cancellationToken)
        => await PhoneMagicLinkCoreAsync(uniquePhone, expectedUserId, true, startup, cancellationToken);

    private async Task PhoneMagicLinkCoreAsync(string uniquePhone, string expectedUserId, bool coldLaunch, IDelayedStartupDeviceDriver? startup, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        await device.ResetAsync(cancellationToken);
        if (await harness.ReadPhoneLinkAsync(uniquePhone, cancellationToken) is not null)
            throw new InvalidOperationException("Use a fresh phone/capture namespace for each independent scenario.");
        await device.StartPhoneChallengeInHubAsync(uniquePhone, cancellationToken);
        using var timeout = CancellationTokenSource.CreateLinkedTokenSource(cancellationToken);
        timeout.CancelAfter(TimeSpan.FromSeconds(30));
        string? link;
        while ((link = await harness.ReadPhoneLinkAsync(uniquePhone, timeout.Token)) is null)
            await Task.Delay(TimeSpan.FromMilliseconds(250), timeout.Token);
        await device.BackgroundAsync(coldLaunch, cancellationToken);
        if (startup is null)
        {
            await device.OpenExternalLinkAsync(link, cancellationToken);
        }
        else
        {
            try
            {
                await startup.HoldInitializationOnNextLaunchAsync(cancellationToken);
                await device.OpenExternalLinkAsync(link, cancellationToken);
                if (await startup.ReadSuccessfulConsumesWhileInitializationHeldAsync(cancellationToken) != 0)
                    throw new InvalidOperationException("Link consumed before native initialization was released.");
            }
            finally
            {
                using var cleanup = new CancellationTokenSource(TimeSpan.FromSeconds(15));
                await startup.ReleaseInitializationAsync(cleanup.Token);
            }
        }

        var initial = await device.CallProtectedApiFromSampleAsync(cancellationToken);
        AssertSession(initial, expectedUserId);
        await device.OpenExternalLinkAsync(link, cancellationToken);
        var replay = await device.CallProtectedApiFromSampleAsync(cancellationToken);
        AssertSession(replay, expectedUserId);
        if (initial.SessionId != replay.SessionId || initial.SuccessfulConsumes != replay.SuccessfulConsumes)
            throw new InvalidOperationException("Replay replaced the session or consumed twice.");
        if (refreshDriver is not null)
            await RefreshRecoveryAsync(refreshDriver, expectedUserId, cancellationToken);
        await device.SignOutFromSampleAndAssertNoSessionAsync(cancellationToken);
    }

    // Run after either real OTP or phone login; this method never creates a session.
    public static async Task RefreshRecoveryAsync(IRefreshDeviceDriver refresh, string expectedUserId, CancellationToken cancellationToken)
    {
        cancellationToken.ThrowIfCancellationRequested();
        var before = await refresh.ObserveAsync(cancellationToken);
        AssertSession(before.Session, expectedUserId);
        await ExpireSavedTokenAsync(refresh, cancellationToken);
        if (await refresh.ReadTokenThroughSampleAsync(cancellationToken) != TokenReadOutcome.Success)
            throw new InvalidOperationException("Native getter did not refresh the expired session.");
        await AssertRecoveredAsync(refresh, before, expectedUserId, cancellationToken);

        var beforeOutage = await refresh.ObserveAsync(cancellationToken);
        await refresh.SaveCurrentNativeTokenAsync(cancellationToken);
        try
        {
            await refresh.SetRefreshUnavailableAsync(true, cancellationToken);
            await refresh.WaitForSavedTokenExpiryAsync(cancellationToken);
            if (await refresh.RequestWithSavedTokenWithoutRefreshAsync(cancellationToken) != 401)
                throw new InvalidOperationException("Saved token must expire at the protected backend.");
            if (await refresh.ReadTokenThroughSampleAsync(cancellationToken) != TokenReadOutcome.RetryableFailure)
                throw new InvalidOperationException("Refresh outage must surface a recoverable getter error.");
            var failed = await refresh.ObserveAsync(cancellationToken);
            AssertStableSession(failed, beforeOutage, expectedUserId);
        }
        finally
        {
            using var cleanup = new CancellationTokenSource(TimeSpan.FromSeconds(15));
            await refresh.SetRefreshUnavailableAsync(false, cleanup.Token);
        }

        if (await refresh.ReadTokenThroughSampleAsync(cancellationToken) != TokenReadOutcome.Success)
            throw new InvalidOperationException("Native getter failed to recover without sign-in.");
        await AssertRecoveredAsync(refresh, beforeOutage, expectedUserId, cancellationToken);
    }

    private static async Task ExpireSavedTokenAsync(IRefreshDeviceDriver refresh, CancellationToken cancellationToken)
    {
        await refresh.SaveCurrentNativeTokenAsync(cancellationToken);
        await refresh.WaitForSavedTokenExpiryAsync(cancellationToken);
        if (await refresh.RequestWithSavedTokenWithoutRefreshAsync(cancellationToken) != 401)
            throw new InvalidOperationException("Saved token must expire at the protected backend.");
    }

    private static async Task AssertRecoveredAsync(IRefreshDeviceDriver refresh, RefreshObservation before, string expectedUserId, CancellationToken cancellationToken)
    {
        var verified = await refresh.CallProtectedApiFromSampleAsync(cancellationToken);
        AssertSession(verified, expectedUserId);
        if (verified.SessionId != before.Session.SessionId)
            throw new InvalidOperationException("Protected request verified a replacement session.");
        var after = await refresh.ObserveAsync(cancellationToken);
        AssertStableSession(after, before, expectedUserId);
        if (after.NativeRefreshes <= before.NativeRefreshes)
            throw new InvalidOperationException("No native refresh was observed.");
    }

    private static void AssertStableSession(RefreshObservation after, RefreshObservation before, string expectedUserId)
    {
        AssertSession(after.Session, expectedUserId);
        if (after.Session.SessionId != before.Session.SessionId || after.SignOutEvents != before.SignOutEvents)
            throw new InvalidOperationException("Refresh changed the session or emitted a false sign-out.");
    }

    private static void AssertSession(SessionObservation observed, string expectedUserId)
    {
        if (string.IsNullOrWhiteSpace(expectedUserId) || observed.UserId != expectedUserId ||
            string.IsNullOrWhiteSpace(observed.SessionId) || observed.SuccessfulConsumes != 1 ||
            observed.HubVisible || !observed.HostResponsive)
            throw new InvalidOperationException("Expected one verified session, dismissed Hub and responsive host.");
    }
}
