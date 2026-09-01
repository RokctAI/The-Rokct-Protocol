#!/usr/bin/env python3
# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

# Licensed under the MIT License.
# Copyright 2024 ROKCT INTELLIGENCE (PTY) LTD
"""Generate protocol.lock.json and rewrite the embedded pin constants.

The protocol fetches parts of its own repository at runtime (skill wrappers,
bootstrappers, the engine loader) and executes what it downloads. Every one of
those fetches is pinned to a single commit SHA (PROTOCOL_REF) and verified
against a SHA-256 recorded here before anything runs.

This tool is the single source of truth for those pins:

  python tools/gen_protocol_lock.py --ref <commit-sha>

1. computes the SHA-256 of every fetched-and-executed target from the git
   object store at that ref (`git show <ref>:<path>` — NOT the working tree),
2. writes protocol.lock.json at the repo root, and
3. rewrites the embedded constants (PROTOCOL_REF / *_SHA256 / EXPECTED_SHA256)
   in every consumer file. Consumers carry embedded constants because skill
   folders are installed standalone into host apps without repo context — they
   cannot read the repo-root lockfile at runtime.

The rewrite is idempotent: running it twice with the same ref produces zero
diff. CI runs tools/verify_protocol_lock.py to keep the lockfile and the
embedded constants honest.
"""

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GITHUB_REPO = "RokctAI/The-Rokct-Protocol"
LOCKFILE_NAME = "protocol.lock.json"

_DELEGATES = "core/utils/agent_delegation"
_ENGINE = "core/utils/startup_os"
_SCRIPTS = "core/skills/agent_delegation/scripts"
_OPPORTUNITIES = "core/utils/opportunities"
_OPP_SCRIPTS = "core/skills/.rok/opportunities_registry/scripts"

# Must match ENGINE_MODULES in core/skills/.rok/startup_os/scripts/_bootstrap.py.
ENGINE_MODULES = (
    "__init__.py",
    "errors.py",
    "paths.py",
    "parser.py",
    "jurisdictions.py",
    "compliance.py",
    "template_engine.py",
    "documents.py",
    "safe_io.py",
    "schemas.py",
    "compiler.py",
    "agent_bridge.py",
    "polish.py",
    "branding.py",
    "render_pptx.py",
    "render_xlsx.py",
)

# Every backend file the opportunities_registry wrappers extract from the
# pinned repository archive into their cache. The wrappers pull the whole
# directory, and any extracted .py can be executed or imported by a sibling,
# so every file is pinned. Relative to _OPPORTUNITIES.
OPPORTUNITIES_FILES = (
    "check_links.py",
    "ci/check_links.py",
    "eeip/discover_eeip.py",
    "equity/discover_sources.py",
    "equity/equity_sync.py",
    "equity/funder_finder.py",
    "equity/funder_manager.py",
    "equity/test_funder_filtering.py",
    "equity/verify_sources.py",
    "grants/scrapers/f4c.py",
    "maintenance/index.py",
    "registry_orchestrator/healers.py",
    "registry_orchestrator/index.py",
    "registry_orchestrator/scanners.py",
    "registry_orchestrator/send_registry_emails.py",
    "registry_orchestrator/updaters.py",
    "response_kits/index.py",
    "tenders/api/ocds.py",
    "tenders/enrichment/extract_requirements.py",
    "tenders/enrichment/pdf_to_md.py",
    "tenders/enrichment/test_extract_requirements.py",
    "tenders/index.py",
    "tenders/scrapers/musina.py",
    "tenders/scrapers/test_musina_dates.py",
    "tenders/utils/tender_resolver.py",
)

# Template/data files the bootstrappers install into host repos. Previously
# covered by an advisory core/templates/manifest.json with truncated hashes;
# folded into the lockfile so protocol.lock.json is the single enforcing
# integrity mechanism for everything the protocol distributes.
TEMPLATE_FILES = (
    "memory.md",
    "active_session.txt",
    "decision_log.md",
    "project_map.md",
    "session_summary.md",
    ".markdownlint.json",
)

# Every repository path that is fetched at runtime and executed (or installed
# as executable content, e.g. a GitHub workflow). Keys of protocol.lock.json.
LOCK_TARGETS = (
    (
        f"{_DELEGATES}/privacy.py",
        f"{_DELEGATES}/job_manager.py",
        f"{_DELEGATES}/reporter.py",
        f"{_DELEGATES}/delegate_to_agent.py",
        f"{_DELEGATES}/handle_groq_output.py",
        f"{_DELEGATES}/update_structure.py",
        f"{_DELEGATES}/manage_sessions.py",
        "core/utils/frappe/compose_backend.py",
        "core/utils/flutter/sdk_composer.py",
        "core/utils/flutter/sdk_installer_base.py",
    )
    + tuple(f"{_ENGINE}/{m}" for m in ENGINE_MODULES)
    + (
        "profiles/local/initiate.py",
        "profiles/web/initiate.py",
        "workflows/maintenance.yml",
    )
    + tuple(f"{_OPPORTUNITIES}/{p}" for p in OPPORTUNITIES_FILES)
    + tuple(f"core/templates/{t}" for t in TEMPLATE_FILES)
)

# The 12 scaffold wrappers that share a byte-identical resolve_delegate().
_WRAPPER_TARGETS = {
    "call_groq.py": f"{_DELEGATES}/delegate_to_agent.py",
    "call_jules.py": f"{_DELEGATES}/delegate_to_agent.py",
    "check_health.py": f"{_DELEGATES}/reporter.py",
    "handle_groq_output.py": f"{_DELEGATES}/handle_groq_output.py",
    "lock_job.py": f"{_DELEGATES}/job_manager.py",
    "manage_sessions.py": f"{_DELEGATES}/manage_sessions.py",
    "privacy_sync.py": f"{_DELEGATES}/privacy.py",
    "response_kits.py": f"{_DELEGATES}/job_manager.py",
    "update_audit_logs.py": f"{_DELEGATES}/reporter.py",
    "update_dashboard.py": f"{_DELEGATES}/reporter.py",
    "update_status.py": f"{_DELEGATES}/job_manager.py",
    "update_structure.py": f"{_DELEGATES}/update_structure.py",
}

_INITIATE_LOCAL_EXPECTED = ("profiles/local/initiate.py", "workflows/maintenance.yml")
_INITIATE_WEB_EXPECTED = ("profiles/web/initiate.py", "workflows/maintenance.yml")

# consumer file -> list of embedded-constant operations.
#   ("ref",)                       PROTOCOL_REF-style pin (syntax by extension)
#   ("sha", VAR, target)           single-target 64-hex constant
#   ("dict", VAR, (targets...))    multi-target {repo-path: sha256} dict
CONSUMERS = {}
for _name, _target in _WRAPPER_TARGETS.items():
    CONSUMERS[f"{_SCRIPTS}/{_name}"] = [("ref",), ("sha", "DELEGATE_SHA256", _target)]
CONSUMERS.update(
    {
        f"{_SCRIPTS}/crypto_utils.py": [
            ("ref",),
            ("sha", "DELEGATE_SHA256", f"{_DELEGATES}/privacy.py"),
        ],
        f"{_SCRIPTS}/update_classifications.py": [
            ("ref",),
            ("sha", "DELEGATE_SHA256", f"{_DELEGATES}/job_manager.py"),
        ],
        "core/skills/.rok/frappe/scripts/compose.py": [
            ("ref",),
            ("sha", "COMPOSER_SHA256", "core/utils/frappe/compose_backend.py"),
        ],
        "core/skills/.rok/flutter/scripts/compose.py": [
            ("ref",),
            (
                "dict",
                "EXPECTED_SHA256",
                (
                    "core/utils/flutter/sdk_composer.py",
                    "core/utils/flutter/sdk_installer_base.py",
                ),
            ),
        ],
        "core/skills/.rok/startup_os/scripts/_bootstrap.py": [
            ("ref",),
            (
                "dict",
                "EXPECTED_SHA256",
                tuple(f"{_ENGINE}/{m}" for m in ENGINE_MODULES),
            ),
        ],
        "profiles/local/initiate.py": [
            ("ref",),
            ("dict", "EXPECTED_SHA256", _INITIATE_LOCAL_EXPECTED),
        ],
        "profiles/web/initiate.py": [
            ("ref",),
            ("dict", "EXPECTED_SHA256", _INITIATE_WEB_EXPECTED),
        ],
        ".rokct/initiate.py": [
            ("ref",),
            ("dict", "EXPECTED_SHA256", _INITIATE_LOCAL_EXPECTED),
        ],
        "profiles/local/end_protocol.py": [("ref",)],
        "profiles/web/end_protocol.py": [("ref",)],
        ".rokct/end_protocol.py": [("ref",)],
        "workflows/sync_workspace.py": [
            ("ref",),
            ("sha", "MAINTENANCE_SHA256", "workflows/maintenance.yml"),
        ],
        ".rokct/sync_workspace.py": [
            ("ref",),
            ("sha", "MAINTENANCE_SHA256", "workflows/maintenance.yml"),
        ],
        "install.sh": [
            ("ref",),
            ("sha", "INITIATE_SHA256_LOCAL", "profiles/local/initiate.py"),
            ("sha", "INITIATE_SHA256_WEB", "profiles/web/initiate.py"),
        ],
        "install.ps1": [
            ("ref",),
            ("sha", "$InitiateSha256Local", "profiles/local/initiate.py"),
            ("sha", "$InitiateSha256Web", "profiles/web/initiate.py"),
        ],
    }
)

# The 22 opportunities_registry wrappers: byte-identical copies of one file,
# each mirroring a backend script's path and carrying the full EXPECTED_SHA256
# dict for the archive extraction it verifies.
_OPP_TARGETS = tuple(f"{_OPPORTUNITIES}/{p}" for p in OPPORTUNITIES_FILES)
for _p in OPPORTUNITIES_FILES:
    if _p in (
        "equity/test_funder_filtering.py",
        "tenders/scrapers/test_musina_dates.py",
        "tenders/enrichment/test_extract_requirements.py",
    ):
        continue  # extracted and pinned with the rest, but have no wrapper
    CONSUMERS[f"{_OPP_SCRIPTS}/{_p}"] = [
        ("ref",),
        ("dict", "EXPECTED_SHA256", _OPP_TARGETS),
    ]


def ref_pattern(path):
    """Regex matching the PROTOCOL_REF constant line for the file's syntax."""
    if path.endswith(".ps1"):
        return re.compile(r'^(\$ProtocolRef\s*=\s*)"([0-9a-f]{40})"', re.M)
    if path.endswith(".sh"):
        return re.compile(r'^(PROTOCOL_REF=)"([0-9a-f]{40})"', re.M)
    return re.compile(r'^(PROTOCOL_REF\s*=\s*)"([0-9a-f]{40})"', re.M)


def sha_pattern(var):
    """Regex matching a single-line 64-hex constant (py, sh and ps1 alike)."""
    return re.compile(r'^(%s\s*=\s*)"([0-9a-f]{64})"' % re.escape(var), re.M)


def dict_pattern(var):
    """Regex matching a `VAR = { ... }` block whose closing brace starts a line."""
    return re.compile(r"^%s = \{\n(.*?)^\}" % re.escape(var), re.M | re.S)


def format_dict(var, targets, hashes):
    lines = [f"{var} = {{"]
    for target in targets:
        lines.append(f'    "{target}": "{hashes[target]}",')
    lines.append("}")
    return "\n".join(lines)


def resolve_ref(ref):
    out = subprocess.run(
        ["git", "-C", REPO_ROOT, "rev-parse", ref],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", out):
        raise SystemExit(
            f"[gen] '{ref}' did not resolve to a full commit SHA (got {out!r})"
        )
    return out


def hash_at_ref(ref, path):
    """SHA-256 of the git blob at <ref>:<path> — never the working tree."""
    result = subprocess.run(
        ["git", "-C", REPO_ROOT, "show", f"{ref}:{path}"],
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise SystemExit(
            f"[gen] Cannot read {path} at {ref}: {result.stderr.decode().strip()}"
        )
    return hashlib.sha256(result.stdout).hexdigest()


def compute_hashes(ref):
    return {path: hash_at_ref(ref, path) for path in LOCK_TARGETS}


def write_lockfile(ref, hashes):
    payload = {
        "ref": ref,
        "generated_from": "tools/gen_protocol_lock.py",
        "files": {path: hashes[path] for path in sorted(hashes)},
    }
    lock_path = os.path.join(REPO_ROOT, LOCKFILE_NAME)
    with open(lock_path, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2)
        handle.write("\n")
    return lock_path


def _sub_exactly_one(pattern, replacement, text, path, what):
    new_text, count = pattern.subn(replacement, text)
    if count != 1:
        raise SystemExit(
            f"[gen] Expected exactly one {what} in {path}, found {count}. "
            "The constant lines must stay greppable and single-line-rewritable."
        )
    return new_text


def rewrite_consumers(ref, hashes):
    changed = []
    for rel_path, ops in sorted(CONSUMERS.items()):
        abs_path = os.path.join(REPO_ROOT, rel_path)
        with open(abs_path, "r", encoding="utf-8") as handle:
            original = handle.read()
        text = original
        for op in ops:
            if op[0] == "ref":
                text = _sub_exactly_one(
                    ref_pattern(rel_path),
                    r'\g<1>"%s"' % ref,
                    text,
                    rel_path,
                    "PROTOCOL_REF constant",
                )
            elif op[0] == "sha":
                _, var, target = op
                text = _sub_exactly_one(
                    sha_pattern(var),
                    r'\g<1>"%s"' % hashes[target],
                    text,
                    rel_path,
                    f"{var} constant",
                )
            elif op[0] == "dict":
                _, var, targets = op
                text = _sub_exactly_one(
                    dict_pattern(var),
                    format_dict(var, targets, hashes),
                    text,
                    rel_path,
                    f"{var} block",
                )
        if text != original:
            with open(abs_path, "w", encoding="utf-8") as handle:
                handle.write(text)
            changed.append(rel_path)
    return changed


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--ref",
        default="origin/main",
        help="Commit (or ref resolving to one) to pin; default origin/main.",
    )
    args = parser.parse_args(argv)

    ref = resolve_ref(args.ref)
    hashes = compute_hashes(ref)
    lock_path = write_lockfile(ref, hashes)
    changed = rewrite_consumers(ref, hashes)

    print(f"[gen] Pinned ref {ref}")
    print(
        f"[gen] Wrote {os.path.relpath(lock_path, REPO_ROOT)} ({len(hashes)} targets)"
    )
    if changed:
        print(f"[gen] Updated embedded constants in {len(changed)} file(s):")
        for rel_path in changed:
            print(f"[gen]   {rel_path}")
    else:
        print(
            f"[gen] Embedded constants already up to date in {len(CONSUMERS)} consumer file(s)"
        )
    return 0


if __name__ == "__main__":
    sys.exit(main())
