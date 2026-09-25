#!/usr/bin/env python3
"""Build a disposable, pinned Swift package overlay; never edit the sibling checkout."""
from pathlib import Path
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
subprocess.run(["python3", str(root / "scripts/check-native-sources.py")], check=True)
native = root.parent / "supertokens-rownd-ios"
overlay = root / "native/ios/build/patched-native"
if overlay.exists():
    shutil.rmtree(overlay)
# Copy tracked package inputs only; exclude caches, generated projects and local data.
files = subprocess.check_output(["git", "ls-files", "-z"], cwd=native).decode().split("\0")
for name in files:
    if name in ("Package.swift", "Package.resolved") or name.startswith(("Sources/", "Packages/", "Tests/")):
        target = overlay / name
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(native / name, target)
command = ["patch", "-p1", "--batch", "--fuzz=0", "-i", str(root / "native/ios/auth-identity.patch")]
subprocess.run(command + ["--dry-run"], cwd=overlay, check=True)
subprocess.run(command, cwd=overlay, check=True)
for test in (root / "native/ios/RegressionTests").glob("*.swift"):
    shutil.copy2(test, overlay / "Tests/RowndTests" / test.name)
