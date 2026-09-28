# M5 session expiry, refresh and recovery

**User-run Mac commands; no M5 runtime result is claimed.** Preserve .NET/workload set 10.0.200, MAUI 10.0.20, Android 36.1.43, iOS 26.2.10217, JDK 21.0.12 and Xcode 26.2. See [status/matrix](m5-status.md) and [M4 startup/device setup](testing-m4.md).

## Shared real fixture

Both platforms use the same pinned Android phone-capable harness and Hub. The disposable M4 overlay now configures real Core `ACCESS_TOKEN_VALIDITY` (seconds), default **90**, bounded to **61–300**, above iOS's 60-second proactive margin. It exposes `/test/m5/config` for runner validation; uses the existing `/counters` native `stRefresh` counter and `/test/refresh-availability` 503 switch. It does not issue acceptance sessions through fixture creation endpoints, edit JWTs, or change same-device policy. Source-shape drift fails preparation.

With locked Android `npm ci` dependencies already installed:

```sh
python3 scripts/prepare-m4-harness.py
artifacts/m4-harness/node_modules/.bin/tsc --noEmit -p artifacts/m4-harness/test-server/tsconfig.json
```

On the Mac, start Docker and the pinned/candidate Hub as in M4, then start **one** observed backend (stop the previous fixture first):

```sh
export ROWND_M5_ACCESS_TOKEN_SECONDS=90
export ANDROID_HOST=127.0.0.1
export ANDROID_HARNESS_PORT=3137
export ANDROID_HUB_URL=http://127.0.0.1:8787
export ANDROID_PUBLIC_API_URL=http://127.0.0.1:3137
node --import ./artifacts/m4-harness/node_modules/tsx/dist/loader.mjs \
  artifacts/m4-harness/test-server/run-harness.ts
```

Change origins/port for the real device setup; both embedded startup JSON and runner JSON must match. Restarting the fixture is necessary for a changed lifetime. Record actual Core image digest (upstream remains unpinned), lifetime, selected same-device policy and source revisions/local patch hashes. The runner validates real expiry by a saved-token **401**, not by trusting its lifetime setting alone. This fixture is test-only; its unauthenticated controls/capture endpoints must remain restricted to the local test environment.

## Build/install the Debug sample

Use `InitializationDelayMs: 0` for session testing. Follow M4's native builds and embedded startup JSON, then:

```sh
dotnet build samples/Passwordless/Passwordless.csproj -c Debug \
  -p:RowndUsePackage=false -p:RowndTargetFrameworks=net10.0-android \
  -p:RowndApplicationId="$ROWND_APPLICATION_ID" \
  -p:RowndStartupConfig="$ROWND_STARTUP_CONFIG" -p:EmbedAssembliesIntoApk=true
dotnet build samples/Passwordless/Passwordless.csproj -c Debug \
  -p:RowndUsePackage=false -p:RowndTargetFrameworks=net10.0-ios \
  -p:RowndApplicationId="$ROWND_APPLICATION_ID" \
  -p:RowndStartupConfig="$ROWND_STARTUP_CONFIG" \
  -p:RuntimeIdentifier=iossimulator-arm64 -p:CodesignKey=- -p:CodesignProvision=
```

Install those outputs and create explicit Appium sessions using [existing setup](testing.md#install-the-sample-and-create-an-appium-session). Set session `newCommandTimeout` sufficiently high (e.g. 300 seconds); keepalives run during expiry waits. The runner uses the same config as M4: real app ID, explicit device serial/UDID, fixture URL, test email, controlled E.164 phone, scheme, and `ios-device-kind: simulator`. No OTP/link/token belongs in config. No SMS provider is required.

```sh
export ROWND_APPIUM_URL=http://127.0.0.1:4723
export ROWND_APPIUM_SESSION='EXISTING_ANDROID_SESSION'
export ROWND_E2E_CONFIG='/absolute/path/e2e-android.json'
ROWND_RUN_E2E=1 bash scripts/test-passwordless.sh --platform android --scenario refresh-recovery

export ROWND_APPIUM_SESSION='EXISTING_IOS_SESSION'
export ROWND_E2E_CONFIG='/absolute/path/e2e-ios.json'
ROWND_RUN_E2E=1 bash scripts/test-passwordless.sh --platform ios --scenario refresh-recovery
```

Run sequentially on a dedicated fixture. Each invocation runs **both email OTP and phone magic-link login**, and repeats a fresh real login after sign-out. Allow at least 10 minutes per platform with the default lifetime. Existing `smoke`/`phone-magic-link` success does not substitute for this scenario.

### Assertions and controls

1. Real native Hub challenge, fresh exact-identity capture, real OTP or untargeted external phone-link dispatch. Same-device confirmation remains a failure, never clicked.
2. One correlated successful consume, backend/C# identity match and session fingerprint from the verified protected endpoint.
3. Debug sample saves the native getter's initial access token **only in process memory**. Plain cookie-free/no-redirect C# HttpClient requests with that saved token first return 200, then 401 after real elapsed expiry. That button never calls the getter or refreshes/retries a request.
4. Explicit getter refresh stores its exact returned token in **separate candidate memory**. Immediately after that getter, the runner requires native `stRefresh` to increase, before any other getter can run. The single-use `candidate-request` sends that same candidate through plain cookie-free/no-redirect HTTP, with no getter, refresh or retry; it must return exactly 200 and the expected verified user/session fingerprint. The ordinary protected button is not used for this assertion because it calls a second getter. Consume count and logical login transitions remain unchanged. Visible native Hub checks run during waits and sample operations; host access remains required. This is bounded UI observation, not an exact native presentation-event counter.
5. Save the current token, enable the existing **503** switch, wait for expiry and confirm saved-token 401. Only `save` replaces the initial expiry token; `getter` and candidate requests cannot overwrite it. The C# getter Task must fault (`Getter error`) while native state stays authenticated. A process-long Debug subscriber counts authenticated→signed-out transitions, detecting transient false logout even if state later recovers. Restore refresh availability in `finally`; recovery uses the same explicit-getter → immediate counter check → same-candidate 200/identity assertion, without login.
6. Real terminate/activate checks process ID change, first with a current session and then with the app terminated throughout expiry. Native persistence supplies the session and refresh; C# saved-token memory is deliberately lost.
7. Sign-out reports no session; process restart still reports no session; a fresh real login succeeds through the same method.

Sample observations contain operation sequence, outcome, auth boolean and transition count; successful candidate requests additionally expose only verified user ID and non-secret session fingerprint using the existing backend identity fields (SHA-256 of `accessTokenPayload.sessionHandle` when `sessionFingerprint` is absent). Tokens, JWT payloads, OTPs and callback URLs never enter result labels, status reports or artifact manifests. Candidate memory is cleared before every getter and consumed before HTTP, including failed requests. Sign-out, process exit and the Debug `clear` control clear both token references; an epoch guard prevents an in-flight getter from restoring references after sign-out/clear. The runner invokes `clear` in final cleanup, including assertion failures. HTTP requests, responses and parsed bodies are disposed; the Debug observer/HttpClient intentionally live for the process to observe transient logout across page recreation. Clearing references does not promise zeroing immutable .NET strings. Raw Appium/backend logs may contain secrets: keep them local. An interrupted process cannot execute cleanup; clear/restart the sample and restore `/test/refresh-availability` to `{"unavailable":false}` or restart the dedicated fixture before rerunning.

## Offline checks, packages and CI

```sh
bash scripts/test-unit.sh --nologo -v quiet
python3 -m unittest discover -s tests/package_checkers -p 'test_*.py' -v
```

PR CI runs managed tests, compiles opt-in integration checks without running them, and runs Python mock/tool checks. A manual `android_build` workflow input adds native/binding build, pack/check and isolated Release consumer build on a **provisioned** `self-hosted, Linux, X64, rownd-android` runner. It needs the existing tooling environment and exact sibling checkouts beside the workflow checkout; all-pin validation intentionally fails if any is unavailable. This job has not been executed here and does not provision a runner. No Mac CI is promised. Device acceptance is a recorded Mac/local release check.

On Mac, once exact candidate sources are available, preserve previous generated outputs, rebuild native Android/iOS artifacts, then `bash scripts/pack.sh all`. Copy the complete feed. `pack.sh` writes `artifact-manifest.json`: package SHA-256, checkout revision/dirty flag, source snapshot hash and declared pins. This records bytes, not provenance of an independently supplied native binary; retain native build logs and actual sibling revisions/local diffs too. Do not reuse historical same-version feeds. `verify-package.sh` creates a fresh consumer/cache each time:

```sh
ROWND_PACKAGE_SOURCE="$PWD/artifacts/packages/all" \
  bash scripts/verify-package.sh android -p:RowndStartupConfig="$ROWND_STARTUP_CONFIG"
ROWND_PACKAGE_SOURCE="$PWD/artifacts/packages/all" \
  bash scripts/verify-package.sh ios -p:RowndStartupConfig="$ROWND_STARTUP_CONFIG" \
  -p:RuntimeIdentifier=iossimulator-arm64 -p:CodesignKey=- -p:CodesignProvision=
```

For package-only automation, build that fresh consumer with `-c Debug --no-restore`, its same `RestorePackagesPath` and startup/signing properties, then install that exact output. Debug probes are excluded from Release. Record Debug automation separately from signed physical Release package-only runtime checks (manual equivalents with a test-only diagnostic consumer when needed). Hash explicit output files with `python3 scripts/artifact-manifest.py /path/package.nupkg /path/sample.apk`; iOS app directories need a sorted per-file hash manifest as in M4. No publication, reservation, upload or real-provider SMS is authorized by this milestone.
