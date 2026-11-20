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

"""ad.json -> finished spot (wav + mp3 + report.json).

    validate -> render lines (cached) -> trim + level each line -> time fit
    -> place on timeline with pauses -> music bed with ducking + fades
    -> sfx -> master to loudness target / true-peak ceiling -> encode
    -> measure (pyloudnorm + ffmpeg ebur128) -> ASR word check -> report
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import shutil
import time
from pathlib import Path

import numpy as np

from . import align, bed, dsp, tts
from .schema import ROOT, load_ad

LINE_LUFS = -20.0          # every rendered line is levelled to this before mixing


def _log_default(msg: str) -> None:
    print(msg, flush=True)


def make_ad(ad_path: str | Path, out_root: str | Path, *, voices_dir: Path | None = None,
            cache_dir: Path | None = None, asr: bool = True, asr_model: str = align.DEFAULT_ASR,
            engine_override: str | None = None, log=_log_default) -> dict:
    t_start = time.time()
    ad, warnings = load_ad(ad_path, voices_dir)
    if engine_override:
        ad["render"]["engine"] = engine_override
    out_dir = Path(out_root) / ad["id"]
    out_dir.mkdir(parents=True, exist_ok=True)
    cache = tts.LineCache(Path(cache_dir or ROOT / "cache" / "tts"))
    sr = ad["output"]["sample_rate"]
    render = ad["render"]
    for w in warnings:
        log(f"  warning: {w}")
    log(f"[{ad['id']}] {ad['format']}, {ad['duration_s']}s, {len(ad['script'])} lines, "
        f"mode={render['resolved_mode']}, engine={render['engine']}")

    # ------------------------------------------------------------------ render
    segs = [dict(s, kind="script", index=i) for i, s in enumerate(ad["script"])]
    tag = ad["tag"]
    if tag:
        segs.append(dict(tag, kind="tag", index=-1, pause_after_s=0.0))

    raw: list[np.ndarray | None] = [None] * len(segs)
    meta: list[dict] = [{} for _ in segs]
    joint_info = None
    mode = render["resolved_mode"]
    if mode == "joint":
        order: list[str] = []
        for s in ad["script"]:
            if s["speaker"] not in order:
                order.append(s["speaker"])
        refs = [ad["cast"][r]["ref_path"] for r in order]
        turns = [(order.index(s["speaker"]), s["text"]) for s in ad["script"]]
        try:
            log("  rendering dialogue jointly (one pass, all speakers)")
            audio, m = tts.render_cached(cache, render, turns, refs, "joint", log)
            if len(turns) > 1:
                clips, joint_info = align.split_joint(audio, tts.ENGINE_SR, [t for _, t in turns], asr_model)
            else:
                clips, joint_info = [audio], {}
            joint_info.update(m)
            for i, clip in enumerate(clips):
                raw[i] = clip
                meta[i] = {"cached": m["cached"], "render_s": None, "cache_key": m["cache_key"], "via": "joint"}
        except Exception as exc:  # noqa: BLE001 - any joint failure falls back
            msg = f"joint render/split failed ({exc}); falling back to per-line"
            warnings.append(msg)
            log(f"  warning: {msg}")
            mode = "per_line"
            raw = [None] * len(segs)
    for i, s in enumerate(segs):
        if raw[i] is not None:
            continue
        ref = ad["cast"][s["speaker"]]["ref_path"]
        log(f"  line {i} ({s['speaker']}): {s['text'][:60]}{'...' if len(s['text']) > 60 else ''}")
        audio, m = tts.render_cached(cache, render, [(0, s["text"])], [ref], "per_line", log)
        if m["cached"]:
            log("    cached")
        raw[i] = audio
        meta[i] = dict(m, via="per_line")

    # ------------------------------------------------------- per-line cleanup
    clips = []
    for i, s in enumerate(segs):
        a = dsp.trim_silence(raw[i], tts.ENGINE_SR)
        a = dsp.normalize_loudness(a, tts.ENGINE_SR, LINE_LUFS)
        a *= dsp.db(ad["cast"][s["speaker"]]["gain_db"] + s.get("gain_db", 0.0))
        clips.append(dsp.resample(a, tts.ENGINE_SR, sr))

    # ------------------------------------------------------------- time fit
    music = ad["music"]
    timing = ad["timing"]
    has_bed = music["bed"] != "none"
    intro = music["intro_s"] if has_bed else 0.2
    outro_min = music["outro_min_s"] if has_bed else 0.2
    window = ad["duration_s"] - intro - outro_min
    pauses = [s["pause_after_s"] for s in segs]
    if tag:
        pauses[len(ad["script"]) - 1] = max(pauses[len(ad["script"]) - 1], 0.0)
        gap_before_tag = tag["gap_before_s"]
    else:
        gap_before_tag = 0.0
    pauses[-1] = 0.0                                   # nothing after the last line

    rates = [s["rate"] for s in segs]
    speech_natural = sum(c.shape[0] / sr / r for c, r in zip(clips, rates))
    pause_total = sum(pauses) + gap_before_tag
    natural_total = speech_natural + pause_total
    tempo = 1.0
    pause_scale = 1.0
    fit = timing["fit"]
    max_st = timing["max_stretch"]
    if fit != "none" and natural_total > window:
        tempo = min(1 + max_st, speech_natural / max(window - pause_total, 1e-3))
        remaining = speech_natural / tempo + pause_total - window
        if remaining > 0 and timing["compress_pauses"] and pause_total > 0:
            pause_scale = max(0.5, 1 - remaining / pause_total)
    elif fit == "both" and natural_total < window * 0.95:
        tempo = max(1 - max_st, speech_natural / max(window * 0.97 - pause_total, 1e-3))
    # A fast tag is exempt from slow-down.
    final_clips, applied = [], []
    for c, s, r in zip(clips, segs, rates):
        t = r * tempo
        if s["kind"] == "tag" and s.get("fast") and tempo < 1:
            t = r
        if abs(t - 1) > 1e-3:
            c = dsp.time_stretch(c, sr, t)
        final_clips.append(c)
        applied.append(round(t, 4))
    pauses = [p * pause_scale for p in pauses]
    gap_before_tag *= pause_scale

    speech_end = intro
    positions = []
    for i, c in enumerate(final_clips):
        if segs[i]["kind"] == "tag":
            speech_end += gap_before_tag
        start = speech_end
        speech_end = start + c.shape[0] / sr
        positions.append((start, speech_end))
        speech_end += pauses[i]
    voice_end = positions[-1][1]
    needed = voice_end + outro_min
    target = float(ad["duration_s"])
    total = max(target, needed)
    over = needed - target
    if over > 0.01:
        status = f"over by {over:.2f}s"
    elif target - needed > 1.5:
        status = f"under by {target - needed:.2f}s (music tail fills it)" if has_bed else \
                 f"under by {target - needed:.2f}s (silence fills it)"
    else:
        status = "fits"
    log(f"  timing: natural speech+pauses {natural_total:.2f}s, window {window:.2f}s, "
        f"tempo x{tempo:.3f}, pauses x{pause_scale:.2f} -> {status}")

    # ------------------------------------------------------------- timeline
    n = int(round(total * sr))
    voice = np.zeros(n, dtype=np.float32)
    for (st, _), c in zip(positions, final_clips):
        a = int(round(st * sr))
        b = min(n, a + c.shape[0])
        voice[a:b] += c[: b - a]
    voice_lufs = dsp.loudness(voice[int(intro * sr): int(voice_end * sr)], sr)

    mix = np.stack([voice, voice], axis=1)
    bed_info = {"bed": music["bed"]}
    if has_bed:
        if music["bed"].startswith("builtin:"):
            style = music["bed"].split(":", 1)[1]
            b = bed.generate_bed(style, total + 0.5, sr, music["seed"])[:n]
        else:
            b = dsp.read_audio(music["bed_path"], sr, channels=2)
            if b.shape[0] < n:                       # loop with a short crossfade
                reps = int(np.ceil(n / max(1, b.shape[0] - sr))) + 1
                parts = [b]
                xf = int(0.5 * sr)
                for _ in range(reps):
                    tail = parts[-1]
                    ramp = np.linspace(0, 1, xf)[:, None]
                    head = b.copy()
                    head[:xf] = head[:xf] * ramp + tail[-xf:] * (1 - ramp)
                    parts[-1] = tail[:-xf]
                    parts.append(head)
                b = np.concatenate(parts)
            b = b[:n]
        b_lufs = dsp.loudness(b, sr)
        b = b * dsp.db(voice_lufs + music["level_db"] - b_lufs)
        env = dsp.envelope(voice, sr)
        gain = 10 ** ((music["duck_db"] * env) / 20.0)
        b = b * gain[:, None]
        b = dsp.fade(b, sr, music["fade_in_s"], 0.0)
        fo = min(music["fade_out_s"], max(0.2, 0.7 * (total - voice_end)))
        b = dsp.fade(b, sr, 0.0, fo)
        mix = mix + b
        bed_info.update({"level_db": music["level_db"], "duck_db": music["duck_db"],
                         "intro_s": intro, "fade_out_s": round(fo, 2)})

    sfx_info = []
    for fx in ad["sfx"]:
        if fx["file"].startswith("builtin:"):
            clip = bed.generate_sfx(fx["file"].split(":", 1)[1], sr)
        else:
            clip = dsp.read_audio(fx["path"], sr, channels=1)
        if "at_s" in fx:
            at = fx["at_s"]
        else:
            k = len(segs) - 1 if fx["segment"] == -1 else fx["segment"]
            at = positions[k][0 if fx["anchor"] == "start" else 1] + fx["offset_s"]
        at = max(0.0, at)
        clip_lufs = dsp.loudness(clip, sr)
        if np.isfinite(clip_lufs):
            clip = clip * dsp.db(voice_lufs + fx["gain_db"] - clip_lufs)
        a = int(at * sr)
        b_ = min(n, a + clip.shape[0])
        if a < n:
            mix[a:b_] += clip[: b_ - a, None]
        sfx_info.append({"file": fx["file"], "at_s": round(at, 3), "gain_db": fx["gain_db"]})

    # --------------------------------------------------------------- master
    out = ad["output"]
    mastered, minfo = dsp.master(mix, sr, out["loudness_lufs"], out["true_peak_dbtp"])
    if out["channels"] == 1:
        mastered = mastered.mean(axis=1)

    wav_path = out_dir / f"{ad['id']}.wav"
    dsp.write_wav(wav_path, mastered, sr, subtype="PCM_16")
    files = {"wav": wav_path.name}
    measured = {"wav": dsp.ffmpeg_ebur128(wav_path)}
    measured["wav"]["duration_s"] = round(mastered.shape[0] / sr, 3)
    if "mp3" in out["formats"]:
        mp3_path = out_dir / f"{ad['id']}.mp3"
        dsp.encode_mp3(wav_path, mp3_path, out["mp3_bitrate_kbps"])
        measured["mp3"] = dsp.ffmpeg_ebur128(mp3_path)
        # MP3 encoding shifts loudness by a tenth or two; trim it back once,
        # never past the true-peak ceiling.
        m3 = measured["mp3"]
        if m3["integrated_lufs"] is not None and abs(m3["integrated_lufs"] - out["loudness_lufs"]) > 0.05:
            adj = out["loudness_lufs"] - m3["integrated_lufs"]
            adj = min(adj, out["true_peak_dbtp"] - m3["true_peak_dbtp"])
            if abs(adj) > 0.05:
                dsp.encode_mp3(wav_path, mp3_path, out["mp3_bitrate_kbps"], gain_db=adj)
                measured["mp3"] = dsp.ffmpeg_ebur128(mp3_path)
                measured["mp3"]["encode_gain_db"] = round(adj, 2)
        files["mp3"] = mp3_path.name
        measured["mp3"]["duration_s"] = round(dsp.media_duration(mp3_path), 3)
    if "wav" not in out["formats"]:
        # WAV is still the master we measured from; keep it only if asked.
        wav_path.unlink()
        del files["wav"]

    # ---------------------------------------------------------------- ASR
    asr_info = None
    if asr and render["engine"] != "dummy":
        full_text = " ".join(s["text"] for s in segs)
        mono = mastered if mastered.ndim == 1 else mastered.mean(axis=1)
        asr_info = align.transcribe(mono, sr, full_text, asr_model)
        per_line = []
        for (st, en), s in zip(positions, segs):
            a, b_ = int(max(0, st - 0.05) * sr), int(min(total, en + 0.05) * sr)
            r = align.transcribe(mono[a:b_], sr, s["text"], asr_model)
            per_line.append(r)
        asr_info["per_line"] = per_line
        log(f"  ASR check ({asr_model}): WER {asr_info['wer']:.1%}")

    # ------------------------------------------------------------- report
    lines = []
    for i, (s, (st, en)) in enumerate(zip(segs, positions)):
        entry = {
            "n": i, "kind": s["kind"], "speaker": s["speaker"],
            "voice": ad["cast"][s["speaker"]]["source"], "text": s["text"],
            "delivery": s.get("delivery"), "start_s": round(st, 3), "end_s": round(en, 3),
            "duration_s": round(en - st, 3), "tempo": applied[i],
            "pause_after_s": round(pauses[i], 3) if i < len(segs) - 1 else 0.0,
            "cached": meta[i].get("cached"), "render_s": meta[i].get("render_s"),
            "rendered_via": meta[i].get("via"), "cache_key": meta[i].get("cache_key"),
        }
        if asr_info:
            entry["asr"] = asr_info["per_line"][i]["transcript"]
            entry["wer"] = asr_info["per_line"][i]["wer"]
        lines.append(entry)
    words = sum(len(s["text"].split()) for s in segs)
    report = {
        "id": ad["id"], "client": ad["client"], "title": ad.get("title"), "format": ad["format"],
        "created": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "source_sha256": hashlib.sha256(Path(ad["_source_path"]).read_bytes()).hexdigest(),
        "files": files,
        "target": {"duration_s": ad["duration_s"], "loudness_lufs": out["loudness_lufs"],
                   "true_peak_dbtp": out["true_peak_dbtp"], "sample_rate": sr,
                   "channels": out["channels"]},
        "timing": {
            "status": status, "actual_duration_s": round(total, 3),
            "voice_window_s": round(window, 3), "natural_speech_s": round(speech_natural, 3),
            "natural_speech_plus_pauses_s": round(natural_total, 3),
            "tempo_applied": round(tempo, 4), "pause_scale": round(pause_scale, 3),
            "voice_start_s": round(intro, 3), "voice_end_s": round(voice_end, 3),
            "words": words, "words_per_minute": round(words / max(1e-6, sum(e - s for s, e in positions)) * 60, 1),
        },
        "loudness": {"mastering": minfo, "measured": measured},
        "render": {"engine": render["engine"], "model": render["model"] if render["engine"] == "vibevoice" else None,
                   "mode_requested": render["mode"], "mode_used": mode,
                   "cfg_scale": render["cfg_scale"], "ddpm_steps": render["ddpm_steps"],
                   "seed": render["seed"], "joint_split": joint_info,
                   "lines_rendered": sum(1 for m in meta if m.get("cached") is False),
                   "lines_cached": sum(1 for m in meta if m.get("cached"))},
        "music": bed_info, "sfx": sfx_info, "lines": lines, "asr": (
            {k: v for k, v in asr_info.items() if k != "per_line"} if asr_info else None),
        "warnings": warnings, "wall_time_s": round(time.time() - t_start, 1),
    }
    (out_dir / "report.json").write_text(json.dumps(report, indent=2, ensure_ascii=False) + "\n",
                                         encoding="utf-8")
    shutil.copyfile(ad["_source_path"], out_dir / "ad.json")
    m = measured.get("mp3") or measured["wav"]
    log(f"  done in {report['wall_time_s']}s: {total:.2f}s, {m['integrated_lufs']} LUFS, "
        f"{m['true_peak_dbtp']} dBTP -> {out_dir}")
    return report
