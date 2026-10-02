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

"""rokct-media compare: the spec's thresholds, on hand-made manifests."""

import copy
import json
import tempfile
import unittest
from pathlib import Path

from rokct_media.cli import main
from rokct_media.compare import compare, load_expected

H1, H2 = "a" * 64, "b" * 64


def wav(path, sha=H1, dur=3.3347, lufs=-20.2, tp=-3.6, f0=109.68, **extra):
    return {
        "path": path,
        "sha256": sha,
        "metrics": {
            "duration_s": dur,
            "integrated_lufs": lufs,
            "true_peak_dbtp": tp,
            "median_f0_hz": f0,
        },
        **extra,
    }


def manifest(engine, outputs, status="baselined"):
    return {
        "run": {"url": "https://example.invalid/run/1"},
        "engines": [{"engine": engine, "status": status, "outputs": outputs}],
    }


class Compare(unittest.TestCase):
    def base(self):
        return manifest(
            "tutor_voice",
            [wav("final/02.wav"), {"path": "scores.json", "sha256": H2, "metrics": {}}],
        )

    def test_identical_passes(self):
        r = compare(self.base(), self.base())
        self.assertEqual(r["status"], "pass")
        self.assertEqual(r["engines"][0]["identical"], "1/1")

    def test_hash_must_match_for_a_deterministic_render(self):
        cand = manifest("tutor_voice", [wav("final/02.wav", sha=H2)])
        r = compare(self.base(), cand)
        self.assertEqual(r["status"], "fail")
        sha = r["engines"][0]["outputs"][0]["checks"][0]
        self.assertEqual((sha["metric"], sha["result"]), ("sha256", "fail"))

    def test_expected_diff_then_metrics_decide(self):
        exp = [
            {
                "engine": "tutor_voice",
                "path": "final/*.wav",
                "reason": "pinned revision",
                "metrics": [],
            }
        ]
        ok = manifest(
            "tutor_voice",
            [wav("final/02.wav", sha=H2, dur=3.37, lufs=-20.5, tp=-3.4, f0=111.0)],
        )
        self.assertEqual(compare(self.base(), ok, expected=exp)["status"], "pass")
        for k, v in (("dur", 3.39), ("lufs", -20.8), ("tp", -3.2), ("f0", 113.0)):
            bad = manifest("tutor_voice", [wav("final/02.wav", sha=H2, **{k: v})])
            r = compare(self.base(), bad, expected=exp)
            self.assertEqual(r["status"], "fail", k)
        allowed = [dict(exp[0], metrics=["median_f0_hz"])]
        r = compare(
            self.base(),
            manifest("tutor_voice", [wav("final/02.wav", sha=H2, f0=113.0)]),
            expected=allowed,
        )
        self.assertEqual(r["status"], "pass")

    def test_mix_uses_one_percent(self):
        b = manifest("radio_ad", [wav("mix.wav", dur=30.0)])
        exp = [{"engine": "radio_ad", "path": "*", "reason": "r", "metrics": []}]
        self.assertEqual(
            compare(
                b,
                manifest("radio_ad", [wav("mix.wav", sha=H2, dur=30.25)]),
                expected=exp,
            )["status"],
            "pass",
        )
        self.assertEqual(
            compare(
                b,
                manifest("radio_ad", [wav("mix.wav", sha=H2, dur=30.4)]),
                expected=exp,
            )["status"],
            "fail",
        )

    def test_qc_window_similarity_and_asr(self):
        qc = {
            "median_f0_hz": 106.87,
            "f0_window_hz": [94, 110],
            "similarity": 0.8936,
            "duration_s": 3.335,
            "asr_word_errors": 0,
        }
        b = manifest("tutor_voice", [wav("final/02.wav", qc=qc)])
        self.assertEqual(compare(b, copy.deepcopy(b))["status"], "pass")
        for k, v in (
            ("median_f0_hz", 111.0),
            ("similarity", 0.82),
            ("asr_word_errors", 1),
        ):
            c = manifest("tutor_voice", [wav("final/02.wav", qc=dict(qc, **{k: v}))])
            self.assertEqual(compare(b, c)["status"], "fail", k)
        c = manifest("tutor_voice", [wav("final/02.wav", qc=dict(qc, similarity=0.86))])
        self.assertEqual(compare(b, c)["status"], "fail")  # dropped 0.034 > 0.02

    def test_missing_output_and_engine(self):
        r = compare(self.base(), manifest("tutor_voice", []))
        self.assertEqual(
            (r["status"], r["engines"][0]["missing"]), ("fail", ["final/02.wav"])
        )
        r = compare(
            self.base(),
            manifest("tutor_voice", [wav("final/02.wav")]),
            engines=["reel_voices"],
        )
        self.assertEqual(r["status"], "fail")
        self.assertIn("no baseline", r["engines"][0]["error"])

    def test_video_and_stills(self):
        vid = {
            "path": "reel.mp4",
            "sha256": H1,
            "metrics": {
                "duration_s": 12.0,
                "integrated_lufs": -16.0,
                "true_peak_dbtp": -1.6,
                "audio": {"codec": "aac"},
                "video": {"fps": 30.0, "frames": 360},
            },
        }
        img = {
            "path": "card.png",
            "sha256": H1,
            "metrics": {"width": 1080, "height": 1440},
        }
        b = manifest("social_reel", [vid, img])
        self.assertEqual(compare(b, copy.deepcopy(b))["status"], "pass")
        c = copy.deepcopy(b)
        c["engines"][0]["outputs"][0]["metrics"]["video"]["fps"] = 25.0
        exp = [{"engine": "social_reel", "path": "*", "reason": "r", "metrics": []}]
        c["engines"][0]["outputs"][0]["sha256"] = H2
        self.assertEqual(compare(b, c, expected=exp)["status"], "fail")
        c = copy.deepcopy(b)
        c["engines"][0]["outputs"][1].update(
            sha256=H2, metrics={"width": 1080, "height": 1350}
        )
        self.assertEqual(compare(b, c, expected=exp)["status"], "fail")

    def test_cli(self):
        with tempfile.TemporaryDirectory() as d:
            b, c, o = Path(d, "b.json"), Path(d, "c.json"), Path(d, "compare.json")
            b.write_text(json.dumps(self.base()))
            c.write_text(json.dumps(self.base()))
            self.assertEqual(main(["compare", str(b), str(c), "-o", str(o)]), 0)
            self.assertEqual(json.loads(o.read_text())["status"], "pass")
            c.write_text(
                json.dumps(manifest("tutor_voice", [wav("final/02.wav", sha=H2)]))
            )
            self.assertEqual(main(["compare", str(b), str(c)]), 1)
            c.write_text("{}")
            self.assertEqual(main(["compare", str(b), str(c)]), 2)
            t = Path(d, "expected_diffs.toml")
            t.write_text(
                '[[diff]]\nengine = "tutor_voice"\npath = "final/*.wav"\nreason = "pinned"\n'
            )
            self.assertEqual(load_expected(t)[0]["metrics"], [])


if __name__ == "__main__":
    unittest.main()
