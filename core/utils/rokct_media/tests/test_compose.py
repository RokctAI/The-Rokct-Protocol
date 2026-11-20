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

"""rokct_media.compose (level 2), ported from factory radio_ads/tests.

Quick tests that need no model: validation, beds, the mix, watch mode.

    python -m unittest discover -s tests -v

Uses the 'dummy' engine (tones instead of speech) and generates its own
reference WAVs, so it runs without the voices/ folder or VibeVoice.
"""
from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path

import numpy as np

from rokct_media.compose import bed, dsp
from rokct_media.compose.pipeline import make_ad
from rokct_media.compose.schema import AdError, load_ad
from rokct_media.compose.watch import watch


def base_ad(**over):
    ad = {
        "id": "test_ad", "client": "Test", "duration_s": 15, "format": "single-voice",
        "cast": {"host": {"voice": "v1"}},
        "script": [{"speaker": "host", "text": "Hello there, this is a short test advert."},
                   {"speaker": "host", "text": "Buy now while stocks last."}],
        "tag": {"speaker": "host", "text": "Terms apply.", "fast": True},
        "music": {"bed": "builtin:calm"},
        "sfx": [{"file": "builtin:ding", "segment": 1, "offset_s": -0.2}],
        "render": {"engine": "dummy"},
    }
    ad.update(over)
    return ad


class FactoryTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.voices = self.tmp / "voices"
        self.voices.mkdir()
        t = np.arange(24000 * 3) / 24000
        for v in ("v1", "v2"):
            dsp.write_wav(self.voices / f"{v}.wav", 0.1 * np.sin(2 * np.pi * 150 * t), 24000)

    def tearDown(self):
        shutil.rmtree(self.tmp)

    def write(self, ad, name="ad.json"):
        p = self.tmp / name
        p.write_text(json.dumps(ad))
        return p


    def test_semantic_errors(self):
        ad = base_ad(format="dialogue")
        ad["script"][1]["speaker"] = "nobody"
        ad["sfx"] = [{"file": "builtin:nope", "at_s": 1, "segment": 0}]
        with self.assertRaises(AdError) as cm:
            load_ad(self.write(ad), self.voices)
        msg = str(cm.exception)
        for needle in ("not in cast", "exactly one of", "unknown built-in"):
            self.assertIn(needle, msg)

    def test_bad_duration_rejected(self):
        with self.assertRaises(AdError):
            load_ad(self.write(base_ad(duration_s=20)), self.voices)

    def test_defaults_filled(self):
        ad, _ = load_ad(self.write(base_ad()), self.voices)
        self.assertEqual(ad["output"]["loudness_lufs"], -23)
        self.assertEqual(ad["output"]["true_peak_dbtp"], -1)
        self.assertEqual(ad["tag"]["rate"], 1.2)
        self.assertEqual(ad["render"]["resolved_mode"], "per_line")

    def test_beds(self):
        for style in bed.STYLES:
            b = bed.generate_bed(style, 4, 22050, seed=3)
            self.assertEqual(b.shape, (4 * 22050, 2))
            self.assertTrue(np.isfinite(b).all())
            self.assertGreater(np.abs(b).max(), 0.1)

    def test_full_mix_hits_loudness_and_length(self):
        for lufs in (-23, -16):
            ad = base_ad(output={"loudness_lufs": lufs, "true_peak_dbtp": -1})
            rep = make_ad(self.write(ad), self.tmp / "out", voices_dir=self.voices,
                          cache_dir=self.tmp / "cache", asr=False, log=lambda m: None)
            m = rep["loudness"]["measured"]
            self.assertAlmostEqual(m["wav"]["integrated_lufs"], lufs, delta=0.3)
            self.assertLessEqual(m["wav"]["true_peak_dbtp"], -0.9)
            self.assertAlmostEqual(m["mp3"]["integrated_lufs"], lufs, delta=0.3)
            self.assertEqual(rep["timing"]["actual_duration_s"], 15.0)
            self.assertTrue((self.tmp / "out" / "test_ad" / "test_ad.mp3").exists())

    def test_cache_rerenders_only_changed_line(self):
        p = self.write(base_ad())
        kw = dict(voices_dir=self.voices, cache_dir=self.tmp / "cache", asr=False, log=lambda m: None)
        make_ad(p, self.tmp / "out", **kw)
        ad = base_ad()
        ad["script"][1]["text"] = "Buy today while stocks last."
        rep = make_ad(self.write(ad), self.tmp / "out", **kw)
        self.assertEqual(rep["render"]["lines_rendered"], 1)
        self.assertEqual(rep["render"]["lines_cached"], 2)

    def test_over_long_script_is_sped_up(self):
        ad = base_ad()
        ad["script"].append({"speaker": "host", "text": "One more sentence that makes this a bit longer than it should be, by quite a few extra words."})
        rep = make_ad(self.write(ad), self.tmp / "out", voices_dir=self.voices,
                      cache_dir=self.tmp / "cache", asr=False, log=lambda m: None)
        self.assertGreater(rep["timing"]["tempo_applied"], 1.0)
        self.assertLessEqual(rep["timing"]["tempo_applied"], 1.08 + 1e-6)

    def test_watch_once_success_and_failure(self):
        inbox = self.tmp / "inbox"
        inbox.mkdir()
        (inbox / "good.json").write_text(json.dumps(base_ad(id="good")))
        (inbox / "bad.json").write_text(json.dumps(base_ad(id="bad", duration_s=7)))
        watch(inbox, self.tmp / "out", once=True, voices_dir=self.voices,
              cache_dir=self.tmp / "cache", asr=False, log=lambda m: None)
        self.assertTrue((self.tmp / "out" / "good" / "good.mp3").exists())
        self.assertTrue((self.tmp / "failed" / "bad.json").exists())
        self.assertIn("duration_s", (self.tmp / "failed" / "bad.error.txt").read_text())
        self.assertFalse((inbox / "bad.json").exists())


if __name__ == "__main__":
    unittest.main()
