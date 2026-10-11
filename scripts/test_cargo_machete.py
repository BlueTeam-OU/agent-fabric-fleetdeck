from __future__ import annotations

import os
import stat
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT = Path(__file__).resolve().parent / "cargo_machete.py"

# Stubs for cargo and cargo-machete: each records its arguments, prints
# $<NAME>_OUT / $<NAME>_ERR and exits $<NAME>_RC, so every outcome of the
# real tools can be staged.
STUB = """#!/bin/sh
printf '%s\\n' "$*" >> "$STUB_ARGS/{name}"
printf '%s' "${{{name}_OUT}}"
printf '%s' "${{{name}_ERR}}" >&2
exit "${{{name}_RC:-0}}"
"""


@unittest.skipUnless(os.name == "posix", "the stub tools are POSIX shell scripts")
class CargoMacheteTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.bin = Path(self.tmp.name) / "bin"
        self.bin.mkdir()
        # The argument records live apart from the stubs: on a case-insensitive
        # filesystem (macOS) a record named CARGO would be the cargo stub itself.
        self.args = Path(self.tmp.name) / "args"
        self.args.mkdir()
        for tool, name in (("cargo", "CARGO"), ("cargo-machete", "MACHETE")):
            path = self.bin / tool
            path.write_text(STUB.format(name=name))
            path.chmod(path.stat().st_mode | stat.S_IXUSR)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def run_script(self, **env: str) -> subprocess.CompletedProcess[str]:
        full = {"PATH": f"{self.bin}{os.pathsep}/usr/bin{os.pathsep}/bin", "STUB_ARGS": str(self.args), **env}
        return subprocess.run(
            [sys.executable, str(SCRIPT)], env=full, capture_output=True, text=True, timeout=60
        )

    def test_clean_workspace_passes(self) -> None:
        result = self.run_script(MACHETE_OUT="cargo-machete didn't find any unused dependencies\n")
        self.assertEqual(result.returncode, 0, result.stderr)
        # The two flags the verdict rests on: the committed lockfile, and
        # the metadata mode that judges every crate (and reports one it
        # could not read).
        self.assertEqual((self.args / "CARGO").read_text(), "metadata --locked --format-version 1\n")
        self.assertEqual((self.args / "MACHETE").read_text(), "--with-metadata\n")

    def test_unused_dependency_fails(self) -> None:
        result = self.run_script(MACHETE_OUT="agent-fabric-fleetdeck -- ./Cargo.toml:\n\tfoo\n", MACHETE_RC="1")
        self.assertEqual(result.returncode, 1)
        self.assertIn("unused dependency", result.stderr)
        self.assertIn("foo", result.stdout)

    def test_unreadable_crate_fails_although_the_tool_exits_zero(self) -> None:
        result = self.run_script(MACHETE_ERR="error when handling ./crates/x/Cargo.toml: metadata\n")
        self.assertEqual(result.returncode, 1)
        self.assertIn("could not read a crate", result.stderr)

    def test_tool_error_fails(self) -> None:
        for code in ("2", "101"):
            with self.subTest(code=code):
                result = self.run_script(MACHETE_RC=code)
                self.assertEqual(result.returncode, 1)
                self.assertIn(f"exit {code}", result.stderr)

    def test_metadata_failure_fails_before_the_tool_runs(self) -> None:
        result = self.run_script(CARGO_RC="101", MACHETE_OUT="SHOULD NOT RUN")
        self.assertEqual(result.returncode, 1)
        self.assertIn("cargo metadata failed", result.stderr)
        self.assertNotIn("SHOULD NOT RUN", result.stdout)

    def test_missing_tool_fails(self) -> None:
        (self.bin / "cargo-machete").unlink()
        result = self.run_script()
        self.assertEqual(result.returncode, 1)
        self.assertIn("not installed", result.stderr)


if __name__ == "__main__":
    unittest.main()
