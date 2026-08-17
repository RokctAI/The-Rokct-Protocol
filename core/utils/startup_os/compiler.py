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

"""StartupOS compilation pipeline.

Reads `questions.md` (the SSOT), sources compliance evidence, and renders the
template suite for an instance.

Contract, in one line: **the compiler never asserts anything a document or an
answer does not support.** Unproven regulated fields render as `Pending`,
regimes that do not exist in the profile's jurisdiction render as
`Not applicable` or are omitted entirely, and every claim carries provenance.
"""

import os
import re
from datetime import date

from core import __version__ as ENGINE_VERSION
from core import compliance as compliance_mod
from core import documents
from core import jurisdictions
from core import paths as path_utils
from core import safe_io
from core import schemas
from core import template_engine
from core.errors import ProfileNotFoundError, TemplateError
from core.parser import parse_questions_md

COMPLIANCE_ROOT_ENV_VAR = "STARTUPOS_COMPLIANCE_ROOT"

# What an unanswered question renders as. Deliberately falsy to `{{#if}}` so a
# template can omit a section instead of printing this into running prose.
UNANSWERED_TEXT = "Not yet provided"

# Re-exported so existing callers keep working.
resolve_workspace_root = path_utils.resolve_workspace_root

FOOTER_MAPS = {
    "business": {
        "01_executive_summary.md": [
            (
                "02_company_description.md",
                "Legal identity, mission and delivery model",
                "Company Description",
            ),
            (
                "03_market_analysis.md",
                "Sizing, competition and segments",
                "Market Analysis",
            ),
            (
                "07_financial_model.md",
                "Revenue streams and projections",
                "Financial Model",
            ),
            (
                "annexures/investor_pitch_deck.md",
                "Slide-by-slide investment case",
                "Investor Pitch Deck",
            ),
        ],
        "02_company_description.md": [
            (
                "business_profile.md",
                "Institution-ready corporate summary",
                "Business Profile",
            ),
            (
                "06_technical_architecture.md",
                "How the offering is built and delivered",
                "Delivery Architecture",
            ),
            (
                "08_risk_and_mitigation.md",
                "Risk register and compliance exposure",
                "Risk & Mitigation",
            ),
            (
                "annexures/succession_plan.md",
                "Leadership continuity",
                "Succession Plan",
            ),
        ],
        "03_market_analysis.md": [
            ("01_executive_summary.md", "The venture in one page", "Executive Summary"),
            (
                "05_marketing_and_sales.md",
                "How the market is reached",
                "Marketing & Sales",
            ),
            (
                "10_lean_canvas.md",
                "Problem, solution and advantage on one grid",
                "Lean Canvas",
            ),
        ],
        "04_product_ecosystem.md": [
            (
                "06_technical_architecture.md",
                "Build and delivery detail",
                "Delivery Architecture",
            ),
            (
                "annexures/product_pricing_list.md",
                "Prices and commercial terms",
                "Price List",
            ),
            (
                "09_business_model_canvas.md",
                "How the offering creates value",
                "Business Model Canvas",
            ),
        ],
        "05_marketing_and_sales.md": [
            ("03_market_analysis.md", "Who the market is", "Market Analysis"),
            ("annexures/marketing_plan.md", "Full marketing plan", "Marketing Plan"),
            ("annexures/sales_plan.md", "Full sales plan", "Sales Plan"),
            ("sales_plan_on_a_page.md", "1-Page sales summary", "Sales Plan on a Page"),
        ],
        "06_technical_architecture.md": [
            ("04_product_ecosystem.md", "What is delivered", "Products & Services"),
            (
                "operational_plan_on_a_page.md",
                "1-Page operating summary",
                "Operational Plan on a Page",
            ),
            (
                "annexures/business_continuity_plan.md",
                "Failure and recovery",
                "Business Continuity Plan",
            ),
            (
                "annexures/quality_management_system.md",
                "Quality controls and records",
                "Quality Management System",
            ),
        ],
        "07_financial_model.md": [
            (
                "financial_plan_on_a_page.md",
                "1-Page financial summary",
                "Financial Plan on a Page",
            ),
            (
                "annexures/product_pricing_list.md",
                "Price points behind the model",
                "Price List",
            ),
            (
                "annexures/investor_pitch_deck.md",
                "The funding ask",
                "Investor Pitch Deck",
            ),
        ],
        "08_risk_and_mitigation.md": [
            (
                "annexures/business_continuity_plan.md",
                "Continuity and recovery targets",
                "Business Continuity Plan",
            ),
            ("annexures/succession_plan.md", "Key-person cover", "Succession Plan"),
            (
                "compliance_log.md",
                "Certificate status and expiry warnings",
                "Compliance Log",
            ),
        ],
        "09_business_model_canvas.md": [
            ("10_lean_canvas.md", "Venture Strategic Lean Canvas", "Lean Canvas"),
            (
                "business_plan_on_a_page.md",
                "1-Page Commercial Mechanics",
                "Business Plan on a Page",
            ),
            (
                "financial_plan_on_a_page.md",
                "1-Page Financial Projections",
                "Financial Plan on a Page",
            ),
        ],
        "10_lean_canvas.md": [
            (
                "09_business_model_canvas.md",
                "High-Level 9-Box Canvas Grid",
                "Business Model Canvas",
            ),
            (
                "business_plan_on_a_page.md",
                "1-Page Commercial Mechanics",
                "Business Plan on a Page",
            ),
            (
                "03_market_analysis.md",
                "Market sizing and competition",
                "Market Analysis",
            ),
        ],
        "business_plan_on_a_page.md": [
            ("01_executive_summary.md", "The long-form summary", "Executive Summary"),
            (
                "09_business_model_canvas.md",
                "High-Level 9-Box Canvas Grid",
                "Business Model Canvas",
            ),
            ("10_lean_canvas.md", "Venture Strategic Lean Canvas", "Lean Canvas"),
            (
                "financial_plan_on_a_page.md",
                "1-Page Financial Projections",
                "Financial Plan on a Page",
            ),
        ],
        "business_profile.md": [
            (
                "02_company_description.md",
                "Full company description",
                "Company Description",
            ),
            (
                "compliance_log.md",
                "Certificate status and expiry warnings",
                "Compliance Log",
            ),
            ("01_executive_summary.md", "The venture in one page", "Executive Summary"),
        ],
        "financial_plan_on_a_page.md": [
            ("07_financial_model.md", "Full financial model", "Financial Model"),
            (
                "09_business_model_canvas.md",
                "High-Level 9-Box Canvas Grid",
                "Business Model Canvas",
            ),
            (
                "business_plan_on_a_page.md",
                "1-Page Commercial Mechanics",
                "Business Plan on a Page",
            ),
        ],
        "strategic_plan_on_a_page.md": [
            ("01_executive_summary.md", "The venture in one page", "Executive Summary"),
            (
                "project_plan_on_a_page.md",
                "Projects delivering the strategy",
                "Project Plan on a Page",
            ),
            (
                "people_plan_on_a_page.md",
                "Team required to deliver it",
                "People Plan on a Page",
            ),
        ],
        "marketing_plan_on_a_page.md": [
            ("annexures/marketing_plan.md", "Full marketing plan", "Marketing Plan"),
            (
                "05_marketing_and_sales.md",
                "Marketing and sales strategy",
                "Marketing & Sales",
            ),
        ],
        "sales_plan_on_a_page.md": [
            ("annexures/sales_plan.md", "Full sales plan", "Sales Plan"),
            (
                "annexures/sales_terms_and_conditions.md",
                "Standard terms of sale",
                "Terms of Sale",
            ),
            ("annexures/product_pricing_list.md", "Price list", "Price List"),
        ],
        "operational_plan_on_a_page.md": [
            (
                "06_technical_architecture.md",
                "Build and delivery detail",
                "Delivery Architecture",
            ),
            (
                "annexures/quality_management_system.md",
                "Quality controls",
                "Quality Management System",
            ),
            (
                "annexures/business_continuity_plan.md",
                "Continuity planning",
                "Business Continuity Plan",
            ),
        ],
        "people_plan_on_a_page.md": [
            (
                "annexures/succession_plan.md",
                "Key-person cover and succession",
                "Succession Plan",
            ),
            (
                "strategic_plan_on_a_page.md",
                "What the team is being built for",
                "Strategic Plan on a Page",
            ),
        ],
        "project_plan_on_a_page.md": [
            (
                "strategic_plan_on_a_page.md",
                "Objectives the projects serve",
                "Strategic Plan on a Page",
            ),
            ("people_plan_on_a_page.md", "Resourcing", "People Plan on a Page"),
        ],
        "annexures/investor_pitch_deck.md": [
            ("01_executive_summary.md", "The written summary", "Executive Summary"),
            ("07_financial_model.md", "Figures behind the deck", "Financial Model"),
            ("business_profile.md", "Corporate standing", "Business Profile"),
        ],
        "annexures/business_continuity_plan.md": [
            ("08_risk_and_mitigation.md", "The risk register", "Risk & Mitigation"),
            (
                "annexures/succession_plan.md",
                "Key-person continuity",
                "Succession Plan",
            ),
        ],
        "annexures/succession_plan.md": [
            (
                "people_plan_on_a_page.md",
                "Team and key-person risk",
                "People Plan on a Page",
            ),
            (
                "annexures/business_continuity_plan.md",
                "Operational continuity",
                "Business Continuity Plan",
            ),
        ],
        "annexures/marketing_plan.md": [
            (
                "marketing_plan_on_a_page.md",
                "1-Page summary",
                "Marketing Plan on a Page",
            ),
            ("03_market_analysis.md", "Market sizing and segments", "Market Analysis"),
        ],
        "annexures/sales_plan.md": [
            ("sales_plan_on_a_page.md", "1-Page summary", "Sales Plan on a Page"),
            (
                "annexures/sales_terms_and_conditions.md",
                "Terms sales may agree",
                "Terms of Sale",
            ),
        ],
        "annexures/product_pricing_list.md": [
            (
                "annexures/sales_terms_and_conditions.md",
                "Full terms of sale",
                "Terms of Sale",
            ),
            ("07_financial_model.md", "Margin and cost basis", "Financial Model"),
        ],
        "annexures/quality_management_system.md": [
            (
                "operational_plan_on_a_page.md",
                "1-Page operating summary",
                "Operational Plan on a Page",
            ),
            ("compliance_log.md", "Certificate status", "Compliance Log"),
        ],
        "annexures/sales_terms_and_conditions.md": [
            (
                "annexures/product_pricing_list.md",
                "Prices these terms apply to",
                "Price List",
            ),
            ("annexures/sales_plan.md", "How they are used in the field", "Sales Plan"),
        ],
    },
    "life": {
        "09_life_model_canvas.md": [
            (
                "10_life_lean_canvas.md",
                "Personal Lean Growth Canvas",
                "Personal Lean Canvas",
            ),
            (
                "life_plan_on_a_page.md",
                "1-Page Life Rhythm Plan",
                "Life Plan on a Page",
            ),
        ],
        "10_life_lean_canvas.md": [
            (
                "09_life_model_canvas.md",
                "Personal Life Model Canvas",
                "Personal Life Canvas",
            ),
            (
                "life_plan_on_a_page.md",
                "1-Page Life Rhythm Plan",
                "Life Plan on a Page",
            ),
        ],
        "life_plan_on_a_page.md": [
            (
                "09_life_model_canvas.md",
                "Personal Life Model Canvas",
                "Personal Life Canvas",
            ),
            (
                "10_life_lean_canvas.md",
                "Personal Lean Growth Canvas",
                "Personal Lean Canvas",
            ),
            (
                "health_plan_on_a_page.md",
                "1-Page Biological Conditioning Plan",
                "Health Plan on a Page",
            ),
            (
                "financial_legacy_plan_on_a_page.md",
                "1-Page Multigenerational Stewardship Plan",
                "Financial Legacy Plan on a Page",
            ),
            (
                "productivity_plan_on_a_page.md",
                "1-Page Master Accountability Plan",
                "Productivity Plan on a Page",
            ),
            (
                "legacy_plan_on_a_page.md",
                "1-Page Legacy Preservations Plan",
                "Legacy Plan on a Page",
            ),
        ],
        "health_plan_on_a_page.md": [
            (
                "life_plan_on_a_page.md",
                "1-Page Life Rhythm Plan",
                "Life Plan on a Page",
            ),
        ],
        "financial_legacy_plan_on_a_page.md": [
            (
                "life_plan_on_a_page.md",
                "1-Page Life Rhythm Plan",
                "Life Plan on a Page",
            ),
        ],
        "productivity_plan_on_a_page.md": [
            (
                "life_plan_on_a_page.md",
                "1-Page Life Rhythm Plan",
                "Life Plan on a Page",
            ),
        ],
        "legacy_plan_on_a_page.md": [
            (
                "life_plan_on_a_page.md",
                "1-Page Life Rhythm Plan",
                "Life Plan on a Page",
            ),
        ],
    },
}


class CompileResult:
    """Outcome of one compilation."""

    def __init__(self, instance_type, instance_name, output_dir, jurisdiction):
        self.instance_type = instance_type
        self.instance_name = instance_name
        self.output_dir = output_dir
        self.jurisdiction = jurisdiction
        self.written = []
        self.removed = []
        self.warnings = []
        self.missing_fields = {}
        self.completeness = 0.0
        self.compliance_status = 0

    @property
    def ok(self):
        return bool(self.written)

    def summary(self):
        # ASCII only: the Windows console defaults to cp1252, and a stray arrow
        # glyph here crashed the run after every document had been written.
        lines = [
            f"[StartupOS] {self.instance_type}/{self.instance_name} "
            f"-> {len(self.written)} documents",
            f"  Jurisdiction : {self.jurisdiction.name} ({self.jurisdiction.code})",
            f"  Completeness : {self.completeness:.0%} of questions answered",
        ]
        if self.removed:
            lines.append(f"  Pruned stale : {', '.join(self.removed)}")
        if self.missing_fields:
            lines.append(f"  Unanswered   : {len(self.missing_fields)} field(s)")
        if self.warnings:
            lines.append(f"  Warnings     : {len(self.warnings)}")
        return "\n".join(lines)


def resolve_compliance_dir(
    workspace_root, instance_type, instance_name, compliance_root=None, warnings=None
):
    """Locate the compliance evidence directory for an instance.

    Order: explicit argument, environment variable, instance-local
    `compliance/`, then `<workspace parent>/Compliance/<name>`.

    Notably absent: the hardcoded `C:\\Users\\sinya\\Desktop\\RokctAI\\Monorepo`
    that the previous engine fell back to. That directory was renamed to
    `occultation` some time ago, so every business compile silently logged
    "compliance folder not found" and proceeded on fabricated defaults.
    """
    warnings = warnings if warnings is not None else []

    if compliance_root:
        candidate = os.path.join(os.path.abspath(compliance_root), instance_name)
        if os.path.isdir(candidate):
            return candidate
        if os.path.isdir(compliance_root):
            return candidate  # honour the explicit root even when empty
        warnings.append(f"--compliance-root {compliance_root!r} does not exist.")

    env_root = os.environ.get(COMPLIANCE_ROOT_ENV_VAR)
    if env_root:
        candidate = os.path.join(os.path.abspath(env_root), instance_name)
        if os.path.isdir(candidate):
            return candidate

    local = os.path.join(
        path_utils.instance_dir(workspace_root, instance_type, instance_name),
        "compliance",
    )
    if os.path.isdir(local):
        return local

    sibling = os.path.join(
        os.path.dirname(os.path.abspath(workspace_root)), "Compliance", instance_name
    )
    if os.path.isdir(sibling):
        return sibling

    return local  # canonical location; caller reports it as missing


def compile_instance(
    instance_type,
    instance_name,
    monorepo_root=None,
    workspace_root=None,
    compliance_root=None,
    quiet=False,
):
    """Compile the template suite for one instance.

    `monorepo_root` is accepted for backwards compatibility and treated as
    `compliance_root`'s parent.
    """
    instance_type = path_utils.validate_instance_type(instance_type)
    instance_name = path_utils.sanitize_instance_name(instance_name)

    root = path_utils.resolve_workspace_root(workspace_root, verbose=not quiet)
    questions_file = path_utils.questions_path(root, instance_type, instance_name)
    out_dir = path_utils.output_dir(root, instance_type, instance_name)
    template_root = path_utils.templates_dir(root, instance_type)

    if not os.path.exists(questions_file):
        raise ProfileNotFoundError(
            f"Missing strategic source of truth: {questions_file}\n"
            f"Provision it first:  python provision.py --type {instance_type} "
            f"--name {instance_name}"
        )
    if not os.path.isdir(template_root):
        raise TemplateError(
            f"Missing template folder: {template_root}\n"
            "Templates ship with the skill; run the compile wrapper so they sync, "
            "or copy them from core/skills/.rok/startup_os/templates/."
        )

    if not compliance_root and monorepo_root:
        compliance_root = os.path.join(monorepo_root, "Compliance")

    profile = parse_questions_md(questions_file)
    warnings = list(profile.warnings)

    jurisdiction = jurisdictions.resolve(profile.answers, warnings)
    result = CompileResult(instance_type, instance_name, out_dir, jurisdiction)
    result.completeness = profile.completeness

    trading_name = profile.get("trading_name") or _humanise(instance_name)

    record = None
    if instance_type == "business":
        compliance_dir = resolve_compliance_dir(
            root, instance_type, instance_name, compliance_root, warnings
        )
        record = compliance_mod.load_compliance(
            compliance_dir, trading_name, jurisdiction
        )
        warnings.extend(record.warnings)

    values = _build_values(
        profile,
        jurisdiction,
        record,
        trading_name,
        instance_name,
        instance_type,
        warnings,
    )

    context = template_engine.RenderContext(
        values=values, jurisdiction=jurisdiction, features=jurisdiction.features
    )

    template_files = list(_iter_templates(template_root))
    if not template_files:
        raise TemplateError(f"No .md templates found in {template_root}")

    os.makedirs(out_dir, exist_ok=True)
    generated_on = date.today()
    written_names = set()

    for template_path, relative_name in template_files:
        with open(template_path, "r", encoding="utf-8") as handle:
            template_text = handle.read()

        rendered, render_warnings = template_engine.render(template_text, context)
        for warning in render_warnings:
            warnings.append(f"{relative_name}: {warning}")

        document = _assemble(
            rendered=rendered,
            filename=relative_name,
            instance_name=instance_name,
            instance_type=instance_type,
            jurisdiction=jurisdiction,
            record=record,
            profile=profile,
            generated_on=generated_on,
        )

        destination = os.path.join(out_dir, *relative_name.split("/"))
        path_utils.assert_contained(out_dir, destination)
        safe_io.atomic_write(destination, document)
        written_names.add(relative_name)
        result.written.append(relative_name)
        if not quiet:
            print(f"  Generated: {relative_name}")

    if record is not None:
        log_text = compliance_mod.build_compliance_log(
            record, instance_name, generated_on
        )
        safe_io.atomic_write(os.path.join(out_dir, "compliance_log.md"), log_text)
        written_names.add("compliance_log.md")
        result.written.append("compliance_log.md")
        status, _messages = compliance_mod.compliance_exit_status(record, generated_on)
        result.compliance_status = status

    # Prune only after everything this run produces is known, or the compliance
    # log would be deleted moments after being written.
    result.removed = safe_io.prune_directory(out_dir, written_names | {".history"})

    result.missing_fields = {
        key: profile.labels.get(key, key) for key in sorted(profile.pending)
    }
    result.warnings = warnings

    if not quiet:
        print(result.summary())
        for warning in warnings:
            print(f"  [warn] {warning}")

    return result


def _iter_templates(template_root):
    """Yield `(absolute_path, relative_path)` for every template, including
    subdirectories such as `annexures/`, whose structure is mirrored in output.
    """
    for directory, subdirs, filenames in os.walk(template_root):
        subdirs[:] = sorted(name for name in subdirs if not name.startswith("."))
        for filename in sorted(filenames):
            if not filename.endswith(".md"):
                continue
            absolute = os.path.join(directory, filename)
            relative = os.path.relpath(absolute, template_root).replace(os.sep, "/")
            yield absolute, relative


def _assemble(
    rendered,
    filename,
    instance_name,
    instance_type,
    jurisdiction,
    record,
    profile,
    generated_on,
):
    """Wrap a rendered body with control block, footers and gap report."""
    fingerprint = documents.content_fingerprint(rendered)

    version_block = documents.build_version_block(
        instance_name=instance_name,
        instance_type=instance_type,
        engine_version=ENGINE_VERSION,
        fingerprint=fingerprint,
        generated_on=generated_on,
        completeness=profile.completeness,
        verified_fields=record.verified_count if record else None,
        applicable_fields=record.applicable_count if record else None,
        privacy_law=jurisdiction.privacy_law,
    )

    document = documents.insert_version_block(rendered, version_block)
    document += documents.build_link_footer(
        FOOTER_MAPS.get(instance_type, {}).get(filename)
    )

    if record is not None:
        document += documents.build_provenance_footer(
            record.provenance_rows(), jurisdiction.name
        )

    missing = {key: profile.labels.get(key, key) for key in sorted(profile.pending)}
    document += documents.build_gap_report(missing, [])

    return document.rstrip() + "\n"


def _humanise(name):
    """`TableMountainTech` -> `Table Mountain Tech`."""
    spaced = re.sub(r"(?<=[a-z0-9])(?=[A-Z])", " ", name)
    spaced = re.sub(r"(?<=[A-Z])(?=[A-Z][a-z])", " ", spaced)
    return spaced.replace("_", " ").replace("-", " ").strip()


def _build_values(
    profile, jurisdiction, record, trading_name, instance_name, instance_type, warnings
):
    """Assemble the full placeholder namespace for the renderer."""
    values = dict(profile.answers)

    # Seed every question the schema knows about, so a template never renders
    # the «not set» marker for a field the user simply has not answered yet.
    # Unanswered fields read as "Not yet provided", which `{{#if}}` treats as
    # falsy — templates can therefore hide a section rather than print a
    # placeholder sentence into an executive summary.
    for key in schemas.schema_keys(instance_type):
        values.setdefault(key, UNANSWERED_TEXT)
    for key in profile.pending:
        values.setdefault(key, UNANSWERED_TEXT)

    values["trading_name"] = trading_name
    values["instance_name"] = instance_name
    values["jurisdiction_code"] = jurisdiction.code
    values["jurisdiction_name"] = jurisdiction.name
    values["currency"] = jurisdiction.currency
    values["currency_symbol"] = jurisdiction.currency_symbol
    values["privacy_law"] = jurisdiction.privacy_law or ""
    values["standards_body"] = jurisdiction.standards_body or ""
    values["registry_name"] = jurisdiction.registry_name or ""
    values["tax_authority"] = jurisdiction.tax_authority or ""

    if instance_type == "business":
        _add_financials(values, profile, jurisdiction)
        _add_computed_financials(values, profile, jurisdiction)
        _add_market_analysis(values, profile)

    if record is not None:
        values.update(record.as_render_dict())
        # The legal name is only the registry's string. When unverified we show
        # the trading name and say so, rather than inventing "<name> (Pty) Ltd".
        if not record.is_verified("company_name"):
            values["company_name"] = trading_name
            values["company_name_status"] = (
                "Trading name — legal registration not yet verified"
            )
        else:
            values["company_name_status"] = "Registered legal name"

        suffix_hint = jurisdictions.entity_suffix_for(
            jurisdiction,
            record.get("reg_number").value if record.get("reg_number") else None,
        )
        values["entity_type_hint"] = suffix_hint or ""

        values["trademarks_details"] = _format_trademarks(record.trademarks)
    else:
        values.setdefault("company_name", trading_name)

    if instance_type == "life":
        _add_life_values(values, profile, warnings)

    return values


def _format_trademarks(trademarks):
    if not trademarks:
        return "No registered trademarks on file."
    lines = []
    for entry in trademarks:
        lines.append(
            f'"{entry["mark"]}" | App {entry["application_number"]} | '
            f"Filed: {entry['application_date']} | Class {entry['international_class']} "
            f"({entry['nature']}) | Status: {entry['status']}"
        )
    return "  • " + "\n  • ".join(lines)


def _add_financials(values, profile, jurisdiction):
    """Build financial summary blocks in the profile's own currency."""
    symbol = jurisdiction.currency_symbol or ""

    def answered(key):
        value = profile.get(key)
        return value if value else None

    year_1 = answered("projected_year_1")
    year_2 = answered("projected_year_2")
    year_3 = answered("projected_year_3")

    rows = []
    for label, value in (("Year 1", year_1), ("Year 2", year_2), ("Year 3", year_3)):
        rows.append(
            f"*   **{label} Projections**: {value}"
            if value
            else f"*   **{label} Projections**: Pending — not yet provided"
        )

    historical = []
    for key, label in (
        ("historical_turnover_2024", "2024"),
        ("historical_turnover_2025", "2025"),
        ("historical_turnover_2026_ytd", "2026 YTD"),
    ):
        value = answered(key)
        if value:
            historical.append(f"{label}: {value}")
    if historical:
        rows.append(f"*   **Historical Base**: {' | '.join(historical)}")

    values["fin_summary"] = "\n".join(rows)

    grid = []
    for label, value in (("Year 1", year_1), ("Year 2", year_2), ("Year 3", year_3)):
        head = (
            value.split("|")[0].strip()
            if value and "|" in value
            else (value or "Pending")
        )
        grid.append(f"• **{label}**: {head}")
    values["fin_grid_rev"] = "<br>".join(grid)
    values["currency_note"] = (
        f"All figures in {jurisdiction.currency} ({symbol})."
        if jurisdiction.currency
        else "Currency not specified."
    )


# ---------------------------------------------------------------------------
# Numeric parsing and derived financials.
#
# Financial answers are free text — "R 4,800,000 revenue | 120 clinics",
# "$1.2m", "ZAR 500k", "2% monthly". The previous financial model only echoed
# those sentences back and shipped a unit-economics table of literal
# "_to be supplied_" cells, even when the answers held every number needed.
# These helpers extract the figures so the compiler can derive growth, runway,
# CAC payback and lifetime value — and every derived figure says which answers
# it was computed from. When an answer does not parse, it is treated as
# narrative and the document falls back to coaching. Nothing is ever invented.
# ---------------------------------------------------------------------------

_MONEY_RE = re.compile(
    r"""(?:(?P<cur>[A-Z]{3}(?=\s?\d)|[R$€£₦₹¥])\s?)?
        (?P<num>\d{1,3}(?:[ ,]\d{3})+(?:\.\d+)?    # 1,200,000 or 1 200 000
              |\d+(?:\.\d+)?)                      # 1200000 or 1.2
        \s*(?P<scale>bn|billion|mn|million|m|k|thousand|b)?\b""",
    re.VERBOSE,
)

_SCALES = {
    "k": 1e3,
    "thousand": 1e3,
    "m": 1e6,
    "mn": 1e6,
    "million": 1e6,
    "b": 1e9,
    "bn": 1e9,
    "billion": 1e9,
}

_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*(?:%|percent\b)", re.IGNORECASE)

_MONTHLY_RE = re.compile(
    r"(?:\bper\s+month\b|\bmonthly\b|\ba\s+month\b|/\s*m(?:o|onth)?\b|\bp/?m\b)",
    re.IGNORECASE,
)
_ANNUAL_RE = re.compile(
    r"(?:\bper\s+(?:year|annum)\b|\bannual(?:ly)?\b|\byearly\b"
    r"|\ba\s+year\b|/\s*y(?:ear|r)?\b|\bp/?a\b)",
    re.IGNORECASE,
)


def parse_money(text):
    """Extract one monetary amount from a free-text answer, or None.

    Preference order: the first figure carrying a currency marker or a scale
    word, then a lone bare figure. Two bare figures with no currency marker
    ("120 clinics in 3 provinces") are ambiguous — that answer is narrative,
    and pretending otherwise is how invented numbers get into documents.
    """
    if not text:
        return None
    candidates = []
    for match in _MONEY_RE.finditer(str(text)):
        end = match.end()
        rest = str(text)[end : end + 1]
        if rest == "%":
            continue  # a percentage, not money
        number = float(match.group("num").replace(",", "").replace(" ", ""))
        scale = (match.group("scale") or "").lower()
        if scale:
            number *= _SCALES[scale]
        marked = bool(match.group("cur") or scale)
        candidates.append((marked, number))
    for marked, number in candidates:
        if marked:
            return number
    if len(candidates) == 1:
        return candidates[0][1]
    return None


def parse_percent(text):
    """Extract the first percentage from a free-text answer, or None."""
    if not text:
        return None
    match = _PERCENT_RE.search(str(text))
    return float(match.group(1)) if match else None


def detect_period(text):
    """Return 'monthly', 'annual' or None for a rate-bearing answer."""
    if not text:
        return None
    if _MONTHLY_RE.search(str(text)):
        return "monthly"
    if _ANNUAL_RE.search(str(text)):
        return "annual"
    return None


def format_money(value, symbol):
    """`4800000, 'R'` -> `R4.8m`; small values keep full digits."""
    if value >= 1e9:
        text = f"{value / 1e9:.2f}".rstrip("0").rstrip(".") + "bn"
    elif value >= 1e6:
        text = f"{value / 1e6:.2f}".rstrip("0").rstrip(".") + "m"
    else:
        text = f"{value:,.0f}"
    return f"{symbol}{text}" if symbol else text


def _coach(label):
    return f"Pending — answer **{label}** in questions.md"


def _add_computed_financials(values, profile, jurisdiction):
    """Derive the projection table, unit economics and consistency checks.

    Replaces the static "_to be supplied_" unit-economics table: every figure
    below is either computed from named answers or an explicit prompt to
    answer the question that would unlock it.
    """
    symbol = jurisdiction.currency_symbol or ""

    revenue = [
        parse_money(profile.get(f"projected_year_{year}")) for year in (1, 2, 3)
    ]
    margin_pct = parse_percent(profile.get("gross_margin_target"))
    arpc = parse_money(profile.get("average_revenue_per_customer"))
    arpc_period = detect_period(profile.get("average_revenue_per_customer"))
    cac = parse_money(profile.get("customer_acquisition_cost"))
    burn = parse_money(profile.get("monthly_operating_costs"))
    cash = parse_money(profile.get("cash_on_hand"))
    churn_pct = parse_percent(profile.get("customer_churn_rate"))
    churn_period = detect_period(profile.get("customer_churn_rate"))
    customers_y1 = parse_money(profile.get("customer_count_year_1"))

    arpc_monthly = None
    if arpc is not None:
        if arpc_period == "monthly":
            arpc_monthly = arpc
        elif arpc_period == "annual":
            arpc_monthly = arpc / 12.0

    churn_monthly_rate = None
    if churn_pct is not None:
        if churn_period == "annual":
            churn_monthly_rate = churn_pct / 100.0 / 12.0
        elif churn_period == "monthly":
            churn_monthly_rate = churn_pct / 100.0

    # -- Three-year projection table -------------------------------------
    growth = [None, None, None]
    for year in (1, 2):
        if revenue[year] is not None and revenue[year - 1]:
            growth[year] = revenue[year] / revenue[year - 1] - 1.0

    if any(amount is not None for amount in revenue):
        if margin_pct is not None:
            header = (
                "| Year | Revenue | YoY growth | "
                f"Gross profit (at {margin_pct:.0f}% target margin) |"
            )
            divider = "| :--- | :--- | :--- | :--- |"
        else:
            header = "| Year | Revenue | YoY growth |"
            divider = "| :--- | :--- | :--- |"
        lines = [header, divider]
        for index, amount in enumerate(revenue):
            year_label = f"Year {index + 1}"
            if amount is None:
                cell = _coach(f"Projected Year {index + 1}")
                row = f"| {year_label} | {cell} | — |"
            else:
                growth_cell = (
                    f"{growth[index]:+.0%}" if growth[index] is not None else "—"
                )
                row = f"| {year_label} | {format_money(amount, symbol)} | {growth_cell} |"
            if margin_pct is not None:
                profit = (
                    format_money(amount * margin_pct / 100.0, symbol)
                    if amount is not None
                    else "—"
                )
                row += f" {profit} |"
            lines.append(row)
        lines.append("")
        basis = "Revenue computed from **Projected Year 1–3**"
        if margin_pct is not None:
            basis += (
                "; gross profit applies the **Gross Margin Target** "
                f"({margin_pct:.0f}%) — no per-year cost projections were supplied"
            )
        lines.append(f"_{basis}._")
        values["fin_projection_table"] = "\n".join(lines)
    else:
        values["fin_projection_table"] = ""

    # -- Unit economics ---------------------------------------------------
    rows = [
        "| Metric | Value | Basis |",
        "| :--- | :--- | :--- |",
    ]

    def add_row(metric, value, basis):
        rows.append(f"| {metric} | {value} | {basis} |")

    if arpc is not None:
        period_note = arpc_period or (
            "period not stated — say per month or per year to unlock "
            "payback and LTV"
        )
        add_row(
            "Average revenue per customer",
            f"{format_money(arpc, symbol)} ({period_note})",
            "from **Average Revenue Per Customer**",
        )
    else:
        add_row(
            "Average revenue per customer",
            _coach("Average Revenue Per Customer"),
            "",
        )

    if margin_pct is not None:
        add_row(
            "Gross margin", f"{margin_pct:.0f}%", "from **Gross Margin Target**"
        )
    else:
        add_row("Gross margin", _coach("Gross Margin Target"), "")

    if cac is not None:
        add_row(
            "Customer acquisition cost",
            format_money(cac, symbol),
            "from **Customer Acquisition Cost**",
        )
    else:
        add_row(
            "Customer acquisition cost", _coach("Customer Acquisition Cost"), ""
        )

    if cac is not None and arpc_monthly:
        if margin_pct is not None:
            payback = cac / (arpc_monthly * margin_pct / 100.0)
            add_row(
                "CAC payback period",
                f"{payback:.1f} months",
                "computed from CAC ÷ (monthly revenue per customer × gross margin)",
            )
        else:
            payback = cac / arpc_monthly
            add_row(
                "CAC payback period",
                f"{payback:.1f} months (revenue basis — no margin supplied)",
                "computed from CAC ÷ monthly revenue per customer",
            )
    else:
        add_row(
            "CAC payback period",
            "Not derivable yet — needs **Customer Acquisition Cost** and a "
            "per-period **Average Revenue Per Customer**",
            "",
        )

    ltv = None
    if arpc_monthly and margin_pct is not None and churn_monthly_rate:
        ltv = arpc_monthly * (margin_pct / 100.0) / churn_monthly_rate
        add_row(
            "Customer lifetime value",
            format_money(ltv, symbol),
            "computed from monthly revenue per customer × gross margin ÷ "
            "monthly churn",
        )
        if cac:
            add_row(
                "LTV : CAC",
                f"{ltv / cac:.1f}x",
                "computed from lifetime value ÷ acquisition cost",
            )
    else:
        add_row(
            "Customer lifetime value",
            "Not derivable yet — needs **Average Revenue Per Customer**, "
            "**Gross Margin Target** and **Customer Churn Rate**",
            "",
        )

    if burn is not None:
        add_row(
            "Monthly burn (operating costs)",
            format_money(burn, symbol),
            "from **Monthly Operating Costs**",
        )
    else:
        add_row("Monthly burn", _coach("Monthly Operating Costs"), "")

    if cash is not None:
        add_row("Cash on hand", format_money(cash, symbol), "from **Cash On Hand**")
    else:
        add_row("Cash on hand", _coach("Cash On Hand"), "")

    if cash is not None and burn:
        add_row(
            "Runway",
            f"{cash / burn:.0f} months",
            "computed from cash on hand ÷ monthly operating costs",
        )
    else:
        add_row(
            "Runway",
            "Not derivable yet — needs **Cash On Hand** and "
            "**Monthly Operating Costs**",
            "",
        )

    values["fin_unit_economics"] = "\n".join(rows)

    # -- Consistency checks -----------------------------------------------
    checks = []
    if revenue[0] and arpc_monthly and customers_y1:
        implied = arpc_monthly * 12.0 * customers_y1
        deviation = implied / revenue[0] - 1.0
        comparison = (
            f"Year 1 revenue ({format_money(revenue[0], symbol)}) vs "
            f"{customers_y1:.0f} customers × "
            f"{format_money(arpc_monthly, symbol)}/month "
            f"(implies {format_money(implied, symbol)}"
        )
        if abs(deviation) <= 0.25:
            checks.append(
                f"*   **Consistent**: {comparison}; within "
                f"{abs(deviation):.0%} — plausible with mid-year onboarding)."
            )
        else:
            checks.append(
                f"*   **Check**: {comparison}; a {deviation:+.0%} gap). "
                "Reconcile **Projected Year 1**, **Customer Count Year 1** "
                "and **Average Revenue Per Customer**."
            )
    for year in (1, 2):
        if growth[year] is not None and growth[year] > 9.0:
            checks.append(
                f"*   **Note**: Year {year + 1} growth of {growth[year]:+.0%} "
                "is above 10× year-on-year. Not an error — but investors will "
                "ask what drives it; name the driver in "
                f"**Projected Year {year + 1}**."
            )
    if revenue[0] and revenue[1] and revenue[1] < revenue[0]:
        checks.append(
            "*   **Check**: Year 2 revenue is below Year 1. If deliberate "
            "(e.g. a one-off contract in Year 1), say so in "
            "**Projected Year 2**."
        )
    values["fin_consistency"] = "\n".join(checks)


def _split_positioning_lines(text):
    """Break a competitive-positioning answer into per-competitor lines."""
    lines = [line.strip(" *-\t") for line in str(text).splitlines()]
    lines = [line for line in lines if line]
    if len(lines) == 1:
        # A single-line answer often packs one sentence per competitor.
        parts = re.split(r"(?<=\.)\s+(?=[A-Z])", lines[0])
        lines = [part.strip() for part in parts if part.strip()]
    return lines


def _add_market_analysis(values, profile):
    """Derive the TAM/SAM/SOM funnel and the competitor positioning table.

    The market analysis chapter previously printed the three sizing answers
    in isolation, so a SOM larger than the SAM sailed through unremarked.
    When the answers carry parseable figures, the funnel below shows each
    layer as a share of the one above and flags incoherent values.
    """
    tam = parse_money(profile.get("market_size_tam"))
    sam = parse_money(profile.get("market_size_sam"))
    som = parse_money(profile.get("market_size_som"))

    # The funnel needs a currency for display; reuse the raw figures' scale
    # via the jurisdiction symbol already used elsewhere in the document.
    symbol = values.get("currency_symbol", "")

    if tam and sam and som:
        values["market_funnel_table"] = "\n".join(
            [
                "| Layer | Size | Share of the layer above |",
                "| :--- | :--- | :--- |",
                f"| **TAM** — the whole category | {format_money(tam, symbol)} | — |",
                f"| **SAM** — reachable with the current model | "
                f"{format_money(sam, symbol)} | {sam / tam:.1%} of TAM |",
                f"| **SOM** — realistic capture over 36 months | "
                f"{format_money(som, symbol)} | {som / sam:.1%} of SAM |",
                "",
                "_Computed from **Market Size TAM / SAM / SOM**. Each figure "
                "should carry a source — a reader will check._",
            ]
        )
        flags = []
        if sam > tam:
            flags.append(
                "*   **Check**: SAM exceeds TAM — the serviceable market "
                "cannot be larger than the whole category. Revisit "
                "**Market Size SAM**."
            )
        if som > sam:
            flags.append(
                "*   **Check**: SOM exceeds SAM — the obtainable share cannot "
                "be larger than the serviceable market. Revisit "
                "**Market Size SOM**."
            )
        if sam and not som > sam and som / sam > 0.3:
            flags.append(
                f"*   **Note**: SOM at {som / sam:.0%} of SAM is an aggressive "
                "36-month capture assumption; be ready to defend it."
            )
        values["market_sizing_flags"] = "\n".join(flags)
    else:
        values["market_funnel_table"] = ""
        values["market_sizing_flags"] = ""

    positioning = profile.get("competitive_positioning")
    competitors = profile.get("key_competitors")
    rows = []
    if positioning:
        for line in _split_positioning_lines(positioning):
            name, _, stance = line.partition(":")
            if stance.strip():
                rows.append((name.strip(), stance.strip()))
            else:
                rows.append(("—", line))
    elif competitors:
        for name in re.split(r",| and ", str(competitors)):
            name = name.strip(" .")
            if name:
                rows.append((name, _coach("Competitive Positioning")))
    if rows:
        table = ["| Competitor | Positioning against them |", "| :--- | :--- |"]
        for name, stance in rows:
            safe_name = name.replace("|", "\\|")
            safe_stance = stance.replace("|", "\\|")
            table.append(f"| {safe_name} | {safe_stance} |")
        values["competitor_table"] = "\n".join(table)
    else:
        values["competitor_table"] = ""


def _add_life_values(values, profile, warnings):
    """Pronouns and the living ledger for life profiles."""
    gender = (profile.get("gender") or "").strip().lower()
    pronouns = (profile.get("pronouns") or "").strip().lower()

    # Default to they/them. The previous engine defaulted to he/him, so every
    # profile that had not answered the question was written about as male.
    forms = {
        "he_she": "They",
        "he_she_lower": "they",
        "his_her": "their",
        "his_her_capital": "Their",
        "him_her": "them",
        "himself_herself": "themselves",
    }

    if pronouns:
        if pronouns.startswith("she"):
            forms = {
                "he_she": "She",
                "he_she_lower": "she",
                "his_her": "her",
                "his_her_capital": "Her",
                "him_her": "her",
                "himself_herself": "herself",
            }
        elif pronouns.startswith("he"):
            forms = {
                "he_she": "He",
                "he_she_lower": "he",
                "his_her": "his",
                "his_her_capital": "His",
                "him_her": "him",
                "himself_herself": "himself",
            }
    elif gender:
        if any(token in gender for token in ("female", "woman", "she")):
            forms = {
                "he_she": "She",
                "he_she_lower": "she",
                "his_her": "her",
                "his_her_capital": "Her",
                "him_her": "her",
                "himself_herself": "herself",
            }
        elif (
            any(token in gender for token in ("male", "man", "he"))
            and "female" not in gender
        ):
            forms = {
                "he_she": "He",
                "he_she_lower": "he",
                "his_her": "his",
                "his_her_capital": "His",
                "him_her": "him",
                "himself_herself": "himself",
            }
        elif not any(token in gender for token in ("non-binary", "nonbinary", "they")):
            warnings.append(
                f"Gender {gender!r} not recognised; using they/them. Add a "
                "'**Pronouns**' question for an exact answer."
            )
    else:
        warnings.append(
            "No pronouns declared; using they/them. Add a '**Pronouns**' "
            "question to questions.md (e.g. 'she/her')."
        )

    values.update(forms)

    milestones = profile.milestones
    if milestones:
        values["living_ledger_cv"] = "\n".join(
            f"*   **{item.date}** | *{item.category}* — {item.text}"
            for item in sorted(milestones, key=lambda m: m.date)
        )
        values["living_ledger_obituary"] = "\n".join(
            f"- In {item.date.split('-')[0]}, {forms['he_she_lower']} reached a "
            f"milestone in *{item.category}*: {item.text}"
            for item in sorted(milestones, key=lambda m: m.date)
        )
        values["milestone_count"] = str(len(milestones))
    else:
        values["living_ledger_cv"] = (
            "*No milestones logged yet. Share them with Hermes and they appear here.*"
        )
        values["living_ledger_obituary"] = (
            "*Legacy milestones will appear here as they are recorded.*"
        )
        values["milestone_count"] = "0"
