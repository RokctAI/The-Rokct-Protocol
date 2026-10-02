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

"""Per-take and per-file measurements for the QC gate.

Lifted verbatim from factory voice_batch/qc.py (Meter, tail_db, tail_ok).

Per take : ASR transcript (word-exact after number/punctuation/spelling
           normalisation, respelled words as wildcards), median F0 (pYIN),
           upward swings (runs of >= 3 voiced frames above the reference's
           90th-percentile F0), speaker-encoder cosine similarity to the
           reference, and the tail level.
"""

from __future__ import annotations

import os
from pathlib import Path

from ..text.pronounce import word_errors_wild

SR = 24_000
# Tail check: the last TAIL_WIN_S of a take or line, relative to its loudest
# 10 ms frame, must be below TAIL_MAX_DB. Speech still sounding there means
# the model stopped mid-word (the ASR often still hears the clipped word).
# Tuned on tutor_001's Voice A lines (25 sentence ends): clean ends measure
# -37.8 dB or lower, clipped ends -30.0 dB or higher. The 50 ms window is
# just over the stitch's 40 ms pad.
TAIL_WIN_S, TAIL_MAX_DB = 0.05, -34.0


def tail_db(x, sr: int = SR, win_s: float = TAIL_WIN_S) -> float:
    """dB of the last `win_s` of `x` relative to its loudest 10 ms frame."""
    import numpy as np

    x = np.asarray(x, dtype=np.float64).reshape(-1)
    n = max(1, int(0.01 * sr))
    frames = x[: len(x) // n * n].reshape(-1, n) if len(x) >= n else x.reshape(1, -1)
    ref = float(np.sqrt(np.mean(frames**2, axis=1)).max())
    if ref <= 0.0:
        return -120.0
    tail = x[-max(1, int(win_s * sr)) :]
    return round(
        max(
            -120.0,
            20 * float(np.log10(max(float(np.sqrt(np.mean(tail**2))), 1e-12) / ref)),
        ),
        2,
    )


def tail_ok(db: float) -> bool:
    return db <= TAIL_MAX_DB


class Meter:
    """ASR, speaker similarity and pitch for one reference voice. Loads the
    ASR and speaker models; never resident with the voice model (the L1
    level runs it in its own process)."""

    def __init__(
        self,
        ref: Path,
        asr_model: str,
        language: str = "en",
        pyin: tuple[float, float] = (50.0, 300.0),
    ):
        self.language = language
        self.pyin_bounds = pyin
        import librosa  # noqa: F401
        from faster_whisper import WhisperModel
        from resemblyzer import VoiceEncoder, preprocess_wav

        self._pre = preprocess_wav
        self.enc = VoiceEncoder("cpu", verbose=False)
        self.asr = WhisperModel(
            asr_model,
            device="cpu",
            compute_type="int8",
            download_root=os.environ.get("ASR_DOWNLOAD_ROOT") or None,
        )
        w = self.r16(ref)
        self.R = self.enc.embed_utterance(preprocess_wav(w))
        import numpy as np

        f, v = self._pyin(w)
        self.hi = float(np.percentile(f[v], 90))

    @staticmethod
    def r16(p):
        import librosa
        import soundfile as sf

        w, sr = sf.read(str(p))
        w = w.mean(1) if w.ndim > 1 else w
        return librosa.resample(w, orig_sr=sr, target_sr=16000)

    def _pyin(self, w):
        import librosa

        fmin, fmax = self.pyin_bounds
        f, v, _ = librosa.pyin(
            w, fmin=fmin, fmax=fmax, sr=16000, frame_length=1024, hop_length=256
        )
        return f, v

    def measure(self, p, text: str, wild: list | None = None) -> dict:
        import numpy as np

        w = self.r16(p)
        segs, _ = self.asr.transcribe(str(p), beam_size=5, language=self.language)
        tx = " ".join(s.text.strip() for s in segs)
        f, v = self._pyin(w)
        fv = f[v]
        hi = np.where(v, f, 0) > self.hi
        swings, run = 0, 0
        for h in list(hi) + [False]:
            if h:
                run += 1
            else:
                swings += run >= 3
                run = 0
        import soundfile as sf

        x, sr = sf.read(str(p))
        x = x.mean(1) if x.ndim > 1 else x
        e = self.enc.embed_utterance(self._pre(w))
        res = float(np.dot(e, self.R) / np.linalg.norm(e) / np.linalg.norm(self.R))
        return {
            "dur": round(len(w) / 16000, 3),
            "res": round(res, 4),
            "err": word_errors_wild(text, tx, wild),
            "f0": round(float(np.median(fv)), 2) if len(fv) else 0.0,
            "swings": int(swings),
            "transcript": tx,
            "tail_db": tail_db(x, sr),
        }
