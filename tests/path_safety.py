import difflib
import functools
import os
import re
import sys
import unittest
import uuid
import winreg
from collections import namedtuple
from datetime import datetime, timezone
from pathlib import Path


DISPOSABLE_TEST_CONTEXT = "BLAS1_DISPOSABLE_TEST_CONTEXT"
USER_ENVIRONMENT_KEY = "Environment"
MACHINE_ENVIRONMENT_KEY = (
    r"SYSTEM\CurrentControlSet\Control\Session Manager\Environment"
)
REPOSITORY_TEST_HIVE = re.compile(
    r"(?i)[\\/]\.wt[\\/]issue-1-[^\\/]+[\\/]tmp[\\/]"
    r"[^;]*[\\/]hive[\\/]\.dotnet[\\/]tools(?:[\\/]|$)"
)

PathSnapshot = namedtuple(
    "PathSnapshot", "user machine context_id phase captured_at"
)
_reported_preflight_entries = set()


def capture_path_snapshot(context_id, phase):
    if not context_id or phase not in {"before", "after"}:
        raise ValueError("A PATH snapshot requires a context id and valid phase.")
    return PathSnapshot(
        _read_persistent_path(winreg.HKEY_CURRENT_USER, USER_ENVIRONMENT_KEY),
        _read_persistent_path(
            winreg.HKEY_LOCAL_MACHINE, MACHINE_ENVIRONMENT_KEY
        ),
        context_id,
        phase,
        datetime.now(timezone.utc),
    )


def _read_persistent_path(root, key_name):
    try:
        with winreg.OpenKey(root, key_name, 0, winreg.KEY_READ) as key:
            value, _ = winreg.QueryValueEx(key, "Path")
            return str(value)
    except FileNotFoundError:
        return None


def is_disposable_context(environ=None):
    # shortcut: this flag is operator-declared; it proves intent, not isolation.
    environment = os.environ if environ is None else environ
    value = environment.get(DISPOSABLE_TEST_CONTEXT, "")
    return value.strip().lower() in {"1", "true", "yes"}


def path_entries(value):
    return [] if not value else value.split(";")


def _split_trailing_empty_entries(value):
    entries = path_entries(value)
    trailing = 0
    while entries and not entries[-1]:
        entries.pop()
        trailing += 1
    return entries, trailing


def repository_test_hive_entries(snapshot):
    entries = []
    for scope, value in (
        ("User", snapshot.user),
        ("Machine", snapshot.machine),
    ):
        for entry in path_entries(value):
            if REPOSITORY_TEST_HIVE.search(entry):
                entries.append((scope, entry))
    return entries


def report_preflight(snapshot):
    entries = repository_test_hive_entries(snapshot)
    new_entries = [
        entry for entry in entries if entry not in _reported_preflight_entries
    ]
    if new_entries:
        print(
            "PATH safety preflight found repository Test Hive entries "
            f"({_snapshot_label(snapshot)}):",
            file=sys.stderr,
        )
        for scope, entry in new_entries:
            print(f"  [{scope}] {entry}", file=sys.stderr)
        _reported_preflight_entries.update(new_entries)
    return entries


def skip_message(entry_count, snapshot=None):
    snapshot_detail = (
        f" Snapshot: {_snapshot_label(snapshot)}." if snapshot else ""
    )
    return (
        "DOTNET_CLI_HOME isolates template-engine state, but it is not a "
        "Windows-user isolation boundary. Dotnet-backed template tests require "
        "a Disposable Test Context: an ephemeral CI runner, Windows Sandbox, or "
        "another disposable VM. Set "
        f"{DISPOSABLE_TEST_CONTEXT}=1 only inside that context. Preflight found "
        f"{entry_count} repository Test Hive PATH entries.{snapshot_detail}"
    )


def _snapshot_label(snapshot):
    if snapshot is None:
        return "missing snapshot"
    captured_at = snapshot.captured_at
    captured_at = (
        captured_at.isoformat()
        if isinstance(captured_at, datetime)
        else captured_at
    )
    return (
        f"context_id={snapshot.context_id} phase={snapshot.phase} "
        f"captured_at={captured_at!s}"
    )


def _assert_path_snapshot_pair(before, after):
    details = f"before[{_snapshot_label(before)}]; after[{_snapshot_label(after)}]"
    if before is None or after is None:
        raise AssertionError(
            "Persistent PATH snapshots require a complete before/after pair: "
            f"{details}"
        )
    if before.phase != "before" or after.phase != "after":
        raise AssertionError(
            "Persistent PATH snapshots require one before and one after "
            f"phase: {details}"
        )
    if not before.context_id or before.context_id != after.context_id:
        raise AssertionError(
            "Persistent PATH snapshots must have the same context id: "
            f"{details}"
        )
    for snapshot in (before, after):
        captured_at = snapshot.captured_at
        if (
            not isinstance(captured_at, datetime)
            or captured_at.utcoffset() != timezone.utc.utcoffset(captured_at)
        ):
            raise AssertionError(
                "Persistent PATH snapshots require a UTC capture time: "
                f"{details}"
            )
    if after.captured_at < before.captured_at:
        raise AssertionError(
            "Persistent PATH snapshot capture times are out of order: "
            f"{details}"
        )
    return before, after


def persistent_path_diff(before, after):
    before, after = _assert_path_snapshot_pair(before, after)
    lines = []
    for scope in ("user", "machine"):
        old = getattr(before, scope)
        new = getattr(after, scope)
        if old == new:
            continue
        diff = list(
            difflib.unified_diff(
                path_entries(old),
                path_entries(new),
                fromfile=(
                    f"{scope} Path before ({_snapshot_label(before)})"
                ),
                tofile=f"{scope} Path after ({_snapshot_label(after)})",
                lineterm="",
            )
        )
        lines.extend(diff or [f"{scope} Path raw value changed"])
    return "\n".join(lines)


def _is_within_hive(entry, hive):
    try:
        entry_path = os.path.normcase(
            os.path.normpath(os.path.abspath(entry))
        )
        hive_path = os.path.normcase(
            os.path.normpath(os.path.abspath(str(hive)))
        )
        return os.path.commonpath([entry_path, hive_path]) == hive_path
    except ValueError:
        return False


def _is_append_only_within_hive(before, after, hive):
    # The .NET CLI may consume one trailing empty separator when it appends.
    old_entries, old_trailing = _split_trailing_empty_entries(before)
    new_entries, new_trailing = _split_trailing_empty_entries(after)
    if new_entries[: len(old_entries)] != old_entries:
        return False
    appended = new_entries[len(old_entries) :]
    if not appended:
        return path_entries(before) == path_entries(after)
    if old_trailing - new_trailing not in (0, 1):
        return False
    return all(_is_within_hive(entry, hive) for entry in appended)


def assert_path_change_allowed(before, after, hive):
    diff = persistent_path_diff(before, after)
    if not diff:
        return ""
    for scope in ("user", "machine"):
        if not _is_append_only_within_hive(
            getattr(before, scope), getattr(after, scope), hive
        ):
            raise AssertionError(
                f"Persistent {scope} Path changed outside the declared Test "
                f"Hive.\nExact diff:\n{diff}"
            )
    return diff


class DotnetTestContext:
    def __init__(self, hive):
        self.hive = Path(hive)
        self.context_id = uuid.uuid4().hex
        self.before = None
        self.active = False

    def start(self):
        self.before = capture_path_snapshot(self.context_id, "before")
        entries = report_preflight(self.before)
        if not is_disposable_context():
            after = capture_path_snapshot(self.context_id, "after")
            assert_path_change_allowed(self.before, after, self.hive)
            raise unittest.SkipTest(
                skip_message(len(entries), self.before)
            )
        self.active = True

    def finish(self):
        if not self.active:
            return
        after = capture_path_snapshot(self.context_id, "after")
        try:
            diff = assert_path_change_allowed(self.before, after, self.hive)
        finally:
            self.active = False
        if diff:
            print(
                "Persistent PATH changes stayed within the declared Test Hive "
                f"{self.hive}:\n{diff}",
                file=sys.stderr,
            )

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.finish()
        return False


def disposable_dotnet_test(method):
    @functools.wraps(method)
    def wrapped(self, *args, **kwargs):
        with DotnetTestContext(self.hive):
            return method(self, *args, **kwargs)

    return wrapped
