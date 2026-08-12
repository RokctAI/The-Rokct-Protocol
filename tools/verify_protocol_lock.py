#!/usr/bin/env python3
"""Verify protocol.lock.json against the embedded pins and the pinned source.

Modes:
  python tools/verify_protocol_lock.py            network mode (default):
      offline checks, plus fetch every lock target from
      https://raw.githubusercontent.com/<repo>/<ref>/<path> and verify its
      SHA-256 against the lockfile.
  python tools/verify_protocol_lock.py --offline  only check that every
      embedded constant (PROTOCOL_REF / *_SHA256 / EXPECTED_SHA256) across all
      consumer files matches the lockfile.
  python tools/verify_protocol_lock.py --git      like network mode, but read
      the pinned content from the local git object store (`git show`) instead
      of the network.

Exits 1 on any inconsistency, with a message naming the file and the
expected/actual values. CI runs the network mode on every PR and push to main.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import gen_protocol_lock as gen  # noqa: E402  (shared pin table and patterns)

REPO_ROOT = gen.REPO_ROOT
RAW_BASE = f"https://raw.githubusercontent.com/{gen.GITHUB_REPO}"

_ERRORS = []


def fail(message):
    _ERRORS.append(message)
    print(f"[verify] MISMATCH: {message}", file=sys.stderr)


def load_lockfile():
    lock_path = os.path.join(REPO_ROOT, gen.LOCKFILE_NAME)
    if not os.path.exists(lock_path):
        print(f"[verify] {gen.LOCKFILE_NAME} not found at the repo root. "
              "Run tools/gen_protocol_lock.py first.", file=sys.stderr)
        sys.exit(1)
    with open(lock_path, "r", encoding="utf-8") as handle:
        lock = json.load(handle)
    ref = lock.get("ref", "")
    if not re.fullmatch(r"[0-9a-f]{40}", ref):
        print(f"[verify] Lockfile ref {ref!r} is not a full 40-char commit SHA.",
              file=sys.stderr)
        sys.exit(1)
    files = lock.get("files", {})
    expected_targets = set(gen.LOCK_TARGETS)
    actual_targets = set(files)
    for missing in sorted(expected_targets - actual_targets):
        fail(f"{gen.LOCKFILE_NAME} is missing target {missing}")
    for extra in sorted(actual_targets - expected_targets):
        fail(f"{gen.LOCKFILE_NAME} has unexpected target {extra}")
    for path, digest in sorted(files.items()):
        if not re.fullmatch(r"[0-9a-f]{64}", str(digest)):
            fail(f"{gen.LOCKFILE_NAME} entry for {path} is not a sha256 hex digest: {digest!r}")
    return ref, files


def _extract_exactly_one(pattern, text, rel_path, what):
    matches = pattern.findall(text)
    if len(matches) != 1:
        fail(f"{rel_path}: expected exactly one {what}, found {len(matches)}")
        return None
    return matches[0]


def check_embedded_constants(ref, files):
    for rel_path, ops in sorted(gen.CONSUMERS.items()):
        abs_path = os.path.join(REPO_ROOT, rel_path)
        if not os.path.exists(abs_path):
            fail(f"consumer file {rel_path} is missing")
            continue
        with open(abs_path, "r", encoding="utf-8") as handle:
            text = handle.read()
        for op in ops:
            if op[0] == "ref":
                match = _extract_exactly_one(
                    gen.ref_pattern(rel_path), text, rel_path, "PROTOCOL_REF constant")
                if match is not None and match[1] != ref:
                    fail(f"{rel_path}: PROTOCOL_REF is {match[1]}, lockfile ref is {ref}")
            elif op[0] == "sha":
                _, var, target = op
                match = _extract_exactly_one(
                    gen.sha_pattern(var), text, rel_path, f"{var} constant")
                if match is not None and match[1] != files.get(target):
                    fail(f"{rel_path}: {var} is {match[1]}, lockfile says "
                         f"{files.get(target)} for {target}")
            elif op[0] == "dict":
                _, var, targets = op
                block = _extract_exactly_one(
                    gen.dict_pattern(var), text, rel_path, f"{var} block")
                if block is None:
                    continue
                entries = dict(re.findall(r'"([^"]+)":\s*"([0-9a-f]{64})"', block))
                for target in targets:
                    if target not in entries:
                        fail(f"{rel_path}: {var} is missing an entry for {target}")
                    elif entries[target] != files.get(target):
                        fail(f"{rel_path}: {var}[{target!r}] is {entries[target]}, "
                             f"lockfile says {files.get(target)}")
                for extra in sorted(set(entries) - set(targets)):
                    fail(f"{rel_path}: {var} has an unexpected entry for {extra}")


def fetch_pinned(ref, path):
    url = f"{RAW_BASE}/{ref}/{path}"
    request = urllib.request.Request(
        url, headers={"User-Agent": "Mozilla/5.0", "X-Trace-Id": "verify-protocol-lock"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read()


def git_show(ref, path):
    result = subprocess.run(
        ["git", "-C", REPO_ROOT, "show", f"{ref}:{path}"],
        capture_output=True, check=False)
    if result.returncode != 0:
        raise RuntimeError(result.stderr.decode().strip())
    return result.stdout


def check_pinned_content(ref, files, use_git):
    source = "git object store" if use_git else RAW_BASE
    print(f"[verify] Checking {len(files)} pinned targets against {source} @ {ref}")
    for path in sorted(files):
        try:
            payload = git_show(ref, path) if use_git else fetch_pinned(ref, path)
        except Exception as exc:
            fail(f"could not read {path} at {ref}: {exc}")
            continue
        digest = hashlib.sha256(payload).hexdigest()
        if digest != files[path]:
            fail(f"{path} at {ref}: expected sha256 {files[path]}, got {digest}")


def report_working_tree_drift(files):
    """Informational only: a target edited since the pin is the normal state
    of a PR that changes fetched code — the lock bump follows the merge."""
    drifted = []
    for path in sorted(files):
        abs_path = os.path.join(REPO_ROOT, path)
        if not os.path.exists(abs_path):
            continue
        with open(abs_path, "rb") as handle:
            digest = hashlib.sha256(handle.read()).hexdigest()
        if digest != files[path]:
            drifted.append(path)
    if drifted:
        print("[verify] Note: working-tree content differs from the pinned hashes for "
              f"{len(drifted)} target(s) (expected while a change is awaiting its lock "
              "bump): " + ", ".join(drifted))


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--offline", action="store_true",
                      help="only check embedded constants against the lockfile")
    mode.add_argument("--git", action="store_true",
                      help="verify pinned content via `git show` instead of the network")
    args = parser.parse_args(argv)

    ref, files = load_lockfile()
    print(f"[verify] Lockfile ref {ref}, {len(files)} targets, "
          f"{len(gen.CONSUMERS)} consumer files")

    check_embedded_constants(ref, files)
    if not args.offline:
        check_pinned_content(ref, files, use_git=args.git)
    report_working_tree_drift(files)

    if _ERRORS:
        print(f"[verify] FAILED with {len(_ERRORS)} inconsistenc"
              f"{'y' if len(_ERRORS) == 1 else 'ies'}.", file=sys.stderr)
        return 1
    print("[verify] OK: lockfile, embedded constants"
          + ("" if args.offline else " and pinned content") + " are consistent.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
