# SuperTokens Rownd MAUI — M1 foundation

Target: .NET 10 Android/iOS, upgrading customers from `Rownd.Maui`.
**Native bindings and live authentication are pending M2.** No installable replacement NuGet is claimed.
Proposed identity `SuperTokens.Rownd.Maui` is not reserved or published.

## Build and unit checks

Use SDK **10.0.401**, workload set **10.0.401**, MAUI **10.0.20** and JDK **21.0.12**.
`eng/versions.json` pins the reviewed native Android 0.1.14, iOS 0.2.4 and Hub sources.

```sh
# This Linux development environment only:
source /home/dev/.config/rownd-android-tooling/env.sh
python3 scripts/check-native-sources.py
./scripts/test-unit.sh
dotnet build tests/Rownd.IntegrationTests/Rownd.IntegrationTests.csproj -c Release
# Install workload once if needed; does not run devices:
dotnet workload install maui-android --version 10.0.401
ROWND_APPLICATION_ID=your.actual.application.id ./scripts/build-sample.sh android
```

On the customer's Mac, install the matching `maui-ios` workload set and Xcode required by iOS workload **26.5.10318**. Confirm exact Xcode compatibility before building; it has not been verified here. Build with `./scripts/build-sample.sh ios` and an explicit `ROWND_APPLICATION_ID`. No Mac CI is configured.

`samples/Passwordless` validates configuration and shows disabled sign-in, protected API and sign-out actions with an unavailable-auth label. It references only `src/Rownd.Foundation`; it never initializes legacy C# auth or fabricates a session. App IDs, schemes and HTTPS associations await customer identifiers; none are registered by this foundation.

## Shared fixture and deferred checks

See [M1 status and fixture setup](docs/m1-status.md), [device scenarios](tests/e2e/scenarios.md) and [full plan](plan.md).
Integration checks require explicit opt-in; they were **not run**:

```sh
ROWND_RUN_INTEGRATION=1 ROWND_HARNESS_URL=http://localhost:3137 ./scripts/test-integration.sh environment
# First create a fresh phone challenge in the real Hub using a unique controlled number.
ROWND_RUN_INTEGRATION=1 ROWND_HARNESS_URL=http://localhost:3137 ROWND_TEST_PHONE=... ./scripts/test-integration.sh phone-capture
./scripts/test-passwordless.sh --platform android --scenario phone-magic-link
```

The E2E entrypoint exits 2 (blocked) until M2 bindings/device drivers exist. **A Mac alone cannot execute the unfinished device automation.** Compiled scenario orchestration in `tests/Rownd.IntegrationTests/PasswordlessScenarios.cs` covers OTP, phone replay, delayed startup and refresh/recovery through explicit driver contracts. No concrete mobile driver or passing fallback exists. Recording/scripted doubles are confined to offline unit tests of orchestration. Captures verify callback shape, not native authentication. No real SMS delivery checks are in the approved scope.

## Customer upgrade

The eventual replacement requires **one fresh sign-in**. Old `rownd_state` credentials will not be imported. Native SDKs will own token storage and refresh. Customers will use ordinary `HttpClient` with a newly retrieved token attached per request; no automatic interception or 401 replay is promised.

`Rownd/`, `examples/` and `Rownd.sln` remain historical legacy sources, outside the new build path. Their old framework targets do not describe this foundation. Inherited release configuration/notification are archived as `.disabled` files in `docs/`; `npm run release` fails explicitly. Publishing remains postponed.
