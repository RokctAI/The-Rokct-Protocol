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

"""Tests for the `sdk_requires` dependency check in compose_backend.py.

Each layer declares only its own requirements in its own manifest (this is
the Frappe backend's). The composer fails early, one clear line per gap,
when an enabled module requires a module the template does not enable.
Run:  python -m pytest core/utils/frappe/tests -q
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

_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "compose_backend.py",
)


class SdkRequiresTest(unittest.TestCase):
    def setUp(self):
        self._old_cwd = os.getcwd()
        self.root = tempfile.mkdtemp()
        os.chdir(self.root)
        name = "compose_backend_under_requires_test"
        spec = importlib.util.spec_from_file_location(name, _SRC)
        self.mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = self.mod
        spec.loader.exec_module(self.mod)

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.root, ignore_errors=True)

    def _module(self, name, manifest=None, enabled=True):
        d = os.path.join(self.root, "src", name)
        os.makedirs(d, exist_ok=True)
        with open(os.path.join(d, "manifest.json"), "w") as f:
            json.dump(manifest or {"name": name}, f)
        return {"name": name, "enabled": enabled, "path": os.path.join("src", name)}

    def test_satisfied_requirement_passes(self):
        mods = [
            self._module("productivity"),
            self._module("projects", {"sdk_requires": ["productivity"]}),
        ]
        self.mod.check_sdk_requires(mods, {})

    def test_missing_requirement_fails_with_clear_line(self):
        mods = [self._module("projects", {"sdk_requires": ["productivity"]})]
        err = io.StringIO()
        with redirect_stderr(err), self.assertRaises(SystemExit):
            self.mod.check_sdk_requires(mods, {})
        self.assertIn("'projects' requires 'productivity'", err.getvalue())

    def test_disabled_module_does_not_satisfy(self):
        mods = [
            self._module("productivity", enabled=False),
            self._module("projects", {"sdk_requires": ["productivity"]}),
        ]
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.mod.check_sdk_requires(mods, {})

    def test_disabled_module_requirements_are_ignored(self):
        mods = [self._module("projects", {"sdk_requires": ["x"]}, enabled=False)]
        self.mod.check_sdk_requires(mods, {})

    def test_suffix_is_optional(self):
        mods = [
            self._module("productivity"),
            self._module("crm", {"sdk_requires": ["productivity_sdk"]}),
        ]
        self.mod.check_sdk_requires(mods, {})

    def test_persona_block_counts_only_for_matching_persona(self):
        mods = [
            self._module(
                "crm", {"app_type": {"tenant": {"sdk_requires": ["productivity"]}}}
            )
        ]
        self.mod.check_sdk_requires(mods, {}, "control")
        with redirect_stderr(io.StringIO()), self.assertRaises(SystemExit):
            self.mod.check_sdk_requires(mods, {}, "tenant")

    def test_no_declaration_means_no_requirement(self):
        self.mod.check_sdk_requires([self._module("orders")], {})


if __name__ == "__main__":
    unittest.main()
