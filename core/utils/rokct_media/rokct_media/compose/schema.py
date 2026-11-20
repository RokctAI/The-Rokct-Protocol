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

"""Load, validate and fill defaults for an ad JSON.

Validation has two layers:

1. JSON Schema (schema/ad.schema.json) for shape and ranges.
2. Semantic checks the schema cannot express: every speaker is cast, the
   format matches the script, referenced files exist, sfx anchors are valid.

`load_ad()` returns a plain dict with every default filled in and every
path resolved to an absolute path, so the rest of the pipeline never has to
guess.
"""
from __future__ import annotations

import copy
import json
import os
import re
from pathlib import Path

# The caller's folder (factory: radio_ads/), for default voices/ and cache/
# and for relative paths in an ad. The schema ships inside the package.
ROOT = Path(os.environ.get("ROKCT_MEDIA_COMPOSE_ROOT") or Path.cwd()).resolve()
SCHEMA_PATH = Path(__file__).resolve().parent / "ad.schema.json"
DEFAULT_VOICES_DIR = ROOT / "voices"

BUILTIN_BEDS = ("upbeat", "calm", "corporate")
BUILTIN_SFX = ("ding", "hooter", "whoosh")
WORDS_PER_SECOND = 2.6          # brisk ad read, used only for the estimate warning
MAX_JOINT_SPEAKERS = 4          # VibeVoice-1.5B supports up to 4 voices in one pass


class AdError(ValueError):
    """The ad JSON is invalid. The message lists every problem found."""


def load_schema() -> dict:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def _defaults_from_schema(schema: dict, node: dict) -> dict:
    """Return {prop: default} for an object schema node (one level)."""
    out = {}
    for name, sub in node.get("properties", {}).items():
        if "$ref" in sub:
            sub = _resolve_ref(schema, sub["$ref"])
        if "default" in sub:
            out[name] = copy.deepcopy(sub["default"])
    return out


def _resolve_ref(schema: dict, ref: str) -> dict:
    assert ref.startswith("#/"), ref
    node = schema
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def _fill(schema: dict, defname: str, value: dict | None) -> dict:
    node = schema["$defs"][defname]
    out = _defaults_from_schema(schema, node)
    out.update(value or {})
    return out


def _resolve_path(p: str, ad_dir: Path) -> Path:
    """Relative paths are tried against the ad's folder, then radio_ads/."""
    path = Path(p).expanduser()
    if path.is_absolute():
        return path
    for base in (ad_dir, ROOT):
        cand = (base / path).resolve()
        if cand.exists():
            return cand
    return (ad_dir / path).resolve()


def estimate_speech_seconds(text: str) -> float:
    return len(text.split()) / WORDS_PER_SECOND


def validate_shape(doc: dict) -> list[str]:
    import jsonschema

    schema = load_schema()
    validator = jsonschema.Draft202012Validator(schema)
    errors = []
    for err in sorted(validator.iter_errors(doc), key=lambda e: list(e.path)):
        where = "/".join(str(p) for p in err.path) or "(root)"
        errors.append(f"{where}: {err.message}")
    return errors


def load_ad(path: str | Path, voices_dir: Path | None = None) -> tuple[dict, list[str]]:
    """Validate and normalise an ad file. Returns (ad, warnings).

    Raises AdError listing every problem when the file is not renderable.
    """
    path = Path(path).resolve()
    voices_dir = Path(voices_dir or DEFAULT_VOICES_DIR).resolve()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise AdError(f"{path.name}: not valid JSON: {exc}") from exc
    if not isinstance(raw, dict):
        raise AdError(f"{path.name}: top level must be an object")

    errors = validate_shape(raw)
    if errors:
        raise AdError(f"{path.name}: schema errors:\n  - " + "\n  - ".join(errors))

    schema = load_schema()
    ad = copy.deepcopy(raw)
    ad_dir = path.parent
    warnings: list[str] = []

    ad["music"] = _fill(schema, "music", raw.get("music"))
    ad["timing"] = _fill(schema, "timing", raw.get("timing"))
    ad["render"] = _fill(schema, "render", raw.get("render"))
    ad["output"] = _fill(schema, "output", raw.get("output"))
    ad["script"] = [_fill(schema, "segment", s) for s in raw["script"]]
    ad["sfx"] = [_fill(schema, "sfx", s) for s in raw.get("sfx") or []]
    tag = raw.get("tag")
    if tag:
        tag = _fill(schema, "tag", tag)
        if "rate" not in tag:
            tag["rate"] = 1.2 if tag["fast"] else 1.0
    ad["tag"] = tag or None

    # --- cast -> reference wav --------------------------------------------
    cast = {}
    for role, member in raw["cast"].items():
        member = dict(member)
        member.setdefault("gain_db", 0.0)
        if "voice" in member:
            ref = voices_dir / f"{member['voice']}.wav"
            member["source"] = f"voice:{member['voice']}"
            spec = voices_dir / f"{member['voice']}.voice.json"
            if spec.exists():
                try:
                    member["spec"] = json.loads(spec.read_text(encoding="utf-8"))
                except json.JSONDecodeError:
                    warnings.append(f"cast.{role}: {spec.name} is not valid JSON; ignored")
        else:
            ref = _resolve_path(member["ref"], ad_dir)
            member["source"] = f"ref:{member['ref']}"
        if not ref.exists():
            hint = (" - copy it from the agent repo, see voices/README.md"
                    if "voice" in member else "")
            errors.append(f"cast.{role}: reference audio not found: {ref}{hint}")
        member["ref_path"] = str(ref)
        cast[role] = member
    ad["cast"] = cast

    # --- script ------------------------------------------------------------
    speakers_in_order: list[str] = []
    for i, seg in enumerate(ad["script"]):
        seg["text"] = _clean_text(seg["text"])
        if not seg["text"]:
            errors.append(f"script/{i}: text is empty after cleaning")
        if re.match(r"^\s*speaker\s*\d+\s*:", seg["text"], re.I):
            errors.append(f"script/{i}: text must not start with 'Speaker N:'")
        if seg["speaker"] not in cast:
            errors.append(f"script/{i}: speaker '{seg['speaker']}' is not in cast "
                          f"({', '.join(cast)})")
        elif seg["speaker"] not in speakers_in_order:
            speakers_in_order.append(seg["speaker"])
    if ad["tag"]:
        ad["tag"]["text"] = _clean_text(ad["tag"]["text"])
        if ad["tag"]["speaker"] not in cast:
            errors.append(f"tag: speaker '{ad['tag']['speaker']}' is not in cast")

    fmt = ad["format"]
    if fmt == "single-voice" and len(speakers_in_order) != 1:
        errors.append(f"format single-voice needs exactly one speaker in the script, "
                      f"found {len(speakers_in_order)}: {speakers_in_order}")
    if fmt == "dialogue" and len(speakers_in_order) < 2:
        errors.append("format dialogue needs at least two speakers in the script")

    mode = ad["render"]["mode"]
    if mode == "auto":
        mode = "joint" if fmt == "dialogue" else "per_line"
    if mode == "joint" and len(speakers_in_order) > MAX_JOINT_SPEAKERS:
        errors.append(f"render.mode joint supports at most {MAX_JOINT_SPEAKERS} speakers")
    ad["render"]["resolved_mode"] = mode

    unused = [r for r in cast if r not in speakers_in_order
              and not (ad["tag"] and ad["tag"]["speaker"] == r)]
    if unused:
        warnings.append(f"cast members never used: {', '.join(unused)}")

    # --- music ---------------------------------------------------------------
    bed = ad["music"]["bed"]
    if bed == "none":
        pass
    elif bed.startswith("builtin:"):
        if bed.split(":", 1)[1] not in BUILTIN_BEDS:
            errors.append(f"music.bed: unknown built-in '{bed}', choose from "
                          + ", ".join("builtin:" + b for b in BUILTIN_BEDS))
    else:
        p = _resolve_path(bed, ad_dir)
        if not p.exists():
            errors.append(f"music.bed: file not found: {p}")
        ad["music"]["bed_path"] = str(p)

    # --- sfx -------------------------------------------------------------------
    for i, fx in enumerate(ad["sfx"]):
        has_at, has_seg = "at_s" in fx, "segment" in fx
        if has_at == has_seg:
            errors.append(f"sfx/{i}: give exactly one of 'at_s' or 'segment'")
        if has_seg:
            s = fx["segment"]
            if s == -1 and not ad["tag"]:
                errors.append(f"sfx/{i}: segment -1 means the tag, but there is no tag")
            elif s != -1 and not (0 <= s < len(ad["script"])):
                errors.append(f"sfx/{i}: segment {s} out of range 0..{len(ad['script']) - 1}")
        f = fx["file"]
        if f.startswith("builtin:"):
            if f.split(":", 1)[1] not in BUILTIN_SFX:
                errors.append(f"sfx/{i}: unknown built-in '{f}', choose from "
                              + ", ".join("builtin:" + b for b in BUILTIN_SFX))
        else:
            p = _resolve_path(f, ad_dir)
            if not p.exists():
                errors.append(f"sfx/{i}: file not found: {p}")
            fx["path"] = str(p)

    # --- rough timing estimate ---------------------------------------------------
    est = sum(estimate_speech_seconds(s["text"]) / s["rate"] + s["pause_after_s"]
              for s in ad["script"])
    if ad["tag"]:
        est += ad["tag"]["gap_before_s"] + estimate_speech_seconds(ad["tag"]["text"]) / ad["tag"]["rate"]
    budget = ad["duration_s"] - ad["music"]["intro_s"] - ad["music"]["outro_min_s"]
    ad["estimate_speech_s"] = round(est, 2)
    if est > budget * (1 + ad["timing"]["max_stretch"]) + 0.5:
        warnings.append(f"script looks long: ~{est:.1f}s of speech for a {budget:.1f}s "
                        f"voice window ({ad['duration_s']}s spot); expect it to run over")
    elif est < budget * 0.6:
        warnings.append(f"script looks short: ~{est:.1f}s of speech for a {budget:.1f}s voice window")

    if errors:
        raise AdError(f"{path.name}:\n  - " + "\n  - ".join(errors))
    ad["_source_path"] = str(path)
    return ad, warnings


def _clean_text(text: str) -> str:
    text = " ".join(str(text).split())
    # Curly quotes and dashes the tokenizer handles poorly.
    return (text.replace("’", "'").replace("‘", "'")
                .replace("“", '"').replace("”", '"')
                .replace("—", ", ").replace("–", "-"))
