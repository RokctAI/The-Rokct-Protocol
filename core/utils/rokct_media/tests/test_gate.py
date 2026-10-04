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

"""The QC gate's selection, tail check, stitch and keep_through cut.
Model-free; lifted from factory voice_batch/tests (Selection, Tail). The
gate numbers are asserted, so a change to one fails here."""

import unittest

import numpy as np

from rokct_media.qc import gate as G
from rokct_media.qc.gate import pick, sim_threshold
from rokct_media.qc.meter import TAIL_MAX_DB, tail_db, tail_ok
from rokct_media.speech.cut import cut_after, text_through

try:
    import librosa  # noqa: F401

    HAVE_LIBROSA = True
except ImportError:
    HAVE_LIBROSA = False

SR = 24000


def tone(s, amp=0.3):
    return amp * np.sin(np.arange(int(s * SR)) * 2 * np.pi * 110 / SR)


class Numbers(unittest.TestCase):
    def test_gate_numbers_unchanged(self):
        self.assertEqual(
            (G.SIM_LONG, G.SIM_SHORT, G.LONG_S, G.TAKE_SIM_MIN), (0.88, 0.83, 5.0, 0.83)
        )
        self.assertEqual((G.TAIL_WIN_S, G.TAIL_MAX_DB), (0.05, -34.0))
        self.assertEqual((G.TARGET_F0, G.F0_TOLERANCE), (102.0, 8.0))
        self.assertEqual(G.f0_range(196, 12), (184, 208))
        self.assertEqual(G.pyin_bounds(102, 8), (50.0, 300.0))
        self.assertEqual(G.pyin_bounds(196, 12), (50.0, 416))
        from rokct_media.speech.stitch import FADE_S, GAPS_S, PAD_S

        self.assertEqual(
            (GAPS_S, PAD_S, FADE_S), ((0.22, 0.20, 0.24, 0.22), 0.04, 0.012)
        )
        from rokct_media.speech.takes import SEED_ROUNDS

        self.assertEqual(SEED_ROUNDS, ([11, 22, 33], [44], [55]))

    def test_final_gate(self):
        m = {"f0": 106.87, "res": 0.8936, "err": 0, "tail_db": -44.59}
        self.assertEqual(
            G.final_gate(m, 3.335),
            ({"f0": True, "similarity": True, "asr": True, "tail": True}, 0.83),
        )
        gate, thr = G.final_gate(dict(m, res=0.86), 5.39)
        self.assertEqual((gate["similarity"], thr), (False, 0.88))
        gate, _ = G.final_gate(dict(m, f0=204.67), 5.0, 196, 12)
        self.assertTrue(gate["f0"])
        gate, _ = G.final_gate(dict(m, f0=110.01), 3.0)
        self.assertFalse(gate["f0"])


class Selection(unittest.TestCase):
    def t(self, err, f0, sw, res):
        return {"err": err, "f0": f0, "swings": sw, "res": res}

    def test_order(self):
        a, b, c = (
            self.t(0, 104, 2, 0.9),
            self.t(0, 101, 5, 0.85),
            self.t(1, 102, 0, 0.99),
        )
        self.assertIs(pick([a, b, c])[0], b)
        d = self.t(0, 101, 1, 0.84)
        self.assertIs(pick([b, d])[0], d)
        e = self.t(0, 101, 1, 0.9)
        self.assertIs(pick([d, e])[0], e)

    def test_tiers(self):
        self.assertEqual(pick([self.t(0, 120, 0, 0.9)])[1], 2)
        self.assertEqual(pick([self.t(2, 100, 0, 0.9)]), (None, 0))
        self.assertEqual(sim_threshold(4.99), 0.83)
        self.assertEqual(sim_threshold(5.0), 0.88)

    def test_voice_b_window(self):
        a = self.t(0, 202.3, 1, 0.87)
        b = self.t(0, 231.1, 0, 0.79)
        self.assertEqual(pick([b], 196, 12)[1], 2)
        self.assertIs(pick([a, b], 196, 12)[0], a)


class Tail(unittest.TestCase):
    def test_abrupt_end_fails(self):
        self.assertGreater(tail_db(tone(1.0), SR), TAIL_MAX_DB)
        self.assertFalse(tail_ok(tail_db(tone(1.0), SR)))

    def test_clean_end_passes(self):
        x = np.concatenate([tone(1.0), np.zeros(int(0.1 * SR))])
        self.assertTrue(tail_ok(tail_db(x, SR)))
        decay = tone(0.3) * np.exp(-np.arange(int(0.3 * SR)) / (0.03 * SR))
        self.assertTrue(tail_ok(tail_db(np.concatenate([tone(1.0), decay]), SR)))

    def test_silence_and_short(self):
        self.assertEqual(tail_db(np.zeros(1000), SR), -120.0)
        self.assertTrue(tail_ok(tail_db(np.zeros(10), SR)))

    def test_pick_skips_clipped_takes(self):
        good = {"err": 0, "f0": 110, "swings": 3, "res": 0.84, "tail_db": -45.0}
        cut = {"err": 0, "f0": 102, "swings": 0, "res": 0.95, "tail_db": -12.0}
        self.assertIs(pick([cut, good])[0], good)
        self.assertEqual(pick([cut]), (None, 0))
        old = {"err": 0, "f0": 102, "swings": 0, "res": 0.95}
        self.assertEqual(pick([old]), (old, 1))


@unittest.skipUnless(HAVE_LIBROSA, "librosa not installed (the [voice] extra)")
class Stitch(unittest.TestCase):
    def test_stitch_pauses(self):
        from rokct_media.speech.stitch import stitch

        pad = np.zeros(int(0.5 * SR))
        y, pauses = stitch([np.concatenate([pad, tone(1), pad])] * 3, SR)
        self.assertEqual(pauses, [300, 280])
        # the first take keeps 40 ms of its own silence; the lead-in tops it up
        self.assertAlmostEqual(
            len(y) / SR, 3 + 6 * 0.04 + 0.22 + 0.20 + (0.20 - 0.04), delta=0.1
        )
        self.assertAlmostEqual(float(y[0]), 0.0, places=6)

    def test_stitch_keeps_a_clipped_end_detectable(self):
        from rokct_media.speech.stitch import stitch

        pad = np.zeros(int(0.5 * SR))
        decay = tone(0.3) * np.exp(-np.arange(int(0.3 * SR)) / (0.02 * SR))
        clean = np.concatenate([pad, tone(1.0), decay, pad])
        clipped = np.concatenate([pad, tone(1.0)])
        self.assertTrue(tail_ok(tail_db(stitch([clean, clean])[0], SR)))
        self.assertFalse(tail_ok(tail_db(stitch([clean, clipped])[0], SR)))


class Cut(unittest.TestCase):
    def test_text_through(self):
        self.assertEqual(text_through("Rokct. Tutors that explain.", "rokct"), "Rokct.")
        self.assertEqual(
            text_through("Meet the Rokct tutors.", "Rokct"), "Meet the Rokct"
        )
        self.assertIsNone(text_through("Meet the tutors.", "Rokct"))

    def test_cut_after_lands_in_the_gap(self):
        x = np.concatenate([tone(0.5), np.zeros(int(0.2 * SR)), tone(0.5)])
        y = cut_after(x, SR, 0.5)
        self.assertIsNotNone(y)
        self.assertAlmostEqual(len(y) / SR, 0.5 + 0.04, delta=0.011)
        self.assertEqual(
            float(np.max(np.abs(y[-int(0.04 * SR) :]))), 0.0
        )  # 40 ms of the gap kept

    def test_cut_after_refuses_run_on(self):
        self.assertIsNone(cut_after(tone(2.0), SR, 0.5))


if __name__ == "__main__":
    unittest.main()
