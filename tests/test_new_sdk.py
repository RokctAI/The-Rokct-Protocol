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

"""Tests for tools/new_sdk.py, the new-SDK scaffold.

Run:  python -m pytest tests/test_new_sdk.py -q
  or: python tests/test_new_sdk.py
"""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
TOOL = os.path.join(ROOT, "tools", "new_sdk.py")

spec = importlib.util.spec_from_file_location("new_sdk", TOOL)
new_sdk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(new_sdk)


def run_scaffold_tests(sdk_dir):
    """Run the scaffolded Next.js half's own gateway-cmd tests."""
    return subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "nextjs/tests"],
        cwd=sdk_dir,
        check=False,
        capture_output=True,
        text=True,
    )


class TestScaffold(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.repo = self._tmp.name
        self.sdk_dir = os.path.join(self.repo, "booking")

    def tearDown(self):
        self._tmp.cleanup()

    def scaffold(self, platforms=new_sdk.PLATFORMS):
        return new_sdk.scaffold("booking", self.repo, "Bookings", list(platforms))

    def load(self, rel):
        with open(os.path.join(self.sdk_dir, rel), encoding="utf-8") as f:
            return json.load(f)

    def test_writes_the_contract_and_all_three_halves(self):
        written = self.scaffold()
        for rel in (
            "CONTRACT.md",
            "frappe/manifest.json",
            "frappe/src/tenant/api/__init__.py",
            "dart/manifest.json",
            "dart/pubspec.yaml",
            "dart/install.py",
            "dart/CHANGELOG.md",
            "dart/lib/booking_sdk.dart",
            "dart/lib/src/common/domain/interface/.gitkeep",
            "nextjs/manifest.json",
            "nextjs/install.py",
            "nextjs/CHANGELOG.md",
            "nextjs/tests/test_gateway_cmds.py",
        ):
            self.assertIn(rel, written)
            self.assertTrue(os.path.isfile(os.path.join(self.sdk_dir, rel)), rel)

    def test_manifests_are_valid_and_start_at_1_0_0(self):
        self.scaffold()
        frappe = self.load("frappe/manifest.json")
        self.assertEqual(frappe["name"], "booking")
        self.assertEqual(frappe["app_type"]["tenant"]["hooks"]["whitelisted_methods"], {})
        for half in ("dart", "nextjs"):
            manifest = self.load(f"{half}/manifest.json")
            self.assertEqual(manifest["name"], "booking_sdk")
            self.assertEqual(manifest["version"], "1.0.0")
        with open(os.path.join(self.sdk_dir, "dart/pubspec.yaml"), encoding="utf-8") as f:
            pubspec = f.read()
        self.assertIn("name: booking_sdk\n", pubspec)
        self.assertIn("version: 1.0.0\n", pubspec)

    def test_contract_names_the_gateway_and_alias_form(self):
        self.scaffold()
        with open(os.path.join(self.sdk_dir, "CONTRACT.md"), encoding="utf-8") as f:
            contract = f.read()
        self.assertIn("/api/v1/method/rokct.platform.api", contract)
        self.assertIn("`{app_name}.api.booking.<method>`", contract)

    def test_files_use_lf_line_endings(self):
        self.scaffold()
        for root, _dirs, files in os.walk(self.sdk_dir):
            for name in files:
                with open(os.path.join(root, name), "rb") as f:
                    self.assertNotIn(b"\r\n", f.read(), name)

    def test_scaffolded_gateway_test_passes_on_a_fresh_sdk(self):
        self.scaffold()
        result = run_scaffold_tests(self.sdk_dir)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_scaffolded_gateway_test_catches_an_unwhitelisted_cmd(self):
        self.scaffold()
        service = os.path.join(
            self.sdk_dir, "nextjs/templates/app/services/all/booking/booking.ts"
        )
        with open(service, "w", encoding="utf-8") as f:
            f.write(
                'const NS = "api.booking";\n'
                "export const list = () => BaseService.call(`${NS}.list_slots`, {});\n"
            )
        self.assertNotEqual(run_scaffold_tests(self.sdk_dir).returncode, 0)

        manifest_path = os.path.join(self.sdk_dir, "frappe/manifest.json")
        manifest = self.load("frappe/manifest.json")
        manifest["app_type"]["tenant"]["hooks"]["whitelisted_methods"] = {
            "{app_name}.api.booking.list_slots": "{app_name}.booking.tenant.api.slots.list_slots"
        }
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest, f)
        result = run_scaffold_tests(self.sdk_dir)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_platform_subset(self):
        written = self.scaffold(["frappe", "nextjs"])
        self.assertFalse(any(rel.startswith("dart/") for rel in written))
        self.assertTrue(any(rel.startswith("nextjs/") for rel in written))

    def test_refuses_to_overwrite(self):
        os.makedirs(self.sdk_dir)
        with self.assertRaises(ValueError):
            self.scaffold()

    def test_rejects_bad_names(self):
        for bad in ("Booking", "booking_sdk", "1booking", "book-ing"):
            with self.assertRaises(ValueError):
                new_sdk.scaffold(bad, self.repo, "x", ["frappe"])


if __name__ == "__main__":
    unittest.main()
