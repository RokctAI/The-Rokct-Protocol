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

"""Bootstrap must not overwrite artwork the app updated by hand."""

import os
import unittest

from test_sdk_installer_base import LayoutIntegrationTestBase

ICON = "android/app/src/main/res/mipmap-hdpi/ic_launcher.png"
FAVICON = "web/favicon.png"
OTHER = "lib/main.dart"


def _write(path, data):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(data)


class BootstrapArtworkTest(LayoutIntegrationTestBase):
    def _sdk(self):
        sdk = os.path.join(self.project_root, "sdk", "home_sdk")
        _write(os.path.join(sdk, "templates", "icon.png"), b"baseline-icon")
        _write(os.path.join(sdk, "templates", "fav.png"), b"baseline-fav")
        _write(os.path.join(sdk, "templates", "main.dart"), b"baseline-main")
        installs = [
            {"from": "templates/icon.png", "to": ICON},
            {"from": "templates/fav.png", "to": FAVICON},
            {"from": "templates/main.dart", "to": OTHER},
        ]
        import json

        with open(os.path.join(sdk, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump({"installs": installs}, f)
        self.installer.resolve_home_sdk = lambda: "home_sdk"
        self.installer.save_state = lambda state: None

    def _read(self, rel):
        with open(os.path.join(self.project_root, rel), "rb") as f:
            return f.read()

    def test_hand_updated_artwork_is_kept(self):
        self._sdk()
        _write(os.path.join(self.project_root, ICON), b"my-own-icon")
        _write(os.path.join(self.project_root, OTHER), b"old-main")
        self.installer.bootstrap_home_sdk_if_missing({})
        self.assertEqual(self._read(ICON), b"my-own-icon")
        self.assertEqual(self._read(FAVICON), b"baseline-fav")
        self.assertEqual(self._read(OTHER), b"baseline-main")

    def test_fresh_scaffold_defaults_are_replaced(self):
        self._sdk()
        _write(os.path.join(self.project_root, ICON), b"flutter-default")
        self.installer.FRESH_SCAFFOLD = True
        self.installer.bootstrap_home_sdk_if_missing({})
        self.assertEqual(self._read(ICON), b"baseline-icon")

    def test_own_written_file_is_refreshed_but_a_later_hand_edit_is_kept(self):
        self._sdk()
        state = {}
        self.installer.bootstrap_home_sdk_if_missing(state)
        self.assertEqual(self._read(ICON), b"baseline-icon")
        self.assertIn(ICON, state["bootstrap_artwork"])
        # The baseline moves on and compose wrote the file itself: replaced.
        _write(
            os.path.join(self.project_root, "sdk", "home_sdk", "templates", "icon.png"),
            b"baseline-icon-v2",
        )
        state.pop("bootstrapped_home_sdk")
        self.installer.bootstrap_home_sdk_if_missing(state)
        self.assertEqual(self._read(ICON), b"baseline-icon-v2")
        # The app edits it by hand: the next baseline change is not applied.
        _write(os.path.join(self.project_root, ICON), b"my-own-icon")
        _write(
            os.path.join(self.project_root, "sdk", "home_sdk", "templates", "icon.png"),
            b"baseline-icon-v3",
        )
        state.pop("bootstrapped_home_sdk")
        self.installer.bootstrap_home_sdk_if_missing(state)
        self.assertEqual(self._read(ICON), b"my-own-icon")


if __name__ == "__main__":
    unittest.main()
