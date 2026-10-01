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

"""Segments from a script file.

script.txt : blank-line paragraphs become segments. A paragraph whose
             first line starts "role:" (a role the cast or voice.txt
             declares) switches speaker from there on.
script.md  : the same, after markdown is reduced to its spoken text
             (spoken_text, lifted from factory voice_batch/lines.py: front
             matter, HTML comments, headings, quotes and tables are never
             spoken; ** and ` markers are dropped). "## Subtopic: <title>"
             headings start one segment per subtopic instead (the lesson
             linkage), each holding that subtopic's paragraphs.
"""
from __future__ import annotations

import re
from pathlib import Path

ROLE_LINE_RE = re.compile(r"^([a-z][a-z0-9_]{0,40}):\s*(.*)$")
SUBTOPIC_RE = re.compile(r"^##\s*Subtopic:\s*(.+?)\s*$", re.IGNORECASE)


def spoken_text(md: str) -> str:
    """The spoken text of a clip script: YAML front matter, headings, HTML
    comments and emphasis markers are metadata/markdown, never spoken."""
    md = md.replace("\r\n", "\n").lstrip("﻿")
    if md.startswith("---\n"):
        end = md.find("\n---", 4)
        if end != -1:
            md = md[end + 4:]
    md = re.sub(r"<!--.*?-->", " ", md, flags=re.S)
    keep = [ln for ln in md.split("\n") if not ln.lstrip().startswith(("#", ">", "|"))]
    text = " ".join(" ".join(keep).split())
    text = re.sub(r"(\*\*|`)(.+?)\1", r"\2", text)
    return text


def _paragraphs(text: str) -> list[str]:
    return [p for p in re.split(r"\n\s*\n", text.replace("\r\n", "\n")) if p.strip()]


def _strip_front_matter(md: str) -> str:
    md = md.replace("\r\n", "\n").lstrip("﻿")
    if md.startswith("---\n"):
        end = md.find("\n---", 4)
        if end != -1:
            md = md[end + 4:]
    return re.sub(r"<!--.*?-->", " ", md, flags=re.S)


def script_segments(path: Path, roles: set[str], default_role: str) -> list[dict]:
    """[{id, role, text, subtopic?}] in order. Raises ValueError when the
    script has nothing to say."""
    path = Path(path)
    raw = path.read_text(encoding="utf-8")
    md = path.suffix.lower() == ".md"
    body = _strip_front_matter(raw) if md else raw.replace("\r\n", "\n").lstrip("﻿")
    role = default_role
    segs: list[dict] = []

    def take_role(par: str) -> str:
        nonlocal role
        first, _, rest = par.partition("\n")
        m = ROLE_LINE_RE.match(first.strip())
        if m and m.group(1) in roles:
            role = m.group(1)
            return (m.group(2) + "\n" + rest).strip()
        return par

    def clean(par: str) -> str:
        return spoken_text(par) if md else " ".join(par.split())

    if md and any(SUBTOPIC_RE.match(ln.strip()) for ln in body.split("\n")):
        blocks: list[tuple[str, list[str]]] = []
        for ln in body.split("\n"):
            m = SUBTOPIC_RE.match(ln.strip())
            if m:
                blocks.append((m.group(1), []))
            elif blocks:
                blocks[-1][1].append(ln)
        for n, (title, lines) in enumerate(blocks, 1):
            pars = [clean(take_role(p)) for p in _paragraphs("\n".join(lines))]
            text = " ".join(p for p in pars if p)
            if text:
                segs.append({"id": f"subtopic_{n}", "role": role, "text": text, "subtopic": f"subtopic_{n}",
                             "title": title})
    else:
        for par in _paragraphs(body):
            text = clean(take_role(par))
            if text:
                segs.append({"id": f"s{len(segs) + 1:02d}", "role": role, "text": text})
    if not segs:
        raise ValueError(f"{path.name}: no spoken text")
    return segs
