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

"""Document assembly: version control blocks, provenance footers, link maps.

The previous implementation injected its version block by replacing the first
standalone `---` line in the rendered document. On a file with YAML front
matter that is the opening fence, so the block landed *inside* the front
matter and `confidential: true` became body text. On a file without front
matter the first `---` is usually a section rule, so the block landed
mid-document — in practice, after the executive summary.

It also hardcoded `Version: 1.0.0`, `Last Updated: 2026-05-22` and one
person's `Security ID` into every document ever produced.
"""

import hashlib
import re
from datetime import date

_FRONT_MATTER_RE = re.compile(r"\A---\r?\n.*?\r?\n---[ \t]*(?:\r?\n|\Z)", re.DOTALL)


def split_front_matter(text):
    """Return `(front_matter, body)`. Front matter is '' when absent."""
    match = _FRONT_MATTER_RE.match(text)
    if not match:
        return "", text
    return match.group(0), text[match.end() :]


def content_fingerprint(text, length=8):
    """Short, stable hash of the rendered body — a real revision identifier."""
    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return digest[:length]


def build_version_block(
    instance_name,
    instance_type,
    engine_version,
    fingerprint,
    generated_on=None,
    completeness=None,
    verified_fields=None,
    applicable_fields=None,
    privacy_law=None,
    depth=None,
    extra_lines=None,
):
    """Build the document version-control callout.

    Every value here is computed. Nothing is a hardcoded literal, because a
    document that always claims `1.0.0 / 2026-05-22` tells a reader nothing
    about whether they are holding the current revision.
    """
    generated_on = generated_on or date.today()

    lines = [
        "> [!IMPORTANT]",
        "> **Document Control**",
        f"> *   **Profile**: `{instance_type}/{instance_name}`",
        f"> *   **Generated**: `{generated_on.isoformat()}`",
        f"> *   **Engine**: StartupOS `v{engine_version}`",
        f"> *   **Revision**: `{fingerprint}` (content hash)",
    ]

    if completeness is not None:
        lines.append(
            f"> *   **Profile completeness**: `{completeness:.0%}` of questions answered"
        )

    if depth:
        # The depth ladder: documents compile at the deepest level the answers
        # support, and this line names the exact answers that unlock the next
        # level — coaching, not a grade.
        lines.append(f"> *   **Depth**: {depth}")

    if applicable_fields:
        lines.append(
            f"> *   **Compliance evidence**: `{verified_fields}/{applicable_fields}` "
            "applicable fields backed by a document"
        )

    if extra_lines:
        # Document-specific control lines the compiler computed — e.g. the
        # will's execution status. Already formatted as `> *   ...` rows.
        lines.extend(extra_lines)

    lines.append(
        "> *   **Status**: Generated from `questions.md`. Fields marked *Pending* "
        "are unverified and must not be relied on."
    )

    if privacy_law:
        lines.append(f"> *   **Data handling**: subject to {privacy_law}")

    return "\n".join(lines) + "\n"


def insert_version_block(text, version_block):
    """Place the version block without destroying structure.

    Order of preference:
    1.  Immediately after YAML front matter, if present.
    2.  After the leading heading run (H1, plus an H2 subtitle if it follows).
    3.  At the very top.
    """
    front_matter, body = split_front_matter(text)

    lines = body.split("\n")
    insert_at = 0

    # Skip blank lines before the title.
    cursor = 0
    while cursor < len(lines) and not lines[cursor].strip():
        cursor += 1

    if cursor < len(lines) and lines[cursor].lstrip().startswith("# "):
        insert_at = cursor + 1
        # Absorb an immediately-following H2 subtitle and any blank line.
        lookahead = insert_at
        while lookahead < len(lines) and not lines[lookahead].strip():
            lookahead += 1
        if lookahead < len(lines) and lines[lookahead].lstrip().startswith("## "):
            insert_at = lookahead + 1

    head = lines[:insert_at]
    tail = lines[insert_at:]

    assembled = "\n".join(head).rstrip()
    if assembled:
        assembled += "\n\n"
    assembled += version_block
    remainder = "\n".join(tail).lstrip("\n")
    if remainder:
        assembled += "\n" + remainder

    return front_matter + assembled


def build_provenance_footer(rows, jurisdiction_name):
    """A table saying where every compliance value came from.

    This is the feature that makes output defensible to an investor, a bank or
    an auditor: each regulated claim is labelled *document-backed*,
    *operator-asserted*, *unverified* or *not applicable here*.
    """
    label = {
        "verified": "Document-backed",
        "override": "Operator-asserted",
        "pending": "**Unverified**",
        "not_applicable": "Not applicable",
    }

    shown = [
        (key, status, source)
        for key, status, source in rows
        if status != "not_applicable"
    ]
    if not shown:
        return ""

    lines = [
        "",
        "---",
        "",
        "## Evidence & Provenance",
        "",
        f"Compliance regime: **{jurisdiction_name}**. Every regulated value below is "
        "labelled with its source. Values marked *Unverified* are placeholders — "
        "no status is being claimed.",
        "",
        "| Field | Status | Source |",
        "| :--- | :--- | :--- |",
    ]
    for key, status, source in shown:
        lines.append(f"| `{key}` | {label.get(status, status)} | {source or '—'} |")
    lines.append("")
    return "\n".join(lines)


def build_link_footer(links):
    """Bidirectional strategic document map."""
    if not links:
        return ""
    lines = [
        "",
        "---",
        "",
        "## Strategic Document Mappings & Dependencies",
        "",
        "> [!NOTE]",
        "> **Bidirectional Strategic Alignment Map**:",
    ]
    for filename, description, title in links:
        lines.append(f"> *   **[{title}]({filename})**: {description}")
    lines.append("")
    return "\n".join(lines)


def build_gap_report(missing_labels, warnings):
    """A visible list of what is missing, instead of `Pending — update…` inline.

    The old behaviour buried `Pending — update questions.md for 'primary_products'`
    inside an executive summary, where it reads as prose. A gap section at the
    end is honest and actionable.
    """
    if not missing_labels and not warnings:
        return ""

    lines = ["", "---", "", "## Completion Gaps", ""]

    if missing_labels:
        lines.append("> [!WARNING]")
        lines.append(
            "> **These fields are unanswered and appear as placeholders above:**"
        )
        for key, label in sorted(missing_labels.items()):
            lines.append(f"> *   `{key}` — {label}")
        lines.append("")

    if warnings:
        lines.append("> [!NOTE]")
        lines.append("> **Compiler notes:**")
        for warning in warnings:
            lines.append(f"> *   {warning}")
        lines.append("")

    return "\n".join(lines)
