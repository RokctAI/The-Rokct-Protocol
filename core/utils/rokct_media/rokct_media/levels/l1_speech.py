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

"""Level 1: script + voice -> gated voice clips.

The round logic is lifted from factory voice_batch/run.py (render_rounds)
and PR #196 radio_ads/reel_voice.py (render_voice). Render and QC run as
separate child processes, so the voice model and the ASR/speaker models
are never resident together.

f0_closest : seed rounds 11/22/33, then 44, then 55. After each round the
             QC worker picks and gates every segment. A segment not yet
             passing gets the next seed for the sentences that lack a
             strictly passing take (all of its sentences if each already
             has one and the stitched file still fails). A segment still
             failing after the last round fails the job.
whole_take : the same rounds (prefer_seeds first, one round each); every
             seed renders the whole segment and is gated as one take, until
             the segment has `takes` passing takes.

Writes out/<asset or id>.wav per segment (plus .mp3 when the job asks),
whole_take's per-seed files and listen copies, and out/result.json.
Logs ids, seeds and numbers only, never the script text.
"""
from __future__ import annotations

import json
import shutil
import subprocess
import sys
import time
from pathlib import Path

from ..audio import encode
from ..manifest.load import IMPLEMENTED_SINKS, PUBLISHING_SINKS, Job
from ..models.base import EngineError, engine_class
from ..models.voice_model import check_revision
from ..qc import gate as qc_gate
from ..result import Delivery, Output, Result
from ..speech import plan
from ..speech.takes import safe, sha256_file
from ..text.norm import TAIL_PAD, tts_prompt
from ..voices.registry import Registry, VoiceError, VoiceRefused


def _run(module: str, argv: list[str], isolate: bool) -> None:
    if isolate:
        subprocess.run([sys.executable, "-m", module, *argv], check=True)
        return
    import importlib
    rc = importlib.import_module(module).main(argv)
    if rc:
        raise subprocess.CalledProcessError(rc, module)


class _Ctx:
    def __init__(self, job: Job, model_path, isolate: bool, on_progress, no_cache: bool):
        self.job, self.isolate, self.on_progress, self.no_cache = job, isolate, on_progress, no_cache
        sp = job.speech
        opts = {"cfg_scale": sp["cfg"], "ddpm_steps": sp["steps"]}
        if sp["engine"] == "voice_model":
            opts.update(revision=sp["model_revision"], model_path=str(model_path) if model_path else None)
        self.engine_opts = opts

    def progress(self, **event) -> None:
        if self.on_progress:
            try:
                self.on_progress(event)
            except Exception:  # noqa: BLE001 - a progress callback never fails a render
                pass

    def render(self, jobs_path: Path, ref: Path) -> None:
        argv = ["--jobs", str(jobs_path), "--ref", str(ref), "--engine", self.job.speech["engine"],
                "--engine-opts", json.dumps(self.engine_opts)]
        if self.no_cache:
            argv.append("--no-cache")
        _run("rokct_media.speech.takes", argv, self.isolate)

    def qc(self, argv: list[str]) -> None:
        sp = self.job.speech
        _run("rokct_media.qc.worker", [*argv, "--asr-model", sp["asr_model"], "--language", sp["language"]],
             self.isolate)


# --------------------------------------------------------------- f0_closest


def sentence_rounds(ctx: _Ctx, items: list[dict], work: Path, voice, label: str) -> list[dict]:
    """Seed rounds of render + QC until every segment passes or the seeds run
    out (voice_batch/run.py render_rounds)."""
    work.mkdir(parents=True, exist_ok=True)
    (work / "lines.json").write_text(json.dumps(items, indent=1, ensure_ascii=False), encoding="utf-8")
    index_path = work / "takes_index.json"
    index = json.loads(index_path.read_text(encoding="utf-8")) if index_path.exists() else {}
    text_of = {f"{it['id']}#{k}": t for it in items for k, t in enumerate(it["render_text"], 1)}
    pending = set(text_of)
    results: list[dict] = []
    for rnd, seeds in enumerate(ctx.job.speech["seed_rounds"], 1):
        jobs = []
        for key in sorted(pending):
            for seed in seeds:
                out = str(work / "takes" / f"{safe(key)}_seed{seed}.wav")
                index[out] = {"key": key, "seed": seed}
                jobs.append({"key": key, "text": text_of[key], "seed": seed, "out": out})
        index_path.write_text(json.dumps(index, indent=1), encoding="utf-8")
        (work / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        print(f"{label} round {rnd}: seeds {seeds}, {len(pending)} sentence(s)", flush=True)
        ctx.progress(stage="round", voice=voice.id, round=rnd, seeds=list(seeds), sentences=len(pending))
        ctx.render(work / "jobs.json", voice.ref)
        ctx.qc(["sentences", "--work", str(work), "--ref", str(voice.ref),
                "--f0-target", str(voice.f0_target_hz), "--f0-tolerance", str(voice.f0_tolerance_hz)])
        results = json.loads((work / "results.json").read_text(encoding="utf-8"))
        pending = set()
        for r in results:
            if r["status"] == "pass":
                continue
            lacking = [x["key"] for x in r.get("lacking", [])]
            if r["status"] == "fail" and not lacking:
                lacking = [k for k in text_of if k.split("#")[0] == r["id"]]
            pending.update(lacking)
        if not pending:
            break
    return results


def _sentence_segment_qc(r: dict) -> dict:
    keep = ("status", "seeds_tried", "seeds", "gate", "duration_s", "median_f0_hz", "upward_swings", "similarity",
            "similarity_threshold", "asr_match", "asr_word_errors", "tail_db", "rms_dbfs", "peak", "pauses_ms",
            "sha256", "takes")
    out = {k: r[k] for k in keep if k in r}
    if r.get("lacking"):
        out["lacking"] = [{"sentence": int(x["key"].rsplit("#", 1)[1]), "tier": x["tier"]} for x in r["lacking"]]
    return out


# --------------------------------------------------------------- whole_take


def whole_take_rounds(ctx: _Ctx, lines: list[dict], work: Path, voice, label: str) -> dict[str, list[dict]]:
    """Seed rounds for one voice's segments; returns every gated take per
    segment (reel_voice.py render_voice)."""
    work.mkdir(parents=True, exist_ok=True)
    gate = {"f0_target_hz": voice.f0_target_hz, "f0_tolerance_hz": voice.f0_tolerance_hz}
    taken: dict[str, list[dict]] = {ln["id"]: [] for ln in lines}
    for rnd in range(1, max(len(ln["rounds"]) for ln in lines) + 1):
        todo = [ln for ln in lines if len(ln["rounds"]) >= rnd
                and sum(t["status"] == "pass" for t in taken[ln["id"]]) < ln["takes"]]
        if not todo:
            continue
        seeds = sorted({s for ln in todo for s in ln["rounds"][rnd - 1]})
        jobs, takes = [], []
        for ln in todo:
            for seed in ln["rounds"][rnd - 1]:
                paths = []
                for k, (part, said) in enumerate(zip(ln["parts"], ln["tts_parts"]), 1):
                    out = str(work / "takes" / f"{safe(ln['id'] + '#' + str(k))}_seed{seed}.wav")
                    jobs.append({"key": f"{ln['id']}#{k}", "text": said, "seed": seed, "out": out})
                    paths.append(out)
                takes.append({"id": ln["id"], "seed": seed, "text": ln["text"], "parts": ln["parts"], "paths": paths,
                              "part_wild": ln["part_wild"], "wild": ln["wild"],
                              "keep_through": ln.get("keep_through"),
                              "final": str(work / "final" / f"{ln['id']}_seed{seed}.wav")})
        (work / "jobs.json").write_text(json.dumps(jobs, ensure_ascii=False), encoding="utf-8")
        (work / "qc.json").write_text(json.dumps({"ref": str(voice.ref), **gate, "takes": takes}, ensure_ascii=False),
                                      encoding="utf-8")
        print(f"{label} round {rnd}: seeds {seeds}, {len(todo)} segment(s)", flush=True)
        ctx.progress(stage="round", voice=voice.id, round=rnd, seeds=seeds, segments=len(todo))
        ctx.render(work / "jobs.json", voice.ref)
        ctx.qc(["takes", "--qc", str(work / "qc.json"), "--qc-out", str(work / "qc_results.json")])
        for r in json.loads((work / "qc_results.json").read_text(encoding="utf-8")):
            taken[r["id"]].append(r)
    return taken


_TAKE_KEEP = ("seed", "status", "reason", "gate", "duration_s", "median_f0_hz", "similarity", "similarity_threshold",
              "asr_word_errors", "tail_db", "pauses_ms", "sha256", "files", "listen_files")


def _take_qc(t: dict) -> dict:
    out = {k: t[k] for k in _TAKE_KEEP if k in t}
    out["parts"] = [{k: v for k, v in p.items() if k != "asr_transcript"} for p in t.get("parts", [])]
    if t.get("cut"):
        out["cut"] = {k: v for k, v in t["cut"].items() if k not in ("text", "asr_transcript")}
    if t.get("listen"):
        out["listen"] = {k: v for k, v in t["listen"].items() if k != "asr_transcript"}
    return out


def write_listen_takes(seg_id: str, takes: list[dict], out: Path) -> None:
    """out/takes/<id>_seed<N>[_cut]_<PASS|FAIL>.mp3 for every take rendered;
    each file is labelled by its own gate (reel_voice.py)."""
    d = out / "takes"
    for t in takes:
        files = []
        for key, gate in (("final_path", t.get("gate")), ("cut_path", (t.get("cut") or {}).get("gate"))):
            if not t.get(key) or not Path(t[key]).exists():
                continue
            ok = bool(gate) and all(gate.values())
            name = f"{seg_id}_seed{t['seed']}{'_cut' if key == 'cut_path' else ''}_{'PASS' if ok else 'FAIL'}.mp3"
            encode.encode(t[key], d / name, bitrate_kbps=64)
            files.append(f"takes/{name}")
        if files:
            t["listen_files"] = files


# --------------------------------------------------------------------- run


def _wav_duration(p: Path) -> float | None:
    try:
        import soundfile as sf
        info = sf.info(str(p))
        return round(info.frames / float(info.samplerate), 4)
    except Exception:  # noqa: BLE001
        return None


def run(job: Job, registry: Registry, *, model_path=None, isolate: bool = True, on_progress=None,
        no_cache: bool = False) -> Result:
    started = time.time()
    sp = job.speech
    res = Result(status="pass", level=1, job_id=job.id)
    res.settings = {"selection": sp["selection"], "seed_rounds": sp["seed_rounds"], "cfg": sp["cfg"],
                    "steps": sp["steps"], "tail_pad": TAIL_PAD, "prompt": tts_prompt("<sentence>"),
                    "asr_model": sp["asr_model"], "language": sp["language"], "sample_rate": 24000,
                    "loudness_dbfs": -20.0, "profiles": job.output["profiles"], "formats": job.output["formats"]}

    def finish(status: str) -> Result:
        res.status = status
        res.elapsed_s = round(time.time() - started, 1)
        res.write(job.out_dir / "result.json")
        return res

    # Voices, then the refusals: all before any model loads.
    try:
        used = {}
        for s in job.segments:
            v = registry.get(job.voice_of(s))
            used[v.id] = v
    except VoiceError as exc:
        res.errors.append(str(exc))
        return finish("invalid")
    publishing = [d["sink"] for d in job.deliver if d["sink"] in PUBLISHING_SINKS]
    if publishing:
        for v in used.values():
            if not v.agreement_in_place:
                res.refusals.append(f"{v.id}: agreement_in_place is false (needed for {publishing[0]})")
        if res.refusals:
            return finish("refused")
    try:
        if sp["engine"] == "voice_model":
            check_revision(sp["model_revision"])
        res.model = engine_class(sp["engine"])(**_Ctx(job, model_path, isolate, None, no_cache).engine_opts).identity()
    except EngineError as exc:
        res.refusals.append(str(exc))
        return finish("refused")
    for v in used.values():
        try:
            v.verify()
        except VoiceRefused as exc:
            res.refusals.append(str(exc))
        except VoiceError as exc:
            res.errors.append(str(exc))
    if res.errors:
        return finish("invalid")
    if res.refusals:
        return finish("refused")
    unsupported = [d["sink"] for d in job.deliver if d["sink"] not in IMPLEMENTED_SINKS]
    if unsupported:
        res.errors.append(f"delivery sink(s) not in this version: {', '.join(unsupported)}")
        return finish("invalid")
    res.voices = {vid: {**v.summary(), "gate": qc_gate.gate_settings(v.f0_target_hz, v.f0_tolerance_hz)}
                  for vid, v in used.items()}

    try:
        items_by_voice: dict[str, list] = {}
        for s in job.segments:
            if sp["selection"] == "f0_closest":
                it = plan.sentence_item(s, job.pronunciations)
                it["final_wav"] = f"{s['id']}.wav"
            else:
                it = plan.whole_take_line(s, job.pronunciations, sp["seed_rounds"])
            items_by_voice.setdefault(job.voice_of(s), []).append(it)
    except plan.PlanError as exc:
        res.errors.append(str(exc))
        return finish("invalid")

    ctx = _Ctx(job, model_path, isolate, on_progress, no_cache)
    out = job.out_dir
    out.mkdir(parents=True, exist_ok=True)
    seg_by_id = {s["id"]: s for s in job.segments}
    seg_qc: dict[str, dict] = {}
    mp3 = "mp3" in job.output["formats"]
    profile = "clip_wav"

    def add_output(path: Path, seg: str, kind: str, fmt: str = "wav") -> Output:
        o = Output(path=path.relative_to(out), profile=profile if fmt == "wav" else "app_r3_mp3", format=fmt,
                   sha256=sha256_file(path), duration_s=_wav_duration(path) if fmt == "wav" else None,
                   segment=seg, kind=kind, publishable=all(v.agreement_in_place for v in used.values()))
        res.outputs.append(o)
        return o

    try:
        for vid, items in items_by_voice.items():
            voice = used[registry.get(vid).id]
            work = job.work_dir / "speech" / voice.id
            if sp["selection"] == "f0_closest":
                results = sentence_rounds(ctx, items, work, voice, voice.id)
                for r in results:
                    seg = seg_by_id[r["id"]]
                    name = seg.get("asset") or f"{seg['id']}.wav"
                    seg_qc[r["id"]] = {"id": r["id"], "voice": voice.id, "selection": "f0_closest",
                                       **_sentence_segment_qc(r)}
                    if r["status"] == "pass":
                        dst = out / name
                        shutil.copyfile(r["final_path"], dst)
                        add_output(dst, r["id"], "clip")
                        if mp3:
                            encode.encode(dst, dst.with_suffix(".mp3"))
                            add_output(dst.with_suffix(".mp3"), r["id"], "clip", "mp3")
            else:
                taken = whole_take_rounds(ctx, items, work, voice, voice.id)
                for ln in items:
                    seg = seg_by_id[ln["id"]]
                    passed = [t for t in taken[ln["id"]] if t["status"] == "pass"][: ln["takes"]]
                    for t in passed:
                        name = f"{ln['id']}_seed{t['seed']}"
                        shutil.copyfile(t["final_path"], out / f"{name}.wav")
                        encode.encode(out / f"{name}.wav", out / f"{name}.mp3")
                        t["files"] = [f"{name}.wav", f"{name}.mp3"]
                        add_output(out / f"{name}.wav", ln["id"], "take")
                        add_output(out / f"{name}.mp3", ln["id"], "take", "mp3")
                        if t.get("cut_path"):
                            shutil.copyfile(t["cut_path"], out / f"{name}_cut.wav")
                            encode.encode(out / f"{name}_cut.wav", out / f"{name}_cut.mp3")
                            t["files"] += [f"{name}_cut.wav", f"{name}_cut.mp3"]
                            add_output(out / f"{name}_cut.wav", ln["id"], "cut")
                            add_output(out / f"{name}_cut.mp3", ln["id"], "cut", "mp3")
                    # The first passing take (its cut, when the segment has
                    # one) is the segment's clip.
                    if passed:
                        dst = out / (seg.get("asset") or f"{ln['id']}.wav")
                        shutil.copyfile(passed[0].get("cut_path") or passed[0]["final_path"], dst)
                        add_output(dst, ln["id"], "clip")
                    write_listen_takes(ln["id"], taken[ln["id"]], out)
                    for f in sorted({f for t in taken[ln["id"]] for f in t.get("listen_files", [])}):
                        add_output(out / f, ln["id"], "listen", "mp3")
                    seg_qc[ln["id"]] = {
                        "id": ln["id"], "voice": voice.id, "selection": "whole_take",
                        "status": "pass" if passed else "fail", "parts": len(ln["parts"]),
                        "seed_order": [s for r in ln["rounds"] for s in r], "takes_wanted": ln["takes"],
                        "takes_passed": len(passed), "chosen_seeds": [t["seed"] for t in passed],
                        "takes": [_take_qc(t) for t in taken[ln["id"]]]}
    except subprocess.CalledProcessError as exc:
        res.errors.append(f"a render or QC worker failed ({exc.cmd if isinstance(exc.cmd, str) else exc.cmd[2]})")
        res.segments = [seg_qc[s["id"]] for s in job.segments if s["id"] in seg_qc]
        return finish("fail")

    res.segments = [seg_qc.get(s["id"], {"id": s["id"], "status": "fail"}) for s in job.segments]
    status = "pass" if all(q.get("status") == "pass" for q in res.segments) else "fail"
    for q in res.segments:
        print(f"segment {q['id']}: {q.get('status')}", flush=True)
    if status == "pass":
        for d in job.deliver:
            if d["sink"] == "local":
                refs = [str(out)]
                if d.get("dir"):
                    dst = Path(d["dir"])
                    dst.mkdir(parents=True, exist_ok=True)
                    for o in res.outputs:
                        (dst / o.path).parent.mkdir(parents=True, exist_ok=True)
                        shutil.copyfile(out / o.path, dst / o.path)
                    refs = [str(dst)]
                res.deliveries.append(Delivery("local", True, refs))
            elif d["sink"] == "return":
                res.returned = [o for o in res.outputs if o.kind in ("clip", "cut")]
                res.deliveries.append(Delivery("return", True, [str(o.path) for o in res.returned]))
    return finish(status)
