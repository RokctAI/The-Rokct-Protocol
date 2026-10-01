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

"""TTS engine protocol and the engine loader.

Built-in engines: "voice_model" (the pinned default) and "dummy" (tone
bursts, for tests). Other engines register through the entry-point group
"rokct_media.engines" and are found by name.
"""
from __future__ import annotations

from pathlib import Path
from typing import Protocol, runtime_checkable


@runtime_checkable
class TTSEngine(Protocol):
    name: str
    sample_rate: int
    capabilities: dict

    def load(self) -> None: ...

    def render(self, text: str, ref: Path, seed: int): ...

    def identity(self) -> dict: ...


class EngineError(RuntimeError):
    """An engine that cannot be used (unknown, unpinned or not installed)."""


def builtin(name: str):
    if name == "voice_model":
        from .voice_model import VoiceModelEngine
        return VoiceModelEngine
    if name == "dummy":
        from .dummy import DummyEngine
        return DummyEngine
    return None


def engine_class(name: str):
    cls = builtin(name)
    if cls is not None:
        return cls
    from importlib.metadata import entry_points
    for ep in entry_points(group="rokct_media.engines"):
        if ep.name == name:
            return ep.load()
    raise EngineError(f"unknown speech engine {name!r}")


def engine_identity(name: str, **opts) -> dict:
    """The engine's identity without loading it (cache keys, result.json)."""
    return engine_class(name)(**opts).identity()
