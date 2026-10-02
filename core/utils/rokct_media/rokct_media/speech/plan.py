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

"""What the engine is given for a segment, and what the gate checks it against.

Two selections, both lifted from factory:

* "f0_closest" (voice_batch/lines.py, the tutor batches): the segment is
  split into sentences; each sentence's render text is the pronounced text
  through speak_text (a spaced dash or a colon becomes a comma). Takes are
  chosen per sentence, so the shipped clip may join different seeds.
* "whole_take" (PR #196 reel_voice.py): the segment is split into
  sentences and any sentence of two words or fewer joins its neighbour; one
  seed renders every part, and the stitched take is gated as a whole. This
  is the mode that supports takes > 1, prefer_seeds and keep_through.

In both, the display text (inline {{display|spoken}} resolved to the
display part) is the ASR reference and every respelled word is a wildcard.
"""

from __future__ import annotations

import hashlib

from ..text import norm as textnorm
from ..text import pronounce as pronunciations
from ..text.norm import speak_text, split_sentences
from .cut import text_through
from .takes import SEED_ROUNDS, all_seeds, seed_rounds

SELECTIONS = ("f0_closest", "whole_take")


class PlanError(ValueError):
    pass


def pronounced_fields(id_: str, text: str, pron: dict | None) -> dict:
    """The text fields every per-sentence item carries, with pronunciations
    applied sentence by sentence (voice_batch/lines.py, verbatim).

    text        display text: inline markup resolved to the display word
    sentences   display sentences (the per-take ASR reference)
    render_text what the TTS is given, one per sentence
    sentence_wild / asr_wild  the respelled words the ASR check wildcards
    tts_text    only when a pronunciation changed the spoken text"""
    try:
        parts = [pronunciations.apply(s, pron) for s in split_sentences(text)]
    except pronunciations.PronunciationError as exc:
        raise pronunciations.PronunciationError(f"segment {id_}: {exc}") from None
    display = " ".join(p[0] for p in parts)
    render = [speak_text(p[1]) for p in parts]
    out = {
        "text": display,
        "source_text": text,
        "text_sha256": hashlib.sha256(display.encode("utf-8")).hexdigest(),
        "render_sha256": hashlib.sha256("\n".join(render).encode("utf-8")).hexdigest(),
        "sentences": [p[0] for p in parts],
        "render_text": render,
        "sentence_wild": [p[2] for p in parts],
        "asr_text": display,
        "asr_wild": [w for p in parts for w in p[2]],
        "pronounced": [w[0] for p in parts for w in p[2]],
    }
    tts = " ".join(p[1] for p in parts)
    if tts != display:
        out["tts_text"] = tts
    return out


def render_parts(text: str) -> list[str]:
    """Sentences to render one at a time; a sentence of two words or fewer
    joins the next one (the previous one when it is last)."""
    parts = textnorm.split_sentences(text)
    while len(parts) > 1:
        short = next((i for i, s in enumerate(parts) if len(s.split()) <= 2), None)
        if short is None:
            break
        j = short + 1 if short + 1 < len(parts) else short - 1
        a, b = sorted((short, j))
        parts[a : b + 1] = [f"{parts[a]} {parts[b]}"]
    return parts


def ambiguous_check(seg_id: str, text: str, pron: dict) -> None:
    for w in pronunciations.ambiguous_uses(text, pron):
        raise PlanError(pronunciations.ambiguous_error(seg_id, w, pron))


def sentence_item(seg: dict, pron: dict) -> dict:
    """A per-sentence ("f0_closest") item for one segment."""
    ambiguous_check(seg["id"], seg["text"], pron)
    try:
        f = pronounced_fields(seg["id"], " ".join(str(seg["text"]).split()), pron)
    except pronunciations.PronunciationError as exc:
        raise PlanError(str(exc)) from None
    if not f["sentences"]:
        raise PlanError(f"segment {seg['id']}: empty text")
    return {"id": seg["id"], **f}


def whole_take_line(seg: dict, pron: dict, rounds=SEED_ROUNDS) -> dict:
    """A whole-take line for one segment (reel_voice.load_batch, per line)."""
    seeds = all_seeds(rounds)
    ln = {"id": seg["id"], "text": seg["text"], "takes": seg.get("takes", 1)}
    for k in ("keep_through", "prefer_seeds"):
        if k in seg:
            ln[k] = seg[k]
    if not str(ln["text"]).strip():
        raise PlanError(f"segment {ln['id']}: empty text")
    if not (isinstance(ln["takes"], int) and 1 <= ln["takes"] <= len(seeds)):
        raise PlanError(f"segment {ln['id']}: takes must be 1-{len(seeds)}")
    try:
        said = [pronunciations.apply(p, pron) for p in render_parts(ln["text"])]
    except pronunciations.PronunciationError as exc:
        raise PlanError(f"segment {ln['id']}: {exc}") from None
    ambiguous_check(ln["id"], ln["text"], pron)
    # "text" and "parts" are the display text (the ASR reference);
    # "tts_parts" is what the model is given.
    ln["source_text"] = ln["text"]
    ln["parts"] = [d for d, _, _ in said]
    ln["text"] = " ".join(ln["parts"])
    ln["tts_parts"] = [t for _, t, _ in said]
    ln["part_wild"] = [w for _, _, w in said]
    ln["wild"] = [x for w in ln["part_wild"] for x in w]
    prefer = ln.get("prefer_seeds", [])
    if not (
        isinstance(prefer, list)
        and all(s in seeds for s in prefer)
        and len(set(prefer)) == len(prefer)
    ):
        raise PlanError(
            f"segment {ln['id']}: prefer_seeds must be distinct seeds from {seeds}"
        )
    ln["rounds"] = seed_rounds(prefer, rounds)
    if "keep_through" in ln and text_through(ln["text"], ln["keep_through"]) is None:
        raise PlanError(
            f"segment {ln['id']}: keep_through {ln['keep_through']!r} is not a word of its text"
        )
    return ln
