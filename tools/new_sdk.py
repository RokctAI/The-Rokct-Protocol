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

"""Scaffold a new SDK: the three-platform skeleton plus a contract stub.

Ray, 2026-10-10: app shells have a template, SDKs had only the manual
"Introducing a new SDK" checklist in SDK_ECOSYSTEM.md. This tool writes the
files that checklist asks for, in the shape the existing SDKs use (modelled
on agent/fav, the smallest SDK with all three halves):

  python3 tools/new_sdk.py booking --repo ../commerce \\
      --description "Bookings: a customer reserves a slot with a merchant"

creates ``../commerce/booking/`` with:

- ``CONTRACT.md`` - fill this in FIRST (decision log, "SDK contract first",
  2026-10-09): every gateway ``cmd``, its manifest alias, payload and
  response shape, before any frappe, Dart or Next.js code is written.
- ``frappe/`` - ``manifest.json`` (empty ``whitelisted_methods`` for the
  contract's aliases), ``src/tenant/api/`` package, ``.gitignore``.
- ``dart/`` - ``manifest.json`` and ``pubspec.yaml`` at 1.0.0, the DDD
  ``lib/src/common/`` layout, ``lib/<name>_sdk.dart``, ``install.py``,
  ``templates/``, ``CHANGELOG.md``, ``analysis_options.yaml``, ``.gitignore``.
- ``nextjs/`` - ``manifest.json`` at 1.0.0, ``install.py``,
  ``templates/app/services/all/<name>/``, ``CHANGELOG.md``, ``.gitignore``,
  and ``tests/test_gateway_cmds.py``, which fails if the service sends a
  ``cmd`` the frappe half does not whitelist.

``--platforms`` limits the halves (default: all three). The tool refuses to
write over an existing directory and touches nothing outside the new SDK
directory: composer templates, ``.relation`` and the consumers index are
still the checklist's later steps, printed at the end.
"""

import argparse
import json
import os
import re
import sys

PLATFORMS = ("frappe", "dart", "nextjs")
NAME_RE = re.compile(r"^[a-z][a-z0-9_]*$")

LICENSE_LINES = [
    "Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD",
    "",
    "This program is free software: you can redistribute it and/or modify",
    "it under the terms of the GNU Affero General Public License as published",
    "by the Free Software Foundation, version 3.",
    "",
    "This program is distributed in the hope that it will be useful,",
    "but WITHOUT ANY WARRANTY; without even the implied warranty of",
    "MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the",
    "GNU Affero General Public License for more details.",
    "",
    "You should have received a copy of the GNU Affero General Public License",
    "along with this program. If not, see <https://www.gnu.org/licenses/>.",
]


def license_header(prefix):
    return "\n".join((prefix + " " + line).rstrip() for line in LICENSE_LINES) + "\n"


PY_LICENSE = license_header("#")
DART_LICENSE = license_header("//")

COMMON_IGNORE_TAIL = """
npm-debug.log*
yarn-debug.log*
yarn-error.log*
.pnpm-debug.log*

# Miscellaneous
*.class
.buildlog/
.history
.svn/
.swiftpm/
migrate_working_dir/
"""

IDE_OS_IGNORE = """# IDE
.vscode/
.idea/
*.swp
*.swo
*~
*.iml
*.ipr
*.iws
.atom/

# OS
.DS_Store
Thumbs.db
"""

DART_GITIGNORE = (
    "# Flutter Project\n"
    + IDE_OS_IGNORE
    + """
# Flutter/Dart/Pub related
**/doc/api/
.dart_tool/
.flutter-plugins
.flutter-plugins-dependencies
.packages
.pub-cache/
.pub/
build/
coverage/
pubspec.lock
*.freezed.dart
*.g.dart
*.gr.dart
"""
    + COMMON_IGNORE_TAIL
)

FRAPPE_GITIGNORE = """# Frappe Project
# Python
__pycache__/
*.py[cod]
*$py.class
build/
dist/
*.egg-info/
.pytest_cache/
.mypy_cache/

# Virtual environments
venv/
.venv
.env

""" + IDE_OS_IGNORE + COMMON_IGNORE_TAIL

NEXTJS_GITIGNORE = (
    "# Next.js Project\n"
    + IDE_OS_IGNORE
    + """
# Next.js/Node
node_modules/
.next/
out/
.turbo
.vercel
.env*.local
*.pem
"""
    + COMMON_IGNORE_TAIL
)


def install_py(sdk_name, call):
    return PY_LICENSE + f"""
import sys
import os


def get_safe_path(base, path):
    abs_base = os.path.abspath(base)
    abs_path = os.path.abspath(os.path.join(base, path))
    if not abs_path.startswith(abs_base):
        raise RuntimeError('Path containment violation')
    return abs_path


sys.path.append(get_safe_path(os.getcwd(), '.rokct'))
import sdk_installer_base

if __name__ == '__main__':
    sdk_name = '{sdk_name}'
    sdk_installer_base.{call}(sdk_name)
"""


def contract_md(name, description, platforms):
    halves = ", ".join(platforms)
    return f"""# {name} SDK contract

{description}

Fill this in **before writing any frappe, Dart or Next.js code** (decision log,
"SDK contract first", 2026-10-09). The halves ({halves}) are then built against
it. A later change to anything in this table is a contract change: keep it
backward compatible, or update every consuming app in the same wave.

Rules the contract must follow (SDK_ECOSYSTEM.md):

- Every client call POSTs to the platform gateway,
  `/api/v1/method/rokct.platform.api`, with `cmd` set to the alias below minus
  `{{app_name}}.` (alias `{{app_name}}.api.{name}.list_items` routes as
  `api.{name}.list_items`). Never `/api/method/...`, never a per-method URL.
- A half only sends `cmd`s its own `frappe/manifest.json` whitelists, plus
  those of SDKs it declares as dependencies (gateway `cmd` co-location).
- Every `cmd` a demo-visible screen sends needs a demo fixture.

## Gateway cmds

| cmd | manifest alias (`frappe/manifest.json`) | handler | payload | response |
|---|---|---|---|---|
| `api.{name}.<method>` | `{{app_name}}.api.{name}.<method>` | `{{app_name}}.{name}.tenant.api.<file>.<method>` | `{{ ... }}` | `{{ ... }}` |

## Manifest keys

List the Dart / Next.js manifest keys this SDK declares beyond `name`,
`version` and `installs` (routes, database tables, `home_sdk`,
`session_policy`, `brand_hook`, integrations), and why. Check no SDK already
composed into the target app declares the same owner-only key.

## Consumers

Apps (composer templates) that will compose this SDK, and SDKs it depends on.
"""


def frappe_files(name, description):
    manifest = {
        "name": name,
        "description": description,
        "app_type": {
            "tenant": {
                "dependencies": [],
                "hooks": {"whitelisted_methods": {}},
            },
            "control": {},
        },
    }
    return {
        "frappe/manifest.json": json.dumps(manifest, indent=2) + "\n",
        "frappe/.gitignore": FRAPPE_GITIGNORE,
        "frappe/src/tenant/__init__.py": PY_LICENSE,
        "frappe/src/tenant/api/__init__.py": PY_LICENSE,
    }


def dart_files(name, description):
    sdk = f"{name}_sdk"
    manifest = {
        "name": sdk,
        "version": "1.0.0",
        "installs": [],
        "routes": [],
        "integrations": [],
    }
    pubspec = f"""name: {sdk}
description: {json.dumps(description)}
version: 1.0.0
publish_to: 'none'
environment:
  sdk: '>=3.10.0 <4.0.0'
  flutter: '>=3.38.5'
dependencies:
  flutter:
    sdk: flutter
  base_sdk:
    path: ../base
dev_dependencies:
  flutter_test:
    sdk: flutter
  flutter_lints: ^5.0.0

# Workspace-relative override so this package resolves standalone for
# codegen/analysis. Ignored when a host app is the resolution root.
dependency_overrides:
  base_sdk:
    path: ../../../core/base/dart
"""
    files = {
        "dart/manifest.json": json.dumps(manifest, indent=2) + "\n",
        "dart/pubspec.yaml": pubspec,
        "dart/install.py": install_py(sdk, "install_sdk_files_and_routes"),
        "dart/.gitignore": DART_GITIGNORE,
        "dart/analysis_options.yaml": (
            "include: package:flutter_lints/flutter.yaml\n\n"
            "analyzer:\n  exclude:\n    - templates/**\n"
        ),
        "dart/CHANGELOG.md": "# Changelog\n\n## 1.0.0\n\n* Initial release.\n",
        "dart/lib/" + sdk + ".dart": DART_LICENSE
        + "\n// Public surface of "
        + sdk
        + ". Export from src/ as the SDK grows;\n"
        "// import only base_sdk from lib/ (ADR-005).\n",
        "dart/templates/.gitkeep": "",
    }
    # The DDD layout from agent's SDK_README.md.
    for sub in (
        "domain/interface",
        "infrastructure/models/data",
        "infrastructure/models/response",
        "infrastructure/repositories",
        "application",
    ):
        files[f"dart/lib/src/common/{sub}/.gitkeep"] = ""
    return files


NEXTJS_TEST = PY_LICENSE + '''
"""Every gateway cmd this SDK's Next.js half sends is whitelisted by its own
frappe half (scaffolded by The-Rokct-Protocol tools/new_sdk.py).

Run from the repository root:

    python3 -m unittest discover -s {name}/nextjs/tests -v

Stdlib only. The gateway cmd is the frappe manifest's whitelisted alias key
minus ``{{app_name}}.``. A service that sends anything else is refused by
the gateway, so the screen comes back silently empty. The manifest version
must match the CHANGELOG's top entry.
"""

import json
import os
import re
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
SDK_ROOT = os.path.abspath(os.path.join(HERE, os.pardir))
MANIFEST = os.path.join(SDK_ROOT, "manifest.json")
CHANGELOG = os.path.join(SDK_ROOT, "CHANGELOG.md")
TEMPLATES = os.path.join(SDK_ROOT, "templates")
FRAPPE_MANIFEST = os.path.join(SDK_ROOT, os.pardir, "frappe", "manifest.json")

TEMPLATE_SUFFIXES = (".ts", ".tsx", ".js", ".jsx", ".mts")
LINE_COMMENT_RE = re.compile(r"(^|\\s)//[^\\n]*")
BLOCK_COMMENT_RE = re.compile(r"/\\*.*?\\*/", re.S)
NS_RE = re.compile(r'^const NS = "([^"]+)";$', re.M)
NS_CMD_RE = re.compile(r"\\$\\{{NS\\}}\\.([a-z_]+)")
CALL_CMD_RE = re.compile(r'\\.call\\(\\s*["\\'`]([^"\\'`]+)["\\'`]')
DIRECT_URL_RE = re.compile(r"/api/(v1/)?method/(?!rokct\\.platform\\.api)")
TOP_ENTRY_RE = re.compile(r"^## (\\d+\\.\\d+\\.\\d+)$", re.M)


def read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


def code_of(path):
    return LINE_COMMENT_RE.sub("", BLOCK_COMMENT_RE.sub("", read(path)))


def template_files():
    for root, _dirs, files in os.walk(TEMPLATES):
        for name in sorted(files):
            if name.endswith(TEMPLATE_SUFFIXES):
                yield os.path.join(root, name)


def whitelisted_cmds():
    with open(FRAPPE_MANIFEST, encoding="utf-8") as f:
        manifest = json.load(f)
    aliases = manifest["app_type"]["tenant"]["hooks"]["whitelisted_methods"]
    prefix = "{{app_name}}."
    return {{key[len(prefix):] for key in aliases if key.startswith(prefix)}}


def cmds_sent_by(path):
    code = code_of(path)
    sent = set()
    ns = NS_RE.search(code)
    if ns:
        sent.update(f"{{ns.group(1)}}.{{m}}" for m in NS_CMD_RE.findall(code))
    sent.update(c for c in CALL_CMD_RE.findall(code) if "${{" not in c)
    return sent


class TestGatewayCmds(unittest.TestCase):
    def test_every_cmd_is_whitelisted_by_the_frappe_half(self):
        allowed = whitelisted_cmds()
        for path in template_files():
            stray = cmds_sent_by(path) - allowed
            self.assertEqual(
                stray, set(), f"{{os.path.relpath(path, SDK_ROOT)}} sends {{sorted(stray)}}"
            )

    def test_no_direct_method_url(self):
        hits = [
            os.path.relpath(path, SDK_ROOT)
            for path in template_files()
            if DIRECT_URL_RE.search(code_of(path))
        ]
        self.assertEqual(hits, [])


class TestVersion(unittest.TestCase):
    def test_manifest_matches_changelog_top_entry(self):
        with open(MANIFEST, encoding="utf-8") as f:
            manifest = json.load(f)
        self.assertEqual(manifest["name"], "{name}_sdk")
        self.assertEqual(
            TOP_ENTRY_RE.search(read(CHANGELOG)).group(1), manifest["version"]
        )


if __name__ == "__main__":
    unittest.main()
'''


def nextjs_files(name, description):
    sdk = f"{name}_sdk"
    manifest = {
        "name": sdk,
        "version": "1.0.0",
        "installs": [
            {
                "from": f"templates/app/services/all/{name}",
                "to": f"app/services/all/{name}",
            }
        ],
        "dependencies": {},
        "devDependencies": {},
        "integrations": [],
        "requires": ["app/services/common/base.ts"],
    }
    return {
        "nextjs/manifest.json": json.dumps(manifest, indent=2) + "\n",
        "nextjs/install.py": install_py(sdk, "install_sdk_files"),
        "nextjs/.gitignore": NEXTJS_GITIGNORE,
        "nextjs/CHANGELOG.md": "# Changelog\n\n## 1.0.0\n\n* Initial release.\n",
        f"nextjs/templates/app/services/all/{name}/.gitkeep": "",
        "nextjs/tests/test_gateway_cmds.py": NEXTJS_TEST.format(name=name),
    }


def scaffold(name, repo, description, platforms):
    """Write the new SDK under repo/name. Returns the list of written paths
    relative to the SDK directory."""
    if not NAME_RE.match(name):
        raise ValueError(f"SDK name must be lowercase snake_case: {name!r}")
    if name.endswith("_sdk"):
        raise ValueError(f"give the module name without _sdk: {name!r}")
    if not os.path.isdir(repo):
        raise ValueError(f"repo directory not found: {repo}")
    target = os.path.join(repo, name)
    if os.path.exists(target):
        raise ValueError(f"refusing to overwrite existing {target}")

    files = {"CONTRACT.md": contract_md(name, description, platforms)}
    builders = {"frappe": frappe_files, "dart": dart_files, "nextjs": nextjs_files}
    for platform in platforms:
        files.update(builders[platform](name, description))

    for rel, content in sorted(files.items()):
        path = os.path.join(target, rel)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as f:
            f.write(content)
    return sorted(files)


NEXT_STEPS = """
Next (SDK_ECOSYSTEM.md, "Introducing a new SDK"):
  1. Fill in {name}/CONTRACT.md and the frappe whitelisted_methods FIRST.
  2. Build the halves against it; read agent's SDK_README.md before Dart code.
  3. Add {name} to every app's composer template in this repo, then rerun
     tools/gen_sdk_consumers.py and tools/gen_nextjs_compose_example.py.
  4. Cross-repo dependencies go in the repo's root .relation.
  5. Run sdk_validator.py --compliance (shared-workflows) and recompose the app.
"""


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("name", help="module name, e.g. booking (no _sdk suffix)")
    parser.add_argument(
        "--repo", required=True, help="domain monorepo checkout, e.g. ../commerce"
    )
    parser.add_argument(
        "--description", required=True, help="one line: what the SDK does"
    )
    parser.add_argument(
        "--platforms",
        default=",".join(PLATFORMS),
        help="comma-separated subset of frappe,dart,nextjs (default: all)",
    )
    args = parser.parse_args(argv)

    platforms = [p.strip() for p in args.platforms.split(",") if p.strip()]
    unknown = [p for p in platforms if p not in PLATFORMS]
    if unknown or not platforms:
        parser.error(f"--platforms must be a subset of {','.join(PLATFORMS)}")
    platforms = [p for p in PLATFORMS if p in platforms]

    try:
        written = scaffold(args.name, args.repo, args.description, platforms)
    except ValueError as exc:
        print(f"new_sdk: {exc}", file=sys.stderr)
        return 1
    for rel in written:
        print(os.path.join(args.repo, args.name, rel))
    print(NEXT_STEPS.format(name=args.name))
    return 0


if __name__ == "__main__":
    sys.exit(main())
