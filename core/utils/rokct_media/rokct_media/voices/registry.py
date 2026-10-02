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

"""The caller's voices registry.

The package ships no voices. The caller supplies a voices file (TOML or
JSON) that names each voice id, its reference clip, the sha256 the clip
must have, the F0 gate window, and the owner's agreement flag:

    # voices.toml (in the caller's private store, never in this repo)
    [voice_a]
    ref = "lms/team/voice_refs/voice_a_ref.wav"   # relative to the voices root
    sha256 = "<64 hex>"
    f0_target_hz = 102
    f0_tolerance_hz = 8
    agreement_in_place = false     # set by the owner only
    # confirmed_by = "owner"       # optional: who set it
    # confirmed_on = 2026-10-01    # optional: when
    aliases = ["tutor_001"]

A relative ref resolves against the voices root: ROKCT_MEDIA_VOICES_ROOT,
else the voices file's own folder. A voice with an empty ref has no cloned
voice yet, and any render with it is refused. A ref whose bytes do not
match its sha256 stops the job before the model loads. The registry holds
no documents and no donor details.
"""
from __future__ import annotations

import datetime as _dt
import hashlib
import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

ID_RE = re.compile(r"[a-z][a-z0-9_]{0,40}")
SHA_RE = re.compile(r"[0-9a-f]{64}")
KEYS = {"ref", "sha256", "f0_target_hz", "f0_tolerance_hz", "agreement_in_place", "confirmed_by",
        "confirmed_on", "aliases"}


class VoiceError(ValueError):
    """A voices file or voice entry that cannot be used (exit 2)."""


class VoiceRefused(VoiceError):
    """A voice the engine must not render with (exit 3)."""


@dataclass
class Voice:
    id: str
    ref: Path | None
    sha256: str
    f0_target_hz: float
    f0_tolerance_hz: float
    agreement_in_place: bool = False
    confirmed_by: str | None = None
    confirmed_on: str | None = None
    aliases: list[str] = field(default_factory=list)

    def verify(self) -> str:
        """Check the reference's bytes against its pin; returns the sha256."""
        if self.ref is None:
            raise VoiceRefused(f"{self.id}: no reference registered (no cloned voice yet)")
        if not self.ref.is_file():
            raise VoiceError(f"{self.id}: reference not found at {self.ref}")
        h = hashlib.sha256()
        with open(self.ref, "rb") as f:
            for chunk in iter(lambda: f.read(1 << 20), b""):
                h.update(chunk)
        got = h.hexdigest()
        if got != self.sha256:
            raise VoiceRefused(f"{self.id}: reference sha256 does not match the registry; refusing to render")
        return got

    def summary(self) -> dict:
        """What result.json records about the voice (no paths, no people)."""
        out = {"id": self.id, "ref_sha256": self.sha256, "f0_target_hz": self.f0_target_hz,
               "f0_tolerance_hz": self.f0_tolerance_hz, "agreement_in_place": self.agreement_in_place}
        for k in ("confirmed_by", "confirmed_on"):
            if getattr(self, k):
                out[k] = getattr(self, k)
        return out


def _read(path: Path) -> dict:
    text = path.read_text(encoding="utf-8")
    if path.suffix.lower() == ".json":
        try:
            raw = json.loads(text)
        except json.JSONDecodeError as exc:
            raise VoiceError(f"{path.name}: not valid JSON ({exc.msg})") from None
        return raw.get("voices", raw) if isinstance(raw, dict) else raw
    import tomllib
    try:
        return tomllib.loads(text)
    except tomllib.TOMLDecodeError as exc:
        raise VoiceError(f"{path.name}: not valid TOML ({exc})") from None


def parse(raw: dict, root: Path) -> dict[str, Voice]:
    if not isinstance(raw, dict):
        raise VoiceError("the voices file must be a table of voice ids")
    voices: dict[str, Voice] = {}
    for vid, e in raw.items():
        if vid.startswith("_"):
            continue
        if not ID_RE.fullmatch(vid):
            raise VoiceError(f"voice id must match {ID_RE.pattern}: {vid!r}")
        if not isinstance(e, dict):
            raise VoiceError(f"{vid}: must be a table")
        unknown = set(e) - KEYS
        if unknown:
            raise VoiceError(f"{vid}: unknown field(s) {sorted(unknown)}")
        ref = str(e.get("ref", "") or "")
        sha = str(e.get("sha256", "") or "")
        if ref and not SHA_RE.fullmatch(sha):
            raise VoiceError(f"{vid}: sha256 must be 64 lowercase hex characters")
        for k in ("f0_target_hz", "f0_tolerance_hz"):
            if ref and not isinstance(e.get(k), (int, float)):
                raise VoiceError(f"{vid}: {k} must be a number")
        agree = e.get("agreement_in_place", False)
        if not isinstance(agree, bool):
            raise VoiceError(f"{vid}: agreement_in_place must be true or false")
        on = e.get("confirmed_on")
        if isinstance(on, (_dt.date, _dt.datetime)):
            on = on.isoformat()
        aliases = e.get("aliases", [])
        if not (isinstance(aliases, list) and all(isinstance(a, str) and ID_RE.fullmatch(a) for a in aliases)):
            raise VoiceError(f"{vid}: aliases must be a list of ids")
        p = None
        if ref:
            p = Path(ref)
            p = p if p.is_absolute() else root / p
        voices[vid] = Voice(id=vid, ref=p, sha256=sha, f0_target_hz=float(e.get("f0_target_hz") or 0),
                            f0_tolerance_hz=float(e.get("f0_tolerance_hz") or 0), agreement_in_place=agree,
                            confirmed_by=e.get("confirmed_by"), confirmed_on=on, aliases=list(aliases))
    seen: dict[str, str] = {}
    for v in voices.values():
        for a in v.aliases:
            if a in voices or a in seen:
                raise VoiceError(f"alias {a!r} of {v.id} is already a voice id or another voice's alias")
            seen[a] = v.id
    return voices


class Registry:
    def __init__(self, voices: dict[str, Voice], source: str = ""):
        self.voices = voices
        self.source = source
        self._alias = {a: v.id for v in voices.values() for a in v.aliases}

    @classmethod
    def load(cls, path: str | os.PathLike | None = None, root: str | os.PathLike | None = None) -> "Registry":
        path = path or os.environ.get("ROKCT_MEDIA_VOICES")
        if not path:
            return cls({}, "")
        p = Path(path)
        if not p.is_file():
            raise VoiceError(f"voices file not found: {p}")
        root = Path(root or os.environ.get("ROKCT_MEDIA_VOICES_ROOT") or p.resolve().parent)
        return cls(parse(_read(p), root), str(p))

    def get(self, vid: str) -> Voice:
        vid = self._alias.get(vid, vid)
        if vid not in self.voices:
            have = ", ".join(sorted(self.voices)) or "(none: pass --voices or set ROKCT_MEDIA_VOICES)"
            raise VoiceError(f"voice {vid!r} is not in the voices registry (registered: {have})")
        return self.voices[vid]
