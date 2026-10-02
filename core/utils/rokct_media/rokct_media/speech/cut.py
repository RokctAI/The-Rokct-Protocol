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

"""keep_through: cut a passing take after one word, then gate the cut.

Lifted verbatim from factory PR #196 radio_ads/reel_voice.py. The word end
comes from ASR word timestamps; the cut lands in the first quiet stretch
(80 ms under -42 dB, searched within 0.6 s), keeps 40 ms of it and fades
over 12 ms. The cut is gated again: word-exact against the text through
that word, a clean tail and similarity >= 0.83. A cut that fails fails the
take.
"""

from __future__ import annotations

import hashlib
from pathlib import Path

from ..qc import gate as qc_gate
from ..qc.meter import tail_ok
from ..text import norm as textnorm
from ..text import pronounce as pronunciations
from .stitch import FADE_S, PAD_S


def sha256_file(p: Path) -> str:
    return hashlib.sha256(Path(p).read_bytes()).hexdigest()


def text_through(text: str, word: str) -> str | None:
    """`text` up to and including the first occurrence of `word`
    (case and punctuation ignored), or None when it is not there."""
    words = text.split()
    for i, w in enumerate(words):
        if textnorm.norm_words(w) == textnorm.norm_words(word):
            return " ".join(words[: i + 1])
    return None


def cut_after(
    x,
    sr: int,
    word_end_s: float,
    quiet_db: float = -42.0,
    quiet_s: float = 0.08,
    search_s: float = 0.6,
):
    """`x` cut in the first quiet stretch (`quiet_s` below `quiet_db` of the
    loudest 10 ms frame) that starts after `word_end_s`, keeping 40 ms of it
    and fading out over the stitch's 12 ms. None when no quiet stretch starts
    within `search_s` (the word runs straight into the next one)."""
    import numpy as np

    x = np.asarray(x, dtype=np.float64).reshape(-1)
    n = max(1, int(0.01 * sr))
    frames = x[: len(x) // n * n].reshape(-1, n)
    rms = np.sqrt(np.mean(frames**2, axis=1))
    db = 20 * np.log10(np.maximum(rms, 1e-12) / max(float(rms.max()), 1e-12))
    need = max(1, int(round(quiet_s / 0.01)))
    first, last = (
        int(word_end_s / 0.01),
        min(len(db) - need, int((word_end_s + search_s) / 0.01)),
    )
    for i in range(max(0, first), last + 1):
        if (db[i : i + need] < quiet_db).all():
            y = x[: min(len(x), (i + int(PAD_S / 0.01)) * n)].copy()
            fade = int(FADE_S * sr)
            y[-fade:] *= np.linspace(1, 0, fade) ** 2
            return y
    return None


def word_end(words: list, want: str, rest: str, wild: list | None) -> float | None:
    """End time of the transcript word that closes `want` when the words
    after it match `rest`: how keep_through finds a respelled word, whose
    transcript spelling is not the display word ("Rock it" for Rocket)."""
    end = None
    for k in range(1, len(words) + 1):
        head = " ".join(w.word for w in words[:k])
        tail = " ".join(w.word for w in words[k:])
        if (
            pronunciations.word_errors_wild(want, head, wild) == 0
            and pronunciations.word_errors_wild(rest, tail, wild) == 0
        ):
            end = words[k - 1].end
    return end


def keep_through(meter, dst: Path, t: dict) -> dict:
    """Cut a passing take after its keep_through word (ASR word timestamps,
    then the next quiet stretch) and gate the cut: word-exact against the
    text through that word, a clean tail and similarity. A cut that fails
    fails the take."""
    import soundfile as sf

    want = text_through(t["text"], t["keep_through"])
    segs, _ = meter.asr.transcribe(
        str(dst), beam_size=5, language=meter.language, word_timestamps=True
    )
    words = [w for s in segs for w in (s.words or [])]
    ends = [
        w.end
        for w in words
        if textnorm.norm_words(w.word) == textnorm.norm_words(t["keep_through"])
    ]
    if not ends:
        ends = [
            e
            for e in [word_end(words, want, t["text"][len(want) :], t.get("wild"))]
            if e is not None
        ]
    x, sr = sf.read(str(dst))
    y = cut_after(x, sr, ends[0]) if ends else None
    if y is None:
        return {
            "status": "fail",
            "reason": f"could not cut after {t['keep_through']!r}",
        }
    cut = dst.with_name(dst.stem + "_cut.wav")
    sf.write(str(cut), y, sr, subtype="PCM_16")
    m = meter.measure(cut, want, t.get("wild"))
    gate = {
        "similarity": m["res"] >= qc_gate.SIM_SHORT,
        "asr": m["err"] == 0,
        "tail": tail_ok(m["tail_db"]),
    }
    out = {
        "cut": {
            "text": want,
            "gate": gate,
            "duration_s": m["dur"],
            "median_f0_hz": m["f0"],
            "similarity": m["res"],
            "asr_word_errors": m["err"],
            "asr_transcript": m["transcript"],
            "tail_db": m["tail_db"],
            "sha256": sha256_file(cut),
        },
        "cut_path": str(cut),
    }
    if not all(gate.values()):
        out.update({"status": "fail", "reason": "the cut fails the gate"})
    return out
