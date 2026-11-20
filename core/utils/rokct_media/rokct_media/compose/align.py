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

"""Speech recognition helpers (faster-whisper).

Two jobs:

* split_joint(): a joint dialogue render comes back as one clip. Recognise
  it with word timestamps, align the words to the script, and cut the clip
  at the quietest point between consecutive lines. That recovers per-line
  audio, so pauses, per-line tempo, SFX anchors and per-line timings work in
  dialogue mode too.
* transcribe(): plain transcript + word-error rate against the script, used
  by the report to confirm the words came out right.
"""
from __future__ import annotations

import difflib
import re

import numpy as np

_MODELS: dict[str, object] = {}
DEFAULT_ASR = "base.en"


def _model(name: str):
    if name not in _MODELS:
        from faster_whisper import WhisperModel
        _MODELS[name] = WhisperModel(name, device="cpu", compute_type="int8")
    return _MODELS[name]


_NUM = {"0": "zero", "1": "one", "2": "two", "3": "three", "4": "four", "5": "five",
        "6": "six", "7": "seven", "8": "eight", "9": "nine", "10": "ten"}


def norm_words(text: str) -> list[str]:
    text = text.lower().replace("-", " ")
    words = re.findall(r"[a-z0-9']+", text)
    return [_NUM.get(w, w).strip("'") for w in words if w.strip("'")]


def recognise(audio: np.ndarray, sr: int, model: str = DEFAULT_ASR, prompt: str | None = None):
    """Return (text, [(word, start, end)]) for 16 kHz-resampled audio."""
    from .dsp import resample

    a16 = resample(audio, sr, 16000)
    segments, _ = _model(model).transcribe(a16, language="en", beam_size=5,
                                           word_timestamps=True, initial_prompt=prompt,
                                           vad_filter=False, condition_on_previous_text=False)
    words, texts = [], []
    for seg in segments:
        texts.append(seg.text.strip())
        for w in seg.words or []:
            words.append((w.word, float(w.start), float(w.end)))
    return " ".join(texts), words


def wer(ref: str, hyp: str) -> float:
    r, h = norm_words(ref), norm_words(hyp)
    if not r:
        return 0.0
    # Levenshtein on word lists.
    d = list(range(len(h) + 1))
    for i in range(1, len(r) + 1):
        prev, d[0] = d[0], i
        for j in range(1, len(h) + 1):
            cur = d[j]
            d[j] = min(d[j] + 1, d[j - 1] + 1, prev + (r[i - 1] != h[j - 1]))
            prev = cur
    return d[len(h)] / len(r)


def transcribe(audio: np.ndarray, sr: int, reference_text: str, model: str = DEFAULT_ASR) -> dict:
    text, _ = recognise(audio, sr, model)
    return {"asr_model": model, "transcript": text, "wer": round(wer(reference_text, text), 3)}


def split_joint(audio: np.ndarray, sr: int, lines: list[str], model: str = DEFAULT_ASR) -> tuple[list[np.ndarray], dict]:
    """Cut a joint render into one clip per script line.

    Returns (clips, info). Raises RuntimeError if the words cannot be
    aligned well enough to trust the cuts.
    """
    _, words = recognise(audio, sr, model)
    hyp, hyp_t = [], []
    for w, s, e in words:
        for tok in norm_words(w):
            hyp.append(tok)
            hyp_t.append((s, e))
    ref, ref_line = [], []
    for i, line in enumerate(lines):
        for tok in norm_words(line):
            ref.append(tok)
            ref_line.append(i)
    sm = difflib.SequenceMatcher(None, ref, hyp, autojunk=False)
    ref_to_hyp = {}
    exact = 0
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            exact += i2 - i1
        if tag in ("equal", "replace") and j2 > j1:
            # 'replace' = misrecognised words (names, slang: "Hau" -> "How").
            # They still mark where the line is, so map them proportionally.
            for k in range(i1, i2):
                ref_to_hyp[k] = j1 + (k - i1) * (j2 - j1) // (i2 - i1)
    ratio = exact / max(1, len(ref))
    info = {"asr_model": model, "word_match": round(ratio, 3)}
    if ratio < 0.6:
        raise RuntimeError(f"joint split: only {ratio:.0%} of script words recognised")

    starts, ends = [], []
    for i in range(len(lines)):
        idx = [ref_to_hyp[k] for k, li in enumerate(ref_line) if li == i and k in ref_to_hyp]
        if not idx:
            raise RuntimeError(f"joint split: no words of line {i} recognised")
        starts.append(hyp_t[min(idx)][0])
        ends.append(hyp_t[max(idx)][1])

    # Cut between line i's last word and line i+1's first word, at the
    # quietest 10 ms frame. Whisper word edges are +-100 ms, so search a
    # little outside the gap too.
    hop = int(0.01 * sr)
    frames = audio[: audio.size // hop * hop].reshape(-1, hop)
    energy = np.sqrt(np.mean(frames ** 2, axis=1) + 1e-12)
    cuts = [0]
    for i in range(len(lines) - 1):
        lo = max(ends[i] - 0.08, starts[i] + 0.05)
        hi = min(starts[i + 1] + 0.08, ends[i + 1] - 0.05)
        if hi <= lo:
            lo, hi = min(ends[i], starts[i + 1]) - 0.1, max(ends[i], starts[i + 1]) + 0.1
        f0, f1 = int(lo * sr / hop), max(int(lo * sr / hop) + 1, int(hi * sr / hop))
        f1 = min(f1, energy.size)
        f0 = min(max(f0, cuts[-1] // hop + 1), f1 - 1)
        best = f0 + int(np.argmin(energy[f0:f1])) if f1 > f0 else f0
        cuts.append(best * hop)
    cuts.append(audio.size)
    clips = [audio[cuts[i]:cuts[i + 1]] for i in range(len(lines))]
    info["cuts_s"] = [round(c / sr, 3) for c in cuts[1:-1]]
    return clips, info
