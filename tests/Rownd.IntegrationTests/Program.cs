using Rownd.Harness;

if (Environment.GetEnvironmentVariable("ROWND_RUN_INTEGRATION") != "1")
{
    Console.Error.WriteLine("Set ROWND_RUN_INTEGRATION=1 explicitly to contact the shared fixture.");
    return 2;
}

try
{
    var origin = Environment.GetEnvironmentVariable("ROWND_HARNESS_URL") ?? throw new InvalidOperationException();
    using var http = new HttpClient(new HttpClientHandler { AllowAutoRedirect = false, UseCookies = false })
    {
        BaseAddress = new Uri(origin.TrimEnd('/') + "/"),
        Timeout = TimeSpan.FromSeconds(15),
    };
    var fixture = new HarnessClient(http);
    await fixture.VerifyEnvironmentAsync();
    if (args.Length == 1 && args[0] == "phone-capture")
    {
        var phone = Environment.GetEnvironmentVariable("ROWND_TEST_PHONE") ?? throw new InvalidOperationException();
        if (await fixture.ReadPhoneLinkAsync(phone) is null) throw new InvalidOperationException();
    }
    else if (args.Length != 1 || args[0] != "environment")
    {
        throw new InvalidOperationException();
    }

    Console.WriteLine("PASS: fixture, SuperTokens session guard and Rownd plugin route; no native authentication or device routing tested.");
    return 0;
}
catch
{
    // Response bodies and callback URLs can contain credentials.
    Console.Error.WriteLine("FAIL: check fixture URL, health, unauthenticated 401, Rownd plugin route, and fresh Hub-created capture for the exact phone.");
    return 1;
}
