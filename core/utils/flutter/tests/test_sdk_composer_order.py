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


"""Regression tests for sdk_composer.py's install ordering.

Background: main() used to move a "core_sdk" entry to the front of the
install list. core_sdk is retired and no composer profile lists it, so the
reorder was dead code, and the entry that actually matters - the one
flagged "home_sdk": true in composer.json - was cached and installed
wherever the profile happened to list it. The install-side collision rule
already makes the home win regardless of order (see
test_home_sdk_precedence.py); order_sdks_for_install() keeps the passes
predictable on top of that. These tests pin:

  * the composer-flagged home entry moves to the front, everything else
    keeps composer.json order
  * a list with no flag (or the flag already first) is returned unchanged
  * only the FIRST flagged entry moves when several carry the flag - the
    same one resolve_home_sdk() answers
  * core_sdk gets no special treatment any more
  * the input list is not mutated

Run:  python -m pytest core/utils/flutter/tests -q
  or: python core/utils/flutter/tests/test_sdk_composer_order.py
"""

import importlib.util
import os
import sys
import unittest

_COMPOSER_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sdk_composer.py",
)


def _import_composer():
    name = "sdk_composer_under_order_test"
    spec = importlib.util.spec_from_file_location(name, _COMPOSER_SRC)
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


def _sdk(name, **extra):
    entry = {"name": name, "enabled": True}
    entry.update(extra)
    return entry


class OrderSdksForInstallTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _import_composer()

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop("sdk_composer_under_order_test", None)

    def names(self, sdks):
        return [s["name"] for s in sdks]

    def test_flagged_home_moves_to_front_others_keep_order(self):
        sdks = [
            _sdk("base_sdk"),
            _sdk("auth_sdk"),
            _sdk("merchants_sdk"),
            _sdk("launch_sdk", home_sdk=True),
            _sdk("map_sdk"),
        ]
        ordered = self.mod.order_sdks_for_install(sdks)
        self.assertEqual(
            self.names(ordered),
            ["launch_sdk", "base_sdk", "auth_sdk", "merchants_sdk", "map_sdk"],
        )

    def test_no_flag_is_unchanged(self):
        sdks = [_sdk("base_sdk"), _sdk("auth_sdk"), _sdk("users_sdk")]
        self.assertEqual(
            self.names(self.mod.order_sdks_for_install(sdks)), self.names(sdks)
        )

    def test_flag_already_first_is_unchanged(self):
        sdks = [_sdk("radio_sdk", home_sdk=True), _sdk("base_sdk"), _sdk("auth_sdk")]
        self.assertEqual(
            self.names(self.mod.order_sdks_for_install(sdks)), self.names(sdks)
        )

    def test_only_first_flagged_entry_moves(self):
        sdks = [
            _sdk("base_sdk"),
            _sdk("delivery_sdk", home_sdk=True),
            _sdk("merchants_sdk", home_sdk=True),
        ]
        self.assertEqual(
            self.names(self.mod.order_sdks_for_install(sdks)),
            ["delivery_sdk", "base_sdk", "merchants_sdk"],
        )

    def test_explicit_false_flag_does_not_move(self):
        sdks = [_sdk("base_sdk", home_sdk=False), _sdk("supacharge_sdk", home_sdk=True)]
        self.assertEqual(
            self.names(self.mod.order_sdks_for_install(sdks)),
            ["supacharge_sdk", "base_sdk"],
        )

    def test_core_sdk_is_not_special(self):
        sdks = [_sdk("base_sdk"), _sdk("core_sdk"), _sdk("auth_sdk")]
        self.assertEqual(
            self.names(self.mod.order_sdks_for_install(sdks)), self.names(sdks)
        )

    def test_input_list_is_not_mutated(self):
        sdks = [_sdk("base_sdk"), _sdk("launch_sdk", home_sdk=True)]
        before = list(sdks)
        self.mod.order_sdks_for_install(sdks)
        self.assertEqual(sdks, before)

    def test_empty_list(self):
        self.assertEqual(self.mod.order_sdks_for_install([]), [])


if __name__ == "__main__":
    unittest.main()
