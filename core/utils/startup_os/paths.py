# Copyright (c) 2026, Rokct Intelligence (pty) Ltd.
# For license information, please see license.txt


"""Workspace resolution and safe path construction.

Two jobs, both security-relevant:

1.  Resolve the StartupOS workspace root deterministically, and say out loud
    which rule fired. The old resolver stacked five silent heuristics, so the
    same command wrote to different places under pytest, cron and Frappe.

2.  Refuse instance names that escape the workspace. `auto_provision_profile`
    is called by Hermes with an entity name lifted from a WhatsApp message —
    that string is untrusted input and must never reach `os.path.join` raw.
"""

import os
import re
import json

from core.errors import UnsafeNameError, WorkspaceError

WORKSPACE_ENV_VAR = "STARTUPOS_ROOT"
CONFIG_FILENAME = ".startupos.json"
WORKSPACE_DIRNAME = "StartupOS"

INSTANCE_TYPES = ("business", "life")

# Deliberately strict: alphanumeric start, then alphanumerics, dot, dash,
# underscore. No separators, no traversal, no leading dot, 64 chars max.
_SAFE_NAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")

# Reserved device names on Windows. `CON`, `NUL` etc. resolve to devices
# regardless of extension, so a profile named "CON" would hang or corrupt.
_WINDOWS_RESERVED = {
    "con",
    "prn",
    "aux",
    "nul",
    *(f"com{i}" for i in range(1, 10)),
    *(f"lpt{i}" for i in range(1, 10)),
}


def sanitize_instance_name(name):
    """Validate an instance (profile) name, or raise UnsafeNameError.

    Rejects traversal, absolute paths, separators, reserved device names and
    trailing dots/spaces. Returns the name unchanged when it is safe — this is
    a validator, not a transformer, because silently rewriting a user's company
    name into something else is its own kind of bug.
    """
    if name is None:
        raise UnsafeNameError("Instance name is required.")
    if not isinstance(name, str):
        raise UnsafeNameError(
            f"Instance name must be a string, got {type(name).__name__}."
        )

    candidate = name.strip()
    if not candidate:
        raise UnsafeNameError("Instance name is empty.")

    if not _SAFE_NAME_RE.match(candidate):
        raise UnsafeNameError(
            f"Unsafe instance name {name!r}. Use 1-64 characters: letters, digits, "
            "dot, dash or underscore, starting with a letter or digit. "
            "Path separators and '..' are not permitted."
        )

    # `_SAFE_NAME_RE` already blocks separators, but be explicit: a future edit
    # to the regex must not silently reopen traversal.
    if os.sep in candidate or (os.altsep and os.altsep in candidate):
        raise UnsafeNameError(f"Instance name {name!r} contains a path separator.")
    if candidate in (os.curdir, os.pardir):
        raise UnsafeNameError(f"Instance name {name!r} is a path traversal token.")
    if candidate.endswith((".", " ")):
        raise UnsafeNameError(
            f"Instance name {name!r} may not end with '.' or a space."
        )

    stem = candidate.split(".")[0].lower()
    if stem in _WINDOWS_RESERVED:
        raise UnsafeNameError(
            f"Instance name {name!r} is a reserved device name on Windows."
        )

    return candidate


def validate_instance_type(instance_type):
    """Validate the profile type, or raise UnsafeNameError.

    The CLI constrained this via argparse `choices`, but the Python API that
    Hermes calls did not — so `instance_type="../../evil"` escaped the
    workspace just as readily as a bad name.
    """
    if not isinstance(instance_type, str):
        raise UnsafeNameError(
            f"Instance type must be a string, got {type(instance_type).__name__}."
        )
    candidate = instance_type.strip().lower()
    if candidate not in INSTANCE_TYPES:
        raise UnsafeNameError(
            f"Unknown instance type {instance_type!r}. Expected one of: "
            f"{', '.join(INSTANCE_TYPES)}."
        )
    return candidate


def assert_contained(root, candidate):
    """Assert `candidate` resolves inside `root`. Belt and braces after validation."""
    root_real = os.path.realpath(root)
    candidate_real = os.path.realpath(candidate)
    try:
        common = os.path.commonpath([root_real, candidate_real])
    except ValueError:
        # Different drives on Windows — definitively outside.
        raise UnsafeNameError(
            f"Resolved path {candidate_real!r} is outside the workspace {root_real!r}."
        )
    if common != root_real:
        raise UnsafeNameError(
            f"Resolved path {candidate_real!r} is outside the workspace {root_real!r}."
        )
    return candidate_real


def _find_upwards(start, filename):
    """Walk up from `start` looking for `filename`. Returns its dir, or None."""
    current = os.path.abspath(start)
    while True:
        if os.path.isfile(os.path.join(current, filename)):
            return current
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def _find_dir_upwards(start, dirname):
    """Walk up from `start` looking for a directory named `dirname`."""
    current = os.path.abspath(start)
    while True:
        candidate = os.path.join(current, dirname)
        if os.path.isdir(candidate):
            return candidate
        parent = os.path.dirname(current)
        if parent == current:
            return None
        current = parent


def resolve_workspace_root(explicit=None, verbose=True):
    """Resolve the StartupOS workspace root, in a fixed, documented order.

    1.  `explicit` argument (CLI `--root`)
    2.  `$STARTUPOS_ROOT`
    3.  `.startupos.json` found by walking up from cwd, key `workspace_root`
    4.  Frappe site path, when running inside a Frappe process
    5.  An existing `StartupOS/` directory found by walking up from cwd
    6.  `<cwd>/StartupOS` (created on demand)

    The rule that fired is printed, so a surprising output location is
    diagnosable from the log instead of by reading five heuristics.
    """

    def _announce(rule, path):
        if verbose:
            print(f"[StartupOS] Workspace root via {rule}: {path}")
        return path

    if explicit:
        return _announce("--root argument", os.path.abspath(explicit))

    env_root = os.environ.get(WORKSPACE_ENV_VAR)
    if env_root:
        return _announce(f"${WORKSPACE_ENV_VAR}", os.path.abspath(env_root))

    config_dir = _find_upwards(os.getcwd(), CONFIG_FILENAME)
    if config_dir:
        config_path = os.path.join(config_dir, CONFIG_FILENAME)
        try:
            with open(config_path, "r", encoding="utf-8") as handle:
                config = json.load(handle)
            configured = config.get("workspace_root")
            if configured:
                resolved = configured
                if not os.path.isabs(resolved):
                    resolved = os.path.join(config_dir, resolved)
                return _announce(CONFIG_FILENAME, os.path.abspath(resolved))
        except (OSError, ValueError) as exc:
            raise WorkspaceError(f"Could not read {config_path}: {exc}") from exc

    frappe_root = _resolve_frappe_root()
    if frappe_root:
        return _announce("Frappe site path", frappe_root)

    discovered = _find_dir_upwards(os.getcwd(), WORKSPACE_DIRNAME)
    if discovered:
        return _announce(f"discovered {WORKSPACE_DIRNAME}/ directory", discovered)

    fallback = os.path.join(os.getcwd(), WORKSPACE_DIRNAME)
    return _announce("default (cwd)", fallback)


def _resolve_frappe_root():
    """Return the Frappe-hosted workspace path, or None when not under Frappe."""
    try:
        import sys

        if "frappe" in sys.modules:
            import frappe

            if hasattr(frappe, "get_site_path"):
                return frappe.get_site_path(WORKSPACE_DIRNAME)
    except Exception:
        # Frappe present but not initialised (no site context). Fall through.
        pass

    bench_sites = "/home/frappe/frappe-bench/sites"
    if os.path.isdir(bench_sites):
        return os.path.join(bench_sites, WORKSPACE_DIRNAME)

    return None


def instance_dir(root, instance_type, instance_name):
    """Build a validated, contained path to an instance directory."""
    instance_type = validate_instance_type(instance_type)
    instance_name = sanitize_instance_name(instance_name)
    candidate = os.path.join(
        os.path.abspath(root), "instances", instance_type, instance_name
    )
    assert_contained(root, candidate)
    return candidate


def questions_path(root, instance_type, instance_name):
    return os.path.join(
        instance_dir(root, instance_type, instance_name), "questions.md"
    )


def output_dir(root, instance_type, instance_name):
    return os.path.join(instance_dir(root, instance_type, instance_name), "output")


def templates_dir(root, instance_type):
    instance_type = validate_instance_type(instance_type)
    return os.path.join(os.path.abspath(root), "templates", instance_type)
