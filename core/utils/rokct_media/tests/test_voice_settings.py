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

"""Per-voice render and gate settings (factory lesson_voices.json): diffusion
steps, similarity minimums, pace, and the near-miss allowance on the last
seed round only. Voice A's approved settings must not move."""

import unittest
from pathlib import Path

from rokct_media.levels.l1_speech import gate_argv, steps_for
from rokct_media.manifest.load import DEFAULT_SPEECH
from rokct_media.voices.registry import VoiceError, parse

SHA = "0" * 64


def voice(**extra):
    e = {"ref": "r.wav", "sha256": SHA, "f0_target_hz": 102, "f0_tolerance_hz": 8}
    return parse({"voice_a": {**e, **extra}}, Path("."))["voice_a"]


def argv_dict(argv):
    return dict(zip(argv[::2], argv[1::2]))


class VoiceSettings(unittest.TestCase):
    def test_voice_a_defaults_unchanged(self):
        v = voice()
        sp = dict(DEFAULT_SPEECH)
        self.assertEqual((sp["cfg"], steps_for(sp, v)), (1.3, 10))
        self.assertEqual(
            sp["model_revision"], "c00898d257e6b46004e3e2866a47534085fb685a"
        )
        a = argv_dict(gate_argv(v, sp, last_round=True))
        self.assertEqual(
            a,
            {
                "--f0-target": "102.0",
                "--f0-tolerance": "8.0",
                "--sim-short": "0.83",
                "--sim-long": "0.88",
                "--pace-wpm": "149.0",
                "--pace-tolerance": "15.0",
                "--near-miss-words": "0",
            },
        )

    def test_per_voice_steps_and_job_override(self):
        v = voice(ddpm_steps=14)
        self.assertEqual(steps_for(dict(DEFAULT_SPEECH), v), 14)
        self.assertEqual(steps_for({**DEFAULT_SPEECH, "steps": 10}, v), 10)
        self.assertEqual(v.summary()["ddpm_steps"], 14)

    def test_per_voice_gate(self):
        v = voice(similarity_min_lt_5s=0.8, similarity_min_ge_5s=0.85, pace_wpm=135)
        a = argv_dict(gate_argv(v, dict(DEFAULT_SPEECH), last_round=False))
        self.assertEqual(
            (a["--sim-short"], a["--sim-long"], a["--pace-wpm"]),
            ("0.8", "0.85", "135.0"),
        )

    def test_near_miss_last_round_only(self):
        sp = {**DEFAULT_SPEECH, "near_miss_words": 1}
        self.assertEqual(
            argv_dict(gate_argv(voice(), sp, False))["--near-miss-words"], "0"
        )
        self.assertEqual(
            argv_dict(gate_argv(voice(), sp, True))["--near-miss-words"], "1"
        )

    def test_bad_values_refused(self):
        for bad in (
            {"ddpm_steps": 0},
            {"ddpm_steps": 1.5},
            {"ddpm_steps": True},
            {"pace_wpm": -1},
        ):
            with self.assertRaises(VoiceError):
                voice(**bad)


if __name__ == "__main__":
    unittest.main()
