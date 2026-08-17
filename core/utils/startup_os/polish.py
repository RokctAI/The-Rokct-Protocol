# Copyright (c) 2026 RokctAI
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

"""Opt-in AI language polish with a hard number firewall.

The compiler is deterministic on purpose: every figure in a generated document
is traceable to `questions.md` or a compliance file. An LLM rephrasing pass is
the one place where that guarantee could silently die — a model that "tidies"
`R 4,800,000` into `R4.8m`, or hallucinates a growth rate, corrupts the very
numbers the rest of the engine goes to such lengths to keep honest.

So this module is built around one invariant: **no digit ever leaves the
machine, and no digit in a document can be changed by the model.**

1.  Documents are segmented. Tables, code fences, headings, blockquotes (which
    include the Document Control block and every compiler callout), lists,
    Evidence & Provenance, Completion Gaps, compliance/B-BBEE sections,
    cross-link footers and the entire financial-model / compliance-log files
    are never sent. When in doubt a block is treated as ineligible.
2.  In eligible prose, every numeric token — currency amounts, percentages,
    dates, phone numbers, registration numbers, bare counts — is replaced by
    an opaque placeholder before the text leaves the process. Placeholders are
    deliberately letter-indexed (`⟦NA⟧`, `⟦NB⟧`, … not `⟦N1⟧`) so that the
    outbound guarantee is literal: the transmitted text contains **zero digit
    characters**, checkable with one scan. A paragraph that still contains any
    digit-like character after masking (including Unicode digits the masker
    does not model, e.g. superscripts) is simply not sent.
3.  The response is verified deterministically before anything is written:
    the placeholder multiset must match what was sent, the response must be
    digit-free outside placeholders, every original token must survive
    restoration, and runaway length (<50% or >200% of the original) is
    rejected. Any violation reverts that paragraph to the original text.
4.  Any transport failure — no API key, non-200, timeout, malformed JSON —
    degrades to a no-op for the affected paragraph(s). The step can never
    make a document worse than the compiler left it.

The HTTP call is a small injectable `transport` callable so the whole pipeline
is testable without a network and the engine stays stdlib-only.
"""

import json
import os
import re
import urllib.request
from collections import Counter

from core import safe_io
from core import paths as path_utils
from core.errors import StartupOSError

GROQ_ENDPOINT = "https://api.groq.com/openai/v1/chat/completions"
API_KEY_ENV_VAR = "GROQ_API_KEY"
MODEL_ENV_VAR = "GROQ_MODEL"
DEFAULT_MODEL = "llama-3.3-70b-versatile"
REQUEST_TIMEOUT_SECONDS = 30

# Shorter than this and a "paragraph" is usually a label or a fragment whose
# rephrasing risks changing meaning without improving anything.
MIN_PARAGRAPH_CHARS = 60

# Length-drift bounds for the restored paragraph relative to the original.
MIN_LENGTH_RATIO = 0.5
MAX_LENGTH_RATIO = 2.0

_PLACEHOLDER_OPEN = "⟦"  # ⟦
_PLACEHOLDER_CLOSE = "⟧"  # ⟧
PLACEHOLDER_RE = re.compile(r"⟦N[A-Z]+⟧")

# The system prompt must itself be digit-free: it travels in the same request
# as the masked text, and the outbound guarantee is "zero digits, full stop".
SYSTEM_PROMPT = (
    "You polish the wording of business-document prose. Rephrase the user's "
    "text for clarity and professional tone while preserving its meaning "
    "exactly. The text contains opaque placeholders that look like "
    f"{_PLACEHOLDER_OPEN}NA{_PLACEHOLDER_CLOSE}; keep every placeholder "
    "exactly as written, unmodified, each appearing exactly as often as in "
    "the input. Do not add facts, figures, claims, names or qualifiers. Do "
    "not add headings, lists, quotes or any markdown structure. Return only "
    "the rephrased text and nothing else."
)

# Any file whose lowercased output-relative name matches one of these is never
# polished at all. The financial model and the compliance log are wall-to-wall
# figures and evidence; the on-a-page financial plans are the same material.
_EXCLUDED_FILE_RE = re.compile(r"financial|compliance", re.IGNORECASE)

# Sections whose entire content is evidence, figures or regulated claims.
# Matched against heading text; a match protects everything under that heading
# until a heading of the same or higher level.
_SKIP_HEADING_RE = re.compile(
    r"provenance|completion gap|compliance|b-?bbee|\bbee\b|document control"
    r"|document mappings|dependencies|regulatory|certificat|\btax\b"
    r"|financial|ownership",
    re.IGNORECASE,
)

# A prose line must not begin with structural markdown. Everything here is a
# deliberate "when in doubt, skip": headings, quotes, tables, lists, fences,
# rules, images, links, HTML, numbered lists, definition-style lines.
_NON_PROSE_LEAD = ("#", ">", "|", "-", "*", "+", "`", "!", "<", "=", "[", ":")
_NUMBERED_LIST_RE = re.compile(r"^\d+[.)]\s")
_BOLD_LABEL_RE = re.compile(r"^\*\*[^*]+\*\*\s*:")

# One numeric token: an optional currency marker, a digit run with internal
# separators (commas, points, spaces, slashes, colons, dashes — covering
# `R 4,800,000`, `2026-08-17`, `+27 82 123 4567`, `2019/123456/07`), and an
# optional magnitude/percent suffix (`$1.2m`, `ZAR 500k`, `12%`). Anything the
# pattern misses is caught by the zero-digit outbound guard and the paragraph
# is not sent — the regex is an optimisation, not the safety boundary.
_NUMERIC_RE = re.compile(
    r"""
    (?:\b(?:ZAR|USD|EUR|GBP|NAD|BWP|R)\s?|[$€£]\s?)?  # currency marker
    [+-]?\d(?:[\d,.\s/:+-]*\d)?                                 # digit run
    (?:\s?(?:million|billion|thousand|bn|k|m)\b|\s?%)?          # magnitude
    """,
    re.IGNORECASE | re.VERBOSE,
)


class PolishSkipped(Exception):
    """One paragraph (or call) was skipped; the original text stands."""


def _contains_digit(text):
    """True when any character is a digit in the Unicode sense.

    Deliberately `str.isdigit`, not `\\d`: superscript two and other exotic
    digit forms are digits to a reader even where the regex engine disagrees.
    """
    return any(ch.isdigit() for ch in text)


def _letters(index):
    """0 -> A, 1 -> B, … 25 -> Z, 26 -> AA. No digits, ever."""
    label = ""
    index += 1
    while index:
        index, remainder = divmod(index - 1, 26)
        label = chr(ord("A") + remainder) + label
    return label


def mask_numbers(text):
    """Replace every numeric token with `⟦NA⟧`-style placeholders.

    Returns `(masked_text, mapping)` where mapping is an ordered list of
    `(placeholder, original_token)` pairs kept strictly on this machine.
    """
    mapping = []

    def _replace(match):
        placeholder = (
            f"{_PLACEHOLDER_OPEN}N{_letters(len(mapping))}{_PLACEHOLDER_CLOSE}"
        )
        mapping.append((placeholder, match.group(0)))
        return placeholder

    return _NUMERIC_RE.sub(_replace, text), mapping


def restore_numbers(text, mapping):
    """Put the original numeric tokens back, placeholder by placeholder."""
    for placeholder, token in mapping:
        text = text.replace(placeholder, token, 1)
    return text


def file_is_eligible(relative_name):
    """Whole-file gate. The financial model and compliance log never qualify."""
    return not _EXCLUDED_FILE_RE.search(relative_name)


class _Segment:
    __slots__ = ("lines", "eligible")

    def __init__(self, lines, eligible):
        self.lines = lines
        self.eligible = eligible

    @property
    def text(self):
        return "\n".join(self.lines)


def _protected_lines(lines):
    """Mark every line that no polish pass may touch or transmit."""
    protected = [False] * len(lines)
    start = 0

    # YAML front matter: opening fence on line one through the closing fence.
    if lines and lines[0].strip() == "---":
        for j in range(1, len(lines)):
            if lines[j].strip() == "---":
                for k in range(j + 1):
                    protected[k] = True
                start = j + 1
                break

    in_fence = False
    skip_levels = {}
    for i in range(start, len(lines)):
        stripped = lines[i].strip()

        if stripped.startswith("```") or stripped.startswith("~~~"):
            in_fence = not in_fence
            protected[i] = True
            continue
        if in_fence:
            protected[i] = True
            continue

        heading = re.match(r"(#{1,6})\s+(.*)", stripped)
        if heading:
            level = len(heading.group(1))
            for known in [lv for lv in skip_levels if lv >= level]:
                del skip_levels[known]
            if _SKIP_HEADING_RE.search(heading.group(2)):
                skip_levels[level] = True
            protected[i] = True
            continue

        if skip_levels:
            protected[i] = True

    return protected


def _is_prose_paragraph(seg_lines):
    """Only plain prose qualifies. Any structural marker disqualifies."""
    total = 0
    for line in seg_lines:
        stripped = line.strip()
        if not stripped:
            return False
        if stripped[0] in _NON_PROSE_LEAD:
            return False
        if _NUMBERED_LIST_RE.match(stripped):
            return False
        if _BOLD_LABEL_RE.match(stripped):
            return False
        total += len(stripped)
    return total >= MIN_PARAGRAPH_CHARS


def segment(document):
    """Split a document into blank-line-delimited segments, losslessly.

    Joining every segment's lines with newlines reproduces the input byte for
    byte, so untouched content can never be reflowed by a round trip.
    """
    lines = document.split("\n")
    protected = _protected_lines(lines)

    segments = []
    current = []

    def _close():
        if not current:
            return
        seg_lines = [lines[j] for j in current]
        eligible = all(not protected[j] for j in current) and _is_prose_paragraph(
            seg_lines
        )
        segments.append(_Segment(seg_lines, eligible))
        current.clear()

    for j, line in enumerate(lines):
        if line.strip() == "":
            _close()
            segments.append(_Segment([line], False))
        else:
            current.append(j)
    _close()
    return segments


def _verify_and_restore(original, masked, response, mapping):
    """All-or-nothing verification. Returns restored text or raises.

    Every check is deterministic and runs before a byte is written:
    placeholder multiset equality, zero digits outside placeholders, exact
    restoration of every original token, and bounded length drift.
    """
    if not response or not response.strip():
        raise PolishSkipped("empty response")

    response = response.strip()

    if Counter(PLACEHOLDER_RE.findall(response)) != Counter(
        PLACEHOLDER_RE.findall(masked)
    ):
        raise PolishSkipped("placeholder multiset mismatch")

    if _contains_digit(PLACEHOLDER_RE.sub("", response)):
        raise PolishSkipped("stray digits in response")

    restored = restore_numbers(response, mapping)

    for _placeholder, token in mapping:
        if token not in restored:
            raise PolishSkipped(f"numeric token {token!r} lost in restoration")
    if _PLACEHOLDER_OPEN in restored or _PLACEHOLDER_CLOSE in restored:
        raise PolishSkipped("unrestored placeholder remains")

    ratio = len(restored) / max(len(original), 1)
    if ratio < MIN_LENGTH_RATIO or ratio > MAX_LENGTH_RATIO:
        raise PolishSkipped(f"length drift {ratio:.2f}x outside bounds")

    return restored


def _urllib_transport(url, data, headers, timeout):
    """The one place the network is touched. Stdlib only, by design."""
    request = urllib.request.Request(url, data=data, headers=headers, method="POST")
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.getcode(), response.read()


def build_call_model(
    api_key,
    model=None,
    transport=None,
    timeout=REQUEST_TIMEOUT_SECONDS,
    endpoint=GROQ_ENDPOINT,
):
    """Return a `call_model(masked_text) -> rephrased_text` callable.

    `transport` is injectable so tests exercise the full pipeline with no
    network. The API key lives only in this closure and the request header —
    it is never logged, never written to disk and never part of an error.
    """
    model = model or os.environ.get(MODEL_ENV_VAR) or DEFAULT_MODEL
    transport = transport or _urllib_transport

    def call_model(masked_text):
        # The final gate: nothing containing a digit is ever transmitted.
        if _contains_digit(masked_text) or _contains_digit(SYSTEM_PROMPT):
            raise PolishSkipped("digits present after masking; refusing to send")

        payload = json.dumps(
            {
                "model": model,
                "temperature": 0.2,
                "messages": [
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {"role": "user", "content": masked_text},
                ],
            }
        ).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        }

        try:
            status, body = transport(endpoint, payload, headers, timeout)
        except Exception as exc:
            raise PolishSkipped(
                f"API call failed ({exc.__class__.__name__})"
            ) from exc
        if status != 200:
            raise PolishSkipped(f"API returned HTTP {status}")

        try:
            parsed = json.loads(body.decode("utf-8"))
            content = parsed["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise PolishSkipped("API response was not well-formed") from exc
        if not isinstance(content, str):
            raise PolishSkipped("API response content is not text")
        return content

    return call_model


def build_call_model_from_env(environ=None, transport=None):
    """Env-driven factory. Returns None when no key is set — a clean no-op."""
    environ = os.environ if environ is None else environ
    api_key = environ.get(API_KEY_ENV_VAR)
    if not api_key:
        return None
    return build_call_model(
        api_key=api_key, model=environ.get(MODEL_ENV_VAR), transport=transport
    )


class PolishOutcome:
    """What one document's polish pass did."""

    def __init__(self, text):
        self.text = text
        self.polished = 0
        self.reverted = 0
        self.skipped = 0
        self.notes = []


def polish_text(document, call_model, filename=None):
    """Polish eligible prose in one document, deterministically guarded."""
    outcome = PolishOutcome(document)
    parts = []

    for seg in segment(document):
        if not seg.eligible:
            parts.append(seg.text)
            continue

        original = seg.text
        masked, mapping = mask_numbers(original)

        if _contains_digit(masked):
            outcome.skipped += 1
            outcome.notes.append(
                f"{filename or 'document'}: paragraph kept — digits survived masking"
            )
            parts.append(original)
            continue

        try:
            response = call_model(masked)
        except PolishSkipped as exc:
            outcome.skipped += 1
            outcome.notes.append(f"{filename or 'document'}: kept — {exc}")
            parts.append(original)
            continue

        try:
            restored = _verify_and_restore(original, masked, response, mapping)
        except PolishSkipped as exc:
            outcome.reverted += 1
            outcome.notes.append(f"{filename or 'document'}: reverted — {exc}")
            parts.append(original)
            continue

        if restored == original:
            # The model had nothing to improve. Not a change, not a revert —
            # and a document full of these must not be rewritten or badged.
            parts.append(original)
            continue

        outcome.polished += 1
        parts.append(restored)

    outcome.text = "\n".join(parts)
    return outcome


_POLISH_NOTE_RE = re.compile(r"^> \*   \*\*Language\*\*:.*\n?", re.MULTILINE)


def add_polish_note(document, polished, reverted):
    """Record the polish pass inside the Document Control block.

    Idempotent: a previous Language line is replaced, not stacked, so
    repeated runs do not accrete provenance noise.
    """
    note = (
        f"> *   **Language**: polished by AI (numbers and evidence untouched); "
        f"{polished} paragraph(s) rephrased, {reverted} reverted by verification."
    )

    document = _POLISH_NOTE_RE.sub("", document)

    lines = document.split("\n")
    for i, line in enumerate(lines):
        if line.strip() == "> **Document Control**":
            end = i
            while end + 1 < len(lines) and lines[end + 1].startswith(">"):
                end += 1
            lines.insert(end + 1, note)
            return "\n".join(lines)

    # No control block (not a compiler-assembled file): standalone note on top.
    return "> [!NOTE]\n" + note + "\n\n" + document


class PolishReport:
    """Outcome of polishing one instance's output directory."""

    def __init__(self, instance_type, instance_name, output_dir):
        self.instance_type = instance_type
        self.instance_name = instance_name
        self.output_dir = output_dir
        self.polished_files = []  # (relative_name, polished, reverted)
        self.excluded_files = []
        self.unchanged_files = []
        self.notes = []

    def summary(self):
        polished_total = sum(p for _n, p, _r in self.polished_files)
        reverted_total = sum(r for _n, _p, r in self.polished_files)
        lines = [
            f"[StartupOS] polish {self.instance_type}/{self.instance_name} "
            f"-> {len(self.polished_files)} document(s) updated",
            f"  Paragraphs   : {polished_total} rephrased, {reverted_total} "
            "reverted by verification",
            f"  Excluded     : {len(self.excluded_files)} file(s) never sent "
            "(financial/compliance)",
        ]
        if self.unchanged_files:
            lines.append(f"  Unchanged    : {len(self.unchanged_files)} file(s)")
        return "\n".join(lines)


def polish_instance(
    instance_type,
    instance_name,
    call_model,
    workspace_root=None,
    quiet=False,
):
    """Polish every eligible compiled document for one instance.

    Writes go through `safe_io.update_file` — lock, `.history` snapshot,
    atomic replace — the same path every other mutation in the engine uses.
    """
    instance_type = path_utils.validate_instance_type(instance_type)
    instance_name = path_utils.sanitize_instance_name(instance_name)
    root = path_utils.resolve_workspace_root(workspace_root, verbose=not quiet)
    out_dir = path_utils.output_dir(root, instance_type, instance_name)

    if not os.path.isdir(out_dir):
        raise StartupOSError(
            f"No compiled output at {out_dir}. Compile first:\n"
            f"  python main.py compile --type {instance_type} --name {instance_name}"
        )

    report = PolishReport(instance_type, instance_name, out_dir)

    for directory, subdirs, filenames in os.walk(out_dir):
        subdirs[:] = sorted(
            name for name in subdirs if name != safe_io.HISTORY_DIRNAME
        )
        for filename in sorted(filenames):
            if not filename.endswith(".md"):
                continue
            full = os.path.join(directory, filename)
            relative = os.path.relpath(full, out_dir).replace(os.sep, "/")

            if not file_is_eligible(relative):
                report.excluded_files.append(relative)
                continue

            holder = {}

            def _transform(current, _holder=holder, _relative=relative):
                outcome = polish_text(current, call_model, filename=_relative)
                _holder["outcome"] = outcome
                if outcome.polished == 0:
                    return None  # nothing improved; do not rewrite the file
                return add_polish_note(
                    outcome.text, outcome.polished, outcome.reverted
                )

            changed = safe_io.update_file(full, _transform)
            outcome = holder.get("outcome")
            if outcome is not None:
                report.notes.extend(outcome.notes)
            if changed and outcome is not None:
                report.polished_files.append(
                    (relative, outcome.polished, outcome.reverted)
                )
                if not quiet:
                    print(
                        f"  Polished: {relative} ({outcome.polished} rephrased, "
                        f"{outcome.reverted} reverted)"
                    )
            else:
                report.unchanged_files.append(relative)

    if not quiet:
        print(report.summary())
        for note in report.notes:
            print(f"  [note] {note}")

    return report
