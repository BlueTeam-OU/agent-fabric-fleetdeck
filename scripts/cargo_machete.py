#!/usr/bin/env python3
"""Run cargo-machete so that only a judged workspace passes.

cargo-machete --with-metadata reads each crate through `cargo metadata`;
when that fails for a crate it prints "error when handling" and carries
on, and still exits 0, so a crate it never read would pass as clean. The
workspace's metadata is checked first (--locked: the committed lockfile),
and that line is a failure.

Exit codes: 0 no unused dependency; 1 an unused dependency, a crate the
tool could not read, or the tool failing.
"""
from __future__ import annotations

import shutil
import subprocess
import sys

SKIPPED = "error when handling"


def main() -> int:
    if shutil.which("cargo-machete") is None:
        print("cargo_machete: cargo-machete is not installed; CARGO_MACHETE_VERSION in .github/workflows/ci.yml is the release CI installs", file=sys.stderr)
        return 1
    metadata = subprocess.run(
        ["cargo", "metadata", "--locked", "--format-version", "1"],
        stdout=subprocess.DEVNULL,
    )
    if metadata.returncode != 0:
        print("cargo_machete: cargo metadata failed, so cargo-machete could not judge the workspace", file=sys.stderr)
        return 1
    run = subprocess.run(["cargo-machete", "--with-metadata"], capture_output=True, text=True)
    sys.stdout.write(run.stdout)
    sys.stderr.write(run.stderr)
    if SKIPPED in run.stderr:
        print(f"cargo_machete: cargo-machete could not read a crate (`{SKIPPED}` above): not a pass", file=sys.stderr)
        return 1
    # 0.9.2 exits 1 only for unused dependencies; 2 is its own error and
    # 101 a panic.
    if run.returncode == 1:
        print("cargo_machete: cargo-machete named an unused dependency above", file=sys.stderr)
        return 1
    if run.returncode != 0:
        print(f"cargo_machete: cargo-machete failed with exit {run.returncode}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
