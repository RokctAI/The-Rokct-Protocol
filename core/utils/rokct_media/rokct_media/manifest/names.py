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

"""File-name conventions: what a job folder holds, read from its file names.

Case-insensitive, any extension. A folder can work with no JSON at all;
job.json (optional) overrides what the names imply. The table is the
spec's "Naming conventions"; this version renders level 1 (speech) and
reports the rest so a folder that asks for more fails clearly.
"""

from __future__ import annotations

import re
from pathlib import Path

ROLE_ID_RE = re.compile(r"[a-z][a-z0-9_]{0,40}")

# role -> regex on the lower-cased file name
PATTERNS = {
    "script": r"script\.(txt|md)",
    "voice": r"voice\.txt",
    "job": r"job\.json",
    # level 2
    "music": r"(music|bed)\.[a-z0-9]+",
    "jingle": r"(jingle|sting)\.[a-z0-9]+",
    "intro": r"intro\.[a-z0-9]+",
    "outro": r"outro\.[a-z0-9]+",
    "sfx": r"sfx_.+\.[a-z0-9]+",
    "chapter": r"chapter_\d+\.(md|txt)",
    # level 3
    "background": r"background(_\d+)?\.[a-z0-9]+",
    "slide": r"(slide|board).*\.[a-z0-9]+",
    "image": r"image.*\.[a-z0-9]+",
    "video": r"video\.[a-z0-9]+",
    "scene": r"(manim_)?scene\.py",
    "captions": r"captions\.srt",
    "brief": r"brief\.json",
    # still composition
    "template": r"template\.[a-z0-9]+",
    "source": r"source\.[a-z0-9]+",
}
L2_ROLES = ("music", "jingle", "intro", "outro", "sfx", "chapter")
L3_ROLES = ("background", "slide", "image", "video", "scene")
S_ROLES = ("template", "source")


def scan(folder: Path) -> dict[str, list[Path]]:
    """{role: [files]} for the top level of a job folder (out/ and .work/
    are the engine's own and never read)."""
    found: dict[str, list[Path]] = {}
    for p in sorted(Path(folder).iterdir()):
        if not p.is_file():
            continue
        name = p.name.lower()
        for role, pat in PATTERNS.items():
            if re.fullmatch(pat, name):
                found.setdefault(role, []).append(p)
                break
    return found


def infer_preset(found: dict[str, list[Path]]) -> str | None:
    """The spec's "Choosing a preset with no JSON"; None means speech only."""
    has = lambda *roles: any(found.get(r) for r in roles)  # noqa: E731
    if has("template", "source") and not has("script"):
        return "social_post"
    if has("chapter"):
        return "audiobook"
    if has("scene"):
        return "lesson"
    if has("brief"):
        return "tiktok"
    if has(*L3_ROLES):
        return "reel"
    if has("music", "jingle", "intro", "outro", "sfx"):
        return "radio_ad"
    return None


def supported_level(found: dict[str, list[Path]], job: dict) -> int:
    """The highest level the folder (and job.json) asks for: 3, 2 or 1."""
    if any(found.get(r) for r in L3_ROLES) or job.get("visual"):
        return 3
    if any(found.get(r) for r in L2_ROLES) or any(
        job.get(k) for k in ("timeline", "music", "cues", "chapters")
    ):
        return 2
    return 1


def parse_voice_txt(text: str) -> dict[str, str]:
    """voice.txt: one registry id, or "role: id" lines for several speakers.
    Returns {role: voice id}; a bare id is the role "default"."""
    lines = [
        ln.strip()
        for ln in text.splitlines()
        if ln.strip() and not ln.strip().startswith("#")
    ]
    if not lines:
        raise ValueError("voice.txt is empty: name a registered voice id")
    if len(lines) == 1 and ":" not in lines[0]:
        vid = lines[0]
        if not ROLE_ID_RE.fullmatch(vid):
            raise ValueError(
                "voice.txt: a voice id is lower-case letters, digits and _"
            )
        return {"default": vid}
    cast: dict[str, str] = {}
    for ln in lines:
        role, sep, vid = (s.strip() for s in ln.partition(":"))
        if not sep or not ROLE_ID_RE.fullmatch(role) or not ROLE_ID_RE.fullmatch(vid):
            raise ValueError(
                "voice.txt: write one voice id, or one 'role: voice_id' per line"
            )
        if role in cast:
            raise ValueError(f"voice.txt: role {role!r} is listed twice")
        cast[role] = vid
    return cast
