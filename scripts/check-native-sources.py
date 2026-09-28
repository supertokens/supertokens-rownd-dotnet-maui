#!/usr/bin/env python3
"""Read-only source pin check; never fetch, checkout, build or start a harness."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

root = Path(__file__).resolve().parents[1]
versions = json.loads((root / "eng/versions.json").read_text())
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--platform", choices=("all", "android", "ios"), default="all")
platform = parser.parse_args().platform
failed = False
for name, pin in versions["nativeSources"].items():
    if platform != "all" and name != platform:
        continue
    path = root.parent / pin["directory"]
    result = subprocess.run(["git", "-C", str(path), "rev-parse", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run(["git", "-C", str(path), "status", "--porcelain", "--untracked-files=no"], capture_output=True, text=True)
    matches = result.returncode == 0 and result.stdout.strip() == pin["commit"] and dirty.returncode == 0 and not dirty.stdout
    print(f"{name}: {'PASS' if matches else 'BLOCKED (missing, mismatched, or modified source)'}")
    failed |= not matches
sys.exit(1 if failed else 0)
