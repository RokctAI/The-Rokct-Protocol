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

"""Generate nextjs_compose_example.json - the generic Next.js shell
composition - from the SDK consumers index alone.

Ray, 2026-09-10: a new Next.js shell needs the SDK list and versions that
are current at the time of its creation, and the file that already gets
updated on every SDK change is the SDK consumers index (SDK_CONSUMERS.md,
rendered from sdk_consumers.json by tools/gen_sdk_consumers.py). Since that
index carries each SDK's Next.js path, version and pin, the compose example
a new shell starts from is derived from it and nothing else, beside it, so
the two change together: the consumers file (path, version, pin) and the
compose example are regenerated in the same commit.

Input, read offline:

  sdk_consumers.json    per SDK: `repo` (owner/repo), `consumers` (the shells
                        composing it) and `nextjs` - null, or {path, version,
                        install_py_sha256} for its Next.js half.

Output, nextjs_compose_example.json at the repo root (beside the index):

  sdks[]            the kernel every Next.js shell composes - telemetry_sdk
                    then base_sdk - enabled, home_sdk false, git/path/ref
                    from the index, sha256 = the index's pin, plus the
                    version the index records. This is what RokctAI/factory
                    copies into a new shell as composer.json at spawn
                    (re-pinning live) when no product template names the
                    shell's app_type.
  _available_sdks   the menu: every other SDK the index gives a Next.js
                    half, same shape, enabled false, with the shells the
                    index says consume it. Documentation for whoever writes
                    the next product template; no composer reads this key.

The product templates (core/utils/frappe/composer/*.json) and the
SDK_ECOSYSTEM.md census are NOT inputs: core/utils/nextjs/tests/
test_nextjs_compose_example.py cross-checks them against the index and
fails on a repo, path or pin that disagrees, and fails when the committed
example is stale.

Usage:
    python3 tools/gen_nextjs_compose_example.py            # write the file
    python3 tools/gen_nextjs_compose_example.py --check    # exit 1 if stale
"""

import argparse
import json
import os
import sys

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
CONSUMERS_JSON = "sdk_consumers.json"
OUTPUT_NAME = "nextjs_compose_example.json"
KERNEL = ("telemetry_sdk", "base_sdk")
GITHUB = "https://github.com/"


class DriftError(Exception):
    """The index cannot yield a complete kernel composition."""


def clean(name):
    return name[:-4] if name.endswith("_sdk") else name


def load_consumers(root):
    """{sdk_name: {"repo", "consumers", "nextjs"}} from the index."""
    with open(os.path.join(root, CONSUMERS_JSON), "r", encoding="utf-8-sig") as fh:
        data = json.load(fh)
    sdks = data.get("sdks")
    if not isinstance(sdks, dict) or not sdks:
        raise DriftError(f"{CONSUMERS_JSON}: no 'sdks' map")
    return sdks


def sdk_path(repo, half):
    """'../core/base/nextjs' from 'RokctAI/core' and 'base/nextjs' - the
    sibling-checkout path convention every composer template uses."""
    return f"../{repo.split('/', 1)[1]}/{half['path'].strip('/')}"


def entry_from_index(name, record, enabled):
    half = record.get("nextjs") or {}
    return {
        "name": name,
        "enabled": enabled,
        "source": "git",
        "git": GITHUB + record["repo"],
        "path": sdk_path(record["repo"], half),
        "ref": "main",
        "sha256": half.get("install_py_sha256"),
        "version": half.get("version"),
        "home_sdk": False,
        "consumers": list(record.get("consumers") or []),
    }


def generate(root=REPO_ROOT):
    """Return (example dict, warnings list). Raises DriftError when a kernel
    SDK is missing from the index or has no Next.js half or pin there."""
    consumers = load_consumers(root)
    warnings = []

    kernel = []
    for name in KERNEL:
        record = consumers.get(name)
        if record is None or not record.get("repo"):
            raise DriftError(f"{name}: kernel SDK missing from {CONSUMERS_JSON}")
        half = record.get("nextjs")
        if not half or not half.get("path"):
            raise DriftError(f"{name}: {CONSUMERS_JSON} records no Next.js half for the kernel SDK")
        if not half.get("install_py_sha256"):
            raise DriftError(f"{name}: {CONSUMERS_JSON} carries no install.py pin for the kernel SDK")
        entry = entry_from_index(name, record, enabled=True)
        entry["_sha256_comment"] = (
            f"SHA-256 of {half['path']}/install.py as {CONSUMERS_JSON} records it "
            f"(version {half.get('version') or '?'}); the factory re-pins it live at spawn and "
            "`scripts/compose.sh refresh` re-pins it from the SDK repo."
        )
        entry["_comment"] = (
            "Mandatory in every Next.js composition (SDK_ECOSYSTEM.md hard invariant 9): "
            "the delivery-policy seam owner, always first."
            if name == "telemetry_sdk" else
            "The platform kernel: app/services/base, the landing host and its registries, "
            "the admin and manager shells. Every other Next.js SDK 'requires' files it installs."
        )
        kernel.append(entry)

    menu = []
    omitted = []
    for name in sorted(consumers):
        if name in KERNEL:
            continue
        record = consumers[name]
        half = record.get("nextjs")
        if not half or not half.get("path") or not record.get("repo"):
            omitted.append(name)
            continue
        entry = entry_from_index(name, record, enabled=False)
        if not entry["sha256"]:
            entry["_sha256_comment"] = (
                f"{CONSUMERS_JSON} records no install.py for this half yet: compute at activation"
            )
            warnings.append(f"{name}: Next.js half without an install.py pin in the index")
        menu.append(entry)

    example = {
        "_generated_by": "tools/gen_nextjs_compose_example.py - do not edit by hand. Generated "
                         f"from {CONSUMERS_JSON} alone; regenerate in the same commit as the "
                         "consumers index (the consumers file - path, version, pin - and this "
                         "compose example change together). test_nextjs_compose_example.py fails "
                         "when this file is stale or a product template disagrees with the index.",
        "_source": CONSUMERS_JSON,
        "_note": (
            "The generic Next.js shell composition. sdks[] is the kernel every Next.js shell "
            "composes and is what RokctAI/factory copies into a new shell as composer.json at "
            "spawn (renamed, re-pinned live) when core/utils/frappe/composer/<app_type>.json "
            "does not exist for that shell. _available_sdks is the menu of every other SDK with "
            "a Next.js half, for writing that product template: copy an entry into "
            "<app_type>.json, set enabled true, flag exactly one non-kernel entry home_sdk true, "
            "and give it a fresh sha256 (SHA-256 of <sdk>/nextjs/install.py at the ref, CRLF "
            "folded to LF). `version` is informational (the half's manifest.json version when "
            "the index was refreshed); the composer reads name, enabled, source, git, path, ref, "
            "sha256 and home_sdk. No composer reads _available_sdks."
        ),
        "name": "nextjs_shell_composer",
        "version": "1.0.0",
        "description": "Generic Next.js shell composition: the kernel (telemetry_sdk, base_sdk) "
                       "plus the menu of every other SDK with a Next.js half",
        "sdks": kernel,
        "_available_sdks": menu,
        "_omitted_no_nextjs_half": omitted,
    }
    return example, warnings


def render(example):
    return json.dumps(example, indent=2, ensure_ascii=False) + "\n"


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--check", action="store_true",
                    help="exit 1 when the committed file differs from what would be generated")
    ap.add_argument("--root", default=REPO_ROOT, help=argparse.SUPPRESS)
    args = ap.parse_args(argv)
    try:
        example, warnings = generate(args.root)
    except DriftError as e:
        print(f"[gen] DRIFT: {e}", file=sys.stderr)
        return 1
    for w in warnings:
        print(f"[gen] warning: {w}")
    out = os.path.join(args.root, OUTPUT_NAME)
    text = render(example)
    if args.check:
        current = open(out, encoding="utf-8").read() if os.path.exists(out) else ""
        if current != text:
            print(f"[gen] {OUTPUT_NAME} is stale: run python3 tools/gen_nextjs_compose_example.py "
                  "and commit the result.", file=sys.stderr)
            return 1
        print(f"[gen] {OUTPUT_NAME} is current: {len(example['sdks'])} kernel SDK(s), "
              f"{len(example['_available_sdks'])} available.")
        return 0
    with open(out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"[gen] wrote {OUTPUT_NAME}: {len(example['sdks'])} kernel SDK(s), "
          f"{len(example['_available_sdks'])} available, {len(example['_omitted_no_nextjs_half'])} "
          "omitted (no Next.js half).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
