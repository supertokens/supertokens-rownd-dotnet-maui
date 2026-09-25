# M3 facade and package status

Implementation advanced from `2a6dca5`; **M3 exit gate is open**. No integration/E2E/device tests ran in this phase. User-recorded Android and iOS results in [testing.md](testing.md) remain valid for their recorded revisions, not proof of M3 Release artifacts.

## Changes

- Minimal API remains `ConfigureAsync`, `RequestSignIn`, `GetAccessTokenAsync`, `SignOut`, `State`/`StateChanged`. Configure once, including after failure; token absence and retrieval errors remain distinct. Dispatcher failures now fault configuration rather than allowing a retry after partial dispatch. Late completions are ignored after disposal; event subscribers are released.
- Android keeps the user's deferred main-handler state delivery. Completion callbacks now also leave JNI before notifying managed Tasks, and remain rooted until the queued completion runs. Disposal suppresses/removes queued callbacks and is idempotent; synchronous invocation failure releases callback roots. Callback implementations carry linker-preservation annotations.
- iOS explicitly retains the state delegate, suppresses late configuration completion, clears observations and disposes once. Native Swift `@escaping` completion blocks are retained by their Tasks; the binding declarations remain aligned with the existing Objective-C surface. The user's direct upstream identity fix and source pins remain untouched.
- Android binding and MAUI facade exclude imported JNI libraries already carried by intact dependency AARs. No Java classes/resources are stripped. The rebuilt native package and whole Android feed pass inspection: no repeated JNI paths, with datastore/graphics libraries present for all four supported ABIs. The binding-only checker cannot detect duplicates introduced by another package; whole-feed inspection and the consumer build also verified the facade fix.
- iOS framework inspection checks device arm64 and Apple Silicon simulator slices, generated selectors and Rownd/GoogleSignIn bundles after archive creation. Actual linker/resource loading remains a Mac/device check. Intel simulator architecture is not claimed by this checker.
- `pack.sh all` produces one public multi-target facade package with conditional native dependencies and validates its dependency groups. Platform packs remain available for development. Package version is `0.0.1-m3`; the sample defaults to package references, while the source-build helper explicitly opts into project references. Combined feed selection is supported by isolated package verification. Sample subscriptions are idempotent across repeated appearance.

## Verification on Linux

- Installed .NET SDK **10.0.200** alongside existing 10.0.401, without changing repository pins. Used the existing tooling environment for JDK/Android paths.
- `bash scripts/test-unit.sh --nologo -v quiet`: **78 passed, 0 failed/skipped**. Five new regressions cover first-callback/error precedence and recovery, disposal before dispatch, late completion, failed dispatcher configuration, and unsubscribe before queued UI delivery.
- Foundation `0.0.1-m3` NuGet packed successfully. Integration project **compiled only**, zero warnings/errors.
- Shell syntax, Python syntax and `git diff --check` pass.
- Pinned Android workload repair **passed**: `dotnet workload install maui-android --version 10.0.200 --disable-parallel`, with `TMPDIR=/tmp/opencode`. The existing tooling environment correctly selects SDK 10.0.200 inside this checkout; Android manifest 36.1.43 and MAUI 10.0.20 are installed. Reclaimed approximately 1.6 GiB only from generated `obj` directories (three earlier isolated consumers, tooling smoke project, Android binding and MAUI facade); earlier packages, APKs and logs were retained. The home filesystem had 57 GiB available before repair; user/group quota queries exposed no limit, so the earlier quota boundary is not established. Existing M2 artifacts are not M3 evidence.
- Native source check: Android and Hub pass; iOS blocked because this host's sibling is clean at `0c89cac`, while the user pin is `95bd10b6c5bec1678fa6094e031a3e1cbf900901`. The local/unreleased pin is deliberately preserved; no historical source substitution occurred.
- Android native Release rebuild, `dotnet build src/Rownd.Maui/Rownd.Maui.csproj -c Release -p:RowndTargetFrameworks=net10.0-android`, `bash scripts/pack.sh android`, and strict `python3 scripts/check-android-package.py`: **passed**. Native runtime inventory contains 118 embedded artifacts and 64 supplied by declared NuGet dependencies. The native wrapper checks all platforms, so its Android steps ran directly after explicit clean Android/Hub pin checks. Run Gradle clean before regenerating the source overlay, since it lives under `native/android/build`.
- Initial clean facade build: 24 warnings, zero errors (BG8605/BG8606 Kotlin synthetic accessors, obsolete `PreserveAttribute`, nullable main looper and StyleCop); subsequent incremental builds passed. Native build retains upstream Kotlin/Gradle deprecation and SDK XML-version warnings; packs report missing package readmes. Evidence logs: `/tmp/opencode/rownd-m3-native.log`, `rownd-m3-android-build.log`, `rownd-m3-android-pack.log`, `rownd-m3-android-package-check.log`; package SHA-256 values: `/tmp/opencode/rownd-m3-packages.sha256`.
- Final `ROWND_APPLICATION_ID=io.supertokens.rownd.m3verification bash scripts/verify-package.sh android`: **passed, zero warnings/errors**, including normal trimming and profiled AOT for arm64/x64; no XA4301 warnings. Consumer: `/tmp/opencode/rownd-consumer.gAiFCO`; log: `/tmp/opencode/rownd-m3-android-consumer.log`. Its isolated restore contains all three M3 packages and no project references. Metadata inspection confirms `PlatformBridge.Changed`, `CompletionCallback.Complete`, and `TokenCallback.Complete` survive linking on both architectures; the APK contains each required JNI library once and the facade AOT libraries. No app was installed or launched.
- Earlier consumer attempts passed compilation with four XA4301 warnings because `Rownd.Maui.aar` re-embedded the binding's JNI payload. Added the facade exclusion, removed stale generated facade AAR/package outputs, and regenerated the same-version package before the successful fresh-cache verification. When repeating after packaging changes, clean both `bin`/`obj` and the affected local `.nupkg`; incremental packing can retain a stale same-version archive. Earlier attempt logs and facade package remain under `/tmp/opencode/rownd-m3-*-before-jni-fix*` and `rownd-m3-android-consumer-stale-package.log`.
- iOS framework/package checker and combined-package checker compile, but cannot run against real current artifacts here: no Mac/Xcode, pinned sibling unavailable, no combined artifact. Their runtime assertions are not reported as passed.

## Remaining gates / next builder

1. Android local build/package gate is **passed** with the pinned workload, no duplicate-JNI warnings and linked callback metadata retained. Repeat against the combined feed once available; physical-device callback/lifecycle behavior remains unrun.
2. On Mac with the pinned sibling/Xcode 26.2, rebuild the XCFramework and run its checker; clean managed iOS consumers before building. Build `pack.sh all`, check both platform dependency groups and verify both isolated consumers from the combined feed. No source-checkout dependency is allowed in the consumer.
3. The upstream iOS identity fix's release is deferred per the user's decision. Continue development; after publication update commit/version and rerun affected checks. Deferred checks are neither blocking development nor marked passed. Separately, native iOS `fatalError` initialization remains an unresolved reliable-error-mapping release gate.
4. User must run package-only physical Android and signed iPhone Release OTP → protected API → sign-out, repeated presentation/subscription and disposal/lifecycle checks. Previous source Debug simulator evidence does not satisfy this gate. Phone/HTTPS/refresh acceptance remains tracked in M4/M5; real SMS and publishing stay outside approved scope.

## Verified Android artifact hashes

SHA-256 for the local `0.0.1-m3` feed:

| Artifact | SHA-256 |
| --- | --- |
| `SuperTokens.Rownd.Foundation.0.0.1-m3.nupkg` | `fcd210beebe993d31de9b189bc99b11fc3d7907ede8bfef7a66490fffc8dbf87` |
| `SuperTokens.Rownd.Maui.0.0.1-m3.nupkg` | `62ce9c498d2af2535243ac50e5d5f7005ac2200cd87ce0057474c963e329ad31` |
| `SuperTokens.Rownd.Native.Android.0.0.1-m3.nupkg` | `495b7f33d50e47ad04ff7ee83dddb27e323dd10a2b94df874bb8f9a26711b645` |
| Isolated consumer `io.supertokens.rownd.m3verification-Signed.apk` (build signing only) | `0c0618a137d1ab2fac70701768b8aa85e86c4379db53ac3cbedf94465aeedf56` |

No commits, pushes or publication performed during verification.
