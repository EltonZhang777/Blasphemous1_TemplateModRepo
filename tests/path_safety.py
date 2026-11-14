import difflib
import functools
import os
import re
import sys
import unittest
import winreg
from collections import namedtuple
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

PathSnapshot = namedtuple("PathSnapshot", "user machine")
_reported_preflight_entries = set()


def capture_path_snapshot():
    return PathSnapshot(
        _read_persistent_path(winreg.HKEY_CURRENT_USER, USER_ENVIRONMENT_KEY),
        _read_persistent_path(
            winreg.HKEY_LOCAL_MACHINE, MACHINE_ENVIRONMENT_KEY
        ),
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
            "PATH safety preflight found repository Test Hive entries:",
            file=sys.stderr,
        )
        for scope, entry in new_entries:
            print(f"  [{scope}] {entry}", file=sys.stderr)
        _reported_preflight_entries.update(new_entries)
    return entries


def skip_message(entry_count):
    return (
        "DOTNET_CLI_HOME isolates template-engine state, but it is not a "
        "Windows-user isolation boundary. Dotnet-backed template tests require "
        "a Disposable Test Context: an ephemeral CI runner, Windows Sandbox, or "
        "another disposable VM. Set "
        f"{DISPOSABLE_TEST_CONTEXT}=1 only inside that context. Preflight found "
        f"{entry_count} repository Test Hive PATH entries."
    )


def persistent_path_diff(before, after):
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
                fromfile=f"{scope} Path before",
                tofile=f"{scope} Path after",
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
    old_entries = path_entries(before)
    new_entries = path_entries(after)
    if new_entries[: len(old_entries)] != old_entries:
        return False
    return all(
        _is_within_hive(entry, hive)
        for entry in new_entries[len(old_entries) :]
    )


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
        self.before = None
        self.active = False

    def start(self):
        self.before = capture_path_snapshot()
        entries = report_preflight(self.before)
        if not is_disposable_context():
            after = capture_path_snapshot()
            assert_path_change_allowed(self.before, after, self.hive)
            raise unittest.SkipTest(skip_message(len(entries)))
        self.active = True

    def finish(self):
        if not self.active:
            return
        after = capture_path_snapshot()
        diff = assert_path_change_allowed(self.before, after, self.hive)
        if diff:
            print(
                "Persistent PATH changes stayed within the declared Test Hive "
                f"{self.hive}:\n{diff}",
                file=sys.stderr,
            )
        self.active = False

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
