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

"""Pronunciation fixes for every batch kind: a global word list plus inline
per-line respellings.

rokct_media/text/pronunciations.json (package data, lifted from factory
voice_batch), with a job's own "pronunciations" merged over it (merge()):

  "words":     {"<word>": "<respelling>"}  every whole-word use of <word>
               (any case) is spoken as <respelling>.
  "ambiguous": {"<word>": ["<variant>", ...]}  a word (usually a name)
               with more than one right pronunciation for the same
               spelling. The global list never touches it; a line that
               uses it must say which one it means inline, or the batch
               fails.

Inline, in a line's script: {{Thendo|TEN-doh}}. The TTS text gets the part
after the bar; the display text (what the manifest records) and the ASR
reference get the part before it. Inline always wins over the global list.
Any respelling is allowed inline, not only a listed variant.

Only the TTS text changes. The QC gate checks the line against the display
text, and every display word that was respelled (inline or global) is a
wildcard there: it matches 1 to N words of the transcript, N = the larger
of its display and respelling word counts, plus one. Every other word stays
word-exact.

R-3 phonics respellings (r3_respellings.json) are a separate, whole-line
file; this runs after them, on the respelled text.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from .norm import norm_words, word_errors

PRONUNCIATIONS = Path(__file__).resolve().parent / "pronunciations.json"

# {{display|spoken}}: neither part may hold braces, a bar or sentence-ending
# punctuation (lines are split into sentences before the markup is resolved).
INLINE_RE = re.compile(r"\{\{([^{}|.!?]+)\|([^{}|.!?]+)\}\}")
WORD_RE = re.compile(r"[^\W\d_](?:[\w'’ -]*[^\W_])?")
SPOKEN_RE = re.compile(r"[^{}|.!?\n]+")


class PronunciationError(ValueError):
    pass


def _clean(s: str) -> str:
    return " ".join(s.split())


def empty() -> dict:
    return {"words": {}, "ambiguous": {}}


def validate(raw) -> dict:
    """The file's content, checked. Raises PronunciationError."""
    if not isinstance(raw, dict):
        raise PronunciationError("pronunciations must be a JSON object")
    unknown = set(raw) - {"words", "ambiguous"} - {k for k in raw if k.startswith("_")}
    if unknown:
        raise PronunciationError(f"unknown field(s): {sorted(unknown)}")
    words, amb = raw.get("words", {}), raw.get("ambiguous", {})
    if not isinstance(words, dict) or not isinstance(amb, dict):
        raise PronunciationError('"words" and "ambiguous" must be objects')
    out = empty()
    for w, r in words.items():
        if not isinstance(w, str) or not WORD_RE.fullmatch(w):
            raise PronunciationError(f"words: bad word {w!r}")
        if not isinstance(r, str) or not SPOKEN_RE.fullmatch(r) or not r.strip():
            raise PronunciationError(
                f"words: bad respelling for {w!r} (no braces, bars or . ! ?)"
            )
        out["words"][w] = _clean(r)
    for w, vs in amb.items():
        if not isinstance(w, str) or not WORD_RE.fullmatch(w):
            raise PronunciationError(f"ambiguous: bad word {w!r}")
        if (
            not isinstance(vs, list)
            or len(vs) < 2
            or not all(
                isinstance(v, str) and SPOKEN_RE.fullmatch(v) and v.strip() for v in vs
            )
        ):
            raise PronunciationError(
                f"ambiguous: {w!r} needs a list of at least two respellings"
            )
        out["ambiguous"][w] = [_clean(v) for v in vs]
    both = {w.lower() for w in out["words"]} & {w.lower() for w in out["ambiguous"]}
    if both:
        raise PronunciationError(f"in both words and ambiguous: {sorted(both)}")
    return out


def merge(base: dict, job: dict | None) -> dict:
    """A job's "words" / "ambiguous" maps over the global list. A job entry
    replaces a global one for the same word (any case), in either map."""
    if not job:
        return base
    job = validate(job)
    out = empty()
    drop = {w.lower() for w in list(job["words"]) + list(job["ambiguous"])}
    for k in ("words", "ambiguous"):
        out[k] = {w: v for w, v in base[k].items() if w.lower() not in drop}
        out[k].update(job[k])
    return validate(out)


def load(path: str | Path = PRONUNCIATIONS) -> dict:
    p = Path(path)
    if not p.is_file():
        return empty()
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise PronunciationError(f"{p.name} is not valid JSON ({exc.msg})") from None
    return validate(raw)


def _word_re(word: str) -> re.Pattern:
    return re.compile(rf"(?<![\w]){re.escape(word)}(?![\w])", re.IGNORECASE)


def _segments(text: str) -> list[tuple[str, str | None]]:
    """[(plain text, None) | (display, spoken)] in order. Raises on markup
    that is not exactly {{display|spoken}}."""
    out, pos = [], 0
    for m in INLINE_RE.finditer(text):
        out.append((text[pos : m.start()], None))
        d, s = _clean(m.group(1)), _clean(m.group(2))
        if not d or not s:
            raise PronunciationError(
                "malformed inline respelling (an empty part): write {{word|respelling}}"
            )
        out.append((d, s))
        pos = m.end()
    out.append((text[pos:], None))
    for plain, spoken in out:
        if spoken is None and has_markup(plain):
            # Never quote the line: errors reach public CI logs.
            raise PronunciationError(
                "malformed inline respelling (a brace outside "
                "{{word|respelling}}): write {{word|respelling}}"
            )
    return out


def has_markup(text: str) -> bool:
    return "{" in text or "}" in text


def display_text(text: str) -> str:
    """The text with every {{display|spoken}} resolved to its display part."""
    return _clean("".join(p for p, _ in _segments(text)))


def apply(text: str, pron: dict | None = None) -> tuple[str, str, list[list[str]]]:
    """(display, tts, wild) for one line or sentence.

    display: inline markup resolved to the display part; nothing else changes.
    tts:     inline markup resolved to the spoken part, then every global
             "words" entry replaced outside inline markup.
    wild:    [[display word, respelling], ...] in order, for the ASR wildcard."""
    pron = pron or empty()
    words = sorted(pron["words"].items(), key=lambda kv: -len(kv[0]))
    disp, tts, wild = [], [], []
    for plain, spoken in _segments(text):
        if spoken is not None:
            disp.append(plain)
            tts.append(spoken)
            wild.append([plain, spoken])
            continue
        disp.append(plain)
        hits = []
        for w, r in words:
            for m in _word_re(w).finditer(plain):
                if not any(a < m.end() and m.start() < b for a, b, _, _ in hits):
                    hits.append((m.start(), m.end(), m.group(0), r))
        hits.sort()
        out, pos = [], 0
        for a, b, found, r in hits:
            out += [plain[pos:a], r]
            wild.append([found, r])
            pos = b
        out.append(plain[pos:])
        tts.append("".join(out))
    return _clean("".join(disp)), _clean("".join(tts)), wild


def ambiguous_uses(text: str, pron: dict | None = None) -> list[str]:
    """Ambiguous words the text uses outside inline markup, in order."""
    pron = pron or empty()
    found = []
    for plain, spoken in _segments(text):
        if spoken is not None:
            continue
        for w in pron["ambiguous"]:
            for m in _word_re(w).finditer(plain):
                found.append((m.start(), w))
    seen, out = set(), []
    for _, w in sorted(found):
        if w not in seen:
            seen.add(w)
            out.append(w)
    return out


def ambiguous_error(line_id: str, word: str, pron: dict) -> str:
    choices = " or ".join(f"{{{{{word}|{v}}}}}" for v in pron["ambiguous"][word])
    return f"line {line_id} uses {word!r}: write {choices}"


def check_ambiguous(items: list[dict], pron: dict | None = None) -> list[str]:
    """One error per (line, ambiguous word) left unresolved. Items carry the
    raw script text (with markup) in "source_text"."""
    pron = pron or empty()
    errs = []
    for it in items:
        for w in ambiguous_uses(it.get("source_text", it["text"]), pron):
            errs.append(ambiguous_error(it["id"], w, pron))
    return errs


# ---------------------------------------------------------------------------
# ASR comparison with wildcards
# ---------------------------------------------------------------------------


def _wild_tokens(reference: str, wild: list[list[str]]) -> list:
    """norm_words(reference), with each respelled word's tokens folded into
    one ('*', max tokens) entry."""
    ref = norm_words(reference)
    specs = []
    for d, s in wild or []:
        dt = norm_words(d)
        if dt:
            specs.append((dt, max(len(dt), len(norm_words(s))) + 1))
    specs.sort(key=lambda x: -len(x[0]))
    out, i = [], 0
    while i < len(ref):
        for dt, n in specs:
            if ref[i : i + len(dt)] == dt:
                out.append(("*", n))
                i += len(dt)
                break
        else:
            out.append(ref[i])
            i += 1
    return out


def word_errors_wild(
    reference: str, hypothesis: str, wild: list[list[str]] | None = None
) -> int:
    """textnorm.word_errors, except that each respelled display word matches
    1 to N transcript words at no cost. With no wildcards it IS word_errors."""
    if not wild:
        return word_errors(reference, hypothesis)
    ref, hyp = _wild_tokens(reference, wild), norm_words(hypothesis)
    if not any(isinstance(t, tuple) for t in ref):
        return word_errors(reference, hypothesis)
    inf = float("inf")
    # d[i][j]: errors aligning ref[:i] with hyp[:j] (edit distance).
    d = [[inf] * (len(hyp) + 1) for _ in range(len(ref) + 1)]
    d[0] = list(range(len(hyp) + 1))
    for i, t in enumerate(ref, 1):
        d[i][0] = d[i - 1][0] + 1
        for j in range(1, len(hyp) + 1):
            best = min(d[i - 1][j] + 1, d[i][j - 1] + 1)
            if isinstance(t, tuple):
                for k in range(1, min(t[1], j) + 1):
                    best = min(best, d[i - 1][j - k])
            else:
                best = min(best, d[i - 1][j - 1] + (t != hyp[j - 1]))
            d[i][j] = best
    return int(d[-1][-1])
