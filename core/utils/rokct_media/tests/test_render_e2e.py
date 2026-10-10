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

"""render() end to end with the dummy engine and a stand-in meter (no ASR or
speaker model): the seed rounds, take selection, stitch, out/ files and
result.json, in-process. Needs librosa (stitch) and an MP3 encoder for the
whole_take listen copies; skipped without them."""

import hashlib
import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import librosa  # noqa: F401

    HAVE_LIBROSA = True
except ImportError:
    HAVE_LIBROSA = False
try:
    import lameenc  # noqa: F401

    HAVE_MP3 = True
except ImportError:
    HAVE_MP3 = bool(shutil.which("ffmpeg"))

from rokct_media import render


class FakeMeter:
    """Every take is word-exact with a clean tail; F0 depends on the seed in
    the file name, so selection has something to choose."""

    F0 = {11: 120.0, 22: 104.0, 33: 99.0, 44: 102.5, 55: 101.0}

    def __init__(self, ref, asr_model, language="en", pyin=(50.0, 300.0)):
        self.language = language

    def measure(self, p, text, wild=None):
        import soundfile as sf
        from rokct_media.qc.meter import tail_db

        x, sr = sf.read(str(p))
        name = Path(p).stem
        seed = next((int(s[4:]) for s in name.split("_") if s.startswith("seed")), 44)
        return {
            "dur": round(len(x) / sr, 3),
            "res": 0.9,
            "err": 0,
            "f0": self.F0.get(seed, 102.0),
            "swings": 0,
            "transcript": text,
            "tail_db": tail_db(x, sr),
        }


@unittest.skipUnless(HAVE_LIBROSA, "librosa not installed")
class EndToEnd(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = Path(self.tmp.name)
        ref = root / "refs" / "voice_a_ref.wav"
        ref.parent.mkdir()
        ref.write_bytes(b"reference")
        sha = hashlib.sha256(ref.read_bytes()).hexdigest()
        self.voices = root / "voices.toml"
        self.voices.write_text(
            f'[voice_a]\nref = "refs/voice_a_ref.wav"\nsha256 = "{sha}"\n'
            'f0_target_hz = 102\nf0_tolerance_hz = 8\naliases = ["tutor_001"]\n'
        )
        self.job = root / "job"
        self.job.mkdir()
        self.patch = mock.patch("rokct_media.qc.worker.Meter", FakeMeter)
        self.patch.start()

    def tearDown(self):
        self.patch.stop()
        self.tmp.cleanup()

    def go(self, **kw):
        return render(
            self.job,
            voices=self.voices,
            isolate=False,
            no_cache=True,
            speech={"engine": "dummy"},
            **kw,
        )

    def test_f0_closest_zero_json(self):
        (self.job / "script.md").write_text(
            "Well done. You checked every step before you moved on.\n"
        )
        (self.job / "voice.txt").write_text("tutor_001\n")
        res = self.go()
        self.assertEqual(res.status, "pass", res.errors)
        self.assertEqual([str(o.path) for o in res.outputs], ["s01.wav"])
        seg = res.segments[0]
        # round 1 renders 11/22/33; 22 (104 Hz) and 33 (99 Hz) are inside 94-110, 104 is closer to 102
        self.assertEqual((seg["seeds"], seg["seeds_tried"]), ([22, 22], [11, 22, 33]))
        result = json.loads((self.job / "out" / "result.json").read_text())
        self.assertEqual(result["status"], "pass")
        self.assertNotIn(
            "Well done", json.dumps(result)
        )  # no script text in result.json
        self.assertEqual(
            result["voices"]["voice_a"]["gate"]["median_f0_hz"], [94.0, 110.0]
        )
        takes = sorted(
            p.name
            for p in (self.job / ".work" / "speech" / "voice_a" / "takes").glob("*.wav")
        )
        self.assertEqual(
            takes, [f"s01_s{k}_seed{s}.wav" for k in (1, 2) for s in (11, 22, 33)]
        )

    @unittest.skipUnless(HAVE_MP3, "no MP3 encoder")
    def test_whole_take_prefer_seeds(self):
        (self.job / "job.json").write_text(
            json.dumps(
                {
                    "cast": {"narrator": {"voice": "voice_a"}},
                    "speech": {"selection": "whole_take"},
                    "segments": [
                        {
                            "id": "open",
                            "role": "narrator",
                            "text": "Looking for funding? Here's one for you.",
                            "asset": "voice_open.wav",
                            "prefer_seeds": [44],
                        }
                    ],
                }
            )
        )
        res = self.go(deliver=["local", "return"])
        self.assertEqual(res.status, "pass", res.errors)
        names = sorted(str(o.path) for o in res.outputs)
        self.assertEqual(
            names,
            [
                "open_seed44.mp3",
                "open_seed44.wav",
                "takes/open_seed44_PASS.mp3",
                "voice_open.wav",
            ],
        )
        out = self.job / "out"
        self.assertEqual(
            (out / "voice_open.wav").read_bytes(),
            (out / "open_seed44.wav").read_bytes(),
        )
        seg = res.segments[0]
        self.assertEqual(
            (seg["seed_order"], seg["chosen_seeds"]), ([44, 11, 22, 33, 55], [44])
        )
        self.assertEqual([str(o.path) for o in res.returned], ["voice_open.wav"])


if __name__ == "__main__":
    unittest.main()
