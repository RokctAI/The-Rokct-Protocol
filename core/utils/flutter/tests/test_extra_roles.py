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

"""Tests for per-SDK extra roles ("roles" on a composer.json SDK entry).

The marker .rokct/config/app_type stays the app's primary role. A shell may
add roles for one SDK, e.g. {"name": "orders_sdk", "roles": ["customer"]}, so
a manager gets the customer flow from that SDK only. These pin that:

  * no "roles" = behaviour identical to before (marker only)
  * extra roles keep their lib/src/<role>/ folder instead of stripping it
  * flavor blocks of every role merge, the marker's own role winning
  * install entries scoped by app_types apply to any of the roles
  * the roles reach the SDK's install.py through ROKCT_EXTRA_ROLES

Run:  python -m pytest core/utils/flutter/tests -q
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_counter = 0


def _load(filename, copy_to=None):
    """Load a module; copy_to puts a copy there first (the installer finds its
    project root from where it sits, so it must live in <root>/.rokct/)."""
    global _counter
    _counter += 1
    name = f"{filename[:-3]}_extra_roles_{_counter}"
    path = os.path.join(_DIR, filename)
    if copy_to:
        shutil.copy2(path, copy_to)
        path = copy_to
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


class ExtraRolesTest(unittest.TestCase):
    def setUp(self):
        self._old_cwd = os.getcwd()
        self._old_env = os.environ.pop("ROKCT_EXTRA_ROLES", None)
        self.root = tempfile.mkdtemp()
        os.chdir(self.root)
        os.makedirs(os.path.join(self.root, ".rokct", "config"))
        self.composer = _load("sdk_composer.py")
        self.installer = _load(
            "sdk_installer_base.py",
            copy_to=os.path.join(self.root, ".rokct", "sdk_installer_base.py"),
        )

    def tearDown(self):
        os.chdir(self._old_cwd)
        os.environ.pop("ROKCT_EXTRA_ROLES", None)
        if self._old_env is not None:
            os.environ["ROKCT_EXTRA_ROLES"] = self._old_env
        shutil.rmtree(self.root, ignore_errors=True)

    def set_marker(self, value):
        with open(
            os.path.join(self.root, ".rokct", "config", "app_type"), "w"
        ) as f:
            f.write(value + "\n")

    def make_sdk(self, personas, manifest_extra=None):
        d = os.path.join(self.root, "orders")
        os.makedirs(os.path.join(d, "lib", "src", "common"))
        for p in personas:
            os.makedirs(os.path.join(d, "lib", "src", p))
        manifest = {"app_type": {p: {} for p in personas}}
        manifest.update(manifest_extra or {})
        with open(os.path.join(d, "manifest.json"), "w") as f:
            json.dump(manifest, f)
        return d

    # --- composer.json parsing ---------------------------------------------
    def test_parse_extra_roles(self):
        parse = self.composer.parse_extra_roles
        self.assertEqual(parse(["Customer", " customer ", "driver"]), ["customer", "driver"])
        self.assertEqual(parse("customer"), ["customer"])
        self.assertEqual(parse(None), [])
        self.assertEqual(parse(5), [])

    def test_register_and_lookup_by_clean_name(self):
        self.composer.register_extra_roles(
            [{"name": "orders_sdk", "roles": ["customer"]}, {"name": "base_sdk"}, "x"]
        )
        self.assertEqual(self.composer.extra_roles_for("orders_sdk"), ["customer"])
        self.assertEqual(self.composer.extra_roles_for("orders"), ["customer"])
        self.assertEqual(self.composer.extra_roles_for("base_sdk"), [])

    # --- role folder stripping ---------------------------------------------
    def test_without_roles_strip_is_unchanged(self):
        self.set_marker("manager")
        d = self.make_sdk(["manager", "customer", "driver"])
        self.assertEqual(
            sorted(self.composer.role_folders_to_strip(d)), ["customer", "driver"]
        )

    def test_extra_role_folder_is_kept(self):
        self.set_marker("manager")
        d = self.make_sdk(["manager", "customer", "driver"])
        self.assertEqual(
            self.composer.role_folders_to_strip(d, ["customer"]), ["driver"]
        )

    def test_marker_not_declared_but_extra_role_is(self):
        # A shell with its own marker (rokct) taking manager from this SDK.
        self.set_marker("rokct")
        d = self.make_sdk(["manager", "customer"])
        self.assertEqual(
            self.composer.role_folders_to_strip(d, ["manager"]), ["customer"]
        )

    def test_no_declared_role_strips_nothing(self):
        self.set_marker("rokct")
        d = self.make_sdk(["manager", "customer"])
        self.assertEqual(self.composer.role_folders_to_strip(d), [])
        self.assertEqual(self.composer.role_folders_to_strip(d, ["driver"]), [])

    def test_source_hash_follows_the_extra_roles(self):
        self.set_marker("manager")
        d = self.make_sdk(["manager", "customer"])
        for p in ("manager", "customer"):
            with open(os.path.join(d, "lib", "src", p, "a.dart"), "w") as f:
                f.write(p)
        plain = self.composer.source_hash(d)
        with_customer = self.composer.source_hash(d, ["customer"])
        self.assertNotEqual(plain, with_customer)

    # --- sdk_requires --------------------------------------------------------
    def test_extra_role_sdk_requires_counts(self):
        self.set_marker("rokct")
        cache = os.path.join(self.root, ".rokct", "cache", "orders")
        os.makedirs(cache)
        with open(os.path.join(cache, "manifest.json"), "w") as f:
            json.dump({"app_type": {"manager": {"sdk_requires": ["pay_sdk"]}}}, f)
        sdks = [{"name": "orders_sdk", "enabled": True, "roles": ["manager"]}]
        self.composer.register_extra_roles(sdks)
        self.assertEqual(
            self.composer.find_missing_sdk_requires(sdks, sdks),
            [("orders_sdk", "pay_sdk")],
        )
        self.composer.register_extra_roles([])
        self.assertEqual(self.composer.find_missing_sdk_requires(sdks, sdks), [])

    # --- installer environment ----------------------------------------------
    def test_installer_env(self):
        self.composer.register_extra_roles(
            [{"name": "orders_sdk", "roles": ["customer", "driver"]}]
        )
        env = self.composer.installer_env("orders_sdk")
        self.assertEqual(env["ROKCT_EXTRA_ROLES"], "customer,driver")
        os.environ["ROKCT_EXTRA_ROLES"] = "leak"
        self.assertNotIn("ROKCT_EXTRA_ROLES", self.composer.installer_env("base_sdk"))

    # --- installer: roles, flavor merge, scoping --------------------------------
    def test_resolve_app_roles(self):
        self.assertEqual(self.installer.resolve_app_roles(), [])
        self.set_marker("rokct")
        self.assertEqual(self.installer.resolve_app_roles(), ["rokct"])
        os.environ["ROKCT_EXTRA_ROLES"] = "manager, customer ,rokct,,"
        self.assertEqual(
            self.installer.resolve_app_roles(), ["rokct", "manager", "customer"]
        )

    def test_flavor_merge_marker_wins_and_lists_combine(self):
        self.set_marker("manager")
        os.environ["ROKCT_EXTRA_ROLES"] = "customer"
        manifest = {
            "app_type": {
                "manager": {
                    "installs": [{"from": "m", "to": "m"}],
                    "session_policy": {"home": "/main"},
                    "constants": {"a": "manager", "b": "m"},
                },
                "customer": {
                    "installs": [{"from": "c", "to": "c"}],
                    "session_policy": {"home": "/home"},
                    "constants": {"a": "customer", "c": "c"},
                },
            }
        }
        merged = self.installer.merged_flavor_block(manifest)
        self.assertEqual(
            merged["installs"], [{"from": "c", "to": "c"}, {"from": "m", "to": "m"}]
        )
        self.assertEqual(merged["session_policy"], {"home": "/main"})
        self.assertEqual(merged["constants"], {"a": "manager", "c": "c", "b": "m"})

    def test_flavor_merge_combines_nested_dicts(self):
        # The marker's own block adds to, not replaces, an extra role's
        # constants.overrides (rokct adds appTitle, manager keeps its nav).
        self.set_marker("rokct")
        os.environ["ROKCT_EXTRA_ROLES"] = "manager"
        manifest = {
            "app_type": {
                "manager": {
                    "constants": {"import": "pkg:x", "overrides": {"nav": "rail"}}
                },
                "rokct": {
                    "app_name": "ROKCT",
                    "constants": {"overrides": {"appTitle": "'ROKCT'"}},
                },
            }
        }
        merged = self.installer.merged_flavor_block(manifest)
        self.assertEqual(merged["app_name"], "ROKCT")
        self.assertEqual(
            merged["constants"],
            {"import": "pkg:x", "overrides": {"nav": "rail", "appTitle": "'ROKCT'"}},
        )

    def test_flavor_merge_without_roles_equals_old_lookup(self):
        self.set_marker("manager")
        block = {"installs": [{"from": "m", "to": "m"}]}
        manifest = {"app_type": {"manager": block, "customer": {"installs": []}}}
        self.assertEqual(self.installer.merged_flavor_block(manifest), block)
        self.assertEqual(self.installer.merged_flavor_block({}), {})
        os.remove(os.path.join(self.root, ".rokct", "config", "app_type"))
        self.assertEqual(self.installer.merged_flavor_block(manifest), {})

    def test_install_entry_applies_to_any_role(self):
        entry = {"app_types": ["customer"]}
        applies = self.installer.install_entry_applies
        self.assertTrue(applies(entry, "customer"))
        self.assertFalse(applies(entry, "manager"))
        self.assertTrue(applies(entry, ["manager", "customer"]))
        self.assertFalse(applies(entry, []))
        self.assertFalse(applies(entry, None))
        self.assertTrue(applies({}, None))


class RokctTemplateTest(unittest.TestCase):
    """composer/rokct.json is manager.json plus the manager role per SDK."""

    def load(self, name):
        with open(os.path.join(_DIR, "composer", name), encoding="utf-8") as f:
            return json.load(f)

    def test_same_sdk_set_as_manager_with_manager_role(self):
        manager = self.load("manager.json")["sdks"]
        rokct = self.load("rokct.json")["sdks"]
        self.assertEqual([s["name"] for s in rokct], [s["name"] for s in manager])
        for m, r in zip(manager, rokct):
            self.assertEqual(r.get("enabled"), m.get("enabled"))
            self.assertEqual(r.get("sha256"), m.get("sha256"))
            self.assertEqual(r.get("roles"), ["manager"], r["name"])


if __name__ == "__main__":
    unittest.main()
