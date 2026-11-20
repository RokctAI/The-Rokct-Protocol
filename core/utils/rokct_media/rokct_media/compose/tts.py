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

"""Speech rendering with VibeVoice-1.5B, with a content-addressed line cache.

Cache key = sha256 of (engine, model, reference-audio sha256 per speaker,
text per line, cfg_scale, ddpm_steps, seed, mode). Change one line's text and
only that line's key changes, so only that line is re-rendered. In joint
(dialogue) mode the whole conversation is one render, keyed on all of it.

Cached audio is stored raw (24 kHz mono float) under cache/tts/<key>.wav;
all trimming, tempo and levelling happens downstream so it never
invalidates the cache.
"""
from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path

import numpy as np

ENGINE_SR = 24000
_FILE_HASHES: dict[str, str] = {}


def file_sha256(path: str | Path) -> str:
    path = str(path)
    if path not in _FILE_HASHES:
        h = hashlib.sha256()
        with open(path, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        _FILE_HASHES[path] = h.hexdigest()
    return _FILE_HASHES[path]


def cache_key(render: dict, refs: list[str], texts: list[str], mode: str) -> str:
    payload = {
        "v": 1,
        "engine": render["engine"],
        "model": render["model"] if render["engine"] == "vibevoice" else None,
        "refs": [file_sha256(r) for r in refs],
        "texts": texts,
        "cfg": render["cfg_scale"],
        "steps": render["ddpm_steps"],
        "seed": render["seed"],
        "mode": mode,
    }
    return hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()[:24]


class LineCache:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)

    def path(self, key: str) -> Path:
        return self.root / f"{key}.wav"

    def get(self, key: str):
        p = self.path(key)
        if not p.exists():
            return None
        import soundfile as sf
        audio, sr = sf.read(str(p), dtype="float32")
        assert sr == ENGINE_SR
        return audio

    def put(self, key: str, audio: np.ndarray, meta: dict) -> None:
        from .dsp import write_wav
        write_wav(self.path(key), audio, ENGINE_SR, subtype="FLOAT")
        (self.root / f"{key}.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")


def pinned_model_path(model: str) -> str:
    """The local snapshot of `model` at TTS_MODEL_REVISION, when the environment
    pins one for this repo (TTS_MODEL names the repo; CI sets both). Anything
    else (a local folder, another repo, no pin set) is returned unchanged."""
    rev = os.environ.get("TTS_MODEL_REVISION")
    if not rev or model != os.environ.get("TTS_MODEL") or Path(model).is_dir():
        return model
    from huggingface_hub import snapshot_download
    return snapshot_download(model, revision=rev)


class VibeVoiceEngine:
    """Loads the model once and keeps it (loading costs ~15 s and ~6 GB)."""

    def __init__(self, model: str, cfg_scale: float, ddpm_steps: int, device: str = "cpu"):
        self.model_path = model
        self.cfg_scale = cfg_scale
        self.ddpm_steps = ddpm_steps
        self.device = device
        self.model = None
        self.processor = None

    def load(self) -> None:
        if self.model is not None:
            return
        import torch
        from vibevoice.modular.modeling_vibevoice_inference import (
            VibeVoiceForConditionalGenerationInference)
        from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor

        t = time.time()
        print(f"  loading {self.model_path} on {self.device} ...", flush=True)
        path = pinned_model_path(self.model_path)
        self.processor = VibeVoiceProcessor.from_pretrained(path)
        dtype = torch.float32 if self.device == "cpu" else torch.bfloat16
        self.model = VibeVoiceForConditionalGenerationInference.from_pretrained(
            path, torch_dtype=dtype, attn_implementation="sdpa",
            device_map=self.device)
        self.model.eval()
        print(f"  model ready in {time.time() - t:.1f}s", flush=True)

    def configure(self, cfg_scale: float, ddpm_steps: int) -> None:
        self.cfg_scale = cfg_scale
        self.ddpm_steps = ddpm_steps

    def render(self, turns: list[tuple[int, str]], refs: list[str], seed: int) -> np.ndarray:
        """turns: [(speaker_index, text)], refs: reference wav per speaker index."""
        import torch

        self.load()
        self.model.set_ddpm_inference_steps(num_steps=self.ddpm_steps)
        script = "\n".join(f"Speaker {i + 1}: {text}" for i, text in turns)
        inputs = self.processor(text=[script], voice_samples=[list(refs)], padding=True,
                                return_tensors="pt", return_attention_mask=True)
        for k, v in inputs.items():
            if torch.is_tensor(v):
                inputs[k] = v.to(self.device)
        torch.manual_seed(seed)
        with torch.no_grad():
            out = self.model.generate(**inputs, max_new_tokens=None, cfg_scale=self.cfg_scale,
                                      tokenizer=self.processor.tokenizer,
                                      generation_config={"do_sample": False}, verbose=False)
        if not out.speech_outputs or out.speech_outputs[0] is None:
            raise RuntimeError("VibeVoice returned no audio")
        return out.speech_outputs[0].float().cpu().numpy().reshape(-1)


class DummyEngine:
    """Tone bursts of the estimated spoken length. For testing the mix only."""

    def configure(self, *a):
        pass

    def render(self, turns, refs, seed):
        from .schema import estimate_speech_seconds
        chunks = []
        for i, text in turns:
            n = int(estimate_speech_seconds(text) * ENGINE_SR)
            t = np.arange(n) / ENGINE_SR
            f = 140 + 60 * i
            syll = 0.5 + 0.5 * np.sign(np.sin(2 * np.pi * 4 * t))
            chunks += [0.2 * np.sin(2 * np.pi * f * t) * syll, np.zeros(int(0.35 * ENGINE_SR))]
        return np.concatenate(chunks).astype(np.float32)


_ENGINES: dict[str, object] = {}


def get_engine(render: dict):
    """One engine per process; kept loaded between ads in watch mode."""
    name = render["engine"]
    if name == "dummy":
        return _ENGINES.setdefault("dummy", DummyEngine())
    eng = _ENGINES.get(("vv", render["model"]))
    if eng is None:
        eng = VibeVoiceEngine(render["model"], render["cfg_scale"], render["ddpm_steps"])
        _ENGINES[("vv", render["model"])] = eng
    eng.configure(render["cfg_scale"], render["ddpm_steps"])
    return eng


def render_cached(cache: LineCache, render: dict, turns: list[tuple[int, str]],
                  refs: list[str], mode: str, log=print) -> tuple[np.ndarray, dict]:
    key = cache_key(render, refs, [f"{i}|{t}" for i, t in turns], mode)
    audio = cache.get(key)
    if audio is not None:
        return audio, {"cache_key": key, "cached": True, "render_s": 0.0}
    engine = get_engine(render)
    t = time.time()
    audio = engine.render(turns, refs, render["seed"])
    elapsed = time.time() - t
    dur = audio.size / ENGINE_SR
    log(f"    rendered {dur:.1f}s audio in {elapsed:.0f}s (RTF {elapsed / max(dur, 1e-6):.1f}x)")
    cache.put(key, audio, {"turns": turns, "refs": refs, "mode": mode,
                           "render_s": round(elapsed, 1), "audio_s": round(dur, 2)})
    return audio, {"cache_key": key, "cached": False, "render_s": round(elapsed, 1)}
