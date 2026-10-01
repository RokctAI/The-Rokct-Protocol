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

"""The default speech engine: the pinned voice model on CPU.

The Renderer below is lifted verbatim from the agent's
lms/team/scripts/render_voices.py, which factory voice_batch rendered
every take with: CPU float32, sdpa attention, cfg 1.3, 10 DDPM steps, the
reference handed to the processor by path, and a "Speaker 1: " prompt.
The pin is what the loader adds: the model is loaded only from a local
snapshot of REVISION, and a branch name or any other revision is refused.
"""
from __future__ import annotations

import os
import random
import re
import time
from pathlib import Path

from .base import EngineError

REPO = "microsoft/VibeVoice-1.5B"
REVISION = "c00898d257e6b46004e3e2866a47534085fb685a"
FORK_REPO = "https://github.com/vibevoice-community/VibeVoice.git"
FORK_COMMIT = "952326ddb264062466a888cf32a5b2f4e803e16e"
DEFAULT_DDPM_STEPS = 10
DEFAULT_CFG_SCALE = 1.3
SAMPLE_RATE = 24_000
PROMPT = "Speaker 1: {text}"

_SHA_RE = re.compile(r"[0-9a-f]{40}")


def check_revision(revision: str) -> str:
    if not isinstance(revision, str) or not _SHA_RE.fullmatch(revision):
        raise EngineError(f"refused: model revision must be a full 40-character commit sha, got {revision!r}")
    return revision


def resolve_model_path(model_path: str | os.PathLike | None = None, revision: str = REVISION) -> str:
    """A local snapshot directory of `revision`.

    An explicit path (argument or ROKCT_MEDIA_MODEL_PATH) must be a
    snapshot directory named by that revision, as the hub cache lays it
    out; otherwise the hub cache is asked for exactly that revision (offline
    when HF_HUB_OFFLINE=1)."""
    check_revision(revision)
    model_path = model_path or os.environ.get("ROKCT_MEDIA_MODEL_PATH") or None
    if model_path:
        p = Path(model_path)
        if not p.is_dir():
            raise EngineError(f"model path is not a directory: {p}")
        if p.name != revision:
            raise EngineError(f"refused: model path {p} is not a snapshot of the pinned revision {revision}")
        return str(p)
    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise EngineError("the voice model needs the [voice] extra (pip install 'rokct-media[voice]')") from exc
    return snapshot_download(REPO, revision=revision)


class Renderer:
    """Loads the voice model once and keeps it, because loading is the expensive part."""

    def __init__(self, model_path: str, device: str, ddpm_steps: int,
                 cfg_scale: float):
        self.model_path = model_path
        self.device = device
        self.ddpm_steps = ddpm_steps
        self.cfg_scale = cfg_scale
        self.model = None
        self.processor = None

    def load(self) -> None:
        import torch
        from vibevoice.modular.modeling_vibevoice_inference import (
            VibeVoiceForConditionalGenerationInference)
        from vibevoice.processor.vibevoice_processor import VibeVoiceProcessor

        started = time.time()
        print(f"Loading the voice model on {self.device} ...", flush=True)
        self.processor = VibeVoiceProcessor.from_pretrained(self.model_path)
        dtype = torch.float32 if self.device == "cpu" else torch.bfloat16
        self.model = VibeVoiceForConditionalGenerationInference.from_pretrained(
            self.model_path,
            torch_dtype=dtype,
            attn_implementation="sdpa",
            device_map=self.device,
        )
        self.model.eval()
        self.model.set_ddpm_inference_steps(num_steps=self.ddpm_steps)
        print(f"Model ready in {time.time() - started:.1f}s", flush=True)

    def render(self, text: str, reference: Path):
        """Return float32 mono samples at SAMPLE_RATE for one line.

        The reference is handed to the processor by path, so a reference
        recording is never copied anywhere.
        """
        import torch

        inputs = self.processor(
            text=[PROMPT.format(text=text)],
            voice_samples=[[str(reference)]],
            padding=True,
            return_tensors="pt",
            return_attention_mask=True,
        )
        for key, value in inputs.items():
            if torch.is_tensor(value):
                inputs[key] = value.to(self.device)

        with torch.no_grad():
            outputs = self.model.generate(
                **inputs,
                max_new_tokens=None,
                cfg_scale=self.cfg_scale,
                tokenizer=self.processor.tokenizer,
                generation_config={"do_sample": False},
                verbose=False,
            )

        if not outputs.speech_outputs or outputs.speech_outputs[0] is None:
            raise RuntimeError("model returned no audio for this line")
        return outputs.speech_outputs[0].float().cpu().numpy().reshape(-1)


class VoiceModelEngine:
    name = "voice_model"
    sample_rate = SAMPLE_RATE
    capabilities = {"native_rate": False, "max_speakers": 4}

    def __init__(self, model_path: str | None = None, revision: str = REVISION,
                 cfg_scale: float = DEFAULT_CFG_SCALE, ddpm_steps: int = DEFAULT_DDPM_STEPS,
                 device: str = "cpu"):
        self.revision = check_revision(revision)
        self.model_path = model_path
        self.cfg_scale = float(cfg_scale)
        self.ddpm_steps = int(ddpm_steps)
        self.device = device
        self._r: Renderer | None = None

    def identity(self) -> dict:
        return {"engine": self.name, "repo": REPO, "revision": self.revision, "fork": FORK_REPO,
                "fork_commit": FORK_COMMIT, "cfg": self.cfg_scale, "steps": self.ddpm_steps,
                "device": self.device, "prompt": PROMPT.format(text="<sentence>")}

    def load(self) -> None:
        path = resolve_model_path(self.model_path, self.revision)
        self._r = Renderer(path, self.device, self.ddpm_steps, self.cfg_scale)
        self._r.load()

    def render(self, text: str, ref: Path, seed: int):
        # Seeded exactly as voice_batch/render_takes.py did before each take.
        import numpy as np
        import torch
        torch.manual_seed(seed); np.random.seed(seed); random.seed(seed)  # noqa: E702
        return self._r.render(text, ref)
