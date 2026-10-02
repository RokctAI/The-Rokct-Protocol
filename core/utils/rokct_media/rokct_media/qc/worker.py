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

"""The QC worker process: measure takes, pick, stitch and gate.

Runs in its own process (python -m rokct_media.qc.worker ...), so the ASR
and speaker models are never resident beside the voice model.

    sentences --work WORK --ref REF.wav [--f0-target 102 --f0-tolerance 8]
        Lifted from factory voice_batch/qc.py: reads WORK/lines.json and
        WORK/takes_index.json ({take path: {key, seed}}), caches per-take
        measurements in WORK/takes_measure.json, picks one take per
        sentence, stitches each segment, gates it, writes WORK/results.json.

    takes --qc QC.json --qc-out RESULTS.json
        Lifted from factory PR #196 reel_voice.py (gate_takes): each
        (segment, seed) is one whole take; every part must pass pick on its
        own, the stitched take is gated, then cut and gated again when the
        segment has keep_through.

Logs ids and numbers only.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from ..audio.dsp import normalise
from ..speech.cut import keep_through, sha256_file
from ..speech.stitch import SR, stitch
from . import gate as qc
from .meter import Meter


def gate_sentences(args) -> int:
    import numpy as np
    import soundfile as sf

    lo, hi = qc.f0_range(args.f0_target, args.f0_tolerance)
    work = Path(args.work)
    lines = json.loads((work / "lines.json").read_text(encoding="utf-8"))
    index = json.loads((work / "takes_index.json").read_text(encoding="utf-8"))
    mpath = work / "takes_measure.json"
    M = json.loads(mpath.read_text(encoding="utf-8")) if mpath.exists() else {}
    meter = Meter(Path(args.ref), args.asr_model, args.language, qc.pyin_bounds(args.f0_target, args.f0_tolerance))
    sentence_of = {f"{it['id']}#{k}": s for it in lines for k, s in enumerate(it["sentences"], 1)}
    wild_of = {f"{it['id']}#{k}": w for it in lines for k, w in enumerate(it.get("sentence_wild", []), 1)}

    for p, meta in index.items():
        if p in M or not Path(p).exists():
            continue
        m = meter.measure(p, sentence_of[meta["key"]], wild_of.get(meta["key"]))
        M[p] = {**m, **meta}
        print(f"take {meta['key']} seed{meta['seed']}: err={m['err']} f0={m['f0']} swings={m['swings']} "
              f"sim={m['res']} dur={m['dur']} tail={m['tail_db']}", flush=True)
        mpath.write_text(json.dumps(M, indent=1), encoding="utf-8")

    results = []
    for it in lines:
        picks, tiers, lacking = [], [], []
        for k in range(1, len(it["sentences"]) + 1):
            key = f"{it['id']}#{k}"
            cands = [dict(m, path=p) for p, m in M.items() if m["key"] == key]
            best, tier = qc.pick(cands, args.f0_target, args.f0_tolerance)
            picks.append(best); tiers.append(tier)  # noqa: E702
            if tier != 1:
                lacking.append({"key": key, "tier": tier})
        tried = sorted({m["seed"] for m in M.values() if m["key"].split("#")[0] == it["id"]})
        r = {"id": it["id"], "seeds_tried": tried, "lacking": lacking}
        if any(t == 0 for t in tiers):
            r["status"] = "incomplete"
            results.append(r)
            print(f"segment {it['id']}: incomplete (no word-exact take for {sum(t == 0 for t in tiers)} sentence(s))")
            continue
        arrays = []
        for b in picks:
            x, sr = sf.read(b["path"])
            assert sr == SR, "unexpected sample rate"
            arrays.append(x)
        y, pauses = stitch(arrays)
        y = normalise(y).astype(np.float32)
        dst = work / "final" / it["final_wav"]
        dst.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(dst), y, SR, subtype="PCM_16")
        fm = meter.measure(dst, it.get("asr_text", it["text"]), it.get("asr_wild"))
        x, _ = sf.read(str(dst))
        dur = round(len(x) / SR, 3)
        thr = qc.sim_threshold(dur)
        gate = {"f0": lo <= fm["f0"] <= hi, "similarity": fm["res"] >= thr, "asr": fm["err"] == 0,
                "tail": qc.tail_ok(fm["tail_db"])}
        r.update({
            "status": "pass" if all(gate.values()) else "fail", "gate": gate, "final_path": str(dst),
            "duration_s": dur, "median_f0_hz": fm["f0"], "upward_swings": fm["swings"],
            "similarity": fm["res"], "similarity_threshold": thr, "asr_match": fm["err"] == 0,
            "asr_word_errors": fm["err"], "asr_transcript": fm["transcript"], "tail_db": fm["tail_db"],
            "rms_dbfs": round(float(20 * np.log10(np.sqrt(np.mean(x ** 2)))), 2),
            "peak": round(float(np.max(np.abs(x))), 4), "pauses_ms": pauses,
            "sha256": sha256_file(dst),
            "seeds": [b["seed"] for b in picks],
            "takes": [{"sentence": k, "seed": b["seed"], "tier": t, "median_f0_hz": b["f0"],
                       "upward_swings": b["swings"], "similarity": b["res"], "duration_s": b["dur"],
                       "tail_db": b.get("tail_db")}
                      for k, (b, t) in enumerate(zip(picks, tiers), 1)],
        })
        results.append(r)
        print(f"segment {it['id']}: {r['status']} dur={dur}s f0={fm['f0']} sim={fm['res']} (>= {thr}) "
              f"asr_errors={fm['err']} tail={fm['tail_db']} seeds={r['seeds']}", flush=True)
    (work / "results.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


def listen_take(meter, t: dict, r: dict) -> None:
    """Stitch a take whose sentence failed pick from every sentence it
    rendered, only so it can be heard: measured ("listen"), not gated."""
    import numpy as np
    import soundfile as sf
    arrays = [sf.read(p)[0] for p in t["paths"] if Path(p).exists()]
    if not arrays:
        return
    y, _ = stitch(arrays)
    dst = Path(t["final"])
    dst.parent.mkdir(parents=True, exist_ok=True)
    sf.write(str(dst), normalise(y).astype(np.float32), SR, subtype="PCM_16")
    m = meter.measure(dst, t["text"], t["wild"])
    r["final_path"] = str(dst)
    r["listen"] = {"duration_s": m["dur"], "median_f0_hz": m["f0"], "similarity": m["res"],
                   "asr_word_errors": m["err"], "asr_transcript": m["transcript"], "tail_db": m["tail_db"]}


def gate_takes(args) -> int:
    import numpy as np
    import soundfile as sf

    spec = json.loads(Path(args.qc).read_text(encoding="utf-8"))
    target, tol = spec["f0_target_hz"], spec["f0_tolerance_hz"]
    lo, hi = qc.f0_range(target, tol)
    meter = Meter(Path(spec["ref"]), args.asr_model, args.language, qc.pyin_bounds(target, tol))
    results = []
    for t in spec["takes"]:
        r = {"id": t["id"], "seed": t["seed"], "status": "fail"}
        parts, arrays = [], []
        for text, p, wild in zip(t["parts"], t["paths"], t["part_wild"]):
            if not Path(p).exists():
                parts.append({"missing": True})
                continue
            m = meter.measure(p, text, wild)
            best, tier = qc.pick([m], target, tol)
            parts.append({"tier": tier, "median_f0_hz": m["f0"], "similarity": m["res"], "asr_word_errors": m["err"],
                          "asr_transcript": m["transcript"], "tail_db": m["tail_db"], "duration_s": m["dur"]})
            if best is not None:
                x, sr = sf.read(p)
                assert sr == SR, "unexpected sample rate"
                arrays.append(x)
        r["parts"] = parts
        if len(arrays) != len(t["parts"]):
            r["reason"] = "a sentence has no word-exact take with a clean tail"
            listen_take(meter, t, r)
            results.append(r)
            print(f"take {t['id']} seed{t['seed']}: fail ({r['reason']})", flush=True)
            continue
        y, pauses = stitch(arrays)
        dst = Path(t["final"])
        dst.parent.mkdir(parents=True, exist_ok=True)
        sf.write(str(dst), normalise(y).astype(np.float32), SR, subtype="PCM_16")
        fm = meter.measure(dst, t["text"], t["wild"])
        dur = fm["dur"]
        thr = qc.sim_threshold(dur)
        gate = {"f0": lo <= fm["f0"] <= hi, "similarity": fm["res"] >= thr, "asr": fm["err"] == 0,
                "tail": qc.tail_ok(fm["tail_db"])}
        r.update({"status": "pass" if all(gate.values()) else "fail", "gate": gate, "final_path": str(dst),
                  "duration_s": dur, "median_f0_hz": fm["f0"], "similarity": fm["res"],
                  "similarity_threshold": thr, "asr_word_errors": fm["err"], "asr_transcript": fm["transcript"],
                  "tail_db": fm["tail_db"], "pauses_ms": pauses, "sha256": sha256_file(dst)})
        if r["status"] == "pass" and t.get("keep_through"):
            r.update(keep_through(meter, dst, t))
        results.append(r)
        print(f"take {t['id']} seed{t['seed']}: {r['status']} dur={dur}s f0={fm['f0']} sim={fm['res']} "
              f"(>= {thr}) asr_errors={fm['err']} tail={fm['tail_db']}", flush=True)
    Path(args.qc_out).write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="mode", required=True)
    s = sub.add_parser("sentences")
    s.add_argument("--work", required=True)
    s.add_argument("--ref", required=True)
    s.add_argument("--f0-target", type=float, default=qc.TARGET_F0)
    s.add_argument("--f0-tolerance", type=float, default=qc.F0_TOLERANCE)
    t = sub.add_parser("takes")
    t.add_argument("--qc", required=True)
    t.add_argument("--qc-out", required=True)
    for p in (s, t):
        p.add_argument("--asr-model", default=os.environ.get("ASR_MODEL", "small.en"))
        p.add_argument("--language", default="en")
    args = ap.parse_args(argv)
    return gate_sentences(args) if args.mode == "sentences" else gate_takes(args)


if __name__ == "__main__":
    sys.exit(main())
