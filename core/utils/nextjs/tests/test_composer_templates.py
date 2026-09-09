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

"""Invariants over the Next.js half of the product templates in
core/utils/frappe/composer/ (their optional sdks[] arrays, read by
core/utils/nextjs/sdk_composer.py) - the Next.js counterpart of
core/utils/flutter/tests/test_composer_templates.py.

  * every template parses as JSON; every sdks[] entry is uniquely named and
    carries a boolean "home_sdk"
  * a template whose sdks[] lists any SDK beyond the kernel (base_sdk,
    auth_sdk, telemetry_sdk) flags exactly one of them home; no template
    flags more than one; the kernel SDKs are never home
  * order_sdks_for_install() puts each template's home SDK directly behind
    the last kernel entry (telemetry_sdk, base_sdk) listed ahead of it

Run:  python -m pytest core/utils/nextjs/tests -q
  or: python core/utils/nextjs/tests/test_composer_templates.py
"""

import importlib.util
import json
import os
import unittest

_UTILS_DIR = os.path.dirname(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
)
COMPOSER_DIR = os.path.join(_UTILS_DIR, "frappe", "composer")
COMPOSER_SRC = os.path.join(_UTILS_DIR, "nextjs", "sdk_composer.py")

# Shared kernel / seam SDKs: composed into every shell, never its home.
NEVER_HOME = ("base_sdk", "auth_sdk", "telemetry_sdk")

# The home SDK each product template flags today (deliveryplatform's is
# provisional: products_sdk is the only non-kernel entry in its Next.js
# half until the delivery-vs-merchants pick lands).
EXPECTED_HOME = {
    "supacharge.json": "lms_sdk",
    "rokctapp.json": "agent_sdk",
    "deliveryplatform.json": "products_sdk",
    "telephony.json": None,
}


def template_paths():
    return sorted(
        os.path.join(COMPOSER_DIR, name)
        for name in os.listdir(COMPOSER_DIR)
        if name.endswith(".json")
    )


def load_composer():
    spec = importlib.util.spec_from_file_location(
        "nextjs_composer_templates_test", COMPOSER_SRC
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestNextjsTemplateHomeSdk(unittest.TestCase):
    def setUp(self):
        self.templates = {}
        for path in template_paths():
            with open(path, "r", encoding="utf-8") as f:
                self.templates[os.path.basename(path)] = json.load(f)
        self.assertTrue(self.templates)

    def sdks(self, name):
        return [s for s in self.templates[name].get("sdks", []) if isinstance(s, dict)]

    def test_every_sdks_entry_carries_a_boolean_home_sdk(self):
        for name, template in self.templates.items():
            names = [s.get("name") for s in self.sdks(name)]
            self.assertEqual(
                len(names), len(set(names)), f"{name}: duplicate sdks[] names"
            )
            for entry in self.sdks(name):
                self.assertIn(
                    "home_sdk",
                    entry,
                    f"{name}: {entry.get('name')} has no home_sdk key",
                )
                self.assertIsInstance(
                    entry["home_sdk"],
                    bool,
                    f"{name}: {entry.get('name')} home_sdk is not a bool",
                )

    def test_exactly_one_home_per_product_template(self):
        for name in self.templates:
            entries = self.sdks(name)
            flagged = [s["name"] for s in entries if s.get("home_sdk") is True]
            self.assertLessEqual(
                len(flagged), 1, f"{name}: several home SDKs {flagged}"
            )
            candidates = [s["name"] for s in entries if s["name"] not in NEVER_HOME]
            if candidates:
                self.assertEqual(
                    len(flagged), 1, f"{name}: no home SDK among {candidates}"
                )
            if name in EXPECTED_HOME:
                self.assertEqual(
                    flagged, [EXPECTED_HOME[name]] if EXPECTED_HOME[name] else [], name
                )

    def test_kernel_sdks_are_never_home(self):
        for name in self.templates:
            for entry in self.sdks(name):
                if entry["name"] in NEVER_HOME:
                    self.assertFalse(
                        entry.get("home_sdk"), f"{name}: {entry['name']} flagged home"
                    )

    def test_home_installs_directly_behind_the_kernel(self):
        composer = load_composer()
        for name in self.templates:
            entries = [s for s in self.sdks(name) if s.get("enabled", True)]
            flagged = [s["name"] for s in entries if s.get("home_sdk") is True]
            ordered = [s["name"] for s in composer.order_sdks_for_install(entries)]
            self.assertEqual(sorted(ordered), sorted(s["name"] for s in entries), name)
            if not flagged:
                self.assertEqual(ordered, [s["name"] for s in entries], name)
                continue
            composer_order = [s["name"] for s in entries]
            kernel_before_home = [
                idx
                for idx, sdk_name in enumerate(
                    composer_order[: composer_order.index(flagged[0])]
                )
                if sdk_name in composer.KERNEL_SDKS
            ]
            expected_idx = kernel_before_home[-1] + 1 if kernel_before_home else 0
            self.assertEqual(
                ordered.index(flagged[0]),
                expected_idx,
                f"{name}: {flagged[0]} order {ordered}",
            )


if __name__ == "__main__":
    unittest.main()
