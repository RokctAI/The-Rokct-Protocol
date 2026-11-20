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


"""Text handling shared by the renderer and the QC gate.

Kept in step with factory voice_batch/textnorm.py (2026-11-20).

* split_sentences: a line is rendered one sentence at a time. A countdown
  ("in 3... 2... 1...") stays in one sentence: rendered alone, a bare "2..."
  never came back word-exact from the ASR.
* render_sentences: the sentences as rendered. A sentence of three words or
  fewer ("Listen.", "Yes!", "q, q, quack.") joins its neighbour: rendered
  alone, the model mostly gave dead air or babble the ASR heard as "Thanks
  for watching!" (606 of the 778 sentences without a word-exact take in
  Kavitha's Grade R failures; 576 of them three words or fewer).
* speak_text: punctuation-only changes for the TTS prompt (a spaced hyphen
  or dash is a pause, never "minus"; a colon is a comma). Words never change.
* tts_prompt: what the model is actually given for one sentence - the
  sentence plus TAIL_PAD, so the model does not stop on the last phoneme;
  a closing countdown's "1..." becomes "1.".
* norm_words / word_errors: the word-exact ASR check. Numbers, a few
  spelling variants and ASR homophones are normalised; everything else
  must match exactly.
"""

from __future__ import annotations

import difflib
import re

_SENT_RE = re.compile(r"(?<=[.!?])(?<!\d\.\.\.)\s+|(?<=\d\.\.\.)\s+(?!\d)")


def split_sentences(text: str) -> list[str]:
    return [s.strip() for s in _SENT_RE.split(" ".join(text.split())) if s.strip()]


SHORT_WORDS = 3


def render_sentences(text: str) -> list[str]:
    """split_sentences, with each short sentence joined to the one before
    it (the first one to the one after it)."""
    out: list[str] = []
    for s in split_sentences(text):
        if out and (
            len(s.split()) <= SHORT_WORDS or len(out[-1].split()) <= SHORT_WORDS
        ):
            out[-1] = f"{out[-1]} {s}"
        else:
            out.append(s)
    return out


def speak_text(sentence: str) -> str:
    s = sentence.replace("’", "'")
    s = s.replace(" — ", ", ").replace("—", ", ").replace(" – ", ", ")
    s = s.replace(" - ", ", ")
    s = re.sub(r":\s+", ", ", s)
    s = join_thousands(s)
    return " ".join(s.split())


def join_thousands(s: str) -> str:
    """'R1 200' and '1 753 m' (SA style, a space between digit groups) as
    one number. The model skips a split number entirely (heard 'a deposit
    of R' for 'R1 200'), and the ASR writes it unsplit."""
    return re.sub(r"(?<=\d)[ \u00a0\u202f](?=\d{3}(?!\d))", "", s)


# The model often stops generating on the final phoneme of its prompt, so a
# take lost the end of its last word (12 of 25 sentences in tutor_001's
# first Voice A lines). A trailing " ..." gives it
# something after that word: it comes out as a short silence, which the
# stitch trim then removes. Not a word, so the ASR check is unaffected.
TAIL_PAD = " ..."


# A sentence ending in a countdown ("takes over in 3... 2... 1...") gave the
# model "1... ..." to finish on: it dropped the "one" or ran on into seconds
# of babble (assistant_005's intro and handover lines, every seed). The
# last count ends the sentence with a full stop instead.
_END_COUNT_RE = re.compile(r"(\d)\.\.\.$")


def tts_prompt(sentence: str) -> str:
    s = _END_COUNT_RE.sub(r"\1.", sentence.rstrip())
    if s and s[-1] not in ".!?":
        s += "."
    return s + TAIL_PAD


_ONES = (
    "zero one two three four five six seven eight nine ten eleven twelve "
    "thirteen fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
_TENS = "_ _ twenty thirty forty fifty sixty seventy eighty ninety".split()


def _n2w(n: int) -> str:
    if n < 20:
        return _ONES[n]
    if n < 100:
        return _TENS[n // 10] + ("" if n % 10 == 0 else " " + _ONES[n % 10])
    if n < 1000:
        rest = n % 100
        return (
            _ONES[n // 100] + " hundred" + ("" if rest == 0 else " and " + _n2w(rest))
        )
    for size, name in ((10**9, "billion"), (10**6, "million"), (1000, "thousand")):
        if n >= size and n < size * 1000:
            rest = n % size
            return (
                _n2w(n // size)
                + " "
                + name
                + ("" if rest == 0 else (" and " if rest < 100 else " ") + _n2w(rest))
            )
    return str(n)


# British/American spelling pairs the ASR model may pick either way.
_SPELLING = {
    "practice": "practise",
    "factorize": "factorise",
    "factorizing": "factorising",
    "factorized": "factorised",
    "recognize": "recognise",
    "organize": "organise",
    "okay": "ok",
    "meter": "metre",
    "meters": "metres",
    "centimeter": "centimetre",
    "centimeters": "centimetres",
    "millimeter": "millimetre",
    "millimeters": "millimetres",
    "kilometer": "kilometre",
    "kilometers": "kilometres",
    "liter": "litre",
    "liters": "litres",
    "milliliter": "millilitre",
    "milliliters": "millilitres",
    "color": "colour",
    "colors": "colours",
    "center": "centre",
    "centers": "centres",
}

# Homophones the ASR model writes for a correctly spoken word (a sentence-
# final "guessed" comes back as "guest"). Applied to both sides, so either
# spelling matches the other; keep this to true sound-alikes.
_HOMOPHONES = {"guest": "guessed"}


def norm_words(text: str) -> list[str]:
    s = join_thousands(text.lower().replace("’", "'").replace("'", ""))
    s = re.sub(r"(?<=\d),(?=\d{3}(?!\d))", "", s)
    s = (
        s.replace("×", " times ")
        .replace("²", " squared ")
        .replace("−", "-")
        .replace("%", " percent ")
    )
    s = re.sub(r"(^|[\s(=,])-\s*(?=\d)", r"\1 minus ", s)
    s = re.sub(r"(\d)([a-z])", r"\1 \2", s)
    s = re.sub(r"\d+", lambda m: " " + _n2w(int(m.group())) + " ", s)
    s = re.sub(r"[^a-z ]", " ", s)
    return [
        _HOMOPHONES.get(w, w) for w in (_ise(_SPELLING.get(w, w)) for w in s.split())
    ]


# -ize/-ise (organizing, summarize, organization): the ASR writes American,
# the scripts British. Both sides fold to -is-.
_IZE_RE = re.compile(r"(?<=\w\w)iz(e|es|ed|ing|ation|ations|er|ers)$")


def _ise(w: str) -> str:
    return _IZE_RE.sub(r"is\1", w)


def _compounds(a: list[str], b: list[str]) -> list[str]:
    """b with each word that is two adjacent words of a run together
    ("markup" for "mark-up", "crosscast" for "cross-cast") split back into
    those two words."""
    pairs = {x + y: (x, y) for x, y in zip(a, a[1:])}
    out: list[str] = []
    for w in b:
        out.extend(pairs[w] if w in pairs and w not in a else (w,))
    return out


def word_errors(reference: str, hypothesis: str) -> int:
    a, b = norm_words(reference), norm_words(hypothesis)
    b = _compounds(a, b)
    a = _compounds(b, a)
    sm = difflib.SequenceMatcher(None, a, b, autojunk=False)
    return sum(
        max(i2 - i1, j2 - j1)
        for op, i1, i2, j1, j2 in sm.get_opcodes()
        if op != "equal"
    )
