#!/usr/bin/env python3
"""Apply the reviewed initialization hook to a disposable native source overlay."""
from pathlib import Path
import os
import shutil
import subprocess

root = Path(__file__).resolve().parents[1]
native = Path(os.environ.get("ROWND_ANDROID_SOURCE", root.parent / "supertokens-rownd-android"))
overlay = root / "native/android/build/patched-native"
if overlay.exists():
    shutil.rmtree(overlay)
shutil.copytree(native / "android/src/main/java", overlay)
command = ["patch", "-p1", "--batch", "--fuzz=0", "-i", str(root / "native/android/initialization.patch")]
subprocess.run(command + ["--dry-run"], cwd=overlay, check=True)
subprocess.run(command, cwd=overlay, check=True)
