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

Kept in step with factory voice_batch/qc.py (Meter, tail_db, tail_ok,
sound_span_s, hiss_db) as of 2026-11-20.

Per take : ASR transcript (word-exact after number/punctuation/spelling
           normalisation, respelled words as wildcards), median F0 (pYIN),
           upward swings (runs of >= 3 voiced frames above the reference's
           90th-percentile F0), speaker-encoder cosine similarity to the
           reference, the tail level, the sound span (dead air), the
           5-11 kHz hiss share and the word timestamps.
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
HISS_BAND_HZ = (5000.0, 11000.0)


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


def sound_span_s(
    x, sr: int = SR, top_db: float = 40.0, frame: int = 512, hop: int = 128
) -> float:
    """Seconds from the first to the last frame within top_db of the loudest
    frame's RMS (librosa.effects.trim's rule, as the stitch trims)."""
    import numpy as np

    x = np.asarray(x, dtype=np.float64)
    if len(x) < frame:
        return round(len(x) / sr, 3)
    n = 1 + (len(x) - frame) // hop
    idx = np.arange(frame)[None, :] + hop * np.arange(n)[:, None]
    rms = np.sqrt(np.mean(x[idx] ** 2, axis=1))
    loud = (
        np.flatnonzero(rms > rms.max() * 10 ** (-top_db / 20)) if rms.max() > 0 else []
    )
    if not len(loud):
        return 0.0
    return round(((loud[-1] - loud[0]) * hop + frame) / sr, 3)


def hiss_db(
    x, sr: int = SR, band: tuple[float, float] = HISS_BAND_HZ, frame_s: float = 0.025
) -> float | None:
    """Median share (dB) of the power in `band` on speech frames (within
    35 dB of the loudest). Broadband hiss under the voice raises it; None
    when the clip is too short or the rate too low to measure."""
    import numpy as np

    x = np.asarray(x, dtype=float)
    x = x.mean(1) if x.ndim > 1 else x
    fr = int(frame_s * sr)
    n = len(x) // fr if fr else 0
    if n < 4 or sr < 2 * band[1]:
        return None
    F = x[: n * fr].reshape(n, fr)
    db = 10 * np.log10((F**2).mean(1) + 1e-12)
    speech = db > db.max() - 35
    P = np.abs(np.fft.rfft(F * np.hanning(fr), axis=1)) ** 2
    fq = np.fft.rfftfreq(fr, 1 / sr)
    hi = P[:, (fq > band[0]) & (fq < band[1])].sum(1)
    tot = P[:, fq > 80].sum(1) + 1e-20
    return round(float(10 * np.log10(np.median(hi[speech] / tot[speech]) + 1e-12)), 2)


class Meter:
    """ASR, speaker similarity, pitch and hiss for one reference voice. Loads
    the ASR and speaker models; never resident with the voice model (the L1
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
        import soundfile as sf

        rx, rsr = sf.read(str(ref))
        self.ref_hiss = hiss_db(rx, rsr)

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
        segs, _ = self.asr.transcribe(
            str(p), beam_size=5, language=self.language, word_timestamps=True
        )
        segs = list(segs)
        tx = " ".join(s.text.strip() for s in segs)
        words = [
            {"w": w.word, "start": w.start, "end": w.end}
            for s in segs
            for w in (getattr(s, "words", None) or [])
        ]
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
            "span": sound_span_s(x, sr),
            "n_words": len(text.split()),
            "hiss": hiss_db(x, sr),
            "words": words,
        }
