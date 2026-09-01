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

"""Hermes agent bridge — programmatic read/write/provision APIs.

Everything here is reachable from a conversational handler, which means every
argument is untrusted input. `auto_provision_profile` in particular is called
with an entity name lifted from a WhatsApp message; the previous version passed
that string straight into `os.path.join`, so a name of `../../../ESCAPED` wrote
`questions.md` outside the workspace. Names are now validated by
`paths.sanitize_instance_name` before any path is built, and the resolved path
is re-checked for containment.

Writes go through `safe_io`: locked, snapshotted, atomic. Failures are returned
rather than printed and swallowed — the old code caught every compile exception,
printed a warning and returned `True`, so a user was told their answer was
saved while the documents silently did not regenerate.
"""

import os
import re
from datetime import date
from pathlib import Path

from . import paths as path_utils
from . import safe_io
from . import schemas
from .compiler import compile_instance
from .errors import ProfileNotFoundError, QuestionNotFoundError, StartupOSError
from .parser import (
    MILESTONE_HEADING_RE,
    MILESTONE_SECTION_HEADING,
    canonical_key,
    locate_answer_span,
    locate_question,
)


class BridgeResult:
    """What a bridge call did, including whether recompilation succeeded."""

    def __init__(self, changed, path, compiled=None, error=None):
        self.changed = changed
        self.path = path
        self.compiled = compiled
        self.error = error

    @property
    def ok(self):
        return self.changed and self.error is None

    def __bool__(self):
        return self.ok

    def __repr__(self):
        return (
            f"BridgeResult(changed={self.changed}, path={self.path!r}, "
            f"error={self.error!r})"
        )


def _parse_instance_details(filepath):
    """Extract `(instance_type, instance_name)` from a questions.md path."""
    parts = Path(filepath).resolve().parts
    if "instances" in parts:
        index = parts.index("instances")
        if index + 2 < len(parts):
            return parts[index + 1].lower(), parts[index + 2]

    match = re.search(
        r"instances[/\\](business|life)[/\\]([^/\\]+)", str(filepath), re.IGNORECASE
    )
    if match:
        return match.group(1).lower(), match.group(2)
    return None, None


def _recompile(filepath, workspace_root=None, quiet=True):
    """Recompile the instance owning `filepath`. Returns `(result, error)`."""
    instance_type, instance_name = _parse_instance_details(filepath)
    if not instance_type or not instance_name:
        return None, (
            f"Could not determine the instance from {filepath!r}; downstream "
            "documents were not regenerated."
        )
    try:
        return compile_instance(
            instance_type=instance_type,
            instance_name=instance_name,
            workspace_root=workspace_root,
            quiet=quiet,
        ), None
    except StartupOSError as exc:
        return None, f"Recompilation failed: {exc}"
    except Exception as exc:  # noqa: BLE001 - surfaced to the caller, not swallowed
        return None, f"Recompilation failed unexpectedly: {exc}"


def auto_provision_profile(
    instance_type,
    instance_name,
    primary_base=None,
    key_relationships=None,
    jurisdiction=None,
    workspace_root=None,
    seed=None,
    full=False,
):
    """Create a new business or life profile.

    Returns the path to `questions.md`. An existing profile is never
    overwritten. Raises `UnsafeNameError` for any name that is not a plain
    identifier — path separators, `..`, reserved Windows device names and
    over-long strings are all rejected before a path is constructed.
    """
    instance_type = path_utils.validate_instance_type(instance_type)
    instance_name = path_utils.sanitize_instance_name(instance_name)

    root = path_utils.resolve_workspace_root(workspace_root, verbose=False)
    directory = path_utils.instance_dir(root, instance_type, instance_name)
    os.makedirs(directory, exist_ok=True)

    questions_file = os.path.join(directory, "questions.md")
    if os.path.exists(questions_file):
        return questions_file

    display_name = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", instance_name).strip()

    seed_values = dict(seed or {})
    seed_values.setdefault(
        "trading_name" if instance_type == "business" else "full_name", display_name
    )
    if primary_base:
        seed_values.setdefault("primary_base", primary_base)
    if jurisdiction:
        seed_values.setdefault("jurisdiction", str(jurisdiction).strip().upper())
    if key_relationships and instance_type == "life":
        seed_values.setdefault("key_relationships", key_relationships)

    content = schemas.render_questions_md(
        instance_type, display_name, seed_values, include_full=full
    )
    safe_io.atomic_write(questions_file, content)
    return questions_file


def update_profile_answer(
    filepath, question_label, new_answer, recompile=True, workspace_root=None
):
    """Replace the answer to one question, preserving file structure.

    Handles multi-line answers on both sides: the full span of the previous
    answer is removed, and a multi-line `new_answer` is written back with the
    continuation indent the file already uses.
    """
    if not os.path.exists(filepath):
        raise ProfileNotFoundError(f"Profile questions file not found: {filepath}")

    target_key = canonical_key(question_label)
    if not target_key:
        raise QuestionNotFoundError(
            f"Question label {question_label!r} is empty after canonicalisation."
        )

    outcome = {"found": False}

    def transform(content):
        lines = content.split("\n")
        question_index = locate_question(lines, question_label)
        if question_index is None:
            return None

        span = locate_answer_span(lines, question_index)
        if span is None:
            # The question exists but has no answer bullet; insert one using the
            # question's own indent plus four spaces.
            question_indent = len(lines[question_index]) - len(
                lines[question_index].lstrip()
            )
            prefix = " " * (question_indent + 4) + "*   **Answer**: "
            rendered = _render_answer(new_answer, prefix, question_indent + 8)
            lines[question_index + 1 : question_index + 1] = rendered
            outcome["found"] = True
            return "\n".join(lines)

        answer_index, last_index, indent = span
        marker = re.match(r"^(\s*(?:\*|-)\s+\*\*Answer\*\*:\s*)", lines[answer_index])
        prefix = marker.group(1) if marker else " " * indent + "*   **Answer**: "
        rendered = _render_answer(new_answer, prefix, indent + 4)

        lines[answer_index : last_index + 1] = rendered
        outcome["found"] = True
        return "\n".join(lines)

    changed = safe_io.update_file(filepath, transform)

    if not outcome["found"]:
        raise QuestionNotFoundError(
            f"Could not find question {question_label!r} in {filepath}. "
            "Labels are matched case- and punctuation-insensitively; check "
            "the question exists."
        )

    compiled, error = (None, None)
    if recompile:
        compiled, error = _recompile(filepath, workspace_root)

    return BridgeResult(changed=True, path=filepath, compiled=compiled, error=error)


def _render_answer(answer, prefix, continuation_indent):
    """Format a possibly multi-line answer as markdown lines."""
    text = "" if answer is None else str(answer)
    parts = text.split("\n")
    rendered = [prefix + parts[0].strip()]
    for part in parts[1:]:
        rendered.append(" " * continuation_indent + part.strip())
    return rendered


def log_ambient_milestone(
    filepath,
    category,
    entry_text,
    entry_date=None,
    recompile=True,
    workspace_root=None,
    deduplicate=True,
):
    """Append a conversational milestone to the living ledger.

    Duplicate suppression compares the normalised entry text against existing
    milestones, so repeating an achievement in conversation does not produce a
    second CV line.
    """
    if not os.path.exists(filepath):
        raise ProfileNotFoundError(f"Target questions file not found: {filepath}")

    clean_entry = " ".join(str(entry_text).split()).strip()
    if not clean_entry:
        raise StartupOSError("Milestone entry text is empty.")

    clean_category = " ".join(str(category).split()).strip() or "General"
    stamp = entry_date or date.today()
    stamp = stamp.isoformat() if hasattr(stamp, "isoformat") else str(stamp)

    outcome = {"duplicate": False}

    def transform(content):
        if deduplicate and _is_duplicate(content, clean_entry):
            outcome["duplicate"] = True
            return None

        lines = content.rstrip("\n").split("\n")
        if not any(MILESTONE_HEADING_RE.match(line) for line in lines):
            lines.extend(["", "---", "", MILESTONE_SECTION_HEADING, ""])

        lines.append(f"*   **[{stamp}] ({clean_category})**: {clean_entry}")
        return "\n".join(lines) + "\n"

    changed = safe_io.update_file(filepath, transform)

    if outcome["duplicate"]:
        return BridgeResult(
            changed=False,
            path=filepath,
            error="Milestone already logged; nothing appended.",
        )

    compiled, error = (None, None)
    if recompile:
        compiled, error = _recompile(filepath, workspace_root)

    return BridgeResult(changed=changed, path=filepath, compiled=compiled, error=error)


def _is_duplicate(content, entry_text):
    """True when an equivalent milestone already exists."""
    normalised = _normalise(entry_text)
    if not normalised:
        return False
    for line in content.split("\n"):
        match = re.match(
            r"^[ \t]*[*-]\s+\*\*\[[^\]]+\]\s*\([^)]+\)\*\*\s*:\s*(.*)$", line
        )
        if match and _normalise(match.group(1)) == normalised:
            return True
    return False


def _normalise(text):
    return re.sub(r"[^a-z0-9]+", " ", str(text).lower()).strip()


def ensure_question(
    filepath, question_label, prompt, answer, recompile=False, workspace_root=None
):
    """Add a question to an existing questions.md if it is not already there.

    Written for the jurisdiction migration: profiles created before jurisdiction
    was a declared field compile as UNKNOWN, which correctly suppresses every
    regulated section but means an existing South African venture loses its
    B-BBEE block until the question is added. This makes that a one-liner
    instead of a hand edit across every profile.
    """
    if not os.path.exists(filepath):
        raise ProfileNotFoundError(f"Profile questions file not found: {filepath}")

    outcome = {"added": False}

    def transform(content):
        lines = content.split("\n")
        if locate_question(lines, question_label) is not None:
            return None

        # Insert after the first section heading, before its first question.
        insert_at = None
        for index, line in enumerate(lines):
            if line.lstrip().startswith("## "):
                insert_at = index + 1
                break
        if insert_at is None:
            insert_at = len(lines)

        block = [
            f"*   **{question_label}**: {prompt}",
            f"    *   **Answer**: {answer}",
        ]
        lines[insert_at:insert_at] = block
        outcome["added"] = True
        return "\n".join(lines)

    changed = safe_io.update_file(filepath, transform)
    if not outcome["added"]:
        return BridgeResult(
            changed=False,
            path=filepath,
            error=f"'{question_label}' is already present.",
        )

    compiled, error = (None, None)
    if recompile:
        compiled, error = _recompile(filepath, workspace_root)

    return BridgeResult(changed=changed, path=filepath, compiled=compiled, error=error)


def expand_profile(filepath, instance_type, recompile=False, workspace_root=None):
    """Append every schema question the file does not already have.

    Used to bring a profile created against the core question set up to the
    full set the complete document suite draws on, without disturbing any
    existing answer. Questions are appended under their own schema section
    heading so the file stays readable.
    """
    if not os.path.exists(filepath):
        raise ProfileNotFoundError(f"Profile questions file not found: {filepath}")

    instance_type = path_utils.validate_instance_type(instance_type)
    added = []

    def transform(content):
        lines = content.rstrip("\n").split("\n")

        # Insert before the milestone log if there is one; it should stay last.
        insert_at = len(lines)
        for index, line in enumerate(lines):
            if MILESTONE_HEADING_RE.match(line):
                insert_at = index
                break

        block = []
        for section in schemas.schema_for(instance_type):
            missing = [
                question
                for question in section.questions
                if locate_question(lines, question.label) is None
            ]
            if not missing:
                continue
            block.extend(["", "---", "", f"## {section.title}"])
            for question in missing:
                hint = f" (e.g. {question.example})" if question.example else ""
                placeholder = f"Pending — {question.prompt.rstrip('?').lower()}{hint}"
                marker = " *(required)*" if question.required else ""
                block.append(f"*   **{question.label}**{marker}: {question.prompt}")
                block.append(f"    *   **Answer**: {placeholder}")
                added.append(question.key)

        if not block:
            return None

        block.append("")
        lines[insert_at:insert_at] = block
        return "\n".join(lines) + "\n"

    changed = safe_io.update_file(filepath, transform)

    if not added:
        return BridgeResult(
            changed=False,
            path=filepath,
            error="Profile already has every schema question.",
        )

    compiled, error = (None, None)
    if recompile:
        compiled, error = _recompile(filepath, workspace_root)

    result = BridgeResult(
        changed=changed, path=filepath, compiled=compiled, error=error
    )
    result.added = added
    return result


def read_profile(filepath):
    """Parse a profile and return the ParsedProfile, for agent read paths."""
    from .parser import parse_questions_md

    if not os.path.exists(filepath):
        raise ProfileNotFoundError(f"Profile questions file not found: {filepath}")
    return parse_questions_md(filepath)


def profile_path(instance_type, instance_name, workspace_root=None):
    """Resolve the questions.md path for an instance, with validation."""
    root = path_utils.resolve_workspace_root(workspace_root, verbose=False)
    return path_utils.questions_path(root, instance_type, instance_name)
