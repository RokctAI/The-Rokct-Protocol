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

# compliance-silent
"""Seed a life profile's living ledger from an existing CV.

The previous version of this script opened the PDF, then returned twelve
hardcoded milestones belonging to one named individual — employers, colleges,
dates and a skills inventory — regardless of whose CV was passed in. Running it
against anyone else's CV wrote that person's history into their profile under
their own name.

This version extracts what the document actually contains. When it cannot find
anything, it says so and writes nothing. `--dry-run` is the default posture for
review: read the extraction before it touches the SSOT.
"""

import argparse
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _bootstrap  # noqa: E402

try:
    import pypdf
except ImportError:
    pypdf = None

_MONTHS = {
    "jan": "01",
    "feb": "02",
    "mar": "03",
    "apr": "04",
    "may": "05",
    "jun": "06",
    "jul": "07",
    "aug": "08",
    "sep": "09",
    "oct": "10",
    "nov": "11",
    "dec": "12",
}

# Section headings commonly found in CVs, mapped to the ledger category used.
_SECTION_PATTERNS = (
    (
        re.compile(
            r"^\s*(work\s+)?experience|employment(\s+history)?|career", re.IGNORECASE
        ),
        "Professional Experience",
    ),
    (
        re.compile(r"^\s*education|qualifications|academic", re.IGNORECASE),
        "Education & Credentials",
    ),
    (
        re.compile(
            r"^\s*(certifications?|licen[cs]es?|training|courses?)", re.IGNORECASE
        ),
        "Certifications & Training",
    ),
    (
        re.compile(r"^\s*(awards?|honou?rs?|nominations?|recognition)", re.IGNORECASE),
        "Awards & Recognition",
    ),
    (
        re.compile(r"^\s*(publications?|patents?|talks?|speaking)", re.IGNORECASE),
        "Publications & Talks",
    ),
    (
        re.compile(
            r"^\s*(skills?|competenc|technical\s+profile|expertise)", re.IGNORECASE
        ),
        "Skills & Expertise",
    ),
    (
        re.compile(r"^\s*(volunteer|community|service)", re.IGNORECASE),
        "Community & Service",
    ),
    (
        re.compile(
            r"^\s*(references?|referees?|contact|personal\s+details)", re.IGNORECASE
        ),
        None,
    ),  # explicitly excluded — contact details are not milestones
)

_DATE_RE = re.compile(r"\b(?:(?P<month>[A-Za-z]{3,9})\s+)?(?P<year>19\d{2}|20\d{2})\b")


def normalise_date(month_text, year_text):
    """Map an extracted month/year to an ISO date, defaulting to January."""
    month = "01"
    if month_text:
        month = _MONTHS.get(month_text[:3].lower(), "01")
    return f"{year_text}-{month}-01"


def read_pdf_text(path):
    if pypdf is None:
        raise ImportError("pypdf is not installed. Run: pip install pypdf")
    reader = pypdf.PdfReader(path)
    pages = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            pages.append("")
    return "\n".join(pages)


def clean_lines(text):
    """Drop page furniture: page numbers and repeated header/footer lines."""
    raw = [line.strip() for line in text.replace("\r\n", "\n").split("\n")]
    counts = {}
    for line in raw:
        if line:
            counts[line] = counts.get(line, 0) + 1

    cleaned = []
    for line in raw:
        if not line:
            continue
        if re.fullmatch(r"\d{1,3}", line):
            continue
        if re.fullmatch(r"page\s+\d+(\s+of\s+\d+)?", line, re.IGNORECASE):
            continue
        # A short line repeated on most pages is a running header or footer.
        if counts.get(line, 0) >= 3 and len(line) < 60:
            continue
        cleaned.append(line)
    return cleaned


def extract_milestones(text):
    """Pull dated entries out of a CV, grouped by the section they appear in."""
    lines = clean_lines(text)
    milestones = []
    section = None

    for index, line in enumerate(lines):
        matched_section = False
        for pattern, category in _SECTION_PATTERNS:
            if pattern.match(line) and len(line) < 60:
                section = category
                matched_section = True
                break
        if matched_section:
            continue

        if section is None:
            continue

        date_match = _DATE_RE.search(line)
        if not date_match:
            continue

        # Build the entry from this line plus the following line when the
        # following line looks like a continuation rather than a new entry.
        body = line
        if index + 1 < len(lines):
            nxt = lines[index + 1]
            if (
                nxt
                and not _DATE_RE.search(nxt)
                and len(nxt) > 15
                and not nxt.endswith(":")
            ):
                body = f"{line} — {nxt}"

        body = " ".join(body.split())
        if len(body) < 8:
            continue

        milestones.append(
            {
                "date": normalise_date(
                    date_match.group("month"), date_match.group("year")
                ),
                "category": section,
                "text": body,
            }
        )

    milestones.sort(key=lambda item: item["date"])
    return milestones


def build_parser():
    parser = argparse.ArgumentParser(
        description="Seed a life profile's living ledger from a CV PDF."
    )
    parser.add_argument("--name", required=True, help="Instance name")
    parser.add_argument("--type", choices=("business", "life"), default="life")
    parser.add_argument("--pdf", required=True, help="Path to the CV PDF")
    parser.add_argument("--root", default=None, help="Workspace root override")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Write the extracted milestones. Without this the "
        "script only prints what it found.",
    )
    parser.add_argument("--quiet", action="store_true")
    return parser


def main():
    args = build_parser().parse_args()

    _bootstrap.prepare(root=args.root, sync=False, verbose=not args.quiet)

    from core.agent_bridge import log_ambient_milestone
    from core.errors import StartupOSError
    from core.paths import questions_path, resolve_workspace_root

    if not os.path.isfile(args.pdf):
        print(f"[Error] CV not found: {args.pdf}", file=sys.stderr)
        return 1

    try:
        root = resolve_workspace_root(args.root, verbose=False)
        target = questions_path(root, args.type, args.name)
    except StartupOSError as exc:
        print(f"[Error] {exc}", file=sys.stderr)
        return 1

    if not os.path.exists(target):
        print(f"[Error] No profile at {target}. Provision it first.", file=sys.stderr)
        return 1

    try:
        text = read_pdf_text(args.pdf)
    except Exception as exc:
        print(f"[Error] Could not read {args.pdf}: {exc}", file=sys.stderr)
        return 1

    milestones = extract_milestones(text)

    if not milestones:
        print(
            "[Error] No dated entries could be extracted from this CV.\n"
            "        Nothing was written. Add milestones directly with "
            "log_milestone.py, or check that the PDF has selectable text "
            "rather than being a scan.",
            file=sys.stderr,
        )
        return 1

    print(
        f"\nExtracted {len(milestones)} candidate milestones from {os.path.basename(args.pdf)}:\n"
    )
    for item in milestones:
        print(f"  [{item['date']}] ({item['category']}) {item['text'][:110]}")

    if not args.apply:
        print(
            "\n[Dry run] Nothing was written. Review the entries above, then "
            "re-run with --apply to add them.\n"
            "          Extraction from a PDF is approximate; entries that read "
            "wrongly should be corrected in questions.md afterwards."
        )
        return 0

    written = 0
    skipped = 0
    for item in milestones:
        try:
            result = log_ambient_milestone(
                filepath=target,
                category=item["category"],
                entry_text=item["text"],
                entry_date=item["date"],
                recompile=False,
                workspace_root=args.root,
            )
        except StartupOSError as exc:
            print(f"[Warning] Skipped an entry: {exc}", file=sys.stderr)
            skipped += 1
            continue
        if result.changed:
            written += 1
        else:
            skipped += 1

    print(
        f"\n[Success] Wrote {written} milestones ({skipped} already present) to {target}"
    )

    from core.compiler import compile_instance

    try:
        compile_instance(
            instance_type=args.type,
            instance_name=args.name,
            workspace_root=args.root,
            quiet=args.quiet,
        )
    except StartupOSError as exc:
        print(f"[Warning] Recompilation failed: {exc}", file=sys.stderr)
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
