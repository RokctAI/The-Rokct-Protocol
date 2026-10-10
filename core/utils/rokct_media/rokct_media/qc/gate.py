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

Lifted verbatim from factory voice_batch/qc.py; the numbers are unchanged.
The F0 window is per voice (the caller's voices registry: Voice A
102 +/- 8 Hz, Voice B 196 +/- 12 Hz in today's batches), never per job.

Selection (pick): tier 1 is word-exact, clean tail, F0 inside target +/-
           tolerance and similarity >= 0.83. Among those the median F0
           closest to the target wins, then fewest upward swings, then
           higher similarity. Tier 2 (word-exact and a clean tail only) is
           allowed and the final gate decides. A take whose last 50 ms is
           above -34 dB of its loudest frame (it ends mid-word) never counts,
           even when the ASR still heard the clipped word.
Gate       : the shipped file's median F0 inside the window; similarity >=
           0.88 at 5 s or longer, >= 0.83 under 5 s; word-exact ASR; tail:
           the last 50 ms at or below -34 dB of the loudest 10 ms frame.
"""

from __future__ import annotations

from .meter import TAIL_MAX_DB, TAIL_WIN_S, tail_db, tail_ok  # noqa: F401  (re-exported)

# Voice A defaults, as voice_batch/qc.py has them; a voice's registry entry
# overrides them.
TARGET_F0 = 102.0
F0_TOLERANCE = 8.0
SIM_LONG, SIM_SHORT, LONG_S = 0.88, 0.83, 5.0
TAKE_SIM_MIN = SIM_SHORT


def sim_threshold(duration_s: float) -> float:
    return SIM_LONG if duration_s >= LONG_S else SIM_SHORT


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


def take_rank(m: dict, target: float = TARGET_F0) -> tuple:
    return (abs(m["f0"] - target), m["swings"], -m["res"])


def pick(
    cands: list[dict], target: float = TARGET_F0, tolerance: float = F0_TOLERANCE
) -> tuple[dict | None, int]:
    """(best take, tier): tier 1 strict pass, tier 2 word-exact only, 0 none."""
    lo, hi = f0_range(target, tolerance)
    # A take that ends mid-word never counts, however well the ASR heard it.
    exact = [c for c in cands if c["err"] == 0 and tail_ok(c.get("tail_db", -120.0))]
    strict = [c for c in exact if lo <= c["f0"] <= hi and c["res"] >= TAKE_SIM_MIN]
    rank = lambda c: take_rank(c, target)  # noqa: E731
    if strict:
        return min(strict, key=rank), 1
    if exact:
        return min(exact, key=rank), 2
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


def gate_settings(target: float, tolerance: float) -> dict:
    """The gate numbers as result.json records them."""
    lo, hi = f0_range(target, tolerance)
    return {
        "median_f0_hz": [round(lo, 2), round(hi, 2)],
        "f0_target_hz": target,
        "f0_tolerance_hz": tolerance,
        "similarity_min_ge_5s": SIM_LONG,
        "similarity_min_lt_5s": SIM_SHORT,
        "asr": "word-exact",
        "tail_max_db": TAIL_MAX_DB,
        "tail_window_ms": int(TAIL_WIN_S * 1000),
    }
