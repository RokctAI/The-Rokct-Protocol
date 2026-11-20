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


"""base_sdk "versions": one fleet version per npm package. The installer sets
it on packages the host already lists and never adds a package. Run:
python -m pytest core/utils/nextjs/tests -q
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sdk_installer_base.py",
)


class SharedVersionsTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp()
        name = "sdk_installer_under_versions_test"
        spec = importlib.util.spec_from_file_location(name, _SRC)
        self.mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = self.mod
        spec.loader.exec_module(self.mod)
        self.mod.PACKAGE_JSON_FILE = os.path.join(self.root, "package.json")
        self.state = {"packages": {}}
        self.mod.load_state = lambda: self.state

    def tearDown(self):
        shutil.rmtree(self.root, ignore_errors=True)

    def _run(self, pkg):
        with open(self.mod.PACKAGE_JSON_FILE, "w") as f:
            json.dump(pkg, f)
        self.mod.update_package_json_dependencies()
        with open(self.mod.PACKAGE_JSON_FILE) as f:
            return json.load(f)

    def test_overwrites_existing_pins_only(self):
        self.state["packages"]["base_sdk"] = {
            "versions": {"swr": "2.5.1", "sharp": "0.35.5", "absent": "1.0.0"}
        }
        out = self._run(
            {"dependencies": {"swr": "2.3.8"}, "devDependencies": {"sharp": "0.35.4"}}
        )
        self.assertEqual(out["dependencies"]["swr"], "2.5.1")
        self.assertEqual(out["devDependencies"]["sharp"], "0.35.5")
        self.assertNotIn("absent", out["dependencies"])
        self.assertNotIn("absent", out["devDependencies"])

    def test_dependencies_stay_additive(self):
        self.state["packages"]["x_sdk"] = {"dependencies": {"swr": "^1.0.0"}}
        out = self._run({"dependencies": {"swr": "2.3.8"}})
        self.assertEqual(out["dependencies"]["swr"], "2.3.8")

    def test_versions_win_over_sdk_ranges(self):
        self.state["packages"]["x_sdk"] = {"dependencies": {"swr": "^2.0.0"}}
        self.state["packages"]["base_sdk"] = {"versions": {"swr": "2.5.1"}}
        out = self._run({"dependencies": {}})
        self.assertEqual(out["dependencies"]["swr"], "2.5.1")


if __name__ == "__main__":
    unittest.main()
