# Copyright (c) 2026, Rokct Intelligence (pty) Ltd.
# For license information, please see license.txt


"""A small, dependency-free template renderer for StartupOS documents.

Why not `str.replace` in a loop, as before? Because that loop was
order-dependent and re-entrant: an answer containing `{{primary_products}}`
got expanded by a later iteration of the same loop, so the output depended on
dict ordering. Values containing `|` also silently destroyed markdown tables.

Why not Jinja2? The skill bootstraps by downloading modules onto arbitrary
machines; a stdlib-only engine keeps that path free of a pip install.

Supported syntax
----------------
    {{name}}                                  substitution (single pass)
    {{#if name}} ... {{else}} ... {{/if}}     render when `name` is a real value
    {{#unless name}} ... {{/unless}}          the inverse
    {{#if_jurisdiction ZA}} ... {{/if_jurisdiction}}
    {{#if_jurisdiction ZA,NA,BW}} ... {{/if_jurisdiction}}
    {{#if_feature bbee}} ... {{/if_feature}}

The `if_feature` / `if_jurisdiction` blocks are what let one template serve
every country: regional prose lives inside a gate instead of being hardcoded
into the body, which is how a California company ended up with a document
asserting B-BBEE Level 1 status.
"""

import re

_VARIABLE_RE = re.compile(r"\{\{([a-zA-Z0-9_]+)\}\}")
_BLOCK_OPEN_RE = re.compile(
    r"\{\{#(if|unless|if_jurisdiction|if_feature)(?:\s+([^}]*?))?\s*\}\}"
)
_ELSE_RE = re.compile(r"\{\{else\}\}")

# Values that read as "we do not have this", for `{{#if}}` truthiness.
_FALSY_PREFIXES = (
    "pending",
    "not applicable",
    "not available",
    "not provided",
    "not verified",
    "not yet",
    "none recorded",
    "unknown",
    "tbd",
    "todo",
    "n/a",
)

# A block tag alone on its line should not leave a blank line behind when the
# block is removed. Same rule Mustache calls "standalone tags".
_STANDALONE_TAG_RE = re.compile(
    r"^[ \t]*(\{\{(?:[#/][a-z_]+[^}]*|else)\}\})[ \t]*\r?\n", re.MULTILINE
)


class RenderContext:
    """Everything a template may ask about."""

    def __init__(self, values=None, jurisdiction=None, features=None):
        self.values = dict(values or {})
        self.jurisdiction = jurisdiction
        self.features = frozenset(features or ())

    def get(self, name):
        return self.values.get(name)

    def is_truthy(self, name):
        value = self.values.get(name)
        if value is None:
            return False
        text = str(value).strip()
        if not text:
            return False
        lowered = text.lower()
        return not any(lowered.startswith(prefix) for prefix in _FALSY_PREFIXES)

    def has_feature(self, feature):
        return feature.strip() in self.features

    def in_jurisdiction(self, codes):
        if not self.jurisdiction:
            return False
        wanted = {code.strip().upper() for code in codes.split(",") if code.strip()}
        return self.jurisdiction.code.upper() in wanted


def render(template_text, context, strict=False):
    """Render a template. Returns `(text, warnings)`.

    `strict=True` makes an unknown placeholder an error rather than a marker;
    used by the template linter.
    """
    warnings = []
    collapsed = _STANDALONE_TAG_RE.sub(r"\1", template_text)
    body = _render_blocks(collapsed, context, warnings)
    text = _substitute(body, context, warnings, strict)
    return _tidy(text), warnings


def _render_blocks(text, context, warnings, depth=0):
    """Resolve `{{#...}}` blocks, innermost handled by recursion."""
    if depth > 25:
        warnings.append("Template block nesting exceeded 25 levels; stopped expanding.")
        return text

    output = []
    cursor = 0

    while True:
        match = _BLOCK_OPEN_RE.search(text, cursor)
        if not match:
            output.append(text[cursor:])
            break

        output.append(text[cursor : match.start()])
        tag = match.group(1)
        argument = (match.group(2) or "").strip()

        body, after = _extract_block(text, match.end(), tag)
        if body is None:
            warnings.append(
                f"Unclosed {{{{#{tag}}}}} block — expected {{{{/{tag}}}}}. "
                "Rendering the block literally."
            )
            output.append(text[match.start() : match.end()])
            cursor = match.end()
            continue

        truth_branch, false_branch = _split_else(body, tag)

        if tag == "if":
            keep = truth_branch if context.is_truthy(argument) else false_branch
        elif tag == "unless":
            keep = truth_branch if not context.is_truthy(argument) else false_branch
        elif tag == "if_jurisdiction":
            keep = truth_branch if context.in_jurisdiction(argument) else false_branch
        elif tag == "if_feature":
            keep = truth_branch if context.has_feature(argument) else false_branch
        else:  # pragma: no cover - regex constrains the tag set
            keep = truth_branch

        output.append(_render_blocks(keep, context, warnings, depth + 1))
        cursor = after

    return "".join(output)


def _extract_block(text, start, tag):
    """Return `(body, index_after_close)` for the block opened at `start`."""
    open_pattern = re.compile(r"\{\{#" + tag + r"(?:\s+[^}]*?)?\s*\}\}")
    close_pattern = re.compile(r"\{\{/" + tag + r"\}\}")

    depth = 1
    cursor = start
    while cursor < len(text):
        next_open = open_pattern.search(text, cursor)
        next_close = close_pattern.search(text, cursor)
        if not next_close:
            return None, len(text)
        if next_open and next_open.start() < next_close.start():
            depth += 1
            cursor = next_open.end()
            continue
        depth -= 1
        if depth == 0:
            return text[start : next_close.start()], next_close.end()
        cursor = next_close.end()
    return None, len(text)


def _split_else(body, tag):
    """Split a block body on a top-level `{{else}}`."""
    if tag not in ("if", "unless", "if_jurisdiction", "if_feature"):
        return body, ""

    open_pattern = re.compile(
        r"\{\{#(if|unless|if_jurisdiction|if_feature)(?:\s+[^}]*?)?\s*\}\}"
    )
    close_pattern = re.compile(r"\{\{/(if|unless|if_jurisdiction|if_feature)\}\}")

    depth = 0
    cursor = 0
    while cursor < len(body):
        opened = open_pattern.search(body, cursor)
        closed = close_pattern.search(body, cursor)
        else_at = _ELSE_RE.search(body, cursor)

        candidates = [c for c in (opened, closed, else_at) if c]
        if not candidates:
            break
        nearest = min(candidates, key=lambda m: m.start())

        if nearest is opened:
            depth += 1
        elif nearest is closed:
            depth -= 1
        elif depth == 0:
            return body[: nearest.start()], body[nearest.end() :]
        cursor = nearest.end()

    return body, ""


def _substitute(text, context, warnings, strict):
    """One pass over the template. Values are never re-scanned for placeholders."""
    missing = set()
    lines = text.split("\n")
    rendered_lines = []

    for line in lines:
        in_table_row = line.lstrip().startswith("|")

        def replace(match, _in_table=in_table_row):
            name = match.group(1)
            if name not in context.values:
                missing.add(name)
                return f"«{name} not set»"
            return _sanitize(context.values[name], _in_table)

        rendered_lines.append(_VARIABLE_RE.sub(replace, line))

    if missing:
        listed = ", ".join(sorted(missing))
        if strict:
            raise KeyError(f"Template references undefined placeholders: {listed}")
        warnings.append(f"Template references undefined placeholders: {listed}")

    return "\n".join(rendered_lines)


def _sanitize(value, in_table_row):
    """Make a value safe to embed.

    Two hazards: a value containing `{{...}}` would be re-expanded by a naive
    second pass (so the braces are neutralised), and a value containing `|`
    silently adds columns to a markdown table.
    """
    text = "" if value is None else str(value)
    text = text.replace("{{", "&#123;&#123;").replace("}}", "&#125;&#125;")
    if in_table_row:
        text = text.replace("|", "\\|")
        text = text.replace("\n", "<br>")
    return text


def _tidy(text):
    """Clean up what block removal leaves behind: blank runs and stranded rules."""
    text = re.sub(r"[ \t]+\n", "\n", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    # Two horizontal rules with nothing between them means the section they
    # framed was gated out.
    text = re.sub(r"\n-{3,}\n+(?=-{3,}\n)", "\n", text)
    # A trailing rule at the end of the document separates nothing.
    text = re.sub(r"\n-{3,}\s*$", "", text)
    return text.strip() + "\n"


def check_blocks(template_text):
    """Return a list of block-structure errors in a template.

    Catches the mismatch that compile-time only warns about: an
    `{{#if_feature}}` closed with `{{/if}}` renders the whole block literally
    into the document. Cheap to check, expensive to notice by eye.
    """
    errors = []
    stack = []

    token_re = re.compile(
        r"\{\{#(if|unless|if_jurisdiction|if_feature)(?:\s+[^}]*?)?\s*\}\}"
        r"|\{\{/(if|unless|if_jurisdiction|if_feature)\}\}"
    )

    for match in token_re.finditer(template_text):
        line = template_text.count("\n", 0, match.start()) + 1
        opened, closed = match.group(1), match.group(2)
        if opened:
            stack.append((opened, line))
            continue
        if not stack:
            errors.append(
                f"line {line}: {{{{/{closed}}}}} with no matching opening tag"
            )
            continue
        expected, opened_line = stack.pop()
        if expected != closed:
            errors.append(
                f"line {line}: {{{{/{closed}}}}} closes a "
                f"{{{{#{expected}}}}} opened on line {opened_line}"
            )

    for name, line in stack:
        errors.append(f"line {line}: {{{{#{name}}}}} is never closed")

    return errors


def find_placeholders(template_text):
    """All `{{name}}` placeholders in a template, excluding block syntax."""
    stripped = _BLOCK_OPEN_RE.sub("", template_text)
    stripped = re.sub(
        r"\{\{/(?:if|unless|if_jurisdiction|if_feature)\}\}", "", stripped
    )
    stripped = _ELSE_RE.sub("", stripped)
    return set(_VARIABLE_RE.findall(stripped))
