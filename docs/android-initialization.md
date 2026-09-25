# Android initialization contract

The MAUI bridge reports ready only after native SuperTokens bootstrap, cache hydration, usable app configuration, legacy-native migration completion, and native session reconciliation. A successful signed-out result needs no token. No native state subscription starts before this gate succeeds.

## Pinned-source findings

Reviewed Android `cd08c866828232d130f32df3c1c47ee7fabe1a2c`:

- `RowndClient.configure` starts `StateRepo.setup`, calls `SuperTokensSessionBridge.initializeIfNeeded`, then starts `observeAndInitialize`.
- `StateRepo.setup` sets `GlobalState.isInitialized` immediately after reading its cache (including its fallback after a cache error), before fetching app configuration or resolving authentication. Cached `auth.isAuthenticated` is therefore not readiness.
- `initializeIfNeeded` sets its atomic flag before building SuperTokens and catches builder exceptions, resetting the flag. Its original public contract loses the exception.
- `observeAndInitialize` waits for a nonempty app-config ID with loading complete. Migration joins an active migration job, but internally handles some failures by retaining legacy credentials.
- `resolveAuthState` is the native authentication authority: serialized native reads/refresh, sign-out generation checks, guarded compatibility-state reconciliation. Retained refresh credentials with a missing token produce `ServerException`, not signed-out success. Missing native sessions clear cached SuperTokens authentication; pending legacy credentials are deliberately preserved.

## Build-local native hook

The source pin and sibling tracked files remain unchanged. `scripts/prepare-android-source.py` copies pinned `android/src/main/java` to ignored `native/android/build/patched-native`, checks/applies `native/android/initialization.patch` with zero fuzz, and Gradle compiles this overlay plus `native/android/hooks` into the native AAR. The normal build first runs the source-pin/cleanliness check. Use `scripts/build-native-android.sh`; invoking the Gradle init script directly requires preparing the overlay first.

Exact upstream source change: add a volatile internal `initializationFailure: Exception?` to `SuperTokensSessionBridge` and retain the caught bootstrap exception there. The first failure is intentionally sticky for this process: the managed API does not retry failed configuration, even if the native fallback later retries internally.

The additive public extension `RowndClient.awaitMauiSessionReady()` lives in the native module so it can call existing internal native reconciliation without reflection or a second session manager. It:

1. Rethrows the recorded bootstrap exception, or fails if bootstrap did not initialize.
2. Waits for cache hydration and usable app configuration.
3. Awaits native migration and runs `resolveAuthState`.
4. Rejects unresolved retained legacy authentication rather than exposing it as a native session.

`RowndBridge` gives this gate 30 seconds, reports exception type through its existing completion contract, and only then enables operations and subscribes to state. Signed-out success and a transient `ServerException` are distinct. The configure-attempt flag is set before calling native configure, preventing retry after a partial native failure.

## Scope and limits

- Readiness establishes native bootstrap and session reconciliation, not backend-verified identity or network availability for subsequent operations.
- A valid cached app configuration can satisfy the native app-config gate. This does not promise a fresh network fetch. Without usable config, the facade timeout becomes an initialization error; native app-config errors are not exposed with their original cause by this pin.
- Legacy migration errors may be swallowed internally. Retained authenticated legacy state is conservatively rejected as incomplete reconciliation; the original migration error cannot always be recovered.
- Coroutine timeout cannot interrupt synchronous native work immediately. Cancellation prevents the facade from publishing readiness when that work returns.
- Focused JVM tests exercise the readiness boundary with controlled native-operation outcomes. They do not execute Android storage, network refresh, Hub UI, integration/E2E or devices.

## Verification

Source `/home/dev/.config/rownd-android-tooling/env.sh`, then:

```sh
bash scripts/build-native-android.sh :android:testDebugUnitTest
dotnet build bindings/Rownd.Android/Rownd.Android.csproj -c Release --nologo -v quiet
python3 scripts/check-native-sources.py
```

Executed on Linux:

- Native Release AAR/facade compilation and `:android:testDebugUnitTest`: **passed**, 1m22s. **58 tests, zero failures/errors/skips**, including six new readiness regressions: swallowed bootstrap failure after cache load, stale cached auth awaiting absent-session reconciliation, successful signed-out startup, transient reconciliation failure, unresolved legacy credentials, and cache/app-config ordering.
- Source-pin/cleanliness check: **passed** for Android, iOS and Hub. Python compilation, shell syntax and diff whitespace checks passed.
- .NET Android binding Release rebuild: **passed**, 9.59s, zero errors. Four BG8605/BG8606 warnings; resolution report excludes only Kotlin-generated `$` accessors, including the new private readiness accessors. Log: `/tmp/opencode/rownd-android-initialization-binding.log`.
- Native build log: `/tmp/opencode/rownd-android-initialization-build.log`. Unit XML: sibling `android/build/test-results/testDebugUnitTest/TEST-io.rownd.android.MauiInitializationTest.xml`.

Final package verification repacked Android NuGets and confirmed both embedded AARs match the current build outputs, including the readiness invocation, native hook and sticky bootstrap failure field. Current hashes and package-consumer results are recorded in [M2 status](m2-status.md). No integration/E2E/device tests were run.
