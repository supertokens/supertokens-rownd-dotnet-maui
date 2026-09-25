using System.Net;
using Rownd.Harness;
using SuperTokens.Rownd.Foundation;
using Xunit;

namespace Rownd.UnitTests;

public sealed class FoundationTests
{
    [Theory]
    [InlineData("https://api.example.com/path", "/auth", "customer")]
    [InlineData("https://secret@api.example.com", "/auth", "customer")]
    [InlineData("https://api.example.com", "//auth", "customer")]
    [InlineData("https://api.example.com", "/../auth", "customer")]
    [InlineData("https://api.example.com", "/auth", "https")]
    [InlineData("https://api.example.com", "/auth", "customer://")]
    public void RejectsAmbiguousConfiguration(string domain, string path, string scheme) =>
        Assert.Throws<ArgumentException>(() => new RowndConfiguration("key", domain, path, "https://hub.example.com", scheme));

    [Fact]
    public void AllowsExplicitLocalFixtureConfiguration()
    {
        var config = new RowndConfiguration("key", "http://10.0.2.2:3001", "/auth", "http://10.0.2.2:3000", "customer");
        Assert.Equal(3001, config.ApiDomain.Port);
        Assert.Equal("/auth", config.ApiBasePath);
    }

    [Theory]
    [InlineData("", "https://hub.example.com")]
    [InlineData("key", "file:///tmp/hub")]
    [InlineData("key", "https://hub.example.com/#secret")]
    public void RejectsMissingKeyAndInvalidHub(string key, string hub) =>
        Assert.ThrowsAny<ArgumentException>(() => new RowndConfiguration(key, "https://api.example.com", "/auth", hub, "customer"));

    [Fact]
    public async Task MissingCaptureRemainsPending()
    {
        using var handler = new ResponseHandler(_ => new(HttpStatusCode.NotFound));
        using var http = new HttpClient(handler) { BaseAddress = new Uri("http://localhost:3001/") };
        Assert.Null(await new HarnessClient(http).ReadPhoneLinkAsync("+15555550123"));
    }

    [Fact]
    public async Task CaptureFailureIsNotTreatedAsMissing()
    {
        using var handler = new ResponseHandler(_ => new(HttpStatusCode.InternalServerError));
        using var http = new HttpClient(handler) { BaseAddress = new Uri("http://localhost:3001/") };
        await Assert.ThrowsAsync<HttpRequestException>(() => new HarnessClient(http).ReadPhoneLinkAsync("+15555550123"));
    }

    [Fact]
    public async Task RejectsCaptureForAnotherPhone()
    {
        using var handler = new ResponseHandler(_ => new(HttpStatusCode.OK)
        {
            Content = new StringContent("{\"phoneNumber\":\"+15555550124\"}"),
        });
        using var http = new HttpClient(handler) { BaseAddress = new Uri("http://localhost:3001/") };
        await Assert.ThrowsAsync<InvalidOperationException>(() => new HarnessClient(http).ReadPhoneLinkAsync("+15555550123"));
    }

    [Fact]
    public async Task InvalidPhoneNeverContactsFixture()
    {
        using var handler = new ResponseHandler(_ => throw new InvalidOperationException("Unexpected request"));
        using var http = new HttpClient(handler) { BaseAddress = new Uri("http://localhost:3001/") };
        await Assert.ThrowsAsync<ArgumentException>(() => new HarnessClient(http).ReadPhoneLinkAsync("15555550123"));
    }

    [Fact]
    public async Task VerifiesHealthUnauthenticatedRejectionAndRowndPlugin()
    {
        var paths = new List<string>();
        using var handler = new ResponseHandler(request =>
        {
            var path = request.RequestUri!.AbsolutePath;
            paths.Add(path);
            return path switch
            {
                "/health" => new(HttpStatusCode.OK),
                "/test/protected" => new(HttpStatusCode.Unauthorized),
                "/auth/plugin/rownd/migrate" => new(HttpStatusCode.BadRequest)
                {
                    Content = new StringContent("{\"status\":\"ERROR\",\"message\":\"Missing authorization header\"}"),
                },
                _ => new(HttpStatusCode.NotFound),
            };
        });
        using var http = new HttpClient(handler) { BaseAddress = new Uri("http://localhost:3001/") };
        await new HarnessClient(http).VerifyEnvironmentAsync();
        Assert.Equal(new[] { "/health", "/test/protected", "/auth/plugin/rownd/migrate" }, paths);
    }

    [Fact]
    public async Task EncodesPhoneAndPreservesCapturedLink()
    {
        const string link = "https://hub.example.com/account/login?preAuthSessionId=a%2Fb&displayContext=mobile_app#c%2Bd";
        using var handler = new ResponseHandler(request =>
        {
            Assert.Equal("?phoneNumber=%2B15555550123", request.RequestUri!.Query);
            return new(HttpStatusCode.OK) { Content = new StringContent("{\"phoneNumber\":\"+15555550123\",\"urlWithLinkCode\":\"" + link + "\"}") };
        });
        using var http = new HttpClient(handler) { BaseAddress = new Uri("http://localhost:3001/") };
        Assert.Equal(link, await new HarnessClient(http).ReadPhoneLinkAsync("+15555550123"));
    }

    [Theory]
    [InlineData("https://hub.example.com/?preAuthSessionId=a#code")]
    [InlineData("https://hub.example.com/?preAuthSessionId=a&displayContext=mobile_app")]
    [InlineData("https://hub.example.com/?preAuthSessionId=&displayContext=mobile_app#code")]
    [InlineData("https://hub.example.com/?preAuthSessionId=a&displayContext=mobile_app&displayContext=web#code")]
    public void RejectsIncompleteOrAmbiguousCaptures(string link) =>
        Assert.Throws<InvalidOperationException>(() => HarnessClient.ValidateMobileLink(link));

    [Theory]
    [InlineData(HttpStatusCode.OK)]
    [InlineData(HttpStatusCode.Forbidden)]
    [InlineData(HttpStatusCode.InternalServerError)]
    public async Task RejectsUnprotectedOrBrokenFixture(HttpStatusCode status)
    {
        using var handler = new ResponseHandler(request => new(request.RequestUri!.AbsolutePath == "/health" ? HttpStatusCode.OK : status));
        using var http = new HttpClient(handler) { BaseAddress = new Uri("http://localhost:3001/") };
        await Assert.ThrowsAsync<InvalidOperationException>(() => new HarnessClient(http).VerifyEnvironmentAsync());
    }

    [Fact]
    public async Task RejectsBackendWithoutRowndPlugin()
    {
        using var handler = new ResponseHandler(request => new(request.RequestUri!.AbsolutePath switch
        {
            "/health" => HttpStatusCode.OK,
            "/test/protected" => HttpStatusCode.Unauthorized,
            _ => HttpStatusCode.NotFound,
        }));
        using var http = new HttpClient(handler) { BaseAddress = new Uri("http://localhost:3001/") };
        await Assert.ThrowsAsync<InvalidOperationException>(() => new HarnessClient(http).VerifyEnvironmentAsync());
    }

    private sealed class ResponseHandler(Func<HttpRequestMessage, HttpResponseMessage> respond) : HttpMessageHandler
    {
        protected override Task<HttpResponseMessage> SendAsync(HttpRequestMessage request, CancellationToken cancellationToken) =>
            Task.FromResult(respond(request));
    }
}
