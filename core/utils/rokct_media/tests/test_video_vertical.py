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

"""rokct_media.video.vertical: the 9:16 assembly moved from the agent's tiktok_render.py."""

import unittest
from pathlib import Path

from rokct_media.video import vertical as V


class Vertical(unittest.TestCase):
    def test_overlay_plan_hook_then_even_slots(self):
        plan = V.overlay_plan({"hook": "Hook", "on_screen_text": ["a", "b"]}, 11.0)
        self.assertEqual(plan[0], ("Hook", 0.0, V.HOOK_SECONDS, True))
        self.assertEqual([p[1:3] for p in plan[1:]], [(3.0, 7.0), (7.0, 11.0)])

    def test_wrapped_never_changes_characters(self):
        t = "the decimal comma in 2,28 stays exactly as written here"
        self.assertEqual(V.wrapped(t, 20).replace("\n", " "), t)

    def test_graph_and_command(self):
        g = V.build_graph("motion", None, False, 5.0, [], silent=False)
        self.assertIn(f"scale={V.WIDTH}:{V.HEIGHT}", g)
        self.assertIn(V.LOUDNORM, g)
        cmd = V.render_cmd(Path("v.mp4"), "motion", Path("a.wav"), g, 5.0, Path("o.mp4"))
        self.assertEqual(cmd[-3:], ["-movflags", "+faststart", "o.mp4"])
        silent = V.render_cmd(Path("v.png"), "still", None, V.build_graph("still", None, True, 5.0, [], True),
                              5.0, Path("o.mp4"))
        self.assertIn("-an", silent)
        self.assertNotIn("[a]", " ".join(silent))

    def test_esc(self):
        self.assertEqual(V.esc("a:b"), "a\\:b")


if __name__ == "__main__":
    unittest.main()
