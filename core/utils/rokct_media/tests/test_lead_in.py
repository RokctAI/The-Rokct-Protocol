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

"""Every finished clip starts with a lead-in of silence, never doubled."""

import unittest

import numpy as np

from rokct_media.speech.stitch import LEAD_FADE_S, LEAD_S, PAD_S, SR, lead_in

WANT = int(round(LEAD_S * SR))


def tone(n):
    return 0.5 * np.sin(2 * np.pi * 220 * np.arange(n) / SR)


class LeadInTest(unittest.TestCase):
    def test_defaults_mirror_tail(self):
        self.assertEqual((LEAD_S, LEAD_FADE_S), (PAD_S, 0.010))

    def test_speech_at_sample_zero_gets_lead_in(self):
        x = np.full(SR // 2, 0.5)
        y = lead_in(x)
        self.assertEqual(len(y), len(x) + WANT)
        self.assertTrue((y[:WANT] == 0).all())
        fade = int(LEAD_FADE_S * SR)
        self.assertEqual(y[WANT], 0.0)
        self.assertLess(y[WANT + fade // 2], 0.5)
        self.assertAlmostEqual(y[WANT + fade], 0.5)

    def test_existing_lead_in_is_not_doubled(self):
        x = np.concatenate([np.zeros(WANT), tone(SR // 2)])
        np.testing.assert_array_equal(lead_in(x), x)
        longer = np.concatenate([np.zeros(3 * WANT), tone(SR // 2)])
        np.testing.assert_array_equal(lead_in(longer), longer)

    def test_short_lead_in_is_topped_up_to_target(self):
        have = WANT // 4
        x = np.concatenate([np.zeros(have), np.full(SR // 2, 0.5)])
        y = lead_in(x)
        self.assertEqual(len(y), len(x) + WANT - have)
        self.assertTrue((y[:WANT] == 0).all())

    def test_silence_and_zero_target_pass_through(self):
        np.testing.assert_array_equal(lead_in(np.zeros(100)), np.zeros(100))
        x = np.full(100, 0.5)
        np.testing.assert_array_equal(lead_in(x, lead_s=0), x)

    def test_stitch_output_starts_with_lead_in(self):
        try:
            import librosa  # noqa: F401
        except ImportError:
            self.skipTest("librosa not installed")
        from rokct_media.speech.stitch import stitch

        y, _ = stitch([np.full(SR // 2, 0.5), np.full(SR // 2, 0.5)])
        self.assertGreaterEqual(int(np.argmax(np.abs(y) > 0.005)), WANT)


if __name__ == "__main__":
    unittest.main()
