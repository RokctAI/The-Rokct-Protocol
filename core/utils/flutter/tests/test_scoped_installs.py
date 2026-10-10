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

"""Regression tests for app_types-scoped manifest installs.

Background: products_sdk and merchants_sdk install demo fixtures
(assets/demo/<sdk>/<cmd>.json) that only marketplace apps (customer,
driver, manager) answer from. Non-marketplace shells such as supacharge
compose both SDKs transitively and got the fixtures too. An installs
entry may now carry "app_types"; these tests pin that:

  * a scoped entry installs only in the listed app types; an unscoped
    entry still installs everywhere
  * the app_assets entry that only the scoped entry fills is not
    registered elsewhere, so the pubspec never names a missing directory
  * copies an earlier compose installed (state-recorded, or committed and
    byte-identical to the template) are retracted; a modified copy is kept
  * the home SDK's owned-file set ignores scoped-away entries

Run:  python -m pytest core/utils/flutter/tests -q
  or: python core/utils/flutter/tests/test_scoped_installs.py
"""

import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

_INSTALLER_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sdk_installer_base.py",
)

_module_counter = 0

MARKETPLACE = ["customer", "driver", "manager"]
FIXTURE_REL = "assets/demo/shop/api.shop.get_shops.json"
SOUND_REL = "assets/audio/ding.txt"


class ScopedInstallTestBase(unittest.TestCase):
    SDK_NAME = "shop_sdk"

    def setUp(self):
        self.project_root = tempfile.mkdtemp(prefix="sdk_scoped_test_")
        self.addCleanup(shutil.rmtree, self.project_root, ignore_errors=True)
        self.rokct_dir = os.path.join(self.project_root, ".rokct")
        self.cache_dir = os.path.join(self.rokct_dir, "cache")
        os.makedirs(self.cache_dir)
        os.makedirs(os.path.join(self.rokct_dir, "config"))
        with open(
            os.path.join(self.project_root, "pubspec.yaml"), "w", encoding="utf-8"
        ) as f:
            f.write("name: testapp\nflutter:\n  assets:\n")
        self._saved_strict = os.environ.pop("ROKCT_COMPOSE_STRICT", None)
        self.addCleanup(self._restore_strict)
        self.write_sdk()

    def _restore_strict(self):
        os.environ.pop("ROKCT_COMPOSE_STRICT", None)
        if self._saved_strict is not None:
            os.environ["ROKCT_COMPOSE_STRICT"] = self._saved_strict

    def write_sdk(self, scope=MARKETPLACE):
        sdk_dir = os.path.join(self.cache_dir, "shop")
        demo = os.path.join(sdk_dir, "templates", "assets", "demo", "shop")
        audio = os.path.join(sdk_dir, "templates", "assets", "audio")
        os.makedirs(demo, exist_ok=True)
        os.makedirs(audio, exist_ok=True)
        with open(
            os.path.join(demo, "api.shop.get_shops.json"), "w", encoding="utf-8"
        ) as f:
            f.write('{"data": [{"id": "${package}-shop"}]}\n')
        with open(os.path.join(audio, "ding.txt"), "w", encoding="utf-8") as f:
            f.write("ding\n")
        fixtures = {"from": "templates/assets/demo/shop", "to": "assets/demo/shop"}
        if scope is not None:
            fixtures["app_types"] = scope
        manifest = {
            "name": self.SDK_NAME,
            "version": "1.0.0",
            "installs": [
                fixtures,
                {"from": "templates/assets/audio", "to": "assets/audio"},
            ],
            "app_assets": ["assets/demo/shop/", "assets/audio/ding.txt"],
        }
        with open(os.path.join(sdk_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)

    def set_app_type(self, app_type):
        path = os.path.join(self.rokct_dir, "config", "app_type")
        if app_type is None:
            if os.path.exists(path):
                os.remove(path)
            return
        with open(path, "w", encoding="utf-8") as f:
            f.write(app_type + "\n")

    def install(self):
        global _module_counter
        _module_counter += 1
        module_path = os.path.join(self.rokct_dir, "sdk_installer_base.py")
        shutil.copy2(_INSTALLER_SRC, module_path)
        spec = importlib.util.spec_from_file_location(
            f"sdk_installer_base_scoped_test_{_module_counter}", module_path
        )
        installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(installer)
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            ok = installer.install_sdk_files_and_routes(self.SDK_NAME)
        self.assertTrue(ok, out.getvalue() + err.getvalue())
        self.installer = installer
        return out.getvalue() + err.getvalue()

    def exists(self, rel):
        return os.path.exists(os.path.join(self.project_root, rel))

    def pubspec(self):
        with open(
            os.path.join(self.project_root, "pubspec.yaml"), encoding="utf-8"
        ) as f:
            return f.read()

    def state_files(self):
        with open(
            os.path.join(self.cache_dir, "install_state.json"), encoding="utf-8"
        ) as f:
            return json.load(f)["packages"][self.SDK_NAME]["files"]


class TestScopedInstall(ScopedInstallTestBase):
    def test_listed_app_type_installs_and_registers(self):
        self.set_app_type("manager")
        self.install()
        self.assertTrue(self.exists(FIXTURE_REL))
        self.assertTrue(self.exists(SOUND_REL))
        self.assertIn("    - assets/demo/shop/", self.pubspec())
        self.assertIn("    - assets/audio/ding.txt", self.pubspec())

    def test_other_app_type_skips_entry_and_its_asset(self):
        self.set_app_type("supacharge")
        out = self.install()
        self.assertFalse(self.exists(FIXTURE_REL))
        self.assertFalse(self.exists("assets/demo"))
        self.assertTrue(self.exists(SOUND_REL))
        self.assertNotIn("assets/demo/shop/", self.pubspec())
        self.assertIn("    - assets/audio/ding.txt", self.pubspec())
        # Scoped out on purpose: no missing-directory warning.
        self.assertNotIn("nothing was installed there", out)

    def test_no_app_type_marker_skips_scoped_entry(self):
        self.set_app_type(None)
        self.install()
        self.assertFalse(self.exists(FIXTURE_REL))
        self.assertTrue(self.exists(SOUND_REL))

    def test_unscoped_entry_installs_everywhere(self):
        self.write_sdk(scope=None)
        self.set_app_type("supacharge")
        self.install()
        self.assertTrue(self.exists(FIXTURE_REL))
        self.assertIn("    - assets/demo/shop/", self.pubspec())

    def test_scope_is_case_insensitive_and_accepts_a_string(self):
        self.write_sdk(scope="Customer")
        self.set_app_type("customer")
        self.install()
        self.assertTrue(self.exists(FIXTURE_REL))


class TestRetraction(ScopedInstallTestBase):
    def test_state_recorded_copy_is_retracted(self):
        # An earlier compose installed the fixtures unscoped...
        self.write_sdk(scope=None)
        self.set_app_type("supacharge")
        self.install()
        self.assertTrue(self.exists(FIXTURE_REL))
        # ...then the manifest scoped them to marketplace apps.
        self.write_sdk(scope=MARKETPLACE)
        out = self.install()
        self.assertIn("RETRACT", out)
        self.assertFalse(self.exists(FIXTURE_REL))
        self.assertFalse(self.exists("assets/demo"))
        self.assertNotIn(FIXTURE_REL, self.state_files())
        self.assertTrue(self.exists(SOUND_REL))
        self.assertNotIn("assets/demo/shop/", self.pubspec())

    def test_committed_identical_copy_is_retracted_without_state(self):
        # A fresh checkout: the copy is committed, no install_state exists.
        self.set_app_type("supacharge")
        path = os.path.join(self.project_root, FIXTURE_REL)
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"data": [{"id": "testapp-shop"}]}\n')
        self.install()
        self.assertFalse(self.exists(FIXTURE_REL))

    def test_modified_copy_is_kept(self):
        self.set_app_type("supacharge")
        path = os.path.join(self.project_root, FIXTURE_REL)
        os.makedirs(os.path.dirname(path))
        with open(path, "w", encoding="utf-8") as f:
            f.write('{"data": [{"id": "my-own-shop"}]}\n')
        out = self.install()
        self.assertTrue(self.exists(FIXTURE_REL))
        self.assertIn("modified locally", out)

    def test_marketplace_app_keeps_its_copy(self):
        self.set_app_type("driver")
        self.install()
        out = self.install()
        self.assertNotIn("RETRACT", out)
        self.assertTrue(self.exists(FIXTURE_REL))


class TestOwnedTargets(ScopedInstallTestBase):
    def test_manifest_install_targets_ignore_scoped_away_entries(self):
        self.set_app_type("supacharge")
        self.install()
        with open(
            os.path.join(self.cache_dir, "shop", "manifest.json"), encoding="utf-8"
        ) as f:
            manifest = json.load(f)
        targets = self.installer._manifest_install_targets(
            manifest, os.path.join(self.cache_dir, "shop")
        )
        self.assertEqual(targets, {SOUND_REL})


if __name__ == "__main__":
    unittest.main()
