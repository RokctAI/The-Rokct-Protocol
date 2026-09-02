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


"""Invariants over the composer templates in core/utils/flutter/composer/.

The templates are the SDK sets each app shell copies to its composer.json.
Nothing exercised them before this file: a template could drop an SDK whose
routes another composed SDK's pages push, and the miss surfaced only when a
shell recomposed and failed to build (fix-wave 2026-09-02, item P3:
merchants_sdk's manager restaurant page pushes CalculatorRoute, which only
generates when calc_sdk is composed - manager.json listed calc_sdk,
launch_manager.json did not). These tests pin:

  * every template parses as JSON and declares a non-empty sdks[] list of
    uniquely named entries, each with the fields the composer's
    unpinned-installer gate needs (source/git/path/ref/sha256)
  * the template set matches the list the folder README advertises, and
    pos.json stays deleted (pos merged into manager, item P7)
  * every manager-role template that composes merchants_sdk also composes
    calc_sdk, enabled
  * an SDK pinned in several templates carries one sha256 (the pin is of
    the SDK's install.py at its ref, not of the template)

Run:  python -m pytest core/utils/flutter/tests -q
  or: python core/utils/flutter/tests/test_composer_templates.py
"""

import json
import os
import re
import unittest

COMPOSER_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "composer"
)
README = os.path.join(COMPOSER_DIR, "README.md")

# Templates copied into shells whose .rokct/config/app_type is "manager".
# Templates carry no app_type themselves (the host marker selects the SDK
# manifests' app_type blocks at install time), so the role is known by name.
MANAGER_ROLE_TEMPLATES = ("manager.json", "launch_manager.json")

# SDKs whose pages push routes another SDK generates: composing the first
# without the second is a compile error in the shell, not a compose error.
# (merchants_sdk manager restaurant page -> CalculatorRoute from calc_sdk.)
MANAGER_ROUTE_DEPENDENCIES = {"merchants_sdk": "calc_sdk"}

PIN_FIELDS = ("source", "git", "path", "ref", "sha256")


def template_paths():
    return sorted(
        os.path.join(COMPOSER_DIR, name)
        for name in os.listdir(COMPOSER_DIR)
        if name.endswith(".json")
    )


def load_template(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def sdk_index(template):
    return {entry["name"]: entry for entry in template.get("sdks", [])}


def readme_template_names():
    with open(README, "r", encoding="utf-8") as f:
        text = f.read()
    # The first paragraph lists the templates as `name.json` code spans.
    head = text.split("**templates**", 1)[0]
    return sorted(set(re.findall(r"`([a-z_]+\.json)`", head)))


class TemplateShapeTest(unittest.TestCase):
    def test_templates_exist(self):
        self.assertTrue(template_paths(), "no composer templates found")

    def test_every_template_parses_with_named_pinned_sdks(self):
        for path in template_paths():
            with self.subTest(template=os.path.basename(path)):
                template = load_template(path)
                sdks = template.get("sdks")
                self.assertIsInstance(sdks, list)
                self.assertTrue(sdks, "empty sdks[] list")
                names = [entry.get("name") for entry in sdks]
                self.assertTrue(all(names), "unnamed sdks[] entry")
                self.assertEqual(
                    len(names), len(set(names)), f"duplicate sdk entries: {names}"
                )
                for entry in sdks:
                    missing = [k for k in PIN_FIELDS if not entry.get(k)]
                    self.assertFalse(missing, f"{entry['name']} lacks {missing}")
                    self.assertRegex(entry["sha256"], r"^[0-9a-f]{64}$")

    def test_template_set_matches_readme_list(self):
        on_disk = sorted(os.path.basename(p) for p in template_paths())
        self.assertEqual(on_disk, readme_template_names())

    def test_pos_template_stays_deleted(self):
        self.assertNotIn("pos.json", os.listdir(COMPOSER_DIR))


class ManagerRoleTemplateTest(unittest.TestCase):
    def test_manager_role_templates_are_present(self):
        for name in MANAGER_ROLE_TEMPLATES:
            self.assertTrue(os.path.exists(os.path.join(COMPOSER_DIR, name)), name)

    def test_merchants_manager_pages_have_their_route_owners(self):
        for name in MANAGER_ROLE_TEMPLATES:
            index = sdk_index(load_template(os.path.join(COMPOSER_DIR, name)))
            for pusher, owner in MANAGER_ROUTE_DEPENDENCIES.items():
                if pusher not in index or index[pusher].get("enabled") is False:
                    continue
                with self.subTest(template=name, sdk=pusher, needs=owner):
                    self.assertIn(
                        owner,
                        index,
                        f"{name} composes {pusher} but not {owner}, whose "
                        f"route {pusher}'s manager pages push",
                    )
                    self.assertTrue(
                        index[owner].get("enabled", True),
                        f"{name} lists {owner} but disabled",
                    )


class PinConsistencyTest(unittest.TestCase):
    def test_same_sdk_and_ref_pins_the_same_installer_across_templates(self):
        seen = {}
        for path in template_paths():
            for entry in load_template(path).get("sdks", []):
                key = (entry["name"], entry["path"], entry["ref"])
                prior = seen.setdefault(key, (entry["sha256"], os.path.basename(path)))
                with self.subTest(sdk=entry["name"], template=os.path.basename(path)):
                    self.assertEqual(
                        entry["sha256"],
                        prior[0],
                        f"{entry['name']}@{entry['ref']} pinned differently in "
                        f"{os.path.basename(path)} and {prior[1]}",
                    )


if __name__ == "__main__":
    unittest.main()
