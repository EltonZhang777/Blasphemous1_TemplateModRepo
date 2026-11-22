import re
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

import path_safety


REPO_ROOT = Path(__file__).resolve().parents[1]
SOURCE_SUFFIXES = {".py", ".ps1", ".psm1", ".bat", ".cmd"}
CAPTURED_AT = datetime(2026, 11, 20, tzinfo=timezone.utc)
PAIR_HIVE = r"C:\repo\hive"


def make_snapshot(
    user,
    machine,
    context_id="test-context",
    phase="before",
    captured_at=CAPTURED_AT,
):
    return path_safety.PathSnapshot(
        user, machine, context_id, phase, captured_at
    )


def make_snapshot_pair(
    before_user,
    before_machine,
    after_user,
    after_machine,
    context_id="test-context",
):
    return (
        make_snapshot(
            before_user, before_machine, context_id, "before", CAPTURED_AT
        ),
        make_snapshot(
            after_user,
            after_machine,
            context_id,
            "after",
            CAPTURED_AT + timedelta(seconds=1),
        ),
    )


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
    def test_capture_snapshot_records_raw_values_and_utc_metadata(self):
        with mock.patch.object(
            path_safety,
            "_read_persistent_path",
            side_effect=[r"C:\User Path", r"C:\Machine Path"],
        ):
            snapshot = path_safety.capture_path_snapshot("context-1", "before")

        self.assertEqual(snapshot.user, r"C:\User Path")
        self.assertEqual(snapshot.machine, r"C:\Machine Path")
        self.assertEqual(snapshot.context_id, "context-1")
        self.assertEqual(snapshot.phase, "before")
        self.assertEqual(snapshot.captured_at.utcoffset(), timedelta(0))

    def test_valid_path_snapshot_pair_is_accepted(self):
        before, after = make_snapshot_pair("user", "machine", "user", "machine")

        self.assertEqual(
            path_safety.assert_path_change_allowed(before, after, PAIR_HIVE),
            "",
        )

    def test_path_snapshot_pair_rejects_missing_snapshot(self):
        before, after = make_snapshot_pair("user", "machine", "user", "machine")

        for pair in ((before, None), (None, after)):
            with self.subTest(pair=pair):
                with self.assertRaisesRegex(
                    AssertionError, "complete before/after pair"
                ):
                    path_safety.assert_path_change_allowed(*pair, PAIR_HIVE)

    def test_path_snapshot_pair_rejects_duplicate_phase(self):
        before = make_snapshot("user", "machine", phase="before")
        after = make_snapshot("user", "machine", phase="before")

        with self.assertRaisesRegex(AssertionError, "one before and one after"):
            path_safety.assert_path_change_allowed(before, after, PAIR_HIVE)

    def test_path_snapshot_pair_rejects_mismatched_context_ids(self):
        before = make_snapshot("user", "machine", context_id="first")
        after = make_snapshot("user", "machine", context_id="second", phase="after")

        with self.assertRaisesRegex(AssertionError, "same context id"):
            path_safety.assert_path_change_allowed(before, after, PAIR_HIVE)

    def test_path_snapshot_pair_rejects_missing_or_non_utc_timestamps(self):
        before = make_snapshot("user", "machine")
        for captured_at in (
            None,
            datetime(2026, 11, 20),
            datetime(2026, 11, 20, tzinfo=timezone(timedelta(hours=1))),
        ):
            with self.subTest(captured_at=captured_at):
                after = make_snapshot(
                    "user", "machine", phase="after", captured_at=captured_at
                )
                with self.assertRaisesRegex(AssertionError, "UTC capture time"):
                    path_safety.assert_path_change_allowed(
                        before, after, PAIR_HIVE
                    )

    def test_path_snapshot_pair_rejects_reversed_capture_times(self):
        before = make_snapshot(
            "user",
            "machine",
            captured_at=CAPTURED_AT + timedelta(seconds=1),
        )
        after = make_snapshot(
            "user", "machine", phase="after", captured_at=CAPTURED_AT
        )

        with self.assertRaisesRegex(
            AssertionError, "capture times are out of order"
        ):
            path_safety.assert_path_change_allowed(before, after, PAIR_HIVE)

    def test_pair_error_diagnostics_identify_context_phase_and_time(self):
        before = make_snapshot("user", "machine", context_id="first")
        after = make_snapshot(
            "user", "machine", context_id="second", phase="after"
        )

        with self.assertRaises(AssertionError) as raised:
            path_safety.assert_path_change_allowed(before, after, PAIR_HIVE)

        message = str(raised.exception)
        self.assertIn("context_id=first", message)
        self.assertIn("phase=before", message)
        self.assertIn(CAPTURED_AT.isoformat(), message)
        self.assertIn("context_id=second", message)
        self.assertIn("phase=after", message)

    def test_raw_value_changes_retain_snapshot_identity(self):
        cases = (
            (
                "user",
                (None, r"C:\Machine"),
                ("", r"C:\Machine"),
            ),
            (
                "machine",
                (r"C:\User", None),
                (r"C:\User", ""),
            ),
        )

        for scope, before_values, after_values in cases:
            with self.subTest(scope=scope):
                before, after = make_snapshot_pair(
                    before_values[0],
                    before_values[1],
                    after_values[0],
                    after_values[1],
                    context_id="raw-path-context",
                )

                with self.assertRaises(AssertionError) as raised:
                    path_safety.assert_path_change_allowed(
                        before, after, PAIR_HIVE
                    )

                message = str(raised.exception)
                self.assertIn(
                    f"Persistent {scope} Path changed outside", message
                )
                self.assertIn(
                    "before: context_id=raw-path-context phase=before "
                    f"captured_at={CAPTURED_AT.isoformat()}",
                    message,
                )
                self.assertIn(
                    "after: context_id=raw-path-context phase=after "
                    "captured_at="
                    f"{(CAPTURED_AT + timedelta(seconds=1)).isoformat()}",
                    message,
                )

    def test_context_snapshots_bracket_the_test_body(self):
        context = path_safety.DotnetTestContext(r"C:\repo\tmp\hive")
        events = []
        captured = []

        def capture(context_id, phase):
            events.append(phase)
            snapshot = make_snapshot("user", "machine", context_id, phase)
            captured.append(snapshot)
            return snapshot

        with mock.patch.object(
            path_safety, "capture_path_snapshot", side_effect=capture
        ), mock.patch.object(
            path_safety, "report_preflight", return_value=[]
        ), mock.patch.object(
            path_safety, "is_disposable_context", return_value=True
        ):
            with context:
                events.append("first dotnet invocation")

        self.assertEqual(events, ["before", "first dotnet invocation", "after"])
        self.assertEqual(captured[0].context_id, captured[1].context_id)
        self.assertEqual([item.phase for item in captured], ["before", "after"])

    def test_normal_host_skips_before_the_test_body(self):
        context = path_safety.DotnetTestContext(r"C:\repo\tmp\hive")
        events = []

        def capture(context_id, phase):
            events.append(phase)
            return make_snapshot("user", "machine", context_id, phase)

        with mock.patch.object(
            path_safety, "capture_path_snapshot", side_effect=capture
        ), mock.patch.object(
            path_safety, "report_preflight", return_value=[]
        ), mock.patch.object(
            path_safety, "is_disposable_context", return_value=False
        ):
            with self.assertRaises(unittest.SkipTest) as raised:
                with context:
                    events.append("first dotnet invocation")

        self.assertEqual(events, ["before", "after"])
        message = str(raised.exception)
        self.assertIn(f"context_id={context.context_id}", message)
        self.assertIn("phase=before", message)
        self.assertIn(CAPTURED_AT.isoformat(), message)

    def test_repository_test_hives_are_reported(self):
        entry = (
            r"C:\repo\.wt\issue-1-worker\tmp"
            r"\blas1-wrapper-test\hive\.dotnet\tools"
        )
        snapshot = make_snapshot(entry, "")

        self.assertEqual(
            [("User", entry)],
            path_safety.repository_test_hive_entries(snapshot),
        )

    def test_unrelated_paths_are_not_reported(self):
        snapshot = make_snapshot(
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
        before, after = make_snapshot_pair(
            r"C:\Tools",
            r"C:\Machine",
            rf"C:\Tools;{hive}\.dotnet\tools",
            r"C:\Machine",
        )

        diff = path_safety.assert_path_change_allowed(before, after, hive)

        self.assertIn("user Path before", diff)
        self.assertIn(hive, diff)
        self.assertIn(
            "context_id=test-context phase=before "
            f"captured_at={CAPTURED_AT.isoformat()}",
            diff,
        )
        self.assertIn(
            "context_id=test-context phase=after captured_at="
            f"{(CAPTURED_AT + timedelta(seconds=1)).isoformat()}",
            diff,
        )

    def test_empty_path_entries_do_not_block_hive_appends(self):
        hive = (
            r"C:\repo\.wt\issue-1-worker\tmp"
            r"\blas1-wrapper-test\hive"
        )
        before, after = make_snapshot_pair(
            r"C:\Tools;",
            None,
            rf"C:\Tools;{hive}\.dotnet\tools",
            None,
        )

        diff = path_safety.assert_path_change_allowed(before, after, hive)

        self.assertIn(hive, diff)

    def test_leading_empty_path_entry_is_rejected(self):
        hive = (
            r"C:\repo\.wt\issue-1-worker\tmp"
            r"\blas1-wrapper-test\hive"
        )
        before, after = make_snapshot_pair(
            r"C:\Tools", None, r";C:\Tools", None
        )

        with self.assertRaisesRegex(
            AssertionError, "changed outside the declared Test Hive"
        ):
            path_safety.assert_path_change_allowed(before, after, hive)

    def test_trailing_empty_path_changes_are_rejected_without_hive_append(self):
        hive = (
            r"C:\repo\.wt\issue-1-worker\tmp"
            r"\blas1-wrapper-test\hive"
        )
        before, after = make_snapshot_pair(
            r"C:\Tools", None, r"C:\Tools;;", None
        )

        with self.assertRaisesRegex(
            AssertionError, "changed outside the declared Test Hive"
        ):
            path_safety.assert_path_change_allowed(before, after, hive)

    def test_hive_append_cannot_consume_multiple_trailing_empty_entries(self):
        hive = (
            r"C:\repo\.wt\issue-1-worker\tmp"
            r"\blas1-wrapper-test\hive"
        )
        before, after = make_snapshot_pair(
            r"C:\Tools;;",
            None,
            rf"C:\Tools;{hive}\.dotnet\tools",
            None,
        )

        with self.assertRaisesRegex(
            AssertionError, "changed outside the declared Test Hive"
        ):
            path_safety.assert_path_change_allowed(before, after, hive)

    def test_addition_outside_declared_hive_is_rejected(self):
        hive = (
            r"C:\repo\.wt\issue-1-worker\tmp"
            r"\blas1-wrapper-test\hive"
        )
        before, after = make_snapshot_pair(
            r"C:\Tools", None, r"C:\Tools;C:\Unexpected", None
        )

        with self.assertRaisesRegex(
            AssertionError, "changed outside the declared Test Hive"
        ):
            path_safety.assert_path_change_allowed(before, after, hive)

    def test_rewriting_existing_path_entries_is_rejected(self):
        hive = (
            r"C:\repo\.wt\issue-1-worker\tmp"
            r"\blas1-wrapper-test\hive"
        )
        before, after = make_snapshot_pair(
            r"C:\Tools;C:\Other",
            None,
            rf"C:\Other;{hive}\.dotnet\tools",
            None,
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
