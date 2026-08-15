# Copyright (c) 2026, Rokct Intelligence (pty) Ltd.
# For license information, please see license.txt


"""Compliance document sourcing — fail-closed, jurisdiction-gated, provenanced.

Design rule, and the reason this module exists separately:

    **A regulatory claim is only ever made when a document says so.**

Everything starts as PENDING. A parsed certificate promotes a field to
VERIFIED. A jurisdiction that has no such regime marks it NOT_APPLICABLE.
Nothing else can promote a field — there are no optimistic defaults.

The engine this replaces defaulted an unverified company to
`B-BBEE Level 1 Contributor`, `100% black ownership`, `100% youth owned` and
`Tax: Good Standing`, then appended `(Pty) Ltd` to a folder name and called it
a registered legal entity. Misstating B-BBEE status is fronting under s13O of
the B-BBEE Amendment Act; the original `generate_canvases.py` defaulted these
to "Pending" and carried a comment reading "never derive from folder". This
module restores that property and makes it structural.
"""

import glob
import json
import os
import re
from datetime import date, datetime

from core import jurisdictions
from core.jurisdictions import (
    FEATURE_BBEE,
    FEATURE_COMPANY_REGISTRY,
    FEATURE_TAX_CLEARANCE,
    FEATURE_TRADEMARKS,
)

try:
    import pypdf
except ImportError:  # pragma: no cover - environment dependent
    pypdf = None


STATUS_VERIFIED = "verified"
STATUS_OVERRIDE = "override"
STATUS_PENDING = "pending"
STATUS_NOT_APPLICABLE = "not_applicable"

# What a field renders as when applicable but unproven, and when the regime
# does not exist in this jurisdiction at all.
NOT_APPLICABLE_TEXT = "Not applicable"

# Fields grouped by the compliance feature that governs them. A jurisdiction
# that lacks the feature marks every field in the group NOT_APPLICABLE.
_FIELD_GROUPS = {
    FEATURE_COMPANY_REGISTRY: (
        "company_name",
        "reg_number",
        "reg_date",
        "registered_office",
        "postal_address",
    ),
    FEATURE_TAX_CLEARANCE: (
        "tax_number",
        "tax_pin",
        "tax_pin_issue_date",
        "tax_pin_expiry_date",
        "tax_compliance_status",
    ),
    FEATURE_BBEE: (
        "bee_level",
        "bee_procurement_recognition",
        "bee_black_ownership",
        "bee_youth_owned",
        "bee_disabled_owned",
        "bee_rural_owned",
        "bee_cert_number",
        "bee_issue_date",
        "bee_expiry_date",
    ),
}

# Human guidance rendered when a field is applicable but has no document.
_PENDING_HINTS = {
    "company_name": "registered name not verified — add {registry_document}.pdf",
    "reg_number": "registration number not verified — add {registry_document}.pdf",
    "reg_date": "registration date not verified — add {registry_document}.pdf",
    "registered_office": "registered office not verified — add {registry_document}.pdf",
    "postal_address": "postal address not verified — add {registry_document}.pdf",
    "tax_number": "tax reference not verified — add Tax_Pin.pdf",
    "tax_pin": "tax compliance PIN not provided — add Tax_Pin.pdf",
    "tax_pin_issue_date": "not provided — add Tax_Pin.pdf",
    "tax_pin_expiry_date": "not provided — add Tax_Pin.pdf",
    "tax_compliance_status": "tax compliance status not verified — add Tax_Pin.pdf",
    "bee_level": "B-BBEE certificate not provided — add BEE.pdf",
    "bee_procurement_recognition": "not provided — add BEE.pdf",
    "bee_black_ownership": "not provided — add BEE.pdf",
    "bee_youth_owned": "not provided — add BEE.pdf",
    "bee_disabled_owned": "not provided — add BEE.pdf",
    "bee_rural_owned": "not provided — add BEE.pdf",
    "bee_cert_number": "not provided — add BEE.pdf",
    "bee_issue_date": "not provided — add BEE.pdf",
    "bee_expiry_date": "not provided — add BEE.pdf",
}

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%Y/%m/%d",
    "%d-%b-%Y",
    "%d-%B-%Y",  # 25-October-2024 — the format that silently defeated the
    # legacy expiry check and let an expired BEE certificate
    # report as "no explicit expiry date".
    "%d %b %Y",
    "%d %B %Y",
    "%b %d, %Y",
    "%B %d, %Y",
)


class Field:
    """A single compliance value plus where it came from."""

    __slots__ = ("key", "value", "status", "source")

    def __init__(self, key, value=None, status=STATUS_PENDING, source=None):
        self.key = key
        self.value = value
        self.status = status
        self.source = source

    @property
    def is_verified(self):
        return self.status in (STATUS_VERIFIED, STATUS_OVERRIDE)

    @property
    def is_applicable(self):
        return self.status != STATUS_NOT_APPLICABLE

    def render(self, pending_hint=None):
        """The string a template should show for this field."""
        if self.status == STATUS_NOT_APPLICABLE:
            return NOT_APPLICABLE_TEXT
        if self.is_verified and self.value:
            return str(self.value)
        return f"Pending — {pending_hint}" if pending_hint else "Pending"

    def __repr__(self):
        return f"Field({self.key!r}, {self.value!r}, {self.status!r})"


class ComplianceRecord:
    """All compliance fields for one instance, with provenance and warnings."""

    def __init__(self, jurisdiction, trading_name):
        self.jurisdiction = jurisdiction
        self.trading_name = trading_name
        self.fields = {}
        self.trademarks = []
        self.warnings = []
        self._init_fields()

    def _init_fields(self):
        for feature, keys in _FIELD_GROUPS.items():
            applicable = self.jurisdiction.supports(feature)
            for key in keys:
                self.fields[key] = Field(
                    key,
                    value=None,
                    status=STATUS_PENDING if applicable else STATUS_NOT_APPLICABLE,
                )

    def set(self, key, value, status=STATUS_VERIFIED, source=None):
        """Record a value. Refuses to promote a NOT_APPLICABLE field.

        This refusal is the guard that keeps a German company from acquiring a
        B-BBEE level because someone dropped a BEE.pdf in its folder.
        """
        field = self.fields.get(key)
        if field is None:
            self.fields[key] = Field(key, value, status, source)
            return True
        if field.status == STATUS_NOT_APPLICABLE and status != STATUS_NOT_APPLICABLE:
            self.warnings.append(
                f"Ignored {key}={value!r} from {source or 'unknown source'}: not "
                f"applicable in {self.jurisdiction.name} ({self.jurisdiction.code})."
            )
            return False
        field.value = value
        field.status = status
        field.source = source
        return True

    def get(self, key):
        return self.fields.get(key)

    def render(self, key):
        field = self.fields.get(key)
        if field is None:
            return ""
        hint = _PENDING_HINTS.get(key)
        if hint:
            hint = hint.format(registry_document=self.jurisdiction.registry_document)
        return field.render(hint)

    def is_verified(self, key):
        field = self.fields.get(key)
        return bool(field and field.is_verified)

    def as_render_dict(self):
        """Flatten to `{placeholder: string}` for the template engine."""
        return {key: self.render(key) for key in self.fields}

    def provenance_rows(self):
        """Rows for the provenance footer: (key, status, source)."""
        rows = []
        for key in sorted(self.fields):
            field = self.fields[key]
            rows.append((key, field.status, field.source or ""))
        return rows

    @property
    def verified_count(self):
        return sum(1 for f in self.fields.values() if f.is_verified)

    @property
    def applicable_count(self):
        return sum(1 for f in self.fields.values() if f.is_applicable)


def parse_date(value):
    """Parse a date string across the formats these certificates actually use."""
    if not value:
        return None
    text = str(value).strip()
    if not text or text.lower().startswith(("pending", "not applicable")):
        return None
    for fmt in _DATE_FORMATS:
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _read_pdf_text(path):
    """Extract text from a PDF, or return None with the reason logged by caller."""
    if not pypdf:
        return None
    reader = pypdf.PdfReader(path)
    chunks = []
    for page in reader.pages:
        try:
            chunks.append(page.extract_text() or "")
        except Exception:
            chunks.append("")
    return "\n".join(chunks)


def load_compliance(compliance_dir, trading_name, jurisdiction, trademark_dir=None):
    """Build a ComplianceRecord from whatever documents exist.

    `compliance_dir` may be missing entirely — that is the common case for a
    freshly provisioned profile, and it yields an all-PENDING record rather
    than an optimistic one.
    """
    record = ComplianceRecord(jurisdiction, trading_name)

    if not jurisdiction.is_known:
        record.warnings.append(
            "Jurisdiction is UNKNOWN — every regulated compliance field is "
            "suppressed. Declare a '**Jurisdiction**' answer to enable them."
        )
        for field in record.fields.values():
            field.status = STATUS_NOT_APPLICABLE
        return record

    if not compliance_dir or not os.path.isdir(compliance_dir):
        record.warnings.append(
            f"No compliance directory at {compliance_dir!r}. All regulated "
            "fields remain Pending — no compliance status is asserted."
        )
        _apply_overrides(record, compliance_dir)
        return record

    if not pypdf:
        record.warnings.append(
            "pypdf is not installed, so certificates cannot be read. All "
            "regulated fields remain Pending. Install with: pip install pypdf"
        )
        _apply_overrides(record, compliance_dir)
        return record

    if jurisdiction.supports(FEATURE_COMPANY_REGISTRY):
        _parse_registry_document(record, compliance_dir, jurisdiction)
    if jurisdiction.supports(FEATURE_BBEE):
        _parse_bee_certificate(record, compliance_dir)
    if jurisdiction.supports(FEATURE_TAX_CLEARANCE):
        _parse_tax_pin(record, compliance_dir)
    if jurisdiction.supports(FEATURE_TRADEMARKS):
        record.trademarks = parse_trademarks(
            trademark_dir or os.path.join(compliance_dir, "TradeMark")
        )

    _apply_overrides(record, compliance_dir)
    return record


def _parse_registry_document(record, compliance_dir, jurisdiction):
    """Parse the company registration certificate (CIPC format today)."""
    filename = f"{jurisdiction.registry_document}.pdf"
    path = os.path.join(compliance_dir, filename)
    if not os.path.exists(path):
        # Tolerate the generic name too, so non-ZA jurisdictions can drop in a
        # file without knowing the registry's local document title.
        fallback = os.path.join(compliance_dir, "Business Registration Certificate.pdf")
        if os.path.exists(fallback):
            path = fallback
        else:
            return

    try:
        text = _read_pdf_text(path)
    except Exception as exc:
        record.warnings.append(f"Could not read {os.path.basename(path)}: {exc}")
        return
    if not text:
        return

    source = os.path.basename(path)

    reg_match = re.search(r"(\d{4}\s*/\s*\d{6,7}\s*/\s*\d{2})", text)
    if reg_match:
        record.set(
            "reg_number",
            re.sub(r"\s+", "", reg_match.group(1)),
            STATUS_VERIFIED,
            source,
        )

    # The registry's own string, used verbatim. The previous engine stripped
    # any suffix off this and re-appended one derived from the enterprise-type
    # code, silently rewriting a legal name that came from the registry.
    # Digits are excluded from the name class on purpose: PDF text extraction
    # runs the registration number straight onto the end of the enterprise
    # name, so a greedy class turns "EXAMPLE TRADING" into
    # "EXAMPLE TRADING 2017".
    name_match = re.search(
        r"Enterprise Name:?\s*([A-Z\s\(\)&.,'-]{3,})", text, re.IGNORECASE
    )
    if name_match:
        legal_name = " ".join(name_match.group(1).split()).strip(" -,.")
        if legal_name:
            record.set("company_name", legal_name, STATUS_VERIFIED, source)

    tax_match = re.search(r"(\d{9,10})\s*TAX\s*Number", text, re.IGNORECASE)
    if tax_match and record.fields["tax_number"].is_applicable:
        record.set("tax_number", tax_match.group(1).strip(), STATUS_VERIFIED, source)

    date_match = re.search(
        r"Registration Date[:\s]+(\d{1,2}\s+\w+\s+\d{4}|\d{4}[-/]\d{2}[-/]\d{2}|\d{1,2}[-/]\d{1,2}[-/]\d{4})",
        text,
        re.IGNORECASE,
    )
    if date_match:
        record.set("reg_date", date_match.group(1).strip(), STATUS_VERIFIED, source)

    addresses = _extract_addresses(text)
    if addresses.get("postal"):
        record.set("postal_address", addresses["postal"], STATUS_VERIFIED, source)
    if addresses.get("registered"):
        record.set(
            "registered_office", addresses["registered"], STATUS_VERIFIED, source
        )


def _extract_addresses(text):
    """Pull postal and registered addresses out of a CIPC certificate body."""
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    start = -1
    for index, line in enumerate(lines):
        if "addresses" in line.lower():
            start = index
            break
    if start == -1:
        return {}

    stop_words = (
        "registration date",
        "business start date",
        "enterprise type",
        "active members",
        "directors",
        "appointment",
        "tax",
    )
    collected = []
    for line in lines[start + 1 : start + 16]:
        if any(word in line.lower() for word in stop_words):
            break
        collected.append(line)

    postal, registered = [], []
    in_registered = False
    for part in collected:
        if not in_registered:
            postal.append(part)
            if re.match(r"^\d{4}$", part):
                in_registered = True
        else:
            registered.append(part)
            if re.match(r"^\d{4}$", part):
                break

    def join_unique(parts):
        seen = []
        for part in parts:
            if part not in seen:
                seen.append(part)
        return ", ".join(seen)

    return {"postal": join_unique(postal), "registered": join_unique(registered)}


def _parse_bee_certificate(record, compliance_dir):
    """Parse a B-BBEE certificate. Only ever called for jurisdictions with the regime."""
    path = os.path.join(compliance_dir, "BEE.pdf")
    if not os.path.exists(path):
        return
    try:
        text = _read_pdf_text(path)
    except Exception as exc:
        record.warnings.append(f"Could not read BEE.pdf: {exc}")
        return
    if not text:
        return

    source = "BEE.pdf"

    level = re.search(r"(LEVEL\s+\d+\s+CONTRIBUTOR)", text, re.IGNORECASE)
    if level:
        record.set(
            "bee_level",
            " ".join(level.group(1).split()).title(),
            STATUS_VERIFIED,
            source,
        )

    procurement = re.search(r"(\d+%)\s*PROCUREMENT\s*RECOGNITION", text, re.IGNORECASE)
    if procurement:
        record.set(
            "bee_procurement_recognition", procurement.group(1), STATUS_VERIFIED, source
        )

    # Certificate identifiers always start with a digit; a bare `\S+` here
    # captured the next word on the page ("Total") when the label and value
    # were separated by a column break.
    cert = re.search(r"Certificate Number\s*:?\s*(\d[\w\-/]*)", text, re.IGNORECASE)
    if not cert:
        cert = re.search(r"Tracking Number\s*:?\s*(\d[\w\-/]*)", text, re.IGNORECASE)
    if cert:
        record.set("bee_cert_number", cert.group(1).strip(), STATUS_VERIFIED, source)

    black = re.search(r"(\d+(?:\.\d+)?%)\s*BLACK\s*OWNERSHIP", text, re.IGNORECASE)
    if black:
        record.set("bee_black_ownership", black.group(1), STATUS_VERIFIED, source)

    youth = re.search(
        r"youth\s+as\s+defined.*?\n\s*(\d+(?:\.\d+)?%)", text, re.DOTALL | re.IGNORECASE
    )
    if youth:
        record.set("bee_youth_owned", youth.group(1), STATUS_VERIFIED, source)

    # Dates: prefer explicit labels, fall back to the last two dates on the page.
    issue = re.search(
        r"Issue\s*Date\s*:?\s*([\d]{1,2}[-/\s][\w]+[-/\s][\d]{4}|[\d]{4}-[\d]{2}-[\d]{2})",
        text,
        re.IGNORECASE,
    )
    expiry = re.search(
        r"Expir\w*\s*Date\s*:?\s*([\d]{1,2}[-/\s][\w]+[-/\s][\d]{4}|[\d]{4}-[\d]{2}-[\d]{2})",
        text,
        re.IGNORECASE,
    )
    if issue:
        record.set("bee_issue_date", issue.group(1).strip(), STATUS_VERIFIED, source)
    if expiry:
        record.set("bee_expiry_date", expiry.group(1).strip(), STATUS_VERIFIED, source)

    if not (issue and expiry):
        found = re.findall(r"(\d{1,2}-[a-zA-Z]+-\d{4})", text)
        if len(found) >= 2:
            if not issue:
                record.set("bee_issue_date", found[-2], STATUS_VERIFIED, source)
            if not expiry:
                record.set("bee_expiry_date", found[-1], STATUS_VERIFIED, source)


def _parse_tax_pin(record, compliance_dir):
    """Parse a tax compliance PIN certificate (SARS TCS format today)."""
    path = os.path.join(compliance_dir, "Tax_Pin.pdf")
    if not os.path.exists(path):
        return
    try:
        text = _read_pdf_text(path)
    except Exception as exc:
        record.warnings.append(f"Could not read Tax_Pin.pdf: {exc}")
        return
    if not text:
        return

    source = "Tax_Pin.pdf"

    ref = re.search(
        r"Taxpayer Reference Number[:\s]+(?:IT\s*-\s*)?(\d+)", text, re.IGNORECASE
    )
    if not ref:
        ref = re.search(r"Tax reference No:?\s*(\d+)", text, re.IGNORECASE)
    if ref:
        record.set("tax_number", ref.group(1).strip(), STATUS_VERIFIED, source)

    pin = re.search(r"\bPIN\s+([A-Z0-9]{8,12})\b", text)
    if pin:
        record.set("tax_pin", pin.group(1).strip(), STATUS_VERIFIED, source)

    issue = re.search(r"Issue Date:?\s*([\d/\-]+)", text, re.IGNORECASE)
    if issue:
        record.set(
            "tax_pin_issue_date", issue.group(1).strip(), STATUS_VERIFIED, source
        )

    expiry = re.search(r"PIN Expiry Date\s*:?\s*([\d/\-]+)", text, re.IGNORECASE)
    if expiry:
        record.set(
            "tax_pin_expiry_date", expiry.group(1).strip(), STATUS_VERIFIED, source
        )

    status = re.search(
        r"Tax Compliance Status\s*:?\s*([A-Za-z ]+)", text, re.IGNORECASE
    )
    if status:
        record.set(
            "tax_compliance_status", status.group(1).strip(), STATUS_VERIFIED, source
        )
    elif pin:
        # A valid PIN was issued; the status wording varies by certificate.
        record.set(
            "tax_compliance_status",
            "Compliant (per issued TCS PIN)",
            STATUS_VERIFIED,
            source,
        )


def parse_trademarks(trademark_dir):
    """Parse CIPC trademark documents, if any."""
    trademarks = []
    if not pypdf or not trademark_dir or not os.path.isdir(trademark_dir):
        return trademarks

    for path in sorted(glob.glob(os.path.join(trademark_dir, "*.pdf"))):
        try:
            text = _read_pdf_text(path)
        except Exception:
            continue
        if not text:
            continue

        entry = {
            "application_number": "Pending",
            "application_date": "Pending",
            "mark": "Pending",
            "status": "Pending",
            "international_class": "Pending",
            "nature": "Ordinary",
        }

        app = re.search(
            r"21\s*Official Application No\.?\s*(\d+/\d+)", text, re.IGNORECASE
        )
        if app:
            entry["application_number"] = app.group(1).strip()
        filed = re.search(r"22\s*Application date\s*([\d\-/]+)", text, re.IGNORECASE)
        if filed:
            entry["application_date"] = filed.group(1).strip()
        mark = re.search(
            r"54\s*Representation of Trade mark\s*\n([^\n]+)", text, re.IGNORECASE
        )
        if mark:
            entry["mark"] = mark.group(1).strip()
        status = re.search(r"TRADE MARK STATUS:?\s*(\S+)", text, re.IGNORECASE)
        if status:
            entry["status"] = status.group(1).strip()
        klass = re.search(
            r"51\s*International Classification\s*(\d+)", text, re.IGNORECASE
        )
        if klass:
            entry["international_class"] = klass.group(1).strip()

        trademarks.append(entry)

    return trademarks


def _apply_overrides(record, compliance_dir):
    """Apply `compliance_overrides.json`, the final user-controlled layer.

    Overrides are marked STATUS_OVERRIDE, not STATUS_VERIFIED, so the
    provenance footer distinguishes "a certificate says this" from "the
    operator asserted this". Overrides still cannot promote a field that the
    jurisdiction marks not-applicable.
    """
    if not compliance_dir:
        return
    path = os.path.join(compliance_dir, "compliance_overrides.json")
    if not os.path.exists(path):
        return

    try:
        with open(path, "r", encoding="utf-8") as handle:
            overrides = json.load(handle)
    except (OSError, ValueError) as exc:
        record.warnings.append(f"Could not read compliance_overrides.json: {exc}")
        return

    for key, value in overrides.items():
        if key.startswith("_") or value is None:
            continue
        if isinstance(value, (dict, list)):
            continue
        record.set(key, value, STATUS_OVERRIDE, "compliance_overrides.json")


def build_compliance_log(record, folder_name, today=None):
    """Render a compliance log with expiry alerts.

    Restores the capability that `generate_canvases.py:write_compliance_log`
    had and the first StartupOS port dropped, plus the date-format fix that
    stops an expired certificate reporting as "no explicit expiry date".
    """
    today = today or date.today()
    jurisdiction = record.jurisdiction
    lines = [
        f"# Compliance Log: {folder_name}",
        f"Generated: {today.isoformat()}",
        f"Jurisdiction: {jurisdiction.name} ({jurisdiction.code})",
        "",
        "## Document Verification & Status",
        "",
    ]

    if not jurisdiction.is_known:
        lines.append(
            "> [!IMPORTANT]\n"
            "> **No jurisdiction declared.** No compliance regime can be "
            "evaluated. Add a `**Jurisdiction**` question to questions.md.\n"
        )
        return "\n".join(lines)

    if jurisdiction.supports(FEATURE_COMPANY_REGISTRY):
        lines.append(_registry_section(record, jurisdiction, folder_name))
    if jurisdiction.supports(FEATURE_BBEE):
        lines.append(
            _expiry_section(
                record,
                today,
                "B-BBEE Certificate",
                "bee_level",
                "bee_expiry_date",
                "bee_cert_number",
                "BEE.pdf",
                folder_name,
            )
        )
    if jurisdiction.supports(FEATURE_TAX_CLEARANCE):
        lines.append(
            _expiry_section(
                record,
                today,
                f"{jurisdiction.tax_authority} Tax Compliance PIN",
                "tax_pin",
                "tax_pin_expiry_date",
                "tax_number",
                "Tax_Pin.pdf",
                folder_name,
            )
        )

    if record.warnings:
        lines.append("## Parser Notes\n")
        for warning in record.warnings:
            lines.append(f"*   {warning}")
        lines.append("")

    return "\n".join(lines)


def _registry_section(record, jurisdiction, folder_name):
    if record.is_verified("company_name") or record.is_verified("reg_number"):
        return (
            f"> [!NOTE]\n"
            f"> **{jurisdiction.registry_name or 'Company registry'} registration verified**.\n"
            f"> * Registered Legal Name: {record.render('company_name')}\n"
            f"> * Registration Number: {record.render('reg_number')}\n"
            f"> * Registration Date: {record.render('reg_date')}\n"
        )
    return (
        f"> [!IMPORTANT]\n"
        f"> **Company registration is not verified**.\n"
        f"> * Place `{jurisdiction.registry_document}.pdf` in "
        f"`Compliance/{folder_name}/`.\n"
        f"> * Until then no registered legal name or number is asserted in any "
        f"generated document.\n"
    )


def _expiry_section(
    record, today, title, primary_key, expiry_key, ref_key, filename, folder_name
):
    if not record.is_verified(primary_key):
        return (
            f"> [!IMPORTANT]\n"
            f"> **{title} is not provided**.\n"
            f"> * Place `{filename}` in `Compliance/{folder_name}/`.\n"
            f"> * No status is claimed for this certificate in any generated document.\n"
        )

    raw_expiry = record.get(expiry_key).value if record.get(expiry_key) else None
    expiry = parse_date(raw_expiry)
    reference = record.render(ref_key)
    primary = record.render(primary_key)

    if expiry is None:
        return (
            f"> [!WARNING]\n"
            f"> **{title} parsed, but its expiry date could not be read** "
            f"(raw value: {raw_expiry!r}).\n"
            f"> * Reference: {reference}\n"
            f"> * Value: {primary}\n"
            f"> * Expiry cannot be monitored until this is corrected — set "
            f"`{expiry_key}` in `compliance_overrides.json`.\n"
        )

    days = (expiry - today).days
    if days < 0:
        return (
            f"> [!CAUTION]\n"
            f"> **{title} EXPIRED** on {expiry.isoformat()} ({abs(days)} days ago).\n"
            f"> * Reference: {reference}\n"
            f"> * Value: {primary}\n"
            f"> * Renew before this is used in any submission.\n"
        )
    if days <= 60:
        return (
            f"> [!WARNING]\n"
            f"> **{title} expires in {days} days** ({expiry.isoformat()}).\n"
            f"> * Reference: {reference}\n"
            f"> * Value: {primary}\n"
        )
    return (
        f"> [!NOTE]\n"
        f"> **{title} is valid** until {expiry.isoformat()} ({days} days remaining).\n"
        f"> * Reference: {reference}\n"
        f"> * Value: {primary}\n"
    )


def compliance_exit_status(record, today=None):
    """Return (code, messages) for CI use.

    0 = everything applicable is verified and unexpired
    1 = something applicable is pending
    2 = something is expired
    """
    today = today or date.today()
    messages = []
    expired = False
    pending = False

    if not record.jurisdiction.is_known:
        # Not "clean" — undetermined. Everything is suppressed precisely because
        # we do not know which regime applies, which is a gap, not a pass.
        return 1, ["PENDING  jurisdiction not declared"]

    for key, field in sorted(record.fields.items()):
        if not field.is_applicable:
            continue
        if not field.is_verified:
            pending = True
            messages.append(f"PENDING  {key}")

    for expiry_key, label in (
        ("bee_expiry_date", "B-BBEE certificate"),
        ("tax_pin_expiry_date", "Tax compliance PIN"),
    ):
        field = record.get(expiry_key)
        if not field or not field.is_applicable or not field.is_verified:
            continue
        expiry = parse_date(field.value)
        if expiry and expiry < today:
            expired = True
            messages.append(f"EXPIRED  {label} ({expiry.isoformat()})")

    if expired:
        return 2, messages
    if pending:
        return 1, messages
    return 0, messages
