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

"""Compare a candidate render against the regression baseline.

    rokct-media compare baseline_manifest.json candidate_manifest.json [-o compare.json]

Both files have the baseline manifest's shape: {"engines": [{"engine",
"status", "outputs": [{"path", "sha256", "metrics": {...}, "qc": {...}?}]}]}.
Every engine in the candidate is compared with the same engine in the
baseline (or only --engine ones), output by output, matched by path.

Rules (spec section 7, "Compare"):

* sha256       a deterministic render must reproduce every baseline media
               file byte for byte, unless baseline/expected_diffs.toml lists
               it with a reason (then the metrics below decide).
* duration     +-50 ms per clip; +-1 % for a full mix.
* loudness     integrated within +-0.5 LU (and on the profile's target when
               the candidate names a profile that has one).
* true peak    within +-0.3 dB of old, and at or under the profile ceiling.
* F0 median    within +-3 Hz, and inside the voice's gate window when the
               candidate records it (qc.f0_window_hz).
* similarity   drop <= 0.02, and >= the gate (0.88 at 5 s or more, else 0.83).
* ASR          0 word errors against the script; no new diffs against old.
* video        fps exact; frame count exact (+-1 when the duration moved
               within its limit). SSIM >= 0.98 and PSNR >= 35 dB at sampled
               frames, caption start/end within 1 frame (33 ms) and identical
               text, when those measurements are present.
* stills       dimensions exact.
* lesson       same subtopic count and order, same event types, primitive
               count +-0.

A metric that is missing on either side is reported as not measured, not
as a pass. Exit 0 when everything compared passes, 1 otherwise, 2 on bad input.
"""

from __future__ import annotations

import fnmatch
import json
from pathlib import Path

AUDIO_EXT = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus"}
VIDEO_EXT = {".mp4", ".mov", ".webm", ".mkv"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".webp"}
MEDIA_EXT = AUDIO_EXT | VIDEO_EXT | IMAGE_EXT
# Engines whose audio is a full mix (+-1 % duration) rather than a clip.
MIX_ENGINES = {"radio_ad", "social_reel", "lesson6", "tiktok_post", "guided_tour"}

T = {
    "clip_duration_s": 0.05,
    "mix_duration_frac": 0.01,
    "lufs": 0.5,
    "true_peak_db": 0.3,
    "f0_hz": 3.0,
    "similarity_drop": 0.02,
    "sim_long": 0.88,
    "sim_short": 0.83,
    "long_s": 5.0,
    "ssim": 0.98,
    "psnr": 35.0,
    "caption_s": 0.033,
}


class CompareError(ValueError):
    pass


def load_manifest(path) -> dict:
    p = Path(path)
    if p.is_dir():
        for name in (
            "baseline_manifest.json",
            "candidate_manifest.json",
            "manifest.json",
        ):
            if (p / name).is_file():
                p = p / name
                break
    try:
        d = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CompareError(f"{path}: cannot read a manifest ({exc})") from None
    if not isinstance(d.get("engines"), list):
        raise CompareError(f"{path}: no 'engines' list")
    return d


def load_expected(path) -> list[dict]:
    if not path:
        return []
    import tomllib

    try:
        d = tomllib.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise CompareError(f"{path}: {exc}") from None
    out = []
    for e in d.get("diff", []):
        if not e.get("engine") or not e.get("path") or not e.get("reason"):
            raise CompareError(f"{path}: every [[diff]] needs engine, path and reason")
        out.append(
            {
                "engine": e["engine"],
                "path": e["path"],
                "reason": e["reason"],
                "metrics": list(e.get("metrics", [])),
            }
        )
    return out


def _check(metric: str, old, new, ok: bool | None, limit: str, note: str = "") -> dict:
    c = {
        "metric": metric,
        "old": old,
        "new": new,
        "limit": limit,
        "result": "not_measured" if ok is None else ("pass" if ok else "fail"),
    }
    if note:
        c["note"] = note
    return c


def _num(d: dict, *keys):
    for k in keys:
        if not isinstance(d, dict):
            return None
        d = d.get(k)
    return d if isinstance(d, (int, float)) and not isinstance(d, bool) else None


def compare_output(
    engine: str,
    path: str,
    old: dict,
    new: dict,
    expected: dict | None = None,
    profile: dict | None = None,
) -> dict:
    ext = Path(path).suffix.lower()
    om, nm = old.get("metrics") or {}, new.get("metrics") or {}
    oq, nq = old.get("qc") or {}, new.get("qc") or {}
    checks = []
    same = bool(old.get("sha256")) and old.get("sha256") == new.get("sha256")
    if expected:
        checks.append(
            _check(
                "sha256",
                old.get("sha256"),
                new.get("sha256"),
                True,
                "expected diff",
                f"listed in expected_diffs: {expected['reason']}",
            )
        )
    else:
        checks.append(
            _check(
                "sha256",
                old.get("sha256"),
                new.get("sha256"),
                same,
                "identical (deterministic)",
            )
        )

    if ext in AUDIO_EXT or ext in VIDEO_EXT:
        o, n = _num(om, "duration_s"), _num(nm, "duration_s")
        mix = engine in MIX_ENGINES or ext in VIDEO_EXT
        if o is None or n is None:
            checks.append(_check("duration_s", o, n, None, ""))
        elif mix:
            checks.append(
                _check(
                    "duration_s",
                    o,
                    n,
                    abs(n - o) <= T["mix_duration_frac"] * o,
                    "+-1 %",
                )
            )
        else:
            checks.append(
                _check(
                    "duration_s",
                    o,
                    n,
                    abs(n - o) <= T["clip_duration_s"] + 1e-9,
                    "+-0.05 s",
                )
            )
        has_audio = ext in AUDIO_EXT or bool(om.get("audio") or nm.get("audio"))
        if has_audio:
            o, n = _num(om, "integrated_lufs"), _num(nm, "integrated_lufs")
            ok = None if o is None or n is None else abs(n - o) <= T["lufs"] + 1e-9
            if ok is not None and profile and profile.get("lufs") is not None:
                ok = ok and abs(n - profile["lufs"]) <= 1.0
            checks.append(_check("integrated_lufs", o, n, ok, "+-0.5 LU"))
            o, n = _num(om, "true_peak_dbtp"), _num(nm, "true_peak_dbtp")
            ok = (
                None
                if o is None or n is None
                else abs(n - o) <= T["true_peak_db"] + 1e-9
            )
            if (
                ok is not None
                and profile
                and profile.get("true_peak_max_dbtp") is not None
            ):
                ok = ok and n <= profile["true_peak_max_dbtp"] + 1e-9
            checks.append(
                _check(
                    "true_peak_dbtp",
                    o,
                    n,
                    ok,
                    "+-0.3 dB, at or under the profile ceiling",
                )
            )
            o, n = _num(om, "median_f0_hz"), _num(nm, "median_f0_hz")
            if o is not None or n is not None or "median_f0_hz" in om:
                ok = None if o is None or n is None else abs(n - o) <= T["f0_hz"] + 1e-9
                win = nq.get("f0_window_hz")
                f0_gate = (
                    _num(nq, "median_f0_hz")
                    if _num(nq, "median_f0_hz") is not None
                    else n
                )
                note = ""
                if (
                    ok is not None
                    and isinstance(win, list)
                    and len(win) == 2
                    and f0_gate is not None
                ):
                    ok = ok and win[0] <= f0_gate <= win[1]
                    note = f"gate window {win[0]}-{win[1]} Hz (gate F0 {f0_gate})"
                checks.append(
                    _check(
                        "median_f0_hz",
                        o,
                        n,
                        ok,
                        "+-3 Hz and inside the gate window",
                        note,
                    )
                )
            o, n = _num(oq, "similarity"), _num(nq, "similarity")
            if o is not None or n is not None:
                dur = _num(nq, "duration_s") or _num(nm, "duration_s") or 0.0
                gate = T["sim_long"] if dur >= T["long_s"] else T["sim_short"]
                ok = None if n is None else n >= gate - 1e-9
                if ok is not None and o is not None:
                    ok = ok and (o - n) <= T["similarity_drop"] + 1e-9
                checks.append(
                    _check("similarity", o, n, ok, f"drop <= 0.02 and >= {gate}")
                )
            o, n = _num(oq, "asr_word_errors"), _num(nq, "asr_word_errors")
            if o is not None or n is not None:
                ok = None if n is None else (n == 0 and (o is None or n <= o))
                checks.append(
                    _check("asr_word_errors", o, n, ok, "0, and no new diffs")
                )
    if ext in VIDEO_EXT:
        ov, nv = om.get("video") or {}, nm.get("video") or {}
        o, n = _num(ov, "fps"), _num(nv, "fps")
        checks.append(
            _check("fps", o, n, None if o is None or n is None else o == n, "exact")
        )
        o, n = _num(ov, "frames"), _num(nv, "frames")
        dur_ok = next(
            (c["result"] == "pass" for c in checks if c["metric"] == "duration_s"),
            False,
        )
        moved = _num(om, "duration_s") != _num(nm, "duration_s")
        tol = 1 if (moved and dur_ok) else 0
        checks.append(
            _check(
                "frames",
                o,
                n,
                None if o is None or n is None else abs(n - o) <= tol,
                "exact" if tol == 0 else "+-1",
            )
        )
        for k, lim in (("ssim", T["ssim"]), ("psnr", T["psnr"])):
            n = _num(nm, k)
            if n is not None:
                checks.append(_check(k, None, n, n >= lim, f">= {lim}"))
        oc, nc = om.get("captions"), nm.get("captions")
        if isinstance(oc, list) and isinstance(nc, list):
            ok = len(oc) == len(nc) and all(
                abs(a.get("start", 0) - b.get("start", 0)) <= T["caption_s"] + 1e-9
                and abs(a.get("end", 0) - b.get("end", 0)) <= T["caption_s"] + 1e-9
                and a.get("text") == b.get("text")
                for a, b in zip(oc, nc)
            )
            checks.append(
                _check(
                    "captions",
                    len(oc),
                    len(nc),
                    ok,
                    "start/end within 33 ms, text identical",
                )
            )
    if ext in IMAGE_EXT:
        o = (om.get("width"), om.get("height"))
        n = (nm.get("width"), nm.get("height"))
        known = None not in o and None not in n
        checks.append(
            _check("dimensions", list(o), list(n), (o == n) if known else None, "exact")
        )
    ol, nl = om.get("lesson"), nm.get("lesson")
    if isinstance(ol, dict) and isinstance(nl, dict):
        ok = (
            ol.get("subtopics") == nl.get("subtopics")
            and ol.get("event_types") == nl.get("event_types")
            and ol.get("primitives") == nl.get("primitives")
        )
        checks.append(
            _check(
                "lesson_structure",
                ol,
                nl,
                ok,
                "same subtopics, event types, primitive count",
            )
        )

    allowed = set((expected or {}).get("metrics", []))
    for c in checks:
        if c["result"] == "fail" and c["metric"] in allowed:
            c["result"] = "expected"
    status = "fail" if any(c["result"] == "fail" for c in checks) else "pass"
    return {"path": path, "status": status, "identical": same, "checks": checks}


def compare(
    baseline: dict,
    candidate: dict,
    engines: list[str] | None = None,
    expected: list[dict] | None = None,
    profiles: dict | None = None,
) -> dict:
    from .profiles import PROFILES

    profiles = profiles or PROFILES
    base = {e.get("engine"): e for e in baseline.get("engines", [])}
    cand = {e.get("engine"): e for e in candidate.get("engines", [])}
    names = engines or [n for n in cand if n]
    out = []
    for name in names:
        b, c = base.get(name), cand.get(name)
        r = {"engine": name, "outputs": [], "missing": [], "extra": []}
        if b is None or b.get("status") != "baselined":
            r.update(
                status="fail",
                error=f"no baseline for engine {name!r}"
                if b is None
                else f"baseline status is {b.get('status')!r}",
            )
            out.append(r)
            continue
        if c is None:
            r.update(status="fail", error="engine missing from the candidate")
            out.append(r)
            continue
        if c.get("status") not in ("baselined", "rendered", "pass"):
            r["error"] = (
                f"candidate status is {c.get('status')!r}: {c.get('error') or c.get('reason') or ''}".strip()
            )
        bo = {
            o["path"]: o
            for o in b.get("outputs", [])
            if Path(o["path"]).suffix.lower() in MEDIA_EXT
        }
        co = {
            o["path"]: o
            for o in c.get("outputs", [])
            if Path(o["path"]).suffix.lower() in MEDIA_EXT
        }
        for path, old in bo.items():
            exp = next(
                (
                    e
                    for e in (expected or [])
                    if e["engine"] == name and fnmatch.fnmatch(path, e["path"])
                ),
                None,
            )
            if path not in co:
                r["missing"].append(path)
                continue
            new = co[path]
            prof = profiles.get(
                (new.get("qc") or {}).get("profile") or new.get("profile") or ""
            )
            r["outputs"].append(compare_output(name, path, old, new, exp, prof))
        r["extra"] = sorted(set(co) - set(bo))
        bad = (
            r.get("error")
            or r["missing"]
            or any(o["status"] == "fail" for o in r["outputs"])
            or not r["outputs"]
        )
        r["status"] = "fail" if bad else "pass"
        r["identical"] = f"{sum(o['identical'] for o in r['outputs'])}/{len(bo)}"
        out.append(r)
    status = "pass" if out and all(e["status"] == "pass" for e in out) else "fail"
    return {
        "kind": "rokct-media compare",
        "status": status,
        "baseline_run": (baseline.get("run") or {}).get("url"),
        "candidate_run": (candidate.get("run") or {}).get("url"),
        "thresholds": T,
        "engines": out,
    }


def render_text(report: dict) -> str:
    lines = [f"rokct-media compare: {report['status'].upper()}"]
    if report.get("baseline_run"):
        lines.append(f"baseline : {report['baseline_run']}")
    if report.get("candidate_run"):
        lines.append(f"candidate: {report['candidate_run']}")
    for e in report["engines"]:
        lines.append("")
        lines.append(
            f"[{e['status'].upper()}] {e['engine']}"
            + (f"  identical {e['identical']}" if e.get("identical") else "")
            + (f"  ({e['error']})" if e.get("error") else "")
        )
        for o in e.get("outputs", []):
            lines.append(f"  {'ok  ' if o['status'] == 'pass' else 'FAIL'} {o['path']}")
            for c in o["checks"]:
                if c["result"] == "not_measured":
                    continue
                old = c["old"][:12] if isinstance(c["old"], str) else c["old"]
                new = c["new"][:12] if isinstance(c["new"], str) else c["new"]
                lines.append(
                    f"       {c['result']:<8} {c['metric']:<16} old={old} new={new}  ({c['limit']})"
                    + (f" {c['note']}" if c.get("note") else "")
                )
        for m in e.get("missing", []):
            lines.append(f"  FAIL {m}: missing from the candidate")
        for x in e.get("extra", []):
            lines.append(f"  info {x}: only in the candidate")
    return "\n".join(lines)
