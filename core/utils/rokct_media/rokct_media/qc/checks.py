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


"""Clip checks on a finished, normalised clip, word timings and pace.

Kept in step with factory voice_batch/qc.py (clip_checks, timings, pace)
as of 2026-11-20; the numbers are unchanged.

Clip checks: integrated level within +/-2.0 dB of the -20 dBFS normalise
target; >= 180 ms silence before the first audible sample; no clipping
(peak below -0.3 dBFS, or fewer than 3 consecutive full-scale samples);
first 50 ms RMS below -60 dBFS and the first onset rising over >= 4 ms.
Pace (report-only until tuned on real renders): wpm against the voice's
target +/- tolerance (default 149 +/- 15) is recorded with an over/under
flag but never fails a clip.
Timings: ASR word timestamps of the final file ({text, duration_s, wpm,
words, gaps >= 80 ms}).
"""

from __future__ import annotations

from ..speech.stitch import LEAD_TOP_DB, SR

PACE_WPM, PACE_TOL_WPM = 149.0, 15.0  # default when the voice spec has no `pace`
# Loudness: gated integrated level (silence excluded) vs the normaliser's
# whole-file RMS target. On tutor_001's accepted renders after lead_in +
# normalise the gated level reads 0.4-1.52 dB above -20 (more silence, more
# bias), so 1.5 dB rejected a good clip; 2.0 dB clears them with margin and
# still catches a normaliser that backed off or a mis-scaled file.
NORM_TARGET_DB, LOUDNESS_TOL_DB = -20.0, 2.0
LEAD_MIN_S = 0.18
CLIP_PEAK_DBFS, CLIP_FULL_SCALE, CLIP_RUN_MAX = -0.3, 0.999, 3
HOT_WIN_S, HOT_FLOOR_DBFS = 0.05, -60.0
# First onset: from the first sample above -40 dB of the peak to 90 % of the
# loudest sample in the 50 ms after it must take >= 4 ms (the stitch's 12 ms
# fade and the lead-in's 10 ms fade both give ~9-12 ms; a hard edge gives ~0).
# 5 ms rejected tutor_001 greetings/05 at 4.96 ms in every seed round with
# silent head (-120 dBFS): a faded onset whose voice peaks early, not an edge.
ONSET_RISE_MIN_S, ONSET_WIN_S, ONSET_REACH = 0.004, 0.05, 0.9
GAP_MIN_S = 0.08


def _db(v: float) -> float:
    import math

    return max(-120.0, 20 * math.log10(max(v, 1e-12)))


def lead_s(x, sr: int = SR) -> float:
    """Seconds before the first sample above -LEAD_TOP_DB of the peak."""
    import numpy as np

    x = np.abs(np.asarray(x, dtype=np.float64).reshape(-1))
    peak = float(x.max()) if x.size else 0.0
    if peak <= 0.0:
        return len(x) / sr
    return int(np.argmax(x > peak * 10 ** (-LEAD_TOP_DB / 20))) / sr


def integrated_db(x, sr: int = SR) -> float:
    """Gated integrated level in dBFS RMS: 400 ms blocks (100 ms hop), blocks
    under -70 dBFS dropped, then blocks 10 dB under their mean dropped."""
    import numpy as np

    x = np.asarray(x, dtype=np.float64).reshape(-1)
    n, hop = int(0.4 * sr), int(0.1 * sr)
    if len(x) < n:
        ms = np.array([np.mean(x**2)]) if x.size else np.array([0.0])
    else:
        ms = np.array(
            [np.mean(x[i : i + n] ** 2) for i in range(0, len(x) - n + 1, hop)]
        )
    ms = ms[ms > 10 ** (-70 / 10)]
    if not ms.size:
        return -120.0
    ms = ms[ms > np.mean(ms) * 10 ** (-10 / 10)]
    return round(10 * float(np.log10(np.mean(ms))), 2)


def longest_full_scale_run(x, full: float = CLIP_FULL_SCALE) -> int:
    import numpy as np

    hot = np.abs(np.asarray(x, dtype=np.float64).reshape(-1)) >= full
    best = run = 0
    for h in hot:
        run = run + 1 if h else 0
        best = max(best, run)
    return best


def onset_rise_s(x, sr: int = SR) -> float:
    """Seconds from the first sample above -40 dB of the peak to the first
    reaching ONSET_REACH of the loudest sample in the ONSET_WIN_S after it
    (one sample = a hard, clicky onset)."""
    import numpy as np

    a = np.abs(np.asarray(x, dtype=np.float64).reshape(-1))
    peak = float(a.max()) if a.size else 0.0
    if peak <= 0.0:
        return 0.0
    start = int(np.argmax(a > peak * 10 ** (-LEAD_TOP_DB / 20)))
    seg = a[start : start + max(1, int(ONSET_WIN_S * sr))]
    return int(np.argmax(seg >= ONSET_REACH * float(seg.max()))) / sr


def pace_spec(spec: dict | None) -> tuple[float, float]:
    """(target wpm, tolerance) from a voice spec's `pace` (a number or
    {wpm|target_wpm, tolerance_wpm|tolerance}); defaults when absent."""
    p = (spec or {}).get("pace")
    if isinstance(p, (int, float)):
        return float(p), PACE_TOL_WPM
    if isinstance(p, dict):
        t = p.get("wpm", p.get("target_wpm", PACE_WPM))
        tol = p.get("tolerance_wpm", p.get("tolerance", PACE_TOL_WPM))
        return float(t), float(tol)
    return PACE_WPM, PACE_TOL_WPM


def clip_checks(
    x,
    sr: int = SR,
    wpm: float | None = None,
    pace: tuple[float, float] = (PACE_WPM, PACE_TOL_WPM),
    target_db: float = NORM_TARGET_DB,
) -> tuple[dict, dict]:
    """(gate booleans, measurements) for a finished, normalised clip."""
    import numpy as np

    x = np.asarray(x, dtype=np.float64).reshape(-1)
    peak = float(np.max(np.abs(x))) if x.size else 0.0
    head = x[: max(1, int(HOT_WIN_S * sr))]
    m = {
        "wpm": None if wpm is None else round(float(wpm), 1),
        "integrated_db": integrated_db(x, sr),
        "lead_in_ms": round(lead_s(x, sr) * 1000, 1),
        "peak_dbfs": round(_db(peak), 2),
        "full_scale_run": longest_full_scale_run(x),
        "head_rms_dbfs": round(_db(float(np.sqrt(np.mean(head**2)))), 2),
        "onset_rise_ms": round(onset_rise_s(x, sr) * 1000, 2),
    }
    m["pace"] = pace_report(wpm, pace)
    # Pace is report-only until its thresholds are tuned on real renders:
    # it is recorded (wpm, target, over/under) but never fails or retries a clip.
    gate = {
        "loudness": abs(m["integrated_db"] - target_db) <= LOUDNESS_TOL_DB,
        "lead_in": m["lead_in_ms"] >= LEAD_MIN_S * 1000,
        "clipping": m["peak_dbfs"] < CLIP_PEAK_DBFS
        or m["full_scale_run"] < CLIP_RUN_MAX,
        "onset": m["head_rms_dbfs"] < HOT_FLOOR_DBFS
        and m["onset_rise_ms"] >= ONSET_RISE_MIN_S * 1000,
    }
    return gate, m


def pace_report(
    wpm: float | None, pace: tuple[float, float] = (PACE_WPM, PACE_TOL_WPM)
) -> dict:
    """{wpm, target_wpm, tolerance_wpm, flag}: flag is "over"/"under" outside
    target +/- tolerance, "ok" inside, None without word timings."""
    t, tol = pace
    flag = (
        None
        if wpm is None
        else ("over" if wpm > t + tol else "under" if wpm < t - tol else "ok")
    )
    return {
        "wpm": None if wpm is None else round(float(wpm), 1),
        "target_wpm": float(t),
        "tolerance_wpm": float(tol),
        "flag": flag,
    }


def timings(text: str, words: list, duration_s: float) -> dict:
    """{text, duration_s, wpm, words:[{w,start,end}], gaps:[{start,end}] >= GAP_MIN_S}."""
    ws = [
        {
            "w": str(w["w"]).strip(),
            "start": round(float(w["start"]), 3),
            "end": round(float(w["end"]), 3),
        }
        for w in words
        if str(w["w"]).strip()
    ]
    span = ws[-1]["end"] - ws[0]["start"] if ws else 0.0
    wpm = round(len(ws) / span * 60, 1) if span > 0 else 0.0
    gaps = [
        {"start": a["end"], "end": b["start"]}
        for a, b in zip(ws, ws[1:])
        if b["start"] - a["end"] >= GAP_MIN_S - 1e-9
    ]
    return {
        "text": text,
        "duration_s": round(float(duration_s), 3),
        "wpm": wpm,
        "words": ws,
        "gaps": gaps,
    }
