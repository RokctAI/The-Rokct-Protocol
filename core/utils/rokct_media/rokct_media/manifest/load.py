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

"""Load a job folder: precedence merge, path resolve, level detect.

Values resolve in this order, highest first: CLI flags / API arguments ->
job.json -> file-name convention -> preset -> package defaults.
"""

from __future__ import annotations

import copy
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

from .. import profiles as _profiles
from ..models.voice_model import REVISION
from ..speech.takes import SEED_ROUNDS
from ..text import pronounce
from . import names, sources

SCHEMA_PATH = Path(__file__).resolve().parent / "job.schema.json"
DEFAULT_SPEECH = {
    "engine": "voice_model",
    "model_revision": REVISION,
    "cfg": 1.3,
    "steps": 10,
    "seed_rounds": [list(r) for r in SEED_ROUNDS],
    "selection": "f0_closest",
    "pace": 1.0,
    "tempo": 1.0,
    "asr_model": "small.en",
    "language": "en",
}
SINKS = ("local", "commit", "publish", "return")
IMPLEMENTED_SINKS = ("local", "return")
PUBLISHING_SINKS = ("publish",)
ID_RE = re.compile(r"[^a-z0-9_-]+")


class JobError(ValueError):
    """A manifest or input error (exit 2)."""


@dataclass
class Job:
    folder: Path
    id: str
    preset: str | None
    level: int
    cast: dict
    segments: list[dict]
    speech: dict
    pronunciations: dict
    output: dict
    deliver: list[dict]
    found: dict = field(default_factory=dict)

    @property
    def out_dir(self) -> Path:
        return self.folder / "out"

    @property
    def work_dir(self) -> Path:
        return self.folder / ".work"

    def voice_of(self, seg: dict) -> str:
        return self.cast[seg["role"]]["voice"]


def schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def validate_manifest(raw: dict) -> None:
    import jsonschema

    v = jsonschema.Draft202012Validator(schema())
    errs = sorted(v.iter_errors(raw), key=lambda e: list(e.path))
    if errs:
        e = errs[0]
        where = "/".join(str(p) for p in e.path) or "(top level)"
        raise JobError(
            f"job.json: {where}: {e.message}"
            + (f" (+{len(errs) - 1} more)" if len(errs) > 1 else "")
        )


def _sink(d) -> dict:
    if isinstance(d, str):
        return {"sink": d}
    if isinstance(d, dict) and isinstance(d.get("sink"), str):
        return dict(d)
    raise JobError(
        f'deliver: each entry is a sink name or {{"sink": name, ...}}, got {d!r}'
    )


def load_job(
    folder,
    *,
    level: int | None = None,
    preset: str | None = None,
    profiles: list[str] | None = None,
    deliver: list | None = None,
    speech: dict | None = None,
) -> Job:
    folder = Path(folder).resolve()
    if not folder.is_dir():
        raise JobError(f"job folder not found: {folder}")
    found = names.scan(folder)
    raw: dict = {}
    if found.get("job"):
        try:
            raw = json.loads(found["job"][0].read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise JobError(
                f"job.json is not valid JSON ({exc.msg}, line {exc.lineno})"
            ) from None
        validate_manifest(raw)

    job_id = raw.get("id") or ID_RE.sub("_", folder.name.lower()).strip("_-") or "job"
    preset = preset or raw.get("preset") or names.infer_preset(found)

    # Level: the highest the folder supports, capped by job.json or the CLI.
    sup = names.supported_level(found, raw)
    cap = level or raw.get("level")
    if cap is not None and cap > sup:
        raise JobError(
            f"level {cap} asked for, but the folder has no inputs for it (it supports level {sup})"
        )
    eff = cap or sup
    if eff > 1 or preset in ("social_post", "thumbnail", "slide_deck"):
        raise JobError(
            f"this job needs level {eff} ({preset or 'speech'}); this version of rokct-media renders "
            f'speech jobs (level 1) only. Set "level": 1 in job.json to render just its speech.'
        )

    # Cast: job.json, else voice.txt. The engine never guesses a voice.
    cast: dict = {}
    if raw.get("cast"):
        cast = {
            r: {
                "voice": c["voice"],
                **({"gain_db": c["gain_db"]} if "gain_db" in c else {}),
            }
            for r, c in raw["cast"].items()
        }
    elif found.get("voice"):
        try:
            cast = {
                r: {"voice": v}
                for r, v in names.parse_voice_txt(
                    found["voice"][0].read_text(encoding="utf-8")
                ).items()
            }
        except ValueError as exc:
            raise JobError(str(exc)) from None
    if not cast:
        raise JobError(
            'no voice: add voice.txt (one registered voice id) or "cast" in job.json'
        )
    default_role = (
        next(iter(cast))
        if len(cast) == 1
        else ("default" if "default" in cast else None)
    )

    # Segments: job.json segments, else segments_from, else script.*.
    segs: list[dict]
    if raw.get("segments"):
        segs = copy.deepcopy(raw["segments"])
        for s in segs:
            if "from_asset" in s:
                raise JobError(
                    f"segment {s['id']}: from_asset (reuse) is not in this version"
                )
            if not str(s.get("text", "")).strip():
                raise JobError(f"segment {s['id']}: no text")
            s.setdefault("role", default_role)
    else:
        sf_ = raw.get("segments_from")
        if sf_:
            split = sf_.get("split", "paragraphs")
            if split == "chapter_headings" or sf_.get("then"):
                raise JobError(
                    "segments_from: chapter splitting (audiobooks) is not in this version"
                )
            path = (folder / sf_["file"]).resolve()
            if not path.is_relative_to(folder) or not path.is_file():
                raise JobError(
                    f"segments_from.file must be a file inside the job folder: {sf_['file']}"
                )
            role = sf_.get("role", default_role)
        elif found.get("script"):
            if len(found["script"]) > 1:
                raise JobError("more than one script.* file: keep one")
            path, split, role = found["script"][0], None, default_role
        else:
            raise JobError(
                "nothing to say: add script.txt / script.md, or segments in job.json"
            )
        try:
            segs = sources.script_segments(path, set(cast), role)
        except ValueError as exc:
            raise JobError(str(exc)) from None
        if split == "subtopic_headings" and not any("subtopic" in s for s in segs):
            raise JobError(f"segments_from: {path.name} has no '## Subtopic:' headings")
        segs = [{k: v for k, v in s.items() if k != "title"} for s in segs]
    seen = set()
    for s in segs:
        if s["id"] in seen:
            raise JobError(f"segment id {s['id']!r} is used twice")
        seen.add(s["id"])
        if not s.get("role"):
            raise JobError(
                f"segment {s['id']}: no role, and the cast has more than one voice"
            )
        if s["role"] not in cast:
            raise JobError(f"segment {s['id']}: role {s['role']!r} is not in the cast")
        if s.get("tempo", 1.0) != 1.0:
            raise JobError(
                f"segment {s['id']}: tempo is not in this version (renders at 1.0)"
            )

    # Speech settings.
    sp = {
        **copy.deepcopy(DEFAULT_SPEECH),
        **copy.deepcopy(raw.get("speech", {})),
        **{k: v for k, v in (speech or {}).items() if v is not None},
    }
    if sp.get("tempo", 1.0) != 1.0 or sp.get("pace", 1.0) != 1.0:
        raise JobError(
            "speech.tempo and speech.pace other than 1.0 are not in this version"
        )
    if sp.get("reuse"):
        raise JobError("speech.reuse is not in this version")
    if sp["selection"] == "f0_closest":
        for s in segs:
            for k in ("takes", "prefer_seeds", "keep_through"):
                if k in s:
                    raise JobError(
                        f'segment {s["id"]}: {k} needs "speech": {{"selection": "whole_take"}}'
                    )
    else:
        for s in segs:
            if "takes" not in s and "takes" in sp:
                s["takes"] = sp["takes"]

    try:
        pron = pronounce.merge(pronounce.load(), raw.get("pronunciations"))
    except pronounce.PronunciationError as exc:
        raise JobError(f"pronunciations: {exc}") from None

    out = raw.get("output", {})
    profs = list(profiles or out.get("profiles") or ["clip_wav"])
    for p in profs:
        if p not in _profiles.PROFILES:
            raise JobError(f"unknown output profile {p!r}")
        if p not in _profiles.IMPLEMENTED:
            raise JobError(
                f"output profile {p!r} is not in this version (level {_profiles.PROFILES[p]['level']})"
            )
    formats = list(out.get("formats") or [])
    if "wav" not in formats:
        formats.insert(0, "wav")
    if "app_r3_mp3" in profs and "mp3" not in formats:
        formats.append("mp3")
    for f in formats:
        if f not in ("wav", "mp3", "json"):
            raise JobError(f"output format {f!r} is not a level-1 format")

    sinks = [
        _sink(d)
        for d in (
            deliver
            if deliver is not None
            else raw.get("deliver") or [{"sink": "local"}]
        )
    ]
    for s in sinks:
        if s["sink"] not in SINKS:
            raise JobError(f"unknown delivery sink {s['sink']!r}")

    return Job(
        folder=folder,
        id=job_id,
        preset=preset,
        level=1,
        cast=cast,
        segments=segs,
        speech=sp,
        pronunciations=pron,
        output={"profiles": profs, "formats": formats},
        deliver=sinks,
        found=found,
    )
