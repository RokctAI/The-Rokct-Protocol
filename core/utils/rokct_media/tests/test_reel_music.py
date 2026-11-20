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

"""rokct_media.compose.reel_music: the Reel music synth moved from factory."""

import hashlib
import tempfile
import unittest
import wave
from pathlib import Path

from rokct_media.compose import reel_music as M


class ReelMusic(unittest.TestCase):
    def test_tempo_rotates_and_is_stable(self):
        self.assertIn(M.tempo_for(1), M.TEMPOS)
        self.assertEqual(M.tempo_for(20261120), M.tempo_for(20261120))

    def test_render_is_deterministic_mono_44k(self):
        with tempfile.TemporaryDirectory() as d:
            a, b = Path(d) / "a.wav", Path(d) / "b.wav"
            M.render_music(7, 4, a)
            M.render_music(7, 4, b)
            self.assertEqual(
                hashlib.sha256(a.read_bytes()).digest(),
                hashlib.sha256(b.read_bytes()).digest(),
            )
            with wave.open(str(a)) as w:
                self.assertEqual((w.getnchannels(), w.getframerate()), (1, M.RATE))
                self.assertAlmostEqual(w.getnframes() / M.RATE, 4, delta=0.05)

    def test_lay_skips_a_missing_line(self):
        with tempfile.TemporaryDirectory() as d:
            m = Path(d) / "m.wav"
            M.render_music(1, 2, m)
            before = m.read_bytes()
            self.assertIsNone(M.lay(m, Path(d) / "missing.wav", lambda n: 0.1))
            self.assertEqual(m.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
