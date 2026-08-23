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

from . import __version__ as ENGINE_VERSION
from . import compliance as compliance_mod
from . import documents
from . import jurisdictions
from . import paths as path_utils
from . import safe_io
from . import schemas
from . import template_engine
from .errors import ProfileNotFoundError, TemplateError, UnknownArtifactError
from .parser import parse_questions_md

COMPLIANCE_ROOT_ENV_VAR = "STARTUPOS_COMPLIANCE_ROOT"

# What an unanswered question renders as. Deliberately falsy to `{{#if}}` so a
# template can omit a section instead of printing this into running prose.
UNANSWERED_TEXT = "Not yet provided"

# The life documents that are enforceable (or medically directive) language
# rather than planning prose. Their filenames are load-bearing: the polish
# firewall never sends them, and `_assemble` stamps each one's execution
# status into Document Control.
WILL_FILENAME = "last_will_and_testament.md"
LIVING_WILL_FILENAME = "living_will_and_healthcare_directive.md"
POA_FILENAME = "power_of_attorney.md"

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
            (
                "monthly_investor_update.md",
                "This month's numbers and milestones",
                "Monthly Investor Update",
            ),
        ],
        "monthly_investor_update.md": [
            ("07_financial_model.md", "Full financial model", "Financial Model"),
            (
                "annexures/cap_table_and_funding_history.md",
                "Who owns what, and what has been raised",
                "Cap Table & Funding History",
            ),
            (
                "annexures/due_diligence_data_room_index.md",
                "What a diligence pass will ask for",
                "Data-Room Index",
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
            (
                "annexures/grant_and_tender_pack.md",
                "Submission-ready registration and returnables",
                "Grant & Tender Pack",
            ),
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
        "annexures/fees_handbook.md": [
            (
                "annexures/product_pricing_list.md",
                "Internal price list behind these fees",
                "Price List",
            ),
            (
                "annexures/sales_terms_and_conditions.md",
                "Full terms of sale",
                "Terms of Sale",
            ),
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
        "annexures/cap_table_and_funding_history.md": [
            ("business_profile.md", "Corporate standing", "Business Profile"),
            (
                "annexures/investor_pitch_deck.md",
                "The investment case this ownership backs",
                "Investor Pitch Deck",
            ),
            ("07_financial_model.md", "Figures behind the raise", "Financial Model"),
        ],
        "annexures/due_diligence_data_room_index.md": [
            (
                "compliance_log.md",
                "Certificate status and expiry warnings",
                "Compliance Log",
            ),
            (
                "annexures/cap_table_and_funding_history.md",
                "Ownership and funding evidence",
                "Cap Table & Funding History",
            ),
            ("business_profile.md", "Corporate summary", "Business Profile"),
        ],
        "annexures/grant_and_tender_pack.md": [
            ("business_profile.md", "Full corporate profile", "Business Profile"),
            (
                "compliance_log.md",
                "Certificate status and expiry warnings",
                "Compliance Log",
            ),
            (
                "annexures/product_pricing_list.md",
                "Prices for the pricing schedule",
                "Price List",
            ),
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
                "last_will_and_testament.md",
                "Draft will assembled from your answers",
                "Last Will & Testament",
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
            (
                "last_will_and_testament.md",
                "Draft will assembled from your answers",
                "Last Will & Testament",
            ),
            (
                "personal_budget_plan_on_a_page.md",
                "Monthly cash flow behind the stewardship",
                "Personal Budget Plan on a Page",
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
            (
                "last_will_and_testament.md",
                "Draft will assembled from your answers",
                "Last Will & Testament",
            ),
        ],
        "last_will_and_testament.md": [
            (
                "legacy_plan_on_a_page.md",
                "Release protocol and memorial wishes",
                "Legacy Plan on a Page",
            ),
            (
                "financial_legacy_plan_on_a_page.md",
                "Assets, cover and beneficiaries behind the estate",
                "Financial Legacy Plan on a Page",
            ),
            (
                "living_will_and_healthcare_directive.md",
                "Healthcare wishes while you are alive but unable",
                "Living Will & Healthcare Directive",
            ),
            (
                "power_of_attorney.md",
                "Who may act for you, and within what limits",
                "Power of Attorney",
            ),
        ],
        "living_will_and_healthcare_directive.md": [
            (
                "last_will_and_testament.md",
                "Draft will assembled from your answers",
                "Last Will & Testament",
            ),
            (
                "emergency_information_page.md",
                "The one-page summary a responder needs",
                "Emergency Information Page",
            ),
            (
                "health_plan_on_a_page.md",
                "1-Page Biological Conditioning Plan",
                "Health Plan on a Page",
            ),
        ],
        "power_of_attorney.md": [
            (
                "last_will_and_testament.md",
                "Draft will assembled from your answers",
                "Last Will & Testament",
            ),
            (
                "financial_legacy_plan_on_a_page.md",
                "The finances an agent may need to manage",
                "Financial Legacy Plan on a Page",
            ),
        ],
        "emergency_information_page.md": [
            (
                "living_will_and_healthcare_directive.md",
                "Healthcare wishes and the proxy's authority",
                "Living Will & Healthcare Directive",
            ),
            (
                "legacy_plan_on_a_page.md",
                "Release protocol and document custody",
                "Legacy Plan on a Page",
            ),
        ],
        "personal_budget_plan_on_a_page.md": [
            (
                "financial_legacy_plan_on_a_page.md",
                "Net worth, cover and stewardship",
                "Financial Legacy Plan on a Page",
            ),
            (
                "life_plan_on_a_page.md",
                "1-Page Life Rhythm Plan",
                "Life Plan on a Page",
            ),
        ],
    },
}


# ---------------------------------------------------------------------------
# Selective generation.
#
# Documents in this engine do not depend on each other as files: every one
# compiles from the same parsed `questions.md` answers and the same compliance
# evidence, and the footer links between documents are navigation, not build
# inputs. A selective compile therefore never materialises intermediates —
# it renders exactly the requested templates and writes nothing else.
# ---------------------------------------------------------------------------

# The generated compliance log is selectable by name even though it has no
# template. Per the selective-generation contract, every selective *business*
# compile writes it alongside the requested artifacts regardless.
COMPLIANCE_LOG_ARTIFACT = "compliance_log"
COMPLIANCE_LOG_FILENAME = "compliance_log.md"

# Engine-computed placeholders mapped to the questions that feed them. The
# templates reference the derived name (`fin_unit_economics`); the gap check
# must prompt for the *inputs*. Maintained by hand beside the computations
# below; the test suite cross-checks every placeholder the shipped templates
# reference against these maps, so a new derived placeholder cannot ship
# without declaring what it needs.
DERIVED_PLACEHOLDER_INPUTS = {
    "fin_summary": frozenset(
        {"projected_year_1", "projected_year_2", "projected_year_3"}
    ),
    "fin_grid_rev": frozenset(
        {"projected_year_1", "projected_year_2", "projected_year_3"}
    ),
    "fin_projection_table": frozenset(
        {
            "projected_year_1",
            "projected_year_2",
            "projected_year_3",
            "gross_margin_target",
        }
    ),
    "fin_unit_economics": frozenset(
        {
            "average_revenue_per_customer",
            "gross_margin_target",
            "customer_acquisition_cost",
            "customer_churn_rate",
            "monthly_operating_costs",
            "cash_on_hand",
        }
    ),
    "fin_consistency": frozenset(
        {
            "projected_year_1",
            "projected_year_2",
            "projected_year_3",
            "customer_count_year_1",
            "average_revenue_per_customer",
        }
    ),
    "market_funnel_table": frozenset(
        {"market_size_tam", "market_size_sam", "market_size_som"}
    ),
    "market_sizing_flags": frozenset(
        {"market_size_tam", "market_size_sam", "market_size_som"}
    ),
    "competitor_table": frozenset({"competitive_positioning", "key_competitors"}),
    "competitor_pricing_table": frozenset({"competitor_pricing"}),
    "fin_cac_by_channel_table": frozenset(
        {"cac_by_channel", "customer_acquisition_cost"}
    ),
    "fin_cohort_analysis": frozenset({"retention_cohorts", "customer_churn_rate"}),
    "cap_table_ownership_table": frozenset({"shareholder_distribution"}),
    "cap_table_ownership_check": frozenset({"shareholder_distribution"}),
    "life_financial_summary": frozenset(
        {
            "assets",
            "liabilities",
            "life_cover_policies",
            "monthly_savings",
            "monthly_income",
        }
    ),
    "will_bequests_list": frozenset({"specific_bequests"}),
    "has_minor_children": frozenset({"children"}),
    "will_execution_status": frozenset({"will_executed"}),
    "living_will_execution_status": frozenset({"living_will_executed"}),
    "poa_execution_status": frozenset({"poa_executed"}),
    "budget_cash_flow_table": frozenset(
        {"monthly_income", "monthly_expenses", "monthly_savings", "liquid_savings"}
    ),
    "budget_flags": frozenset(
        {"monthly_income", "monthly_expenses", "monthly_savings"}
    ),
    "he_she": frozenset({"pronouns"}),
    "he_she_lower": frozenset({"pronouns"}),
    "his_her": frozenset({"pronouns"}),
    "his_her_capital": frozenset({"pronouns"}),
    "him_her": frozenset({"pronouns"}),
    "himself_herself": frozenset({"pronouns"}),
}

# Derived placeholders whose inputs are evidence documents rather than
# questions: the data-room table summarises the certificate-backed fields.
EVIDENCE_PLACEHOLDER_INPUTS = {
    "dd_evidence_table": frozenset(
        {"company_name", "reg_number", "tax_number", "tax_pin", "bee_level"}
    ),
}

# Placeholders a template may reference that need neither an answer nor a
# certificate: identity strings, jurisdiction constants resolved from the
# profile, and the milestone ledgers (fed by `startupos milestone`, always
# rendered — empty ledgers coach rather than block).
GAP_EXEMPT_PLACEHOLDERS = frozenset(
    {
        "trading_name",
        "instance_name",
        "company_name_status",
        "entity_type_hint",
        "jurisdiction_code",
        "jurisdiction_name",
        "currency",
        "currency_symbol",
        "currency_note",
        "privacy_law",
        "standards_body",
        "registry_name",
        "tax_authority",
        "trademarks_details",
        "business_milestone_ledger",
        "living_ledger_cv",
        "living_ledger_obituary",
        "milestone_count",
    }
)


def _artifact_map(template_root):
    """Map artifact stem (`investor_pitch_deck`) -> template name
    (`annexures/investor_pitch_deck.md`). Stems are unique across each suite;
    the test suite enforces that, so a stem is an unambiguous artifact name.
    """
    return {
        relative.rsplit("/", 1)[-1][: -len(".md")]: relative
        for _absolute, relative in _iter_templates(template_root)
    }


def list_artifacts(root, instance_type):
    """Every valid artifact name for a selective compile or gap check."""
    template_root = path_utils.templates_dir(root, instance_type)
    names = set(_artifact_map(template_root))
    if instance_type == "business":
        names.add(COMPLIANCE_LOG_ARTIFACT)
    return sorted(names)


def resolve_artifact_selection(names, template_root, instance_type):
    """Normalise a requested artifact selection.

    Accepts template stems (`investor_pitch_deck`, `business_profile`) and
    tolerates a trailing `.md` or a directory prefix. Returns
    `(stems, template_names)` — the stems in request order, deduplicated, and
    the set of output-relative template names to render (the generated
    compliance log has no template and is not in the set). An unknown name
    raises `UnknownArtifactError` listing every valid artifact; an empty
    selection is an error, never a silent full-suite compile.
    """
    mapping = _artifact_map(template_root)
    valid = set(mapping)
    if instance_type == "business":
        valid.add(COMPLIANCE_LOG_ARTIFACT)
    listed = ", ".join(sorted(valid))

    stems = []
    for raw in names:
        stem = str(raw).strip().replace("\\", "/")
        if stem.endswith(".md"):
            stem = stem[: -len(".md")]
        stem = stem.rsplit("/", 1)[-1]
        if stem not in valid:
            raise UnknownArtifactError(
                f"Unknown {instance_type} artifact {str(raw).strip()!r}. "
                f"Valid artifacts: {listed}"
            )
        if stem not in stems:
            stems.append(stem)

    if not stems:
        raise UnknownArtifactError(
            f"Empty artifact selection. Name at least one of: {listed} — or "
            "omit the selection to compile the full suite."
        )

    template_names = {
        mapping[stem] for stem in stems if stem != COMPLIANCE_LOG_ARTIFACT
    }
    return stems, template_names


def artifact_requirements(instance_type, template_text):
    """`(question_keys, evidence_keys)` one template needs.

    Derived from the template itself — its `{{name}}` placeholders and its
    `{{#if}}`/`{{#unless}}` condition names — plus the maintained input maps
    for engine-computed placeholders. The scan is jurisdiction-agnostic:
    keys inside gated blocks are included, and the evidence report filters
    out fields the profile's jurisdiction marks not applicable.
    """
    referenced = template_engine.find_placeholders(
        template_text
    ) | template_engine.find_condition_names(template_text)

    collected = schemas.schema_keys(instance_type)
    question_keys = set(referenced & collected)
    evidence_keys = set(referenced & compliance_mod.field_keys())
    for name in referenced:
        question_keys |= DERIVED_PLACEHOLDER_INPUTS.get(name, frozenset())
        evidence_keys |= EVIDENCE_PLACEHOLDER_INPUTS.get(name, frozenset())
    return question_keys & collected, evidence_keys


def missing_for_artifacts(data, names):
    """What blocks each requested artifact, without writing anything.

    Returns `{artifact: {"unanswered": {key: label}, "evidence": {key: hint}}}`
    in request order. "Unanswered" means the question is pending or absent
    from `questions.md`. "Evidence" lists the compliance fields the artifact
    renders that are applicable in this jurisdiction but backed by neither a
    parsed certificate nor an operator override — each with the exact next
    step. The generated compliance log needs every evidence field and no
    questions.
    """
    template_root = path_utils.templates_dir(data.root, data.instance_type)
    if not os.path.isdir(template_root):
        raise TemplateError(f"Missing template folder: {template_root}")

    stems, _template_names = resolve_artifact_selection(
        names, template_root, data.instance_type
    )
    mapping = _artifact_map(template_root)
    schema_labels = {
        key: question.label
        for key, question in schemas.questions_by_key(data.instance_type).items()
    }

    report = {}
    for stem in stems:
        if stem == COMPLIANCE_LOG_ARTIFACT:
            question_keys = frozenset()
            evidence_keys = compliance_mod.field_keys()
        else:
            template_path = os.path.join(template_root, *mapping[stem].split("/"))
            with open(template_path, "r", encoding="utf-8") as handle:
                question_keys, evidence_keys = artifact_requirements(
                    data.instance_type, handle.read()
                )

        unanswered = {
            key: data.profile.labels.get(key) or schema_labels.get(key, key)
            for key in sorted(question_keys)
            if key not in data.profile.answers
        }

        evidence = {}
        if data.record is not None:
            for key in sorted(evidence_keys):
                field = data.record.get(key)
                if field is None or not field.is_applicable or field.is_verified:
                    continue
                evidence[key] = data.record.render(key)

        report[stem] = {"unanswered": unanswered, "evidence": evidence}
    return report


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


class InstanceData:
    """Everything one parse of the SSOT yields, ready for any renderer.

    The markdown compiler consumed all of this inline, so the binary
    renderers had no way to reach the same parsed answers and computed
    values without re-running a full compile. This object is that seam:
    `load_instance_data` builds it once, and markdown, .pptx and .xlsx
    rendering all read from it.
    """

    def __init__(
        self,
        instance_type,
        instance_name,
        root,
        out_dir,
        profile,
        jurisdiction,
        record,
        trading_name,
        values,
        warnings,
        brand=None,
    ):
        self.instance_type = instance_type
        self.instance_name = instance_name
        self.root = root
        self.out_dir = out_dir
        self.profile = profile
        self.jurisdiction = jurisdiction
        self.record = record
        self.trading_name = trading_name
        self.values = values
        self.warnings = warnings
        self.brand = brand


def load_instance_data(
    instance_type,
    instance_name,
    workspace_root=None,
    compliance_root=None,
    monorepo_root=None,
    quiet=True,
):
    """Parse the SSOT and build the full renderer namespace, writing nothing.

    `monorepo_root` is accepted for backwards compatibility and treated as
    `compliance_root`'s parent.
    """
    instance_type = path_utils.validate_instance_type(instance_type)
    instance_name = path_utils.sanitize_instance_name(instance_name)

    root = path_utils.resolve_workspace_root(workspace_root, verbose=not quiet)
    questions_file = path_utils.questions_path(root, instance_type, instance_name)
    out_dir = path_utils.output_dir(root, instance_type, instance_name)

    if not os.path.exists(questions_file):
        raise ProfileNotFoundError(
            f"Missing strategic source of truth: {questions_file}\n"
            f"Provision it first:  python provision.py --type {instance_type} "
            f"--name {instance_name}"
        )

    if not compliance_root and monorepo_root:
        compliance_root = os.path.join(monorepo_root, "Compliance")

    profile = parse_questions_md(questions_file)
    warnings = list(profile.warnings)

    jurisdiction = jurisdictions.resolve(profile.answers, warnings)
    trading_name = profile.get("trading_name") or _humanise(instance_name)

    record = None
    brand = None
    if instance_type == "business":
        compliance_dir = resolve_compliance_dir(
            root, instance_type, instance_name, compliance_root, warnings
        )
        record = compliance_mod.load_compliance(
            compliance_dir, trading_name, jurisdiction
        )
        warnings.extend(record.warnings)

        # Optional designer brand assets. A missing brand/ folder is a
        # coaching line in the compile output; a malformed system file or
        # image raises immediately — never a half-branded deck.
        from . import branding as branding_mod

        brand = branding_mod.load_brand(
            path_utils.instance_dir(root, instance_type, instance_name),
            trading_name,
            warnings,
        )

    values = _build_values(
        profile,
        jurisdiction,
        record,
        trading_name,
        instance_name,
        instance_type,
        warnings,
    )

    return InstanceData(
        instance_type=instance_type,
        instance_name=instance_name,
        root=root,
        out_dir=out_dir,
        profile=profile,
        jurisdiction=jurisdiction,
        record=record,
        trading_name=trading_name,
        values=values,
        warnings=warnings,
        brand=brand,
    )


def render_binary_artifacts(data, quiet=False, only_markdown=None):
    """Render the derived .pptx and .xlsx artifacts for a business instance.

    The markdown stays canonical: both files are regenerated from the same
    `InstanceData` that fills the templates, and a plain recompile without
    `--render` prunes them rather than leaving stale binaries that look
    current. Returns the output-relative filenames written.

    `only_markdown` — the template names of a selective compile — restricts
    rendering to the binaries derived from a selected document: the deck from
    `annexures/investor_pitch_deck.md`, the model from `07_financial_model.md`.
    """
    # Imported lazily: a skill install with a cached pre-renderer engine can
    # still compile markdown; only rendering needs the new modules.
    from . import render_pptx, render_xlsx

    written = []
    for module, filename, source in (
        (
            render_pptx,
            render_pptx.PITCH_DECK_FILENAME,
            "annexures/investor_pitch_deck.md",
        ),
        (render_xlsx, render_xlsx.FINANCIAL_MODEL_FILENAME, "07_financial_model.md"),
    ):
        if only_markdown is not None and source not in only_markdown:
            continue
        destination = os.path.join(data.out_dir, filename)
        path_utils.assert_contained(data.out_dir, destination)
        module.render(data, destination)
        written.append(filename)
        if not quiet:
            print(f"  Rendered : {filename}")
    return written


def compile_instance(
    instance_type,
    instance_name,
    monorepo_root=None,
    workspace_root=None,
    compliance_root=None,
    quiet=False,
    render=False,
    only=None,
):
    """Compile the template suite for one instance.

    `monorepo_root` is accepted for backwards compatibility and treated as
    `compliance_root`'s parent. With `render=True` the derived binary
    artifacts (investor deck .pptx, financial model .xlsx) are regenerated
    alongside the markdown for business instances.

    `only` — an iterable of artifact names (template stems such as
    `investor_pitch_deck`; see `list_artifacts`) — switches to selective
    generation: exactly the requested documents are written, plus the
    compliance log for a business instance, and **nothing else in the output
    directory is touched or pruned** — safe to point at a folder that already
    holds a full suite or unrelated files. With `render=True` only the
    binaries whose source document was selected are rendered. `only=None`
    keeps the full-suite behaviour unchanged, pruning included; an empty or
    unknown selection raises `UnknownArtifactError` naming the valid
    artifacts.
    """
    data = load_instance_data(
        instance_type=instance_type,
        instance_name=instance_name,
        workspace_root=workspace_root,
        compliance_root=compliance_root,
        monorepo_root=monorepo_root,
        quiet=quiet,
    )
    instance_type = data.instance_type
    instance_name = data.instance_name
    out_dir = data.out_dir
    template_root = path_utils.templates_dir(data.root, instance_type)

    if not os.path.isdir(template_root):
        raise TemplateError(
            f"Missing template folder: {template_root}\n"
            "Templates ship with the skill; run the compile wrapper so they sync, "
            "or copy them from core/skills/.rok/startup_os/templates/."
        )

    profile = data.profile
    jurisdiction = data.jurisdiction
    record = data.record
    warnings = data.warnings

    result = CompileResult(instance_type, instance_name, out_dir, jurisdiction)
    result.completeness = profile.completeness

    context = template_engine.RenderContext(
        values=data.values, jurisdiction=jurisdiction, features=jurisdiction.features
    )

    template_files = list(_iter_templates(template_root))
    if not template_files:
        raise TemplateError(f"No .md templates found in {template_root}")

    selected_names = None
    if only is not None:
        _stems, selected_names = resolve_artifact_selection(
            only, template_root, instance_type
        )
        template_files = [
            (template_path, relative_name)
            for template_path, relative_name in template_files
            if relative_name in selected_names
        ]

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
        safe_io.atomic_write(os.path.join(out_dir, COMPLIANCE_LOG_FILENAME), log_text)
        written_names.add(COMPLIANCE_LOG_FILENAME)
        result.written.append(COMPLIANCE_LOG_FILENAME)
        status, _messages = compliance_mod.compliance_exit_status(record, generated_on)
        result.compliance_status = status

    if render:
        if instance_type == "business":
            rendered_names = render_binary_artifacts(
                data, quiet=quiet, only_markdown=selected_names
            )
            for name in rendered_names:
                written_names.add(name)
                result.written.append(name)
            if selected_names is not None and not rendered_names:
                warnings.append(
                    "--render with a selection only regenerates the binaries "
                    "whose source document was requested "
                    "(investor_pitch_deck -> .pptx, 07_financial_model -> "
                    ".xlsx); neither was selected, so none was rendered."
                )
        else:
            warnings.append(
                "--render produces business artifacts (investor deck, "
                "financial model); nothing to render for a life profile."
            )

    # Prune only after everything this run produces is known, or the compliance
    # log would be deleted moments after being written. A selective compile
    # never prunes: it must be safe to request one artifact into a directory
    # that already holds a full suite — or anything else.
    if only is None:
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

    depth_line = schemas.describe_depth(
        schemas.compute_depth(instance_type, profile.answers)
    )

    # Will-execution accountability. Until the owner records a signing date,
    # the will and the legacy plan carry a visible unsigned-draft warning in
    # their Completion Gaps, and the will's Document Control states outright
    # that it has no legal force. A recorded date is noted — with the
    # professional-review caveat kept, because a compiled file is never the
    # signed original.
    extra_control = []
    gap_warnings = []
    if instance_type == "life" and filename in (
        WILL_FILENAME,
        "legacy_plan_on_a_page.md",
    ):
        status = will_execution_status(profile)
        if filename == WILL_FILENAME:
            if status:
                extra_control.append(
                    "> *   **Will execution**: recorded by the owner — "
                    f"{status}. Professional review is still required, and "
                    "only the signed original has legal force."
                )
            else:
                extra_control.append(
                    "> *   **Will execution**: NOT EXECUTED — this compiled "
                    "file is an unsigned draft with no legal force."
                )
        if not status:
            gap_warnings.append(
                "The last will and testament is an UNSIGNED DRAFT with no "
                "legal force. Once it has been formally signed and "
                "witnessed, record the date under **Will Executed** in "
                "questions.md."
            )

    # The living will and the power of attorney carry the same execution
    # accountability as the will: a dated owner record is stamped into
    # Document Control, and until one exists the file is loudly an unsigned
    # draft — because both documents only matter at the exact moment nobody
    # can ask the owner whether they ever signed them.
    if instance_type == "life" and filename in (LIVING_WILL_FILENAME, POA_FILENAME):
        label, answer_key, answer_label = {
            LIVING_WILL_FILENAME: (
                "Living will execution",
                "living_will_executed",
                "Living Will Executed",
            ),
            POA_FILENAME: (
                "Power of attorney execution",
                "poa_executed",
                "POA Executed",
            ),
        }[filename]
        status = directive_execution_status(profile, answer_key)
        if status:
            extra_control.append(
                f"> *   **{label}**: recorded by the owner — {status}. "
                "Professional review is still required, and only the signed "
                "original has legal force."
            )
        else:
            extra_control.append(
                f"> *   **{label}**: NOT EXECUTED — this compiled file is "
                "an unsigned draft with no legal force."
            )
            gap_warnings.append(
                f"This document is an UNSIGNED DRAFT with no legal force. "
                f"Once it has been formally signed, record the date under "
                f"**{answer_label}** in questions.md."
            )

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
        depth=depth_line,
        extra_lines=extra_control,
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
    document += documents.build_gap_report(missing, gap_warnings)

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
        _add_diligence_analysis(values, profile, jurisdiction)
        _add_cap_table_analysis(values, profile)
        _add_business_ledger(values, profile)
        _add_dd_analysis(values, record, jurisdiction)

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
        _add_life_computed(values, profile, jurisdiction)

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


def extract_financial_inputs(profile):
    """Parse every numeric financial answer once, in one place.

    The markdown compiler and the binary renderers (`render_pptx`,
    `render_xlsx`) must agree on every figure, so the parsing lives here and
    both consume the result. A renderer that re-parsed the answers itself
    would eventually drift from the documents it claims to be derived from.

    Every value is a float or None — None meaning the answer is absent or
    narrative, never zero. Callers render None as coaching, not as a number.
    """
    revenue = [parse_money(profile.get(f"projected_year_{year}")) for year in (1, 2, 3)]
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

    return {
        "revenue": revenue,
        "margin_pct": margin_pct,
        "arpc": arpc,
        "arpc_period": arpc_period,
        "arpc_monthly": arpc_monthly,
        "cac": cac,
        "burn": burn,
        "cash": cash,
        "churn_pct": churn_pct,
        "churn_period": churn_period,
        "churn_monthly_rate": churn_monthly_rate,
        "customers_y1": customers_y1,
        "tam": parse_money(profile.get("market_size_tam")),
        "sam": parse_money(profile.get("market_size_sam")),
        "som": parse_money(profile.get("market_size_som")),
    }


def derive_financial_metrics(fin):
    """Every derived financial figure, from the parsed inputs, in one place.

    The formulas here are the single source of the arithmetic: the markdown
    unit-economics table prints these values, and the .xlsx renderer writes
    the same formulas into live cells with these values cached — so a reader
    pressing F9 in Excel and a reader of the markdown see the same numbers.

    A metric that cannot be derived is None, and `*_basis` says which formula
    variant produced a value that *was* derived.
    """
    revenue = fin["revenue"]
    margin_pct = fin["margin_pct"]
    arpc_monthly = fin["arpc_monthly"]
    cac = fin["cac"]

    growth = [None, None, None]
    for year in (1, 2):
        if revenue[year] is not None and revenue[year - 1]:
            growth[year] = revenue[year] / revenue[year - 1] - 1.0

    gross_profit = [
        (
            amount * margin_pct / 100.0
            if (amount is not None and margin_pct is not None)
            else None
        )
        for amount in revenue
    ]

    cac_payback_months = None
    cac_payback_basis = None
    if cac is not None and arpc_monthly:
        if margin_pct is not None:
            cac_payback_months = cac / (arpc_monthly * margin_pct / 100.0)
            cac_payback_basis = "margin"
        else:
            cac_payback_months = cac / arpc_monthly
            cac_payback_basis = "revenue"

    ltv = None
    if arpc_monthly and margin_pct is not None and fin["churn_monthly_rate"]:
        ltv = arpc_monthly * (margin_pct / 100.0) / fin["churn_monthly_rate"]

    ltv_cac = ltv / cac if (ltv is not None and cac) else None

    runway_months = None
    if fin["cash"] is not None and fin["burn"]:
        runway_months = fin["cash"] / fin["burn"]

    implied_year_1_revenue = None
    if arpc_monthly and fin["customers_y1"]:
        implied_year_1_revenue = arpc_monthly * 12.0 * fin["customers_y1"]

    return {
        "growth": growth,
        "gross_profit": gross_profit,
        "cac_payback_months": cac_payback_months,
        "cac_payback_basis": cac_payback_basis,
        "ltv": ltv,
        "ltv_cac": ltv_cac,
        "runway_months": runway_months,
        "arpc_annual": (arpc_monthly * 12.0 if arpc_monthly is not None else None),
        "annual_operating_costs": (
            fin["burn"] * 12.0 if fin["burn"] is not None else None
        ),
        "implied_year_1_revenue": implied_year_1_revenue,
    }


def _add_computed_financials(values, profile, jurisdiction):
    """Derive the projection table, unit economics and consistency checks.

    Replaces the static "_to be supplied_" unit-economics table: every figure
    below is either computed from named answers or an explicit prompt to
    answer the question that would unlock it.
    """
    symbol = jurisdiction.currency_symbol or ""

    fin = extract_financial_inputs(profile)
    metrics = derive_financial_metrics(fin)

    revenue = fin["revenue"]
    margin_pct = fin["margin_pct"]
    arpc = fin["arpc"]
    arpc_period = fin["arpc_period"]
    arpc_monthly = fin["arpc_monthly"]
    cac = fin["cac"]
    burn = fin["burn"]
    cash = fin["cash"]
    customers_y1 = fin["customers_y1"]

    # -- Three-year projection table -------------------------------------
    growth = metrics["growth"]

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
                row = (
                    f"| {year_label} | {format_money(amount, symbol)} | {growth_cell} |"
                )
            if margin_pct is not None:
                profit = (
                    format_money(metrics["gross_profit"][index], symbol)
                    if metrics["gross_profit"][index] is not None
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
            "period not stated — say per month or per year to unlock payback and LTV"
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
        add_row("Gross margin", f"{margin_pct:.0f}%", "from **Gross Margin Target**")
    else:
        add_row("Gross margin", _coach("Gross Margin Target"), "")

    if cac is not None:
        add_row(
            "Customer acquisition cost",
            format_money(cac, symbol),
            "from **Customer Acquisition Cost**",
        )
    else:
        add_row("Customer acquisition cost", _coach("Customer Acquisition Cost"), "")

    if metrics["cac_payback_months"] is not None:
        payback = metrics["cac_payback_months"]
        if metrics["cac_payback_basis"] == "margin":
            add_row(
                "CAC payback period",
                f"{payback:.1f} months",
                "computed from CAC ÷ (monthly revenue per customer × gross margin)",
            )
        else:
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

    if metrics["ltv"] is not None:
        add_row(
            "Customer lifetime value",
            format_money(metrics["ltv"], symbol),
            "computed from monthly revenue per customer × gross margin ÷ monthly churn",
        )
        if metrics["ltv_cac"] is not None:
            add_row(
                "LTV : CAC",
                f"{metrics['ltv_cac']:.1f}x",
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

    if metrics["runway_months"] is not None:
        add_row(
            "Runway",
            f"{metrics['runway_months']:.0f} months",
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
    if revenue[0] and metrics["implied_year_1_revenue"]:
        implied = metrics["implied_year_1_revenue"]
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


def extract_competitor_rows(profile):
    """`(name, positioning)` rows for the competitor table.

    Shared by the markdown market analysis and the pitch-deck renderer, so a
    competitor named in the documents is never missing from the deck. A
    competitor named without a stance gets a coaching cell, never silence.
    """
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
    return rows


def _add_market_analysis(values, profile):
    """Derive the TAM/SAM/SOM funnel and the competitor positioning table.

    The market analysis chapter previously printed the three sizing answers
    in isolation, so a SOM larger than the SAM sailed through unremarked.
    When the answers carry parseable figures, the funnel below shows each
    layer as a share of the one above and flags incoherent values.
    """
    fin = extract_financial_inputs(profile)
    tam, sam, som = fin["tam"], fin["sam"], fin["som"]

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

    rows = extract_competitor_rows(profile)
    if rows:
        table = ["| Competitor | Positioning against them |", "| :--- | :--- |"]
        for name, stance in rows:
            safe_name = name.replace("|", "\\|")
            safe_stance = stance.replace("|", "\\|")
            table.append(f"| {safe_name} | {safe_stance} |")
        values["competitor_table"] = "\n".join(table)
    else:
        values["competitor_table"] = ""


def _one_line(text):
    """Collapse a multi-line answer for embedding inside a list bullet."""
    return "; ".join(part.strip() for part in str(text).splitlines() if part.strip())


def _cell(text):
    """Escape a value for a markdown table cell."""
    return str(text).replace("|", "\\|")


def _add_diligence_analysis(values, profile, jurisdiction):
    """Build the Level 3 (diligence-grade) analysis blocks — or lock them.

    The depth ladder's rule is that deeper analysis unlocks only at its
    level: a profile that has answered one diligence question but not the
    rest stays at Level 2, and these placeholders render empty so the
    templates show the unlock coaching instead. The Depth line in Document
    Control names the exact missing answers.
    """
    report = schemas.compute_depth("business", profile.answers)
    unlocked = report is not None and report.level >= schemas.DEPTH_DILIGENCE

    if not unlocked:
        values["competitor_pricing_table"] = ""
        values["fin_cac_by_channel_table"] = ""
        values["fin_cohort_analysis"] = ""
        return

    symbol = jurisdiction.currency_symbol or ""

    # -- Named-competitor pricing (03) ------------------------------------
    rows = ["| Competitor | Pricing |", "| :--- | :--- |"]
    for line in _split_positioning_lines(profile.get("competitor_pricing")):
        name, _, pricing = line.partition(":")
        if pricing.strip():
            cells = (name.strip(), pricing.strip())
        else:
            cells = ("—", line)
        rows.append(f"| {_cell(cells[0])} | {_cell(cells[1])} |")
    rows.append("")
    rows.append(
        "_Stated in **Competitor Pricing** — founder-supplied; verify against "
        "current price lists before quoting it to an investor._"
    )
    values["competitor_pricing_table"] = "\n".join(rows)

    # -- CAC by channel (07) ----------------------------------------------
    rows = ["| Channel | Acquisition cost | Basis |", "| :--- | :--- | :--- |"]
    for line in _split_positioning_lines(profile.get("cac_by_channel")):
        channel, _, rest = line.partition(":")
        if rest.strip():
            amount = parse_money(rest)
            cost = format_money(amount, symbol) if amount is not None else rest.strip()
            rows.append(
                f"| {_cell(channel.strip())} | {_cell(cost)} | "
                "from **CAC By Channel** |"
            )
        else:
            rows.append(f"| — | {_cell(line)} | from **CAC By Channel** |")
    blended = parse_money(profile.get("customer_acquisition_cost"))
    if blended is not None:
        rows.append(
            f"| **Blended (all channels)** | {format_money(blended, symbol)} | "
            "from **Customer Acquisition Cost** |"
        )
    values["fin_cac_by_channel_table"] = "\n".join(rows)

    # -- Cohort & retention analysis (07) ---------------------------------
    fin = extract_financial_inputs(profile)
    lines = [
        "*   **Stated cohort behaviour** (from **Retention Cohorts**): "
        f"{_one_line(profile.get('retention_cohorts'))}"
    ]
    churn_monthly = fin["churn_monthly_rate"]
    if churn_monthly:
        retention_12m = (1.0 - churn_monthly) ** 12
        lifetime_months = 1.0 / churn_monthly
        lines.append(
            f"*   **Implied by Customer Churn Rate**: {retention_12m:.0%} of a "
            "signup cohort remains after twelve months; average customer "
            f"lifetime ≈ {lifetime_months:.0f} months (computed from "
            "**Customer Churn Rate** — reconcile against the stated cohorts "
            "above)."
        )
    else:
        lines.append(
            "*   **Churn-implied retention**: not derivable — state "
            "**Customer Churn Rate** as a percentage per month or per year."
        )
    values["fin_cohort_analysis"] = "\n".join(lines)


def extract_ownership_rows(profile):
    """`(holder, percent_or_None, raw_line)` rows from Shareholder Distribution.

    A single-line answer often packs the whole split ("Ray: 60%; Naledi:
    40%"), so one line is split on semicolons and commas before parsing.
    A line without a parseable percentage stays in the table as narrative —
    never silently dropped, never forced into a number.
    """
    text = _real_answer(profile, "shareholder_distribution")
    if not text:
        return []
    lines = [line.strip(" *-\t") for line in str(text).splitlines()]
    lines = [line for line in lines if line]
    if len(lines) == 1:
        parts = re.split(r"[;,]\s*", lines[0])
        if len(parts) > 1:
            lines = [part.strip() for part in parts if part.strip()]

    rows = []
    for line in lines:
        percent = parse_percent(line)
        name, _, rest = line.partition(":")
        if rest.strip():
            holder = name.strip()
        else:
            holder = _PERCENT_RE.sub("", line).strip(" -—:•\t") or "—"
        rows.append((holder, percent, line))
    return rows


def _add_cap_table_analysis(values, profile):
    """Ownership table plus the sum-to-100% sanity check.

    Renders only what **Shareholder Distribution** states. The check is the
    honest-compiler move: stated percentages that do not sum to roughly 100%
    are flagged for reconciliation, not normalised.
    """
    rows = extract_ownership_rows(profile)
    if not rows:
        values["cap_table_ownership_table"] = ""
        values["cap_table_ownership_check"] = ""
        return

    table = ["| Holder | Stated share | Basis |", "| :--- | :--- | :--- |"]
    total = 0.0
    parsed = 0
    for holder, percent, raw in rows:
        if percent is not None:
            total += percent
            parsed += 1
            share = f"{percent:g}%"
        else:
            share = f"stated without a percentage — {_cell(raw)}"
        table.append(
            f"| {_cell(holder)} | {share} | from **Shareholder Distribution** |"
        )

    if not parsed:
        # Narrative answer, no figures: the template coaches instead.
        values["cap_table_ownership_table"] = ""
        values["cap_table_ownership_check"] = ""
        return

    table.append(
        f"| **Total stated** | **{total:g}%** | computed from the {parsed} "
        "percentage-bearing line(s) above |"
    )
    values["cap_table_ownership_table"] = "\n".join(table)

    if abs(total - 100.0) > 1.0:
        values["cap_table_ownership_check"] = (
            f"*   **Check**: stated shareholdings sum to {total:g}%, not "
            "100%. Reconcile **Shareholder Distribution** — an option pool, "
            "an unlisted holder or a typo usually explains the gap."
        )
    else:
        values["cap_table_ownership_check"] = (
            f"*   **Consistent**: stated shareholdings sum to {total:g}% — "
            "a full allocation (within 1%)."
        )


def _add_business_ledger(values, profile):
    """The venture's milestone ledger, for the monthly investor update.

    Same source as the life suite's living ledger: milestones logged into
    `questions.md` by `startupos milestone` (or Hermes). Empty stays empty —
    the template coaches; no milestone is ever invented.
    """
    milestones = getattr(profile, "milestones", None) or []
    if milestones:
        values["business_milestone_ledger"] = "\n".join(
            f"*   **{item.date}** | *{item.category}* — {item.text}"
            for item in sorted(milestones, key=lambda m: m.date)
        )
    else:
        values["business_milestone_ledger"] = ""


def _add_dd_analysis(values, record, jurisdiction):
    """The data-room evidence table: what is proven, asserted or missing.

    Each row is one certificate-backed evidence item in this jurisdiction's
    regime, labelled with the same provenance discipline as the compliance
    footer: *Document-backed* (a parsed certificate), *Operator-asserted*
    (`compliance_overrides.json`), or *Unverified* with the exact file to
    add. Regimes the jurisdiction does not have produce no row at all.
    """
    if record is None or not jurisdiction.is_known:
        values["dd_evidence_table"] = ""
        return

    def status_cells(keys, filename):
        fields = [record.get(key) for key in keys]
        fields = [field for field in fields if field is not None]
        verified = [
            field
            for field in fields
            if field.status == compliance_mod.STATUS_VERIFIED and field.value
        ]
        asserted = [
            field
            for field in fields
            if field.status == compliance_mod.STATUS_OVERRIDE and field.value
        ]
        if verified:
            return "Document-backed", verified[0].source or filename
        if asserted:
            return "Operator-asserted", "compliance_overrides.json"
        return (
            "**Unverified**",
            f"place `{filename}` in the compliance folder",
        )

    rows = ["| Evidence item | Status | Source / next step |", "| :--- | :--- | :--- |"]

    if jurisdiction.supports(jurisdictions.FEATURE_COMPANY_REGISTRY):
        status, source = status_cells(
            ("company_name", "reg_number"),
            f"{jurisdiction.registry_document}.pdf",
        )
        registry = jurisdiction.registry_name or "Company registry"
        rows.append(f"| {registry} registration certificate | {status} | {source} |")
    if jurisdiction.supports(jurisdictions.FEATURE_TAX_CLEARANCE):
        status, source = status_cells(("tax_pin", "tax_number"), "Tax_Pin.pdf")
        authority = jurisdiction.tax_authority or "Tax authority"
        rows.append(f"| {authority} tax compliance PIN | {status} | {source} |")
    if jurisdiction.supports(jurisdictions.FEATURE_BBEE):
        status, source = status_cells(("bee_level",), "BEE.pdf")
        rows.append(f"| B-BBEE certificate | {status} | {source} |")
    if jurisdiction.supports(jurisdictions.FEATURE_TRADEMARKS):
        count = len(record.trademarks)
        if count:
            rows.append(
                f"| Trademark registrations | Document-backed | "
                f"{count} document(s) parsed from `TradeMark/` |"
            )
        else:
            rows.append(
                "| Trademark registrations | None on file | add filings to "
                "the compliance folder's `TradeMark/` directory, if any |"
            )

    rows.append("")
    rows.append(
        "_Statuses are read from the evidence on disk — nothing above is "
        "asserted without a document, and operator-asserted values come from "
        "`compliance_overrides.json`._"
    )
    values["dd_evidence_table"] = "\n".join(rows)


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


# ---------------------------------------------------------------------------
# Computed life financials and the will's derived values.
#
# Same contract as the business financials: every derived figure names the
# answers it was computed from, an answer that does not parse is narrative
# and falls back to coaching, and nothing — no heir, no amount, no signing
# date — is ever invented.
# ---------------------------------------------------------------------------

_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")

# A literal "none" answer to Specific Bequests or Children is a real answer
# ("I have no children", "no specific gifts") — it must not render as a
# bequest called "None".
_NONE_ANSWER_RE = re.compile(r"^\s*(?:none|no|n/a)\b[.\s]*$", re.IGNORECASE)

_MINOR_RE = re.compile(r"\bminor\b", re.IGNORECASE)


def _real_answer(profile, key):
    """The answer for `key`, or None when it is absent or a placeholder.

    Uses the same truthiness the templates' `{{#if}}` applies, so the
    compiler and the rendered document never disagree about whether a
    question has really been answered.
    """
    value = profile.get(key)
    context = template_engine.RenderContext(values={"value": value})
    return value if context.is_truthy("value") else None


def directive_execution_status(profile, key):
    """The owner's execution record for `key`, if it carries a date.

    An answer without a year ("yes", "signed it") does not count: the whole
    point of the record is a verifiable signing date, so a dateless answer
    keeps the unsigned-draft warnings in place. Shared by the will, the
    living will and the power of attorney — one rule, three documents.
    """
    value = _real_answer(profile, key)
    if value and _YEAR_RE.search(str(value)):
        return _one_line(value)
    return None


def will_execution_status(profile):
    """The will's execution record — see `directive_execution_status`."""
    return directive_execution_status(profile, "will_executed")


def sum_money_lines(text):
    """Sum the parseable amounts in a one-item-per-line answer.

    Returns `(total, parsed_count, line_count)`. `total` is None when no
    line carries a figure `parse_money` accepts — the answer is narrative
    and the caller coaches instead of computing.
    """
    if not text:
        return None, 0, 0
    lines = [line.strip(" *-\t") for line in str(text).splitlines()]
    lines = [line for line in lines if line]
    total = 0.0
    parsed = 0
    for line in lines:
        amount = parse_money(line)
        if amount is not None:
            total += amount
            parsed += 1
    return (total if parsed else None), parsed, len(lines)


def _numbered_lines(text):
    """Render a one-item-per-line answer as a numbered markdown list."""
    lines = [line.strip(" *-\t") for line in str(text).splitlines()]
    lines = [line for line in lines if line]
    return "\n".join(f"{index}.  {line}" for index, line in enumerate(lines, 1))


def _add_life_computed(values, profile, jurisdiction):
    """Derive net worth, total cover and savings rate, plus the will's
    conditional values. Coaching, never invention, where answers are missing.
    """
    symbol = jurisdiction.currency_symbol or ""

    assets_total, assets_parsed, assets_lines = sum_money_lines(
        _real_answer(profile, "assets")
    )
    liabilities_total, liabilities_parsed, liabilities_lines = sum_money_lines(
        _real_answer(profile, "liabilities")
    )
    cover_total, cover_parsed, _cover_lines = sum_money_lines(
        _real_answer(profile, "life_cover_policies")
    )
    savings = parse_money(_real_answer(profile, "monthly_savings"))
    income = parse_money(_real_answer(profile, "monthly_income"))

    rows = ["| Measure | Value | Basis |", "| :--- | :--- | :--- |"]

    def add_row(measure, value, basis):
        rows.append(f"| {measure} | {value} | {basis} |")

    if assets_total is not None:
        add_row(
            "Total assets",
            format_money(assets_total, symbol),
            f"computed from **Assets** ({assets_parsed} of {assets_lines} "
            "lines carried an amount)",
        )
    else:
        add_row(
            "Total assets",
            _coach("Assets") + " — one asset per line, with its value",
            "",
        )

    if liabilities_total is not None:
        add_row(
            "Total liabilities",
            format_money(liabilities_total, symbol),
            f"computed from **Liabilities** ({liabilities_parsed} of "
            f"{liabilities_lines} lines carried an amount)",
        )
    else:
        add_row(
            "Total liabilities",
            _coach("Liabilities") + " — one debt per line, with the amount",
            "",
        )

    if assets_total is not None and liabilities_total is not None:
        add_row(
            "Net worth",
            format_money(assets_total - liabilities_total, symbol),
            "computed from total assets − total liabilities",
        )
    else:
        add_row(
            "Net worth",
            "Not derivable yet — needs amounts in both **Assets** and **Liabilities**",
            "",
        )

    if cover_total is not None:
        add_row(
            "Total life cover",
            format_money(cover_total, symbol),
            f"computed from **Life Cover Policies** ({cover_parsed} policy line(s))",
        )
    else:
        add_row(
            "Total life cover",
            _coach("Life Cover Policies") + " — one policy per line, with "
            "the cover amount",
            "",
        )

    if savings is not None:
        add_row(
            "Monthly savings",
            format_money(savings, symbol),
            "from **Monthly Savings**",
        )
        if income:
            add_row(
                "Savings rate",
                f"{savings / income:.0%} of monthly income",
                "computed from monthly savings ÷ monthly income",
            )
        else:
            add_row(
                "Savings rate",
                "Not derivable yet — needs a numeric **Monthly Income**",
                "",
            )
    else:
        add_row("Monthly savings", _coach("Monthly Savings"), "")

    values["life_financial_summary"] = "\n".join(rows)

    # -- Will: bequests, minors, execution -------------------------------
    bequests = _real_answer(profile, "specific_bequests")
    if bequests and not _NONE_ANSWER_RE.match(str(bequests)):
        values["will_bequests_list"] = _numbered_lines(bequests)
    else:
        values["will_bequests_list"] = ""

    children = _real_answer(profile, "children")
    if children and _NONE_ANSWER_RE.match(str(children)):
        children = None
    values["has_minor_children"] = (
        "yes" if children and _MINOR_RE.search(str(children)) else ""
    )

    values["will_execution_status"] = will_execution_status(profile) or ""
    values["living_will_execution_status"] = (
        directive_execution_status(profile, "living_will_executed") or ""
    )
    values["poa_execution_status"] = (
        directive_execution_status(profile, "poa_executed") or ""
    )

    _add_budget_computed(values, profile, jurisdiction)


def _split_labelled_amount_lines(text):
    """`(label, amount_or_None, raw_line)` rows from a category: amount answer."""
    lines = [line.strip(" *-\t") for line in str(text or "").splitlines()]
    lines = [line for line in lines if line]
    rows = []
    for line in lines:
        name, _, rest = line.partition(":")
        label = name.strip() if rest.strip() else line
        amount = parse_money(rest if rest.strip() else line)
        rows.append((label, amount, line))
    return rows


def _add_budget_computed(values, profile, jurisdiction):
    """The monthly cash-flow table and its coverage/pressure checks.

    Same contract as every other computed block: figures come only from
    **Monthly Income**, **Monthly Expenses**, **Monthly Savings** and
    **Liquid Savings**; a missing or narrative answer coaches instead of
    computing, and every derived line names its inputs.
    """
    symbol = jurisdiction.currency_symbol or ""

    income = parse_money(_real_answer(profile, "monthly_income"))
    savings = parse_money(_real_answer(profile, "monthly_savings"))
    liquid = parse_money(_real_answer(profile, "liquid_savings"))
    expense_rows = _split_labelled_amount_lines(
        _real_answer(profile, "monthly_expenses")
    )
    expenses_total = sum(
        amount for _l, amount, _r in expense_rows if amount is not None
    )
    expenses_parsed = sum(1 for _l, amount, _r in expense_rows if amount is not None)

    rows = ["| Line | Monthly amount | Basis |", "| :--- | :--- | :--- |"]

    if income is not None:
        rows.append(
            f"| Income (after tax) | {format_money(income, symbol)} | "
            "from **Monthly Income** |"
        )
    else:
        rows.append(f"| Income (after tax) | {_coach('Monthly Income')} | |")

    for label, amount, raw in expense_rows:
        if amount is not None:
            rows.append(
                f"| Expense — {_cell(label)} | {format_money(amount, symbol)} | "
                "from **Monthly Expenses** |"
            )
        else:
            rows.append(
                f"| Expense — {_cell(label)} | no amount parsed — {_cell(raw)} | "
                "from **Monthly Expenses** |"
            )
    if expenses_parsed:
        rows.append(
            f"| **Total expenses** | **{format_money(expenses_total, symbol)}** | "
            f"computed from **Monthly Expenses** ({expenses_parsed} of "
            f"{len(expense_rows)} lines carried an amount) |"
        )
    else:
        rows.append(
            f"| Total expenses | {_coach('Monthly Expenses')} — one category "
            "per line, with the amount | |"
        )

    if savings is not None:
        rows.append(
            f"| Savings committed | {format_money(savings, symbol)} | "
            "from **Monthly Savings** |"
        )
    else:
        rows.append(f"| Savings committed | {_coach('Monthly Savings')} | |")

    if income is not None and expenses_parsed:
        net = income - expenses_total - (savings or 0.0)
        basis = "computed from income − total expenses"
        if savings is not None:
            basis += " − savings committed"
        else:
            basis += " (no **Monthly Savings** answered — none subtracted)"
        rows.append(f"| **Unallocated** | **{format_money(net, symbol)}** | {basis} |")
    else:
        net = None
        rows.append(
            "| Unallocated | Not derivable yet — needs a numeric "
            "**Monthly Income** and amounts in **Monthly Expenses** | |"
        )

    if savings is not None and income:
        rows.append(
            f"| Savings rate | {savings / income:.0%} of income | "
            "computed from monthly savings ÷ monthly income |"
        )

    if liquid is not None and expenses_parsed and expenses_total:
        rows.append(
            f"| Expense cover | {liquid / expenses_total:.1f} months | "
            "computed from **Liquid Savings** ÷ total monthly expenses |"
        )
    else:
        rows.append(
            "| Expense cover | Not derivable yet — needs **Liquid Savings** "
            "and amounts in **Monthly Expenses** | |"
        )

    values["budget_cash_flow_table"] = "\n".join(rows)

    flags = []
    if net is not None and net < 0:
        flags.append(
            "*   **Check**: expenses plus committed savings exceed income by "
            f"{format_money(abs(net), symbol)} per month. Reconcile "
            "**Monthly Income**, **Monthly Expenses** and **Monthly Savings** "
            "— one of them is out of date, or the plan runs a deficit."
        )
    if expense_rows and expenses_parsed < len(expense_rows):
        flags.append(
            f"*   **Note**: {len(expense_rows) - expenses_parsed} expense "
            "line(s) carried no parseable amount and are excluded from the "
            "totals — add an amount to each line of **Monthly Expenses**."
        )
    values["budget_flags"] = "\n".join(flags)
