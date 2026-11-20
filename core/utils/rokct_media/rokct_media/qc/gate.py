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

"""Take selection and the final gate.

Kept in step with factory voice_batch/qc.py as of 2026-11-20; the numbers
are unchanged.
The F0 window is per voice (the caller's voices registry: Voice A
102 +/- 8 Hz, Voice B 196 +/- 12 Hz in today's batches), never per job.

Selection (pick): tier 1 is word-exact, clean tail, F0 inside target +/-
           tolerance and similarity >= 0.83. Among those the median F0
           closest to the target wins, then fewest upward swings, then
           higher similarity. Tier 2 (word-exact and a clean tail only) is
           allowed and the final gate decides. A take whose last 50 ms is
           above -34 dB of its loudest frame (it ends mid-word) never counts,
           even when the ASR still heard the clipped word. Nor does one
           whose sound span runs past 1.5 s + 0.75 s per word (dead air the
           ASR skipped over), nor a hissy take ("open mic": its 5-11 kHz
           share more than 12 dB above the reference's). With near_miss N
           (lessons, last seed round only), a sentence with no word-exact
           take may use one heard at most N words off that passes every
           other check (tier 3), flagged for a human listen.
Gate       : the shipped file's median F0 inside the window; similarity >=
           0.88 at 5 s or longer, >= 0.83 under 5 s; word-exact ASR; tail:
           the last 50 ms at or below -34 dB of the loudest 10 ms frame.
"""

from __future__ import annotations

from .meter import (
    TAIL_MAX_DB,
    TAIL_WIN_S,
    tail_db,
    tail_ok,
)  # noqa: F401  (re-exported)

# Voice A defaults, as voice_batch/qc.py has them; a voice's registry entry
# overrides them.
TARGET_F0 = 102.0
F0_TOLERANCE = 8.0
SIM_LONG, SIM_SHORT, LONG_S = 0.88, 0.83, 5.0
TAKE_SIM_MIN = SIM_SHORT
HISS_MARGIN_DB = 12.0
# Dead air: a take's sound span (trimmed at -40 dB, as the stitch trims) may
# last at most SPAN_BASE_S + SPAN_PER_WORD_S per word of its sentence. The
# model sometimes generates seconds of loud non-speech before a sentence; the
# ASR hears the words after it and passes the take. 0.75 s/word is ~80 wpm,
# half the slowest pace any voice targets, so a slow real read never trips it.
SPAN_BASE_S, SPAN_PER_WORD_S = 1.5, 0.75


def sim_threshold(
    duration_s: float, short: float = SIM_SHORT, long: float = SIM_LONG
) -> float:
    return long if duration_s >= LONG_S else short


def f0_range(
    target: float = TARGET_F0, tolerance: float = F0_TOLERANCE
) -> tuple[float, float]:
    return (target - tolerance, target + tolerance)


def pyin_bounds(
    target: float = TARGET_F0, tolerance: float = F0_TOLERANCE
) -> tuple[float, float]:
    """pYIN search range: 50-300 Hz for Voice A, widened for a voice whose
    gate reaches outside it (e.g. a higher voice)."""
    lo, hi = f0_range(target, tolerance)
    return min(50.0, round(lo * 0.6)), max(300.0, hi * 2)


def hiss_ok(c: dict, ref_hiss: float | None, margin: float = HISS_MARGIN_DB) -> bool:
    """A take's hiss is within `margin` dB of the reference's; takes measured
    before hiss was recorded, or without a reference figure, count as fine."""
    h = c.get("hiss")
    return h is None or ref_hiss is None or h <= ref_hiss + margin


def span_ok(c: dict) -> bool:
    """A take's sound span fits its word count (no dead air); takes measured
    before the span was recorded count as fitting."""
    span, n = c.get("span"), c.get("n_words")
    return span is None or not n or span <= SPAN_BASE_S + SPAN_PER_WORD_S * n


def take_rank(m: dict, target: float = TARGET_F0) -> tuple:
    return (abs(m["f0"] - target), m["swings"], -m["res"])


def pick(
    cands: list[dict],
    target: float = TARGET_F0,
    tolerance: float = F0_TOLERANCE,
    sim_min: float = TAKE_SIM_MIN,
    ref_hiss: float | None = None,
    near_miss: int = 0,
) -> tuple[dict | None, int]:
    """(best take, tier) — tier 1 strict pass, tier 2 word-exact only, 0 none.
    With near_miss > 0 and no word-exact take, tier 3: a take the ASR heard
    at most near_miss words off that passes every other take check. It is
    flagged for a human listen (the ASR mishears subject words such as
    "formulae" on takes that sound right)."""
    lo, hi = f0_range(target, tolerance)
    # A take that ends mid-word never counts, however well the ASR heard it.
    # Nor does one padded with seconds of non-speech the ASR skipped over.
    clean = [
        c
        for c in cands
        if tail_ok(c.get("tail_db", -120.0)) and span_ok(c) and hiss_ok(c, ref_hiss)
    ]
    exact = [c for c in clean if c["err"] == 0]
    strict = [c for c in exact if lo <= c["f0"] <= hi and c["res"] >= sim_min]
    rank = lambda c: take_rank(c, target)  # noqa: E731
    if strict:
        return min(strict, key=rank), 1
    if exact:
        return min(exact, key=rank), 2
    near = [
        c
        for c in clean
        if 0 < c["err"] <= near_miss and lo <= c["f0"] <= hi and c["res"] >= sim_min
    ]
    if near:
        return min(near, key=lambda c: (c["err"], *rank(c))), 3
    return None, 0


def final_gate(
    m: dict,
    duration_s: float,
    target: float = TARGET_F0,
    tolerance: float = F0_TOLERANCE,
) -> tuple[dict, float]:
    """The gate on a shipped file from its measurement `m` (Meter.measure):
    ({"f0", "similarity", "asr", "tail"}: bool, similarity threshold used)."""
    lo, hi = f0_range(target, tolerance)
    thr = sim_threshold(duration_s)
    gate = {
        "f0": lo <= m["f0"] <= hi,
        "similarity": m["res"] >= thr,
        "asr": m["err"] == 0,
        "tail": tail_ok(m["tail_db"]),
    }
    return gate, thr


def gate_settings(
    target: float,
    tolerance: float,
    sim_short: float | None = None,
    sim_long: float | None = None,
) -> dict:
    """The gate numbers as result.json records them."""
    lo, hi = f0_range(target, tolerance)
    return {
        "median_f0_hz": [round(lo, 2), round(hi, 2)],
        "f0_target_hz": target,
        "f0_tolerance_hz": tolerance,
        "similarity_min_ge_5s": sim_long or SIM_LONG,
        "similarity_min_lt_5s": sim_short or SIM_SHORT,
        "asr": "word-exact",
        "tail_max_db": TAIL_MAX_DB,
        "tail_window_ms": int(TAIL_WIN_S * 1000),
    }
