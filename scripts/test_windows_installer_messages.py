from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
INSTALLER = ROOT / "distribution" / "install.ps1"
INSTALLER_TESTS = [ROOT / "scripts" / "windows_install_conpty_package_test.ps1"]

THROW = re.compile(r'throw "((?:[^"`]|`.)*)"')
EXPECTED_MESSAGE = re.compile(r'Exception\.Message -(?:not)?like "((?:[^"`]|`.)*)"')


def static_prefix(message: str) -> str:
    """The text of a PowerShell string before its first interpolation."""
    return message.split("$", 1)[0]


class WindowsInstallerMessageTests(unittest.TestCase):
    # The installer tests recognise an expected refusal by its message, and run
    # only on a Windows runner. A renamed message there turns a refusal the test
    # wanted into a failure nobody sees until CI on Windows; this catches it on
    # every platform.
    def test_every_expected_refusal_is_a_message_the_installer_throws(self) -> None:
        thrown = [static_prefix(m) for m in THROW.findall(INSTALLER.read_text(encoding="utf-8"))]
        self.assertTrue(thrown, f"no throw statements found in {INSTALLER}")
        for test_script in INSTALLER_TESTS:
            patterns = EXPECTED_MESSAGE.findall(test_script.read_text(encoding="utf-8"))
            self.assertTrue(patterns, f"no expected messages found in {test_script}")
            for pattern in patterns:
                literal = re.split(r"[*?\[]", pattern, maxsplit=1)[0]
                with self.subTest(script=test_script.name, pattern=pattern):
                    self.assertTrue(
                        any(
                            message.startswith(literal) or literal.startswith(message)
                            for message in thrown
                            if message
                        ),
                        f"{test_script.name} expects {pattern!r}, which install.ps1 never throws",
                    )


if __name__ == "__main__":
    unittest.main()
