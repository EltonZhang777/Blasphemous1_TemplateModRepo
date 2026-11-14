import re
import unittest
from pathlib import Path

import path_safety


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {".py", ".ps1", ".psm1", ".bat", ".cmd"}


def find_forbidden_path_writes(text):
    lowered = text.lower()
    findings = []
    if re.search(r"\bset" + r"x\b", lowered):
        findings.append("set" + "x")
    if "winreg.set" + "value" in lowered:
        findings.append("winreg.Set" + "Value/SetValueEx")
    if "setenvironment" + "variable" in lowered and re.search(
        r"(?i)['\"](?:user|machine)['\"]", text
    ):
        findings.append("SetEnvironment" + "Variable(User/Machine)")

    write_commands = (
        "set-" + "itemproperty",
        "new-" + "itemproperty",
        "remove-" + "itemproperty",
        "reg " + "add",
        "reg " + "import",
    )
    registry_roots = (
        "hk" + "cu:",
        "hk" + "lm:",
        "hkey_" + "current_user",
        "hkey_" + "local_machine",
    )
    if any(command in lowered for command in write_commands) and any(
        root in lowered for root in registry_roots
    ):
        findings.append("PowerShell/reg persistent environment write")
    return findings


class PathSafetyTests(unittest.TestCase):
    def test_repository_test_hives_are_reported(self):
        entry = (
            r"C:\repo\.wt\issue-1-worker\tmp"
            r"\blas1-wrapper-test\hive\.dotnet\tools"
        )
        snapshot = path_safety.PathSnapshot(entry, "")

        self.assertEqual(
            [("User", entry)],
            path_safety.repository_test_hive_entries(snapshot),
        )

    def test_unrelated_paths_are_not_reported(self):
        snapshot = path_safety.PathSnapshot(
            r"C:\Tools;C:\Windows", r"C:\Program Files\dotnet"
        )

        self.assertEqual(
            [], path_safety.repository_test_hive_entries(snapshot)
        )

    def test_disposable_context_requires_explicit_flag(self):
        self.assertFalse(path_safety.is_disposable_context({}))
        self.assertTrue(
            path_safety.is_disposable_context(
                {path_safety.DISPOSABLE_TEST_CONTEXT: "1"}
            )
        )

    def test_append_within_declared_hive_is_allowed(self):
        hive = (
            r"C:\repo\.wt\issue-1-worker\tmp"
            r"\blas1-wrapper-test\hive"
        )
        before = path_safety.PathSnapshot(r"C:\Tools", r"C:\Machine")
        after = path_safety.PathSnapshot(
            rf"C:\Tools;{hive}\.dotnet\tools", r"C:\Machine"
        )

        diff = path_safety.assert_path_change_allowed(before, after, hive)

        self.assertIn("user Path before", diff)
        self.assertIn(hive, diff)

    def test_addition_outside_declared_hive_is_rejected(self):
        hive = (
            r"C:\repo\.wt\issue-1-worker\tmp"
            r"\blas1-wrapper-test\hive"
        )
        before = path_safety.PathSnapshot(r"C:\Tools", None)
        after = path_safety.PathSnapshot(r"C:\Tools;C:\Unexpected", None)

        with self.assertRaisesRegex(
            AssertionError, "changed outside the declared Test Hive"
        ):
            path_safety.assert_path_change_allowed(before, after, hive)

    def test_rewriting_existing_path_entries_is_rejected(self):
        hive = (
            r"C:\repo\.wt\issue-1-worker\tmp"
            r"\blas1-wrapper-test\hive"
        )
        before = path_safety.PathSnapshot(r"C:\Tools;C:\Other", None)
        after = path_safety.PathSnapshot(
            rf"C:\Other;{hive}\.dotnet\tools", None
        )

        with self.assertRaisesRegex(
            AssertionError, "changed outside the declared Test Hive"
        ):
            path_safety.assert_path_change_allowed(before, after, hive)

    def test_skip_message_names_isolation_boundary_and_routes(self):
        message = path_safety.skip_message(25)

        self.assertIn("DOTNET_CLI_HOME", message)
        self.assertIn("not a Windows-user isolation boundary", message)
        self.assertIn("ephemeral CI runner", message)
        self.assertIn("Windows Sandbox", message)
        self.assertIn("disposable VM", message)
        self.assertIn("Preflight found 25", message)

    def test_static_scanner_detects_persistent_path_writes(self):
        samples = (
            "set" + "x PATH C:\\Unexpected",
            "winreg.Set" + "Value(key, 'Path', value)",
            "[Environment]::SetEnvironment"
            + "Variable('Path', $value, 'User')",
            "Set-" + "ItemProperty HK" + "CU:\\Environment -Name Path",
        )

        for sample in samples:
            with self.subTest(sample=sample):
                self.assertTrue(find_forbidden_path_writes(sample))

    def test_repository_code_has_no_persistent_path_writes(self):
        violations = []
        for folder in (REPO_ROOT / "tests", REPO_ROOT / "tools"):
            for path in folder.rglob("*"):
                if not path.is_file() or path.suffix.lower() not in SOURCE_SUFFIXES:
                    continue
                findings = find_forbidden_path_writes(
                    path.read_text(encoding="utf-8", errors="replace")
                )
                for finding in findings:
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}: {finding}"
                    )

        self.assertEqual([], violations)


if __name__ == "__main__":
    unittest.main()
