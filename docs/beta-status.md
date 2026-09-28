# 0.0.1-beta.1 candidate validation

This is a candidate for GitHub distribution, not a stable SDK release. No packages were published by this validation. Use the [integration guide](beta-integration.md) and distribute all four matching packages together.

## Recorded checks — 28 September 2026

- Fresh native builds from Android 0.1.14 (`cd08c866828232d130f32df3c1c47ee7fabe1a2c`) and released iOS 0.2.5 (`aec3b4c4f092deb7ed5c468a679959014b1ede7d`). Android's removed custom attempt store is absent from the rebuilt AAR. iOS device/simulator XCFramework and resources validated.
- Combined four-package feed, conditional platform dependencies, native Android classes/resources/JNI uniqueness: PASS.
- Managed tests 111/111; packaging/tool tests 65/65: PASS.
- Fresh package-only Android Release and iOS simulator Release consumers with isolated NuGet caches: PASS. Android Debug consumer also built successfully for WebView automation.
- Android API 34 emulator, exact package-only Debug app: real email OTP, protected identity/session, replay, persisted session after process restart, sign-out and signed-out restart, presenter cancellation/reopening: PASS on the third attempt.
- iOS 26.3 iPhone 17 Pro simulator, exact package-only Release app: the same smoke checks PASS on the first attempt. This is simulator Release execution, not signed physical-device acceptance.

Android's first attempt reached authenticated native state but did not complete UI/protected checks. The second timed out attaching to a visible Hub; Appium recorded a stale ChromeDriver connection. A fresh Appium session passed with unchanged APK/data. No new Android crash was recorded during these beta attempts. Initial failures remain recorded; this is not a claim of a flake-free run or a resolved fatal-error cause.

Smoke used unmodified pinned Hub `086014e0f29c00722b260e69a9f28ff47512bf0f` and real 3600-second Core access tokens. The separate local short-token Hub correction was neither deployed nor required. Core image ID: `sha256:8302ef1766b05c2b85cbed85de8d6e7fb38dedfe041918327e24e5b33d6f2590`. Fixture observation hooks did not manufacture acceptance sessions.

## Scope still open

These checks do not close known fatal-error investigation, terminal native disposal with queued callbacks, active-Hub activity recreation, iOS scene hosts, physical signed-device acceptance, verified HTTPS/app-link associations, cross-device/replay/expiry coverage beyond this smoke, legacy upgrades, real-provider SMS, customer backend/signing integration or production release readiness. The M5 short-token matrix was not rerun for this beta. Ordinary WebView passwordless storage retains the documented immediate-force-stop durability limitation; missing-origin confirmation must not be bypassed.

Version is centralized in `Rownd.Package.props`. The GitHub handoff bundle contains only the four matching beta packages, the integration guide, these validation notes, relative package SHA256 sums and source/build provenance. Historical M3/M4/M5 results describe their own artifacts and do not replace this candidate's evidence.
