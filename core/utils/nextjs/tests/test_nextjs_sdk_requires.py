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

"""Tests for the `sdk_requires` dependency check in nextjs/sdk_composer.py.

Each layer declares only its own requirements in its own manifest; the
composer fails early, with one clear line per gap, when a required SDK is
not enabled in composer.json. Run:  python -m pytest core/utils/nextjs/tests -q
"""

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr

_COMPOSER_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sdk_composer.py",
)


class SdkRequiresTest(unittest.TestCase):
    def setUp(self):
        self._old_cwd = os.getcwd()
        self.root = tempfile.mkdtemp()
        os.chdir(self.root)
        name = "sdk_composer_under_requires_test"
        spec = importlib.util.spec_from_file_location(name, _COMPOSER_SRC)
        self.mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = self.mod
        spec.loader.exec_module(self.mod)

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.root, ignore_errors=True)

    def _manifest(self, sdk_name, manifest):
        clean = self.mod.clean_sdk_name(sdk_name)
        d = os.path.join(self.root, ".rokct", "cache", clean)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "manifest.json"), "w") as f:
            json.dump(manifest, f)

    @staticmethod
    def _sdks(*names):
        return [{"name": n, "enabled": True} for n in names]

    def test_satisfied_requirement_passes(self):
        self._manifest("tasks_sdk", {"sdk_requires": ["base"]})
        sdks = self._sdks("base_sdk", "tasks_sdk")
        self.assertEqual(self.mod.find_missing_sdk_requires(sdks, sdks), [])
        self.mod.check_sdk_requires(sdks, sdks)

    def test_missing_requirement_fails_with_clear_line(self):
        self._manifest("tasks_sdk", {"sdk_requires": ["productivity_sdk"]})
        sdks = self._sdks("tasks_sdk")
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit) as cm:
            self.mod.check_sdk_requires(sdks, sdks)
        self.assertEqual(cm.exception.code, 1)
        self.assertIn("'tasks_sdk' requires 'productivity_sdk'", err.getvalue())

    def test_suffix_is_optional(self):
        self._manifest("tasks_sdk", {"sdk_requires": ["productivity"]})
        sdks = self._sdks("tasks_sdk", "productivity_sdk")
        self.assertEqual(self.mod.find_missing_sdk_requires(sdks, sdks), [])

    def test_scoped_run_checks_against_full_enabled_set(self):
        self._manifest("tasks_sdk", {"sdk_requires": ["productivity"]})
        all_enabled = self._sdks("tasks_sdk", "productivity_sdk")
        scoped = self._sdks("tasks_sdk")
        self.assertEqual(self.mod.find_missing_sdk_requires(scoped, all_enabled), [])

    def test_no_declaration_means_no_requirement(self):
        self._manifest("tasks_sdk", {"name": "tasks"})
        sdks = self._sdks("tasks_sdk")
        self.assertEqual(self.mod.find_missing_sdk_requires(sdks, sdks), [])

    def test_persona_block_counts_only_for_matching_persona(self):
        self._manifest(
            "tasks_sdk",
            {"app_type": {"manager": {"sdk_requires": ["projects"]}}},
        )
        sdks = self._sdks("tasks_sdk")
        self.mod.resolve_app_type = lambda: "customer"
        self.assertEqual(self.mod.find_missing_sdk_requires(sdks, sdks), [])
        self.mod.resolve_app_type = lambda: "manager"
        self.assertEqual(
            self.mod.find_missing_sdk_requires(sdks, sdks),
            [("tasks_sdk", "projects")],
        )

    def test_missing_manifest_is_skipped(self):
        sdks = self._sdks("ghost_sdk")
        self.assertEqual(self.mod.find_missing_sdk_requires(sdks, sdks), [])


if __name__ == "__main__":
    unittest.main()
