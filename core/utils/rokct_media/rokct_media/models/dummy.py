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

"""A model-free engine for tests: one tone burst per word, seeded.

Deterministic for a given text and seed, 24 kHz mono, with a short
silence at the end (so a take ends cleanly). Needs numpy only.
"""
from __future__ import annotations

import hashlib
from pathlib import Path

SAMPLE_RATE = 24_000


class DummyEngine:
    name = "dummy"
    sample_rate = SAMPLE_RATE
    capabilities = {"native_rate": False, "max_speakers": 4}

    def __init__(self, f0_hz: float = 110.0, **_ignored):
        self.f0_hz = float(f0_hz)

    def identity(self) -> dict:
        return {"engine": self.name, "f0_hz": self.f0_hz}

    def load(self) -> None:
        pass

    def render(self, text: str, ref: Path, seed: int):
        import numpy as np
        words = max(1, len(text.split()))
        h = int.from_bytes(hashlib.sha256(f"{seed}|{text}".encode()).digest()[:4], "big")
        rng = np.random.default_rng(h)
        sr = SAMPLE_RATE
        out = [np.zeros(int(0.05 * sr), dtype=np.float32)]
        for _ in range(words):
            n = int(sr * (0.18 + 0.08 * rng.random()))
            t = np.arange(n) / sr
            env = np.sin(np.pi * np.arange(n) / n) ** 2
            out.append((0.3 * env * np.sin(2 * np.pi * self.f0_hz * t)).astype(np.float32))
            out.append(np.zeros(int(0.06 * sr), dtype=np.float32))
        out.append(np.zeros(int(0.2 * sr), dtype=np.float32))
        return np.concatenate(out)
