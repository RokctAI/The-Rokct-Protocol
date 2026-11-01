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

"""Regression tests for a persona block's ``"common": false``.

A Next.js manifest's top level is common: it always installs, and an
``app_type`` persona block only adds to it. A block that sets
``"common": false`` opts the host whose ``.rokct/config/app_type`` names
it out of the top level: only the block's installs, dependencies,
integrations and requires apply there. These tests pin:

  * a matching persona with ``"common": false`` installs only its own
    files, dependencies and integrations, never the top level's
  * a persona without the key (or ``true``) still gets the top level too
  * a host with another marker, or none, still gets the top level and none
    of the opted-out persona's content
  * the composer's post-install checklist does not report the skipped top
    level's requires or integration targets as missing

Run:  python -m pytest core/utils/nextjs/tests -q
  or: python core/utils/nextjs/tests/test_nextjs_common_false.py
"""

import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout

_NEXTJS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_INSTALLER_SRC = os.path.join(_NEXTJS_DIR, "sdk_installer_base.py")
_COMPOSER_SRC = os.path.join(_NEXTJS_DIR, "sdk_composer.py")
_counter = 0

MARKER = "// @rokct-sdk-site-metadata-start"
REGISTRY_REL = "components/custom/landing/site-metadata.ts"


def _load(src, name):
    spec = importlib.util.spec_from_file_location(name, src)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class CommonFalseTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="nextjs_common_false_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        self.rokct = os.path.join(self.root, ".rokct")
        sdk = os.path.join(self.rokct, "cache", "demo")
        for rel in ("templates/app/chat.tsx", "templates/sticks/app/page.tsx"):
            path = os.path.join(sdk, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(f"// {rel}\n")
        self.write_json(os.path.join(self.root, "package.json"), {"name": "t", "dependencies": {}})
        with open(os.path.join(self.root, "tsconfig.json"), "w", encoding="utf-8") as f:
            f.write('{"compilerOptions": {"paths": {"@/*": ["./*"]}}}\n')
        registry = os.path.join(self.root, REGISTRY_REL)
        os.makedirs(os.path.dirname(registry), exist_ok=True)
        with open(registry, "w", encoding="utf-8") as f:
            f.write(f"export const R = [\n  {MARKER}\n  {MARKER.replace('-start', '-end')}\n];\n")
        self.manifest = {
            "name": "demo_sdk",
            "version": "1.0.0",
            "installs": [{"from": "templates/app/chat.tsx", "to": "app/chat.tsx"}],
            "dependencies": {"top-only": "^1.0.0"},
            "requires": ["db/index.ts"],
            "integrations": [
                {"target": "app/sidebar.tsx", "placeholder": "// @x-start", "replacement": "  top,"}
            ],
            "app_type": {
                "sticks": {
                    "common": False,
                    "installs": [{"from": "templates/sticks/app/page.tsx", "to": "app/page.tsx"}],
                    "dependencies": {"sticks-only": "^2.0.0"},
                    "integrations": [
                        {"target": REGISTRY_REL, "placeholder": MARKER, "replacement": '  { id: "sticks" },'}
                    ],
                },
                "rokct": {"installs": []},
            },
        }
        self.write_manifest()

    def write_json(self, path, data):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f)

    def write_manifest(self):
        self.write_json(os.path.join(self.rokct, "cache", "demo", "manifest.json"), self.manifest)

    def set_app_type(self, value):
        path = os.path.join(self.rokct, "config", "app_type")
        if value is None:
            if os.path.exists(path):
                os.remove(path)
            return
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(value + "\n")

    def install(self):
        global _counter
        _counter += 1
        dest = os.path.join(self.rokct, "sdk_installer_base.py")
        shutil.copy2(_INSTALLER_SRC, dest)
        module = _load(dest, f"common_false_installer_{_counter}")
        with redirect_stdout(io.StringIO()) as out:
            module.install_sdk_files("demo_sdk")
        with open(os.path.join(self.root, "package.json"), encoding="utf-8") as f:
            deps = json.load(f).get("dependencies", {})
        return out.getvalue(), deps

    def exists(self, rel):
        return os.path.exists(os.path.join(self.root, rel))

    def registry(self):
        with open(os.path.join(self.root, REGISTRY_REL), encoding="utf-8") as f:
            return f.read()

    def test_common_false_installs_only_the_persona(self):
        self.set_app_type("sticks")
        log, deps = self.install()
        self.assertTrue(self.exists("app/page.tsx"))
        self.assertFalse(self.exists("app/chat.tsx"))
        self.assertIn("sticks-only", deps)
        self.assertNotIn("top-only", deps)
        self.assertIn('{ id: "sticks" }', self.registry())
        self.assertIn('"common": false', log)

    def test_persona_without_the_key_keeps_the_top_level(self):
        del self.manifest["app_type"]["sticks"]["common"]
        self.write_manifest()
        self.set_app_type("sticks")
        _, deps = self.install()
        self.assertTrue(self.exists("app/page.tsx"))
        self.assertTrue(self.exists("app/chat.tsx"))
        self.assertIn("top-only", deps)
        self.assertIn("sticks-only", deps)

    def test_other_marker_and_no_marker_keep_the_top_level(self):
        for marker in ("rokct", None):
            self.set_app_type(marker)
            _, deps = self.install()
            self.assertTrue(self.exists("app/chat.tsx"), marker)
            self.assertFalse(self.exists("app/page.tsx"), marker)
            self.assertIn("top-only", deps)
            self.assertNotIn("sticks-only", deps)

    def test_composer_checklist_skips_the_top_level(self):
        self.set_app_type("sticks")
        global _counter
        _counter += 1
        composer = _load(_COMPOSER_SRC, f"common_false_composer_{_counter}")
        composer.PROJECT_ROOT = self.root
        self.assertIs(
            composer.common_manifest(self.manifest, "rokct"), self.manifest
        )
        stripped = composer.common_manifest(self.manifest, "sticks")
        for key in ("installs", "dependencies", "requires", "integrations"):
            self.assertNotIn(key, stripped)
        self.assertIn("app_type", stripped)


if __name__ == "__main__":
    unittest.main()
