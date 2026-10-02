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

"""The render worker with the dummy engine: seeded, deterministic takes in
the clip_wav format, skip-if-exists and the take cache. Model-free."""

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

import numpy as np
import soundfile as sf

from rokct_media.audio.dsp import normalise
from rokct_media.speech import takes


class Worker(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.d = Path(self.tmp.name)
        self.ref = self.d / "ref.wav"
        self.ref.write_bytes(b"ref")
        self.env = mock.patch.dict(
            os.environ, {"ROKCT_MEDIA_CACHE": str(self.d / "cache")}
        )
        self.env.start()

    def tearDown(self):
        self.env.stop()
        self.tmp.cleanup()

    def jobs(self, sub: str, seeds=(11, 22)) -> Path:
        j = [
            {
                "key": f"s01#{k}",
                "text": t,
                "seed": s,
                "out": str(self.d / sub / f"s01_s{k}_seed{s}.wav"),
            }
            for k, t in enumerate(["Hello there.", "This is a take"], 1)
            for s in seeds
        ]
        p = self.d / f"{sub}.json"
        p.write_text(json.dumps(j))
        return p

    def run_worker(self, jobs: Path, *extra) -> int:
        return takes.main(
            ["--jobs", str(jobs), "--ref", str(self.ref), "--engine", "dummy", *extra]
        )

    def test_deterministic_clip_wav(self):
        self.assertEqual(self.run_worker(self.jobs("a"), "--no-cache"), 0)
        self.assertEqual(self.run_worker(self.jobs("b"), "--no-cache"), 0)
        a, b = (
            sorted((self.d / "a").glob("*.wav")),
            sorted((self.d / "b").glob("*.wav")),
        )
        self.assertEqual(len(a), 4)
        for x, y in zip(a, b):
            self.assertEqual(takes.sha256_file(x), takes.sha256_file(y))
        info = sf.info(str(a[0]))
        self.assertEqual(
            (info.samplerate, info.channels, info.subtype), (24000, 1, "PCM_16")
        )
        x, _ = sf.read(str(a[0]))
        self.assertAlmostEqual(20 * np.log10(np.sqrt(np.mean(x**2))), -20.0, delta=0.05)
        self.assertNotEqual(
            takes.sha256_file(a[0]), takes.sha256_file(a[1])
        )  # seeds differ

    def test_skip_existing_and_cache(self):
        self.run_worker(self.jobs("a"))
        first = {p.name: takes.sha256_file(p) for p in (self.d / "a").glob("*.wav")}
        self.assertEqual(len(list((self.d / "cache" / "takes").rglob("*.wav"))), 4)
        with mock.patch(
            "rokct_media.models.dummy.DummyEngine.render",
            side_effect=AssertionError("re-rendered"),
        ):
            self.assertEqual(self.run_worker(self.jobs("a")), 0)  # every file exists
            self.assertEqual(self.run_worker(self.jobs("c")), 0)  # every take is cached
        self.assertEqual(
            {p.name: takes.sha256_file(p) for p in (self.d / "c").glob("*.wav")}, first
        )

    def test_cache_key(self):
        ident = {"engine": "voice_model", "revision": "c" * 40, "cfg": 1.3, "steps": 10}
        k = takes.cache_key(ident, "r" * 64, "Hello. ...", 11)
        self.assertEqual(k, takes.cache_key(dict(ident), "r" * 64, "Hello. ...", 11))
        for other in (
            takes.cache_key(dict(ident, revision="d" * 40), "r" * 64, "Hello. ...", 11),
            takes.cache_key(ident, "s" * 64, "Hello. ...", 11),
            takes.cache_key(ident, "r" * 64, "Hello. ...", 22),
        ):
            self.assertNotEqual(k, other)

    def test_runs_as_a_child_process(self):
        p = subprocess.run(
            [
                sys.executable,
                "-m",
                "rokct_media.speech.takes",
                "--jobs",
                str(self.jobs("p", (11,))),
                "--ref",
                str(self.ref),
                "--engine",
                "dummy",
                "--no-cache",
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(p.returncode, 0, p.stderr)
        self.assertIn("2 take(s) to render", p.stdout)
        self.assertNotIn("Hello", p.stdout)  # logs ids, never the text

    def test_seed_rounds(self):
        self.assertEqual(takes.seed_rounds([44]), [[44], [11, 22, 33], [55]])
        self.assertEqual(takes.seed_rounds([33, 44]), [[33], [44], [11, 22], [55]])
        self.assertEqual(takes.seed_rounds(), [[11, 22, 33], [44], [55]])
        self.assertEqual(
            takes.safe("tutor_001/acknowledgements/02#1"),
            "tutor_001_acknowledgements_02_s1",
        )

    def test_normalise(self):
        self.assertEqual(normalise(np.zeros(10)).tolist(), [0.0] * 10)
        y = normalise(np.array([1.0, -1.0, 0.0, 0.0] * 100))
        self.assertLessEqual(float(np.max(np.abs(y))), 0.99 + 1e-6)


class Pin(unittest.TestCase):
    def test_model_pin(self):
        from rokct_media.models.base import EngineError
        from rokct_media.models.voice_model import (
            REVISION,
            VoiceModelEngine,
            resolve_model_path,
        )

        self.assertEqual(REVISION, "c00898d257e6b46004e3e2866a47534085fb685a")
        for bad in ("main", "v1", "c00898d"):
            with self.assertRaises(EngineError):
                VoiceModelEngine(revision=bad)
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaisesRegex(
                EngineError, "not a snapshot of the pinned revision"
            ):
                resolve_model_path(d)
            snap = Path(d, REVISION)
            snap.mkdir()
            self.assertEqual(resolve_model_path(snap), str(snap))
        ident = VoiceModelEngine().identity()
        self.assertEqual(
            (ident["cfg"], ident["steps"], ident["fork_commit"][:8], ident["prompt"]),
            (1.3, 10, "952326dd", "Speaker 1: <sentence>"),
        )


if __name__ == "__main__":
    unittest.main()
