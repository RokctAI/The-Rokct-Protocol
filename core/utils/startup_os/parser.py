"""Structure-preserving parser for `questions.md`, the StartupOS SSOT.

The old parser silently lost data in five ways: it only matched `*` bullets,
truncated every answer to its first line, let duplicate labels overwrite each
other without a word, captured the literal `**Answer**` line as a question in
its own right, and reported nothing when a question went unanswered.

Silence is the problem. A strategy document where a founder's three-paragraph
value proposition became its first eight words — with no warning — is worse
than one that refuses to compile. This parser collects warnings and hands them
back so the compiler can surface them.
"""

import os
import re

# `*` or `-` bullets, any indent. Non-greedy label so `**A**: **B**` takes A.
# `meta` absorbs a trailing annotation between the bold label and the colon,
# e.g. `*   **Trading Name** *(required)*: ...` — without it, every required
# question in a provisioned file would be invisible to the parser.
_BULLET_RE = re.compile(
    r"^(?P<indent>[ \t]*)[*-]\s+\*\*(?P<label>[^*]+?)\*\*(?P<meta>[^:]*?):\s*(?P<rest>.*)$"
)

# `*   **[2026-01-01] (Technical Mastery)**: text`
_MILESTONE_RE = re.compile(
    r"^[ \t]*[*-]\s+\*\*\[(?P<date>[^\]]+)\]\s*\((?P<category>[^)]+)\)\*\*\s*:\s*(?P<text>.*)$"
)

_HEADING_RE = re.compile(r"^[ \t]*#")
_RULE_RE = re.compile(r"^[ \t]*-{3,}[ \t]*$")

# Matches both the historical `## 4. Conversational Milestone Log (…)` heading
# and the unnumbered one written by newer provisioning.
MILESTONE_HEADING_RE = re.compile(
    r"^[ \t]*#{2,}\s*(?:\d+\.\s*)?Conversational Milestone Log", re.IGNORECASE
)
MILESTONE_SECTION_HEADING = "## Conversational Milestone Log (Living Ledger)"

# An answer opening with any of these is a prompt to the user, not a value.
_PENDING_PREFIXES = ("pending", "tbd", "todo", "n/a — pending", "unanswered")


def canonical_key(label):
    """Map a human question label to a stable placeholder key.

    'Key Suppliers' and 'Key-Suppliers' both canonicalise to `key_suppliers`;
    that collision is real and is reported as a warning rather than silently
    resolved last-wins.
    """
    return re.sub(r"[^a-z0-9_]+", "_", label.lower()).strip("_")


def _indent_width(text):
    return len(text) - len(text.lstrip(" \t"))


def is_pending(value):
    """True when an answer is a placeholder rather than a real answer."""
    if value is None:
        return True
    stripped = value.strip()
    if not stripped:
        return True
    lowered = stripped.lower()
    return any(lowered.startswith(prefix) for prefix in _PENDING_PREFIXES)


class Milestone:
    __slots__ = ("date", "category", "text")

    def __init__(self, date, category, text):
        self.date = date
        self.category = category
        self.text = text

    def __repr__(self):
        return f"Milestone({self.date!r}, {self.category!r}, {self.text!r})"


class ParsedProfile:
    """Result of parsing a questions.md file."""

    def __init__(self):
        self.answers = {}       # canonical key -> answered value
        self.pending = {}       # canonical key -> placeholder text
        self.labels = {}        # canonical key -> original human label
        self.line_numbers = {}  # canonical key -> 1-based line of the answer
        self.milestones = []
        self.warnings = []

    def __contains__(self, key):
        return key in self.answers

    def get(self, key, default=None):
        return self.answers.get(key, default)

    def keys(self):
        return self.answers.keys()

    def items(self):
        return self.answers.items()

    @property
    def answered_count(self):
        return len(self.answers)

    @property
    def total_count(self):
        return len(self.answers) + len(self.pending)

    @property
    def completeness(self):
        """Fraction of questions with a real answer, 0.0-1.0."""
        total = self.total_count
        return (len(self.answers) / total) if total else 0.0


def parse_questions_md(filepath):
    """Parse a questions.md file into a ParsedProfile.

    A missing file yields an empty profile with a warning rather than an
    exception — callers that require the file check for it explicitly, and
    tolerating absence here keeps the milestone/CV paths simple.
    """
    profile = ParsedProfile()

    if not os.path.exists(filepath):
        profile.warnings.append(f"questions.md not found: {filepath}")
        return profile

    try:
        with open(filepath, "r", encoding="utf-8") as handle:
            content = handle.read()
    except OSError as exc:
        profile.warnings.append(f"Could not read {filepath}: {exc}")
        return profile

    lines = content.splitlines()
    index = 0

    while index < len(lines):
        line = lines[index]

        # Milestones are identified by their own shape (`**[date] (category)**:`),
        # so they are collected wherever they appear rather than depending on a
        # section heading that has changed spelling over time.
        milestone_match = _MILESTONE_RE.match(line)
        if milestone_match:
            profile.milestones.append(
                Milestone(
                    milestone_match.group("date").strip(),
                    milestone_match.group("category").strip(),
                    milestone_match.group("text").strip(),
                )
            )
            index += 1
            continue

        bullet_match = _BULLET_RE.match(line)
        if not bullet_match:
            index += 1
            continue

        label = bullet_match.group("label").strip()

        # The `**Answer**:` line matches the same shape as a question. Skip it
        # here; it is consumed by the question branch below.
        if label.lower() == "answer":
            index += 1
            continue

        key = canonical_key(label)
        if not key:
            profile.warnings.append(
                f"Line {index + 1}: question label {label!r} canonicalises to an empty key; skipped."
            )
            index += 1
            continue

        answer_value, consumed = _read_answer(lines, index)

        if key in profile.labels:
            previous = profile.labels[key]
            profile.warnings.append(
                f"Line {index + 1}: question {label!r} collides with earlier question "
                f"{previous!r} (both map to '{key}'). The later answer wins — "
                "rename one of them."
            )

        profile.labels[key] = label

        if answer_value is None:
            profile.pending[key] = ""
            profile.warnings.append(
                f"Line {index + 1}: question {label!r} has no '**Answer**:' line."
            )
        elif is_pending(answer_value):
            profile.pending[key] = answer_value
            profile.answers.pop(key, None)
        else:
            profile.answers[key] = answer_value
            profile.pending.pop(key, None)
            profile.line_numbers[key] = index + 1 + consumed

        index += 1 + consumed

    return profile


def _read_answer(lines, question_index):
    """Read the answer belonging to the question at `question_index`.

    Returns `(value_or_None, lines_consumed)`. Handles multi-line answers,
    including paragraph breaks, by consuming continuation lines indented at
    least as far as the `**Answer**:` bullet.
    """
    # The answer bullet normally sits on the next line; allow one blank between.
    answer_index = None
    for offset in (1, 2):
        candidate = question_index + offset
        if candidate >= len(lines):
            break
        if not lines[candidate].strip():
            continue
        match = _BULLET_RE.match(lines[candidate])
        if match and match.group("label").strip().lower() == "answer":
            answer_index = candidate
            break
        # Anything else non-blank means this question has no answer bullet.
        break

    if answer_index is None:
        return None, 0

    answer_match = _BULLET_RE.match(lines[answer_index])
    parts = [answer_match.group("rest").strip()]
    answer_indent = _indent_width(lines[answer_index])

    cursor = answer_index + 1
    pending_blanks = 0

    while cursor < len(lines):
        line = lines[cursor]

        if not line.strip():
            pending_blanks += 1
            cursor += 1
            continue

        # Indent decides first. A line indented deeper than the `**Answer**:`
        # bullet belongs to the answer even when it starts with `*` — otherwise
        # an answer that is itself a bulleted list (an executive team, a set of
        # revenue streams) is silently truncated to its first entry on the
        # round trip through update_profile_answer.
        if _indent_width(line) <= answer_indent:
            break

        # A heading or horizontal rule can never sit inside an answer, at any
        # indent — those end the answer regardless.
        if _HEADING_RE.match(line) or _RULE_RE.match(line):
            break

        if pending_blanks:
            parts.append("")
            pending_blanks = 0
        parts.append(line.strip())
        cursor += 1

    # Trailing blank lines belong to the document, not the answer.
    consumed = (cursor - pending_blanks) - question_index - 1

    value = "\n".join(parts).strip()
    return value, max(consumed, 0)


def locate_question(lines, question_label):
    """Find the line index of a question by label. Returns None when absent."""
    target = canonical_key(question_label)
    for index, line in enumerate(lines):
        if _MILESTONE_RE.match(line):
            continue
        match = _BULLET_RE.match(line)
        if not match:
            continue
        label = match.group("label").strip()
        if label.lower() == "answer":
            continue
        if canonical_key(label) == target:
            return index
    return None


def locate_answer_span(lines, question_index):
    """Return `(answer_index, last_line_index, indent)` for a question's answer.

    Spans the full multi-line answer, so a rewrite replaces all of it rather
    than leaving orphaned continuation lines behind the new first line.
    """
    value, consumed = _read_answer(lines, question_index)
    if value is None:
        return None

    for offset in (1, 2):
        candidate = question_index + offset
        if candidate >= len(lines):
            break
        match = _BULLET_RE.match(lines[candidate])
        if match and match.group("label").strip().lower() == "answer":
            return candidate, question_index + consumed, _indent_width(lines[candidate])
    return None


def parse_milestones(filepath):
    """Convenience wrapper returning only the milestone log."""
    return parse_questions_md(filepath).milestones
