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

"""Build a safety file binder, gap report and expiry log from one profile.

Public entry points (what an SDK's gateway cmd calls):

- `status(profile, today=None)` -> gaps and expiries, writes nothing.
- `build(profile, out_dir, today=None)` -> writes binder.md, binder.pdf,
  gap_report.json and expiry_log.json, and returns the same summary.

Neither ever returns a "compliant" verdict: the summary's `status` is always
"draft" while `templates.REVIEW` is None, and "ready_for_review" at most
after that, because sign-off belongs to a person.
"""

import hashlib
import json
import os
import textwrap
from datetime import date

from . import __version__, templates
from .pdf import Document

EXPIRY_WARNING_DAYS = 60  # same window as StartupOS compliance.py


class ProfileError(ValueError):
    """The profile cannot be built into a safety file."""


# ---------------------------------------------------------------- helpers


def _get(profile, dotted):
    value = profile
    for part in dotted.split("."):
        if not isinstance(value, dict):
            return None
        value = value.get(part)
    return value


def _parse_date(value):
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except ValueError:
        return None


def _today(today):
    if today is None:
        return date.today()
    if isinstance(today, date):
        return today
    parsed = _parse_date(today)
    if parsed is None:
        raise ProfileError("today must be an ISO date (YYYY-MM-DD)")
    return parsed


def fingerprint(profile):
    canonical = json.dumps(profile, sort_keys=True, ensure_ascii=False, default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:8]


def validate(profile):
    """Raise ProfileError for anything that stops a build. Returns profile."""
    if not isinstance(profile, dict):
        raise ProfileError("profile must be a JSON object")
    jurisdiction = (profile.get("jurisdiction") or "").upper()
    if jurisdiction not in templates.SUPPORTED_JURISDICTIONS:
        raise ProfileError(
            "jurisdiction %r is not supported; supported: %s"
            % (profile.get("jurisdiction"), ", ".join(templates.SUPPORTED_JURISDICTIONS))
        )
    if not _get(profile, "company.name"):
        raise ProfileError("company.name is required")
    if not _get(profile, "site.name"):
        raise ProfileError("site.name is required")
    for key in ("people", "hazards", "procedures", "training", "medicals", "documents", "incidents"):
        if profile.get(key) is not None and not isinstance(profile.get(key), list):
            raise ProfileError("%s must be a list" % key)
    return profile


# ---------------------------------------------------------------- evidence


def _evidence(profile, base_dir, today):
    """Fail-closed status for each supporting document type."""
    supplied = {}
    for doc in profile.get("documents") or []:
        if isinstance(doc, dict) and doc.get("type"):
            supplied.setdefault(doc["type"], doc)
    rows = []
    for spec in templates.EVIDENCE_TYPES:
        doc = supplied.get(spec["key"])
        row = {"type": spec["key"], "label": spec["label"], "reference": "", "expires": ""}
        if not doc or not doc.get("reference"):
            row["status"] = "not_provided"
        else:
            row["reference"] = str(doc["reference"])
            row["expires"] = str(doc.get("expires") or "")
            path = doc.get("file")
            if path and not os.path.isfile(os.path.join(base_dir, path) if base_dir else path):
                row["status"] = "file_missing"
            else:
                expiry = _parse_date(doc.get("expires"))
                if spec["expires"] and expiry is None:
                    row["status"] = "expiry_unknown"
                elif expiry is not None and expiry < today:
                    row["status"] = "expired"
                else:
                    row["status"] = "provided"
        rows.append(row)
    return rows


EVIDENCE_TEXT = {
    "provided": "Provided",
    "not_provided": "Not provided",
    "file_missing": "Listed, but the file was not found",
    "expiry_unknown": "Provided, expiry date not given",
    "expired": "Expired",
}


# ---------------------------------------------------------------- reports


def gap_report(profile, base_dir=None, today=None):
    today = _today(today)
    gaps = []
    for section in templates.SECTIONS:
        source = section["source"]
        if source in ("company", "policy", "documents"):
            continue
        rows = _get(profile, source) or []
        need = section.get("min_rows", 0)
        if need and len(rows) < need:
            gaps.append(
                {
                    "section": section["key"],
                    "title": section["title"],
                    "status": "missing",
                    "message": "No entries yet for %s." % section["title"].lower(),
                }
            )
    company = profile.get("company") or {}
    for field, label in (("registration_number", "company registration number"), ("contact_person", "contact person"), ("phone", "phone number")):
        if not company.get(field):
            gaps.append({"section": "contractor_details", "title": "Contractor and site details", "status": "missing", "message": "Add the %s." % label})
    policy = profile.get("policy") or {}
    if not policy.get("signed_by"):
        gaps.append({"section": "policy", "title": "Health and safety policy", "status": "unsigned", "message": "The policy has no signatory yet."})
    for row in _evidence(profile, base_dir, today):
        if row["status"] != "provided":
            gaps.append(
                {
                    "section": "supporting_documents",
                    "title": row["label"],
                    "status": row["status"],
                    "message": "%s: %s." % (row["label"], EVIDENCE_TEXT[row["status"]].lower()),
                }
            )
    if templates.REVIEW is None:
        gaps.append(
            {
                "section": "review",
                "title": "Practitioner review",
                "status": "not_reviewed",
                "message": "Templates are not yet reviewed by a registered OHS practitioner.",
            }
        )
    return gaps


def expiry_log(profile, today=None):
    today = _today(today)
    entries = []

    def add(kind, who, what, when):
        expiry = _parse_date(when)
        if expiry is None:
            return
        days = (expiry - today).days
        state = "expired" if days < 0 else ("due_soon" if days <= EXPIRY_WARNING_DAYS else "ok")
        entries.append({"kind": kind, "who": who, "what": what, "date": expiry.isoformat(), "days_left": days, "state": state})

    for row in profile.get("training") or []:
        add("training", row.get("person", ""), row.get("course", ""), row.get("expires"))
    for row in profile.get("medicals") or []:
        add("medical", row.get("person", ""), "Medical fitness", row.get("expires"))
    for row in _get(profile, "registers.equipment") or []:
        add("inspection", row.get("item", ""), "Next inspection", row.get("next_inspection"))
    for row in profile.get("documents") or []:
        add("document", "", row.get("type", ""), row.get("expires"))
    entries.sort(key=lambda e: e["date"])
    return entries


def status(profile, base_dir=None, today=None):
    """Gaps and expiries without writing anything."""
    validate(profile)
    today = _today(today)
    gaps = gap_report(profile, base_dir, today)
    expiries = expiry_log(profile, today)
    return {
        "status": "draft" if templates.REVIEW is None else "ready_for_review",
        "reviewed": templates.REVIEW is not None,
        "jurisdiction": profile["jurisdiction"].upper(),
        "generated_on": today.isoformat(),
        "fingerprint": fingerprint(profile),
        "engine_version": __version__,
        "gaps": gaps,
        "expiries": expiries,
        "summary": {
            "gaps": len(gaps),
            "expired": sum(1 for e in expiries if e["state"] == "expired"),
            "due_soon": sum(1 for e in expiries if e["state"] == "due_soon"),
        },
    }


# ---------------------------------------------------------------- binder


TABLE_WIDTH = 100  # characters of Courier 8pt that fit inside the margins


def _table_lines(columns, rows, blank_rows=0):
    """Plain-text table; long cells wrap inside their column, never truncate."""
    natural = []
    for key, label in columns:
        cells = [len(label)] + [len(str(r.get(key, "") or "")) for r in rows]
        natural.append(max(cells + [8]))
    budget = TABLE_WIDTH - 3 * (len(columns) - 1)
    widths = list(natural)
    while sum(widths) > budget:
        widest = widths.index(max(widths))
        widths[widest] -= 1
    if blank_rows:  # registers filled in by hand: use the full width
        spare = budget - sum(widths)
        for i in range(len(widths)):
            widths[i] += spare // len(widths)
    def fmt(values):
        wrapped = [textwrap.wrap(str(v), w) or [""] for v, w in zip(values, widths)]
        height = max(len(c) for c in wrapped)
        out = []
        for i in range(height):
            out.append(" | ".join((c[i] if i < len(c) else "").ljust(w) for c, w in zip(wrapped, widths)).rstrip())
        return out
    lines = fmt([label for _, label in columns])
    lines.append("-+-".join("-" * w for w in widths))
    for row in rows:
        lines.extend(fmt([row.get(key, "") or "" for key, _ in columns]))
    for _ in range(blank_rows):
        lines.append(" | ".join("_" * w for w in widths))
    return lines


def _section_body(section, profile, evidence):
    """Return a list of (style, text) for one section."""
    out = [("body", section["intro"]), ("space", "")]
    key = section["key"]
    if key == "contractor_details":
        company = profile.get("company") or {}
        site = profile.get("site") or {}
        pairs = [
            ("Company", company.get("name")),
            ("Registration number", company.get("registration_number")),
            ("Trade", company.get("trade")),
            ("Address", company.get("address")),
            ("Contact person", company.get("contact_person")),
            ("Phone", company.get("phone")),
            ("Email", company.get("email")),
            ("Site", site.get("name")),
            ("Site address", site.get("address")),
            ("Client", site.get("client")),
            ("Project", site.get("project")),
            ("Work period", " to ".join(x for x in (site.get("start_date"), site.get("end_date")) if x)),
        ]
        for label, value in pairs:
            out.append(("body", "%s: %s" % (label, value or "____________________")))
    elif key == "policy":
        policy = profile.get("policy") or {}
        commitments = policy.get("commitments") or section["default_commitments"]
        out.append(("body", "%s commits to:" % (_get(profile, "company.name"))))
        for number, line in enumerate(commitments, start=1):
            out.append(("body", "%d. %s" % (number, line)))
        out.append(("space", ""))
        out.append(("body", "Signed: %s" % (policy.get("signed_by") or "____________________")))
        out.append(("body", "Position: %s" % (policy.get("position") or "____________________")))
        out.append(("body", "Date: %s" % (policy.get("signed_on") or "____________________")))
    elif key == "safe_work_procedures":
        procedures = profile.get("procedures") or []
        if not procedures:
            out.append(("body", "No procedures entered yet."))
        for number, proc in enumerate(procedures, start=1):
            out.append(("h2", "%d. %s" % (number, proc.get("title", "Untitled procedure"))))
            if proc.get("ppe"):
                out.append(("body", "PPE: %s" % ", ".join(proc["ppe"])))
            for step_no, step in enumerate(proc.get("steps") or [], start=1):
                out.append(("body", "  %d) %s" % (step_no, step)))
            out.append(("space", ""))
    elif key == "supporting_documents":
        cols = [("label", "Document"), ("reference", "Reference"), ("expires", "Expires"), ("state", "Status")]
        rows = [dict(r, state=EVIDENCE_TEXT[r["status"]]) for r in evidence]
        out.extend(("mono", line) for line in _table_lines(cols, rows))
    elif key == "incident_report":
        rows = profile.get("incidents") or []
        if rows:
            out.extend(("mono", line) for line in _table_lines(section["columns"], rows))
            out.append(("space", ""))
        out.append(("h2", "Blank incident report"))
        for field in section["form_fields"]:
            out.append(("body", "%s: ________________________________________________" % field))
    else:
        rows = _get(profile, section["source"]) or []
        if not rows and not section.get("blank_rows"):
            out.append(("body", "No entries yet."))
        else:
            out.extend(("mono", line) for line in _table_lines(section["columns"], rows, section.get("blank_rows", 0)))
    return out


def _emit(doc, items):
    for style, text in items:
        if style == "space":
            doc.space()
        else:
            doc.text(text, style)


def render(profile, base_dir=None, today=None):
    """Return (markdown, pdf_bytes, report) for the profile."""
    report = status(profile, base_dir, today)
    today_s = report["generated_on"]
    evidence = _evidence(profile, base_dir, _today(today_s))
    provenance = "Safety Files %s | generated %s | revision %s | status: %s" % (
        report["engine_version"],
        today_s,
        report["fingerprint"],
        report["status"],
    )
    header = "NOT YET REVIEWED - have your safety officer check this file" if not report["reviewed"] else ""
    company = _get(profile, "company.name")
    site = _get(profile, "site.name")

    # Body first, so the index knows each section's page.
    body = Document()
    starts = []
    for number, section in enumerate(templates.SECTIONS, start=1):
        body.new_page()
        starts.append(body.page_number)
        body.text("%d. %s" % (number, section["title"]), "h1")
        body.space(6)
        _emit(body, _section_body(section, profile, evidence))

    front = Document()
    front.text("Site Safety File", "title")
    front.space(10)
    front.text(company, "h1")
    front.text("Site: %s" % site, "h2")
    client = _get(profile, "site.client")
    if client:
        front.text("Client: %s" % client, "h2")
    front.space(20)
    if not report["reviewed"]:
        front.text(templates.REVIEW_NOTICE, "body")
        front.space(10)
    front.text("Open items: %d. Expired: %d. Due within %d days: %d." % (
        report["summary"]["gaps"], report["summary"]["expired"], EXPIRY_WARNING_DAYS, report["summary"]["due_soon"]))
    for gap in report["gaps"]:
        front.text("- " + gap["message"], "small")
    front.space(10)
    front.text(provenance, "small")
    front_pages = len(front.pages)
    front.new_page()
    front.text("Index", "h1")
    front.space(6)
    offset = front_pages + 1  # index is one page
    for number, (section, start) in enumerate(zip(templates.SECTIONS, starts), start=1):
        front.text("%2d. %s %s page %d" % (number, section["title"], "." * max(2, 60 - len(section["title"])), start + offset), "mono")

    final = Document(header=header, footer=provenance)
    final.pages = front.pages + body.pages
    pdf_bytes = final.render()

    md = ["---", "engine: safety_files %s" % report["engine_version"], "status: %s" % report["status"], "revision: %s" % report["fingerprint"], "---", ""]
    md.append("# Site Safety File: %s" % company)
    md.append("")
    md.append("Site: %s" % site)
    md.append("")
    if not report["reviewed"]:
        md.append("> " + templates.REVIEW_NOTICE)
        md.append("")
    md.append("## Index")
    for number, section in enumerate(templates.SECTIONS, start=1):
        md.append("%d. %s" % (number, section["title"]))
    for number, section in enumerate(templates.SECTIONS, start=1):
        md.append("")
        md.append("## %d. %s" % (number, section["title"]))
        md.append("")
        in_code = False
        for style, text in _section_body(section, profile, evidence):
            if style == "mono" and not in_code:
                md.append("```")
                in_code = True
            elif style != "mono" and in_code:
                md.append("```")
                in_code = False
            if style == "space":
                md.append("")
            elif style == "h2":
                md.append("### " + text)
            else:
                md.append(text)
        if in_code:
            md.append("```")
    md.append("")
    md.append("---")
    md.append("_%s_" % provenance)
    return "\n".join(md) + "\n", pdf_bytes, report


def build(profile, out_dir, base_dir=None, today=None):
    """Write the binder and reports into out_dir and return the report."""
    markdown, pdf_bytes, report = render(profile, base_dir, today)
    os.makedirs(out_dir, exist_ok=True)
    outputs = {
        "binder_md": os.path.join(out_dir, "binder.md"),
        "binder_pdf": os.path.join(out_dir, "binder.pdf"),
        "gap_report": os.path.join(out_dir, "gap_report.json"),
        "expiry_log": os.path.join(out_dir, "expiry_log.json"),
    }
    with open(outputs["binder_md"], "w", encoding="utf-8") as fh:
        fh.write(markdown)
    with open(outputs["binder_pdf"], "wb") as fh:
        fh.write(pdf_bytes)
    with open(outputs["gap_report"], "w", encoding="utf-8") as fh:
        json.dump(report["gaps"], fh, indent=2)
    with open(outputs["expiry_log"], "w", encoding="utf-8") as fh:
        json.dump(report["expiries"], fh, indent=2)
    report["outputs"] = outputs
    return report
