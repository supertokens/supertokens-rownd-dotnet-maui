# Create a GitHub beta release from the Mac

The release command uploads already-built and smoke-tested packages. It does not rebuild packages, push source commits, publish to NuGet.org, or run automatically when `main` is pushed.

## Prepare

1. Build and validate the combined packages for the version in `Rownd.Package.props`. Use a new prerelease version for changed package bytes.
2. Keep the individual assets under `artifacts/releases/<version>/`: the four matching `.nupkg` files, `SHA256SUMS`, `manifest.json`, `beta-integration.md`, and `VALIDATION.md`. Keep the matching ZIP at `artifacts/releases/SuperTokens.Rownd.<version>.zip`. The existing beta bundle already uses this layout.
3. Commit and push the source changes. Install Python 3 and GitHub CLI (`gh`), then authenticate with `gh auth login` using an account allowed to create releases in this repository.

## Validate without publishing

```sh
npm run release
# Equivalent, without Node/npm:
python3 scripts/release-github.py --dry-run
```

The default is an offline dry run. It checks package identities/versions, all package checksums, matching ZIP contents, recorded Android/iOS smoke results, and the selected commit's version and dependency pins. It reports the repository, tag, target commit and original build provenance. Recorded smoke results are evidence supplied by the build process, not tests rerun by this command.

## Publish the prerelease

```sh
npm run release -- --publish
```

The default target is the current `HEAD`; use `--target <commit>` to select another committed target. Use `--assets <directory>` and `--zip <path>` for a different artifact location.

Publishing requires a clean working tree and a target commit already available on GitHub. The script creates `v<version>` at that target, uploads all nine assets to a draft, checks the uploaded asset names/sizes, then publishes it as a prerelease without marking it Latest. The nine assets are the four packages, tutorial, validation notes, checksum file, manifest, and convenience ZIP.

An existing release, including a draft, is never overwritten. An existing remote tag is accepted only if it points to the selected commit. If uploading or final verification fails, inspect the draft on GitHub; the script leaves it for recovery rather than deleting evidence or replacing assets automatically. A network interruption during final publication can leave publication status uncertain: inspect GitHub before retrying.

## Build provenance

The first beta was built and tested from an uncommitted source snapshot before the beta preparation commit. The original manifest intentionally records that state. The release command preserves it and states the separate release target in the notes; it does not claim a clean rebuild from the tag. Future candidates should be built from their committed source when possible. Never edit provenance or package hashes to make different files look like the tested candidate.

The known beta limitations and exact Debug/Release simulator/emulator test scopes are included from the bundled validation notes. Publishing does not close those remaining acceptance gates.
