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

"""Question schemas — the contract between provisioning and the templates.

The previous provisioner asked for `core_value_proposition`, `customer_segments`
and `power_continuity_strategy`, none of which any template used, while every
business template needed `key_suppliers`, `board_directors`,
`shareholder_distribution`, `personnel_count`, `primary_products` and
`growth_strategy`, none of which provisioning asked for. A freshly provisioned
profile therefore compiled to an executive summary reading "operating under the
primary classification of **Pending — update questions.md for
'primary_products'**".

Declaring the questions here, in one place, makes that class of drift
detectable: `validate_schema_against_templates()` fails when a template needs a
field the schema never collects.
"""

from .parser import canonical_key

# Question tiers. `core` is what a fresh profile collects by default — enough to
# produce the one-page suite. `full` adds what the complete business-plan set
# needs (market sizing, technical architecture, terms of sale, succession).
# `diligence` is the deepest set: the answers an investor's due-diligence pass
# asks for (per-channel CAC, cohort retention, competitor pricing, cap-table
# detail). All tiers are always part of the schema so the linter can check
# every template; the tier only decides what a newly provisioned file writes
# out and which depth level an answer unlocks.
TIER_CORE = "core"
TIER_FULL = "full"
TIER_DILIGENCE = "diligence"


class Question:
    __slots__ = ("label", "prompt", "default", "required", "example", "tier")

    def __init__(
        self, label, prompt, default=None, required=False, example=None, tier=TIER_CORE
    ):
        self.label = label
        self.prompt = prompt
        self.default = default
        self.required = required
        self.example = example
        self.tier = tier

    @property
    def key(self):
        return canonical_key(self.label)


class Section:
    __slots__ = ("title", "questions")

    def __init__(self, title, questions):
        self.title = title
        self.questions = questions


BUSINESS_SCHEMA = [
    Section(
        "Venture Identity & Jurisdiction",
        [
            Question(
                "Trading Name",
                "What is the primary commercial brand or trading name?",
                required=True,
            ),
            Question(
                "Jurisdiction",
                "Which country's company law and tax regime does this venture operate under? "
                "Use an ISO country code (ZA, US, GB, DE, KE, NG, AE, IN, AU, SG, BR...).",
                required=True,
                example="ZA",
            ),
            Question(
                "Primary Base",
                "What is the primary geographical base of operations?",
                required=True,
            ),
            Question("Establishment Date", "When was the venture established?"),
            Question(
                "Industry",
                "Which industry or sector does the venture operate in?",
                required=True,
                example="Healthcare services",
            ),
            Question(
                "Vision Statement", "What is the venture's core vision?", required=True
            ),
            Question(
                "Core Value Proposition",
                "What is the product or service's unique value statement?",
                required=True,
            ),
        ],
    ),
    Section(
        "Market & Product",
        [
            Question(
                "Primary Products",
                "What are the core components of the product or service suite?",
                required=True,
            ),
            Question(
                "Customer Segments",
                "Who are the primary target customers?",
                required=True,
            ),
            Question(
                "Growth Strategy",
                "What is the key customer acquisition loop?",
                required=True,
            ),
            Question("Key Competitors", "Who else serves this customer today?"),
            Question("Unfair Advantage", "What is hard for a competitor to copy?"),
        ],
    ),
    Section(
        "Operations & People",
        [
            Question(
                "Key Suppliers", "Who are the primary strategic suppliers or vendors?"
            ),
            Question("Personnel Count", "What is the current headcount?"),
            Question("Board Directors", "Who are the active directors on the board?"),
            Question(
                "Shareholder Distribution", "What is the shareholder percentage split?"
            ),
            Question(
                "Key Operational Risks",
                "What are the top operational risks and their mitigations?",
            ),
            Question(
                "Business Continuity Strategy",
                "How does the venture handle its main infrastructure or supply disruption risk?",
            ),
        ],
    ),
    Section(
        "Financial Projections & History",
        [
            Question("Projected Year 1", "Year 1 revenue, profit and milestones?"),
            Question("Projected Year 2", "Year 2 revenue, profit and milestones?"),
            Question("Projected Year 3", "Year 3 revenue, profit and milestones?"),
            Question("Historical Turnover 2024", "Annual turnover for 2024?"),
            Question("Historical Turnover 2025", "Annual turnover for 2025?"),
            Question("Historical Turnover 2026 YTD", "Year-to-date turnover for 2026?"),
            Question(
                "Funding Requirement", "How much capital is being sought, and for what?"
            ),
        ],
    ),
    # ---- Extended set: needed by the full business-plan suite ----
    Section(
        "Mission & Philosophy",
        [
            Question(
                "Mission Statement",
                "What does the venture do, for whom, and why?",
                tier=TIER_FULL,
            ),
            Question(
                "Core Philosophy",
                "What principles govern how the venture builds and operates? "
                "One line per principle.",
                tier=TIER_FULL,
            ),
            Question(
                "Head Office",
                "Where is the registered head office or main premises?",
                tier=TIER_FULL,
            ),
            Question(
                "Secondary Locations",
                "Any additional sites, branches or field offices?",
                tier=TIER_FULL,
            ),
            Question(
                "Target Sectors",
                "Which sectors or markets does the venture sell into?",
                tier=TIER_FULL,
            ),
            Question(
                "Intellectual Property",
                "What proprietary assets exist — patents, trademarks, software, "
                "recipes, methods, licences?",
                tier=TIER_FULL,
            ),
        ],
    ),
    Section(
        "Market & Opportunity",
        [
            Question(
                "Problem Statement",
                "What specific problem does the venture solve? Name who has it "
                "and what it costs them today.",
                tier=TIER_FULL,
            ),
            Question(
                "Market Size TAM",
                "Total addressable market — the whole category, with a source.",
                tier=TIER_FULL,
            ),
            Question(
                "Market Size SAM",
                "Serviceable addressable market — the slice reachable with the "
                "current model.",
                tier=TIER_FULL,
            ),
            Question(
                "Market Size SOM",
                "Serviceable obtainable market — realistic capture over 36 months.",
                tier=TIER_FULL,
            ),
            Question(
                "Market Trends",
                "Which trends make this the right moment?",
                tier=TIER_FULL,
            ),
            Question(
                "Competitive Positioning",
                "How does the venture compare to each named competitor? "
                "One line per competitor.",
                tier=TIER_FULL,
            ),
            Question(
                "Substitute Solutions",
                "What do customers use instead of buying from this category "
                "at all — spreadsheets, paper, an in-house workaround, doing "
                "nothing?",
                tier=TIER_FULL,
            ),
            Question(
                "Customer Segment Primary",
                "Describe the primary customer: who they are, what they buy, how "
                "often.",
                tier=TIER_FULL,
            ),
            Question(
                "Customer Segment Secondary",
                "The second customer group, if any.",
                tier=TIER_FULL,
            ),
            Question(
                "Customer Segment Tertiary",
                "A third customer group, if any.",
                tier=TIER_FULL,
            ),
        ],
    ),
    Section(
        "Product & Technology",
        [
            Question(
                "Product Components",
                "Break the offering into its named components and what each does.",
                tier=TIER_FULL,
            ),
            Question(
                "Technical Architecture",
                "How is the product built and delivered? Systems, stack, "
                "infrastructure, or for non-software: plant, equipment, process.",
                tier=TIER_FULL,
            ),
            Question(
                "Product Roadmap",
                "What ships in the next 12-24 months?",
                tier=TIER_FULL,
            ),
            Question(
                "Hardware Or Equipment",
                "Any physical hardware, machinery or devices involved?",
                tier=TIER_FULL,
            ),
        ],
    ),
    Section(
        "Marketing & Sales",
        [
            Question(
                "Acquisition Channels",
                "Through which channels do customers actually arrive? One per line.",
                tier=TIER_FULL,
            ),
            Question(
                "Pricing Tiers",
                "What does the venture charge, per tier or product line?",
                tier=TIER_FULL,
            ),
            Question(
                "Sales Process",
                "From first contact to signed customer, what happens?",
                tier=TIER_FULL,
            ),
            # The canvases previously reused `growth_strategy` for both the
            # Channels and Customer Relationships boxes — one acquisition loop
            # answered three different questions. These give each box its own
            # concept; templates fall back to `growth_strategy` for profiles
            # that have not answered them yet.
            Question(
                "Sales Channels",
                "Through which channels is the product sold and delivered to "
                "the customer?",
                tier=TIER_FULL,
            ),
            Question(
                "Customer Relationships",
                "How are customers won, kept and grown — self-serve, dedicated "
                "support, account management, community?",
                tier=TIER_FULL,
            ),
            Question(
                "Brand Positioning",
                "In one sentence, how should the market see you?",
                tier=TIER_FULL,
            ),
            Question(
                "Marketing Budget",
                "What is committed to marketing, and over what period?",
                tier=TIER_FULL,
            ),
        ],
    ),
    Section(
        "Operations & Quality",
        [
            Question(
                "Key Processes",
                "What are the core repeatable operations, from order to delivery?",
                tier=TIER_FULL,
            ),
            Question(
                "Quality Standards",
                "Which standards, certifications or inspections apply?",
                tier=TIER_FULL,
            ),
            Question(
                "Service Levels",
                "What does the venture commit to on delivery or uptime?",
                tier=TIER_FULL,
            ),
            Question(
                "Capacity Constraints",
                "What limits how much the venture can deliver today?",
                tier=TIER_FULL,
            ),
        ],
    ),
    Section(
        "People & Governance",
        [
            Question(
                "Executive Team",
                "Who holds each executive role, and what do they own? "
                "One line per person.",
                tier=TIER_FULL,
            ),
            Question(
                "HR Vision",
                "What kind of team is being built, and how?",
                tier=TIER_FULL,
            ),
            Question(
                "Hiring Plan",
                "Which roles are being hired, when, and at what cost?",
                tier=TIER_FULL,
            ),
            Question(
                "Organisational Culture",
                "What behaviour is expected and rewarded?",
                tier=TIER_FULL,
            ),
            Question(
                "Key Person Dependencies",
                "Which individuals would the venture struggle to replace?",
                tier=TIER_FULL,
            ),
            Question(
                "Succession Arrangements",
                "If a key person becomes unavailable, who steps in and how?",
                tier=TIER_FULL,
            ),
        ],
    ),
    Section(
        "Financial Detail",
        [
            Question(
                "Revenue Streams",
                "Every way the venture earns money, with the rate or fee for each.",
                tier=TIER_FULL,
            ),
            Question(
                "Cost Structure",
                "The main fixed and variable cost lines.",
                tier=TIER_FULL,
            ),
            Question(
                "Gross Margin Target",
                "Target gross margin, by line if they differ.",
                tier=TIER_FULL,
            ),
            # Unit economics. The previous financial model shipped a table of
            # literal "_to be supplied_" cells because nothing ever collected
            # these; with them answered, the compiler derives CAC payback,
            # customer lifetime value and runway instead of leaving blanks.
            Question(
                "Average Revenue Per Customer",
                "What does one customer pay on average? State the period — "
                "per month or per year.",
                example="R 3,500 per month",
                tier=TIER_FULL,
            ),
            Question(
                "Customer Acquisition Cost",
                "What does it cost, all-in, to win one customer — sales, "
                "marketing and onboarding included?",
                tier=TIER_FULL,
            ),
            Question(
                "Customer Churn Rate",
                "What share of customers leave? State the period — per month "
                "or per year.",
                example="2% monthly",
                tier=TIER_FULL,
            ),
            Question(
                "Customer Count Year 1",
                "How many paying customers by the end of Year 1?",
                tier=TIER_FULL,
            ),
            Question(
                "Monthly Operating Costs",
                "What does the venture spend per month, all costs in — the "
                "monthly burn?",
                tier=TIER_FULL,
            ),
            Question(
                "Cash On Hand",
                "How much cash is in the bank today?",
                tier=TIER_FULL,
            ),
            Question(
                "Break Even Point",
                "What revenue or volume covers fixed costs?",
                tier=TIER_FULL,
            ),
            Question(
                "Capital Allocation",
                "How would new capital be spent, by category?",
                tier=TIER_FULL,
            ),
            Question(
                "Funding History",
                "What has been raised or granted so far, from whom?",
                tier=TIER_FULL,
            ),
        ],
    ),
    Section(
        "Strategy & Milestones",
        [
            Question(
                "Strategic Objectives",
                "The three to five objectives for the year.",
                tier=TIER_FULL,
            ),
            Question(
                "Milestones 12 Month",
                "What must be true 12 months from now?",
                tier=TIER_FULL,
            ),
            Question(
                "Milestones 36 Month",
                "What must be true in three years?",
                tier=TIER_FULL,
            ),
            Question(
                "Key Projects",
                "Named projects in flight, with owner and due date.",
                tier=TIER_FULL,
            ),
            Question(
                "Achievements To Date",
                "Wins worth citing: grants, pilots, awards, contracts.",
                tier=TIER_FULL,
            ),
            Question(
                "Reference Contacts",
                "Contactable references for tenders and grants — one per "
                "line: organisation, contact person, role, phone or email.",
                example="Dept of Health Limpopo: Dr N. Baloyi, programme lead, 015 000 0000",
                tier=TIER_FULL,
            ),
        ],
    ),
    Section(
        "Commercial Terms",
        [
            Question(
                "Payment Terms",
                "Deposit, credit period, late-payment terms?",
                tier=TIER_FULL,
            ),
            Question(
                "Delivery Terms",
                "Lead times, delivery responsibility, risk transfer?",
                tier=TIER_FULL,
            ),
            Question(
                "Warranty Terms",
                "What is warranted, for how long, with what remedy?",
                tier=TIER_FULL,
            ),
            Question(
                "Returns Policy",
                "Under what conditions are returns or refunds accepted?",
                tier=TIER_FULL,
            ),
            Question(
                "Dispute Resolution",
                "How are disputes handled, and under which law?",
                tier=TIER_FULL,
            ),
        ],
    ),
    # ---- Diligence set: the answers that unlock depth Level 3 ----
    Section(
        "Diligence & Deep Metrics",
        [
            Question(
                "Competitor Pricing",
                "What does each named competitor actually charge? One "
                "competitor per line, with the price.",
                example="GoodX: R 4,100/month for a two-practitioner practice",
                tier=TIER_DILIGENCE,
            ),
            Question(
                "CAC By Channel",
                "What does one customer cost to win, per acquisition channel? "
                "One channel per line, with the all-in cost.",
                example="Bureau partnerships: R 9,000 per clinic",
                tier=TIER_DILIGENCE,
            ),
            Question(
                "Sales Cycle Length",
                "How long from first contact to signed customer, on average?",
                example="21 days median",
                tier=TIER_DILIGENCE,
            ),
            Question(
                "Retention Cohorts",
                "How do customer cohorts behave over time — the share of a "
                "signup cohort still active after three, six and twelve "
                "months, or the repeat-purchase rate?",
                tier=TIER_DILIGENCE,
            ),
            Question(
                "Cap Table",
                "Beyond the percentage split: share classes, option pool "
                "size, outstanding notes or SAFEs, and any special investor "
                "rights.",
                tier=TIER_DILIGENCE,
            ),
        ],
    ),
]


# ---------------------------------------------------------------------------
# Depth ladder.
#
# Documents compile at the deepest level the answers support — never deeper.
# Each level names the exact answers that define it, so the coaching in the
# Document Control block can list the real missing fields instead of a vague
# "answer more questions". Levels are cumulative: Level 3 requires every
# Level 1 and Level 2 field as well as its own.
# ---------------------------------------------------------------------------


class DepthLevel:
    __slots__ = ("number", "name", "keys")

    def __init__(self, number, name, keys):
        self.number = number
        self.name = name
        self.keys = keys


BUSINESS_DEPTH_LEVELS = (
    DepthLevel(
        1,
        "foundation",
        (
            "trading_name",
            "jurisdiction",
            "primary_base",
            "industry",
            "vision_statement",
            "core_value_proposition",
            "primary_products",
            "customer_segments",
            "growth_strategy",
        ),
    ),
    DepthLevel(
        2,
        "investor-ready",
        (
            "problem_statement",
            "market_size_tam",
            "market_size_sam",
            "market_size_som",
            "competitive_positioning",
            "revenue_streams",
            "pricing_tiers",
            "executive_team",
            "funding_requirement",
            "gross_margin_target",
            "average_revenue_per_customer",
            "customer_acquisition_cost",
            "monthly_operating_costs",
            "cash_on_hand",
        ),
    ),
    DepthLevel(
        3,
        "diligence-grade",
        (
            "customer_churn_rate",
            "funding_history",
            "hiring_plan",
            "competitor_pricing",
            "cac_by_channel",
            "sales_cycle_length",
            "retention_cohorts",
            "cap_table",
        ),
    ),
)

DEPTH_DILIGENCE = BUSINESS_DEPTH_LEVELS[-1].number


LIFE_DEPTH_LEVELS = (
    DepthLevel(
        1,
        "foundation",
        (
            "full_name",
            "pronouns",
            "primary_base",
            "life_purpose",
            "wellness_focus",
            "daily_rhythm",
        ),
    ),
    DepthLevel(
        2,
        "stewardship-ready",
        (
            "sleep_target",
            "training_routine",
            "health_metrics",
            "focus_blocks",
            "personal_values",
            "assets",
            "liabilities",
            "life_cover_policies",
            "monthly_savings",
            "beneficiaries",
            "digital_asset_inventory",
            "release_protocol",
        ),
    ),
    DepthLevel(
        3,
        "estate-ready",
        (
            "legal_full_name",
            "marital_status",
            "children",
            "executor",
            "alternate_executor",
            "specific_bequests",
            "residue_beneficiaries",
            "alternate_heirs",
            # Estate-readiness also means naming who acts while you are
            # alive but unable: the medical and financial agents behind the
            # living will and the power-of-attorney draft.
            "healthcare_proxy",
            "attorney_in_fact",
        ),
    ),
)

_DEPTH_LADDERS = {"business": BUSINESS_DEPTH_LEVELS, "life": LIFE_DEPTH_LEVELS}


def depth_levels(instance_type):
    """The ladder for an instance type. Unknown types have no ladder."""
    return _DEPTH_LADDERS.get(instance_type, ())


class DepthReport:
    """Achieved depth plus exactly what unlocks the next level."""

    __slots__ = ("level", "name", "total", "next_level", "next_name", "missing")

    def __init__(self, level, name, total, next_level, next_name, missing):
        self.level = level
        self.name = name
        self.total = total
        self.next_level = next_level
        self.next_name = next_name
        self.missing = missing  # ordered (key, label) pairs for the next level


def compute_depth(instance_type, answered_keys):
    """Compute the achieved depth level from which answers are present.

    Returns a `DepthReport`, or None for instance types without a ladder.
    An old questions.md that has never seen the newer questions simply stays
    at the level its answers support — nothing about a missing question stops
    a compile.
    """
    levels = depth_levels(instance_type)
    if not levels:
        return None

    answered = set(answered_keys)
    labels = questions_by_key(instance_type)

    achieved = 0
    achieved_name = "unstarted"
    for level in levels:
        missing = [key for key in level.keys if key not in answered]
        if missing:
            return DepthReport(
                level=achieved,
                name=achieved_name,
                total=levels[-1].number,
                next_level=level.number,
                next_name=level.name,
                missing=[
                    (key, labels[key].label if key in labels else key)
                    for key in missing
                ],
            )
        achieved = level.number
        achieved_name = level.name

    return DepthReport(
        level=achieved,
        name=achieved_name,
        total=levels[-1].number,
        next_level=None,
        next_name=None,
        missing=[],
    )


def describe_depth(report):
    """One Document Control line: the level, and exactly what unlocks more."""
    if report is None:
        return None
    if report.next_level is None:
        return (
            f"Level {report.level} of {report.total} — {report.name}; "
            "every depth-defining answer is present"
        )
    fields = ", ".join(label for _key, label in report.missing)
    return (
        f"Level {report.level} of {report.total} — {report.name}; "
        f"to reach Level {report.next_level} ({report.next_name}) answer: "
        f"{fields}"
    )


LIFE_SCHEMA = [
    Section(
        "Personal Identity & Focus",
        [
            Question("Full Name", "What is your full name?", required=True),
            Question(
                "Pronouns",
                "Which pronouns should documents use? (e.g. she/her, he/him, they/them)",
                required=True,
                example="they/them",
            ),
            Question(
                "Primary Base", "What is your primary geographical base?", required=True
            ),
            Question(
                "Jurisdiction",
                "Which country are you resident in? Use an ISO code.",
                example="ZA",
            ),
            Question(
                "Life Purpose",
                "What is your core mission or purpose statement?",
                required=True,
            ),
            Question(
                "Wellness Focus", "What is your primary wellness or performance goal?"
            ),
        ],
    ),
    Section(
        "Relationships & Stewardship",
        [
            Question(
                "Key Relationships",
                "Who are the primary partners, confidants or trustees?",
            ),
            Question("Legacy Vision", "What is the key long-term stewardship goal?"),
            Question("Dependants", "Who depends on you financially or practically?"),
        ],
    ),
    Section(
        "Venture & Career Integration",
        [
            Question(
                "Business Ownership",
                "Do you own a registered business or run a side venture?",
            ),
            Question("Current Role", "What is your current professional role?"),
            Question(
                "Skill Focus",
                "Which capability are you deliberately building right now?",
            ),
        ],
    ),
    Section(
        "Productivity & Rhythm",
        [
            Question("Daily Rhythm", "What does a productive day look like?"),
            Question("Accountability Partner", "Who holds you to your commitments?"),
            Question(
                "Focus Blocks",
                "When are your deep-focus blocks, and how long do they run?",
                example="06:00-09:00 daily, phone off",
                tier=TIER_FULL,
            ),
            Question(
                "Productivity Tools",
                "Which tools or systems keep your commitments visible and on track?",
                tier=TIER_FULL,
            ),
            Question(
                "Key Bottlenecks",
                "What most limits your energy, focus or progress right now?",
                tier=TIER_FULL,
            ),
        ],
    ),
    # ---- Extended set: the full life-planning suite draws on these ----
    Section(
        "Health & Vitality",
        [
            Question(
                "Sleep Target",
                "What sleep schedule and duration are you committing to?",
                example="22:00-06:00, eight hours, screens off an hour before",
                tier=TIER_FULL,
            ),
            Question(
                "Training Routine",
                "What is your weekly training or movement routine?",
                tier=TIER_FULL,
            ),
            Question(
                "Health Metrics",
                "Which health metrics or goals do you track, and what are the "
                "current targets?",
                example="resting heart rate under 60; 10,000 steps daily",
                tier=TIER_FULL,
            ),
            Question(
                "Nutrition Approach",
                "What nutrition approach fuels your day?",
                tier=TIER_FULL,
            ),
        ],
    ),
    Section(
        "Values & Philosophy",
        [
            Question(
                "Personal Values",
                "Which values do you refuse to trade away? One per line.",
                tier=TIER_FULL,
            ),
            Question(
                "Financial Philosophy",
                "What principles govern how you earn, spend and invest? "
                "One line per principle.",
                tier=TIER_FULL,
            ),
        ],
    ),
    Section(
        "Financial Stewardship",
        [
            Question(
                "Assets",
                "What do you own? One asset per line, with its estimated value "
                "where known.",
                example="Home: R 1,500,000",
                tier=TIER_FULL,
            ),
            Question(
                "Liabilities",
                "What do you owe? One debt per line, with the outstanding amount.",
                example="Home loan: R 900,000",
                tier=TIER_FULL,
            ),
            Question(
                "Life Cover Policies",
                "Which life insurance policies do you hold? One per line: "
                "insurer, policy reference, and the cover amount.",
                example="Alpha Insure, policy LC-1: R 2,000,000",
                tier=TIER_FULL,
            ),
            Question(
                "Beneficiaries",
                "Who benefits from your policies, savings and investments? "
                "One per line.",
                tier=TIER_FULL,
            ),
            Question(
                "Monthly Income",
                "What is your total monthly income, after tax?",
                tier=TIER_FULL,
            ),
            Question(
                "Monthly Savings",
                "How much do you save or invest per month?",
                tier=TIER_FULL,
            ),
            Question(
                "Monthly Expenses",
                "What do you spend per month, by category? One category per "
                "line, with the monthly amount.",
                example="Housing: R 12,000",
                tier=TIER_FULL,
            ),
            Question(
                "Liquid Savings",
                "How much is held in cash or same-day-accessible savings "
                "today — the emergency fund?",
                tier=TIER_FULL,
            ),
        ],
    ),
    Section(
        "Legacy & Digital Estate",
        [
            Question(
                "Executor",
                "Who should administer your estate as executor?",
                tier=TIER_FULL,
            ),
            Question(
                "Alternate Executor",
                "Who steps in if your first-choice executor cannot act?",
                tier=TIER_FULL,
            ),
            Question(
                "Digital Asset Inventory",
                "Which digital assets matter — accounts, domains, wallets, "
                "repositories — and where is access to them documented?",
                tier=TIER_FULL,
            ),
            Question(
                "Release Protocol",
                "How should sensitive documents be released after your death "
                "or incapacity — who verifies the event, over which channels, "
                "and after what waiting period?",
                tier=TIER_FULL,
            ),
            Question(
                "Memorial Wishes",
                "Any wishes for your memorial or funeral — burial or "
                "cremation, ceremony, tone?",
                tier=TIER_FULL,
            ),
        ],
    ),
    Section(
        "Healthcare Directives",
        [
            Question(
                "Healthcare Proxy",
                "Who should make healthcare decisions on your behalf if you "
                "cannot speak for yourself?",
                tier=TIER_FULL,
            ),
            Question(
                "Alternate Healthcare Proxy",
                "Who steps in if your first-choice healthcare proxy cannot act?",
                tier=TIER_FULL,
            ),
            Question(
                "Life Sustaining Treatment",
                "If you are terminally ill or permanently unconscious, should "
                "life-sustaining treatment be continued or withheld? Say it "
                "in your own words.",
                tier=TIER_FULL,
            ),
            Question(
                "Resuscitation Preference",
                "Should resuscitation (CPR) be attempted if your heart or "
                "breathing stops? State any conditions.",
                tier=TIER_FULL,
            ),
            Question(
                "Pain Relief Priority",
                "How should pain relief be weighed against other goals of "
                "care — e.g. comfort first, even at the cost of alertness?",
                tier=TIER_FULL,
            ),
            Question(
                "Organ Donation Wishes",
                "What are your wishes on organ and tissue donation?",
                tier=TIER_FULL,
            ),
            Question(
                "Living Will Executed",
                "Has the living will / advance directive been signed and "
                "witnessed? Record the signing date and place once done; "
                "leave pending until then.",
                example="Signed 2026-03-01 at Polokwane before two witnesses",
                tier=TIER_FULL,
            ),
        ],
    ),
    Section(
        "Power of Attorney",
        [
            Question(
                "Attorney In Fact",
                "Who should act as your agent (attorney-in-fact) under a "
                "power of attorney?",
                tier=TIER_FULL,
            ),
            Question(
                "Alternate Attorney In Fact",
                "Who steps in if your first-choice agent cannot act?",
                tier=TIER_FULL,
            ),
            Question(
                "Powers Granted",
                "Which powers are granted — general authority, or special "
                "powers listed one per line (bank account, property, a "
                "specific transaction)?",
                tier=TIER_FULL,
            ),
            Question(
                "POA Effective Conditions",
                "From when, and under what conditions, does the power "
                "operate — immediately, from a date, or only for a named "
                "transaction or period?",
                tier=TIER_FULL,
            ),
            Question(
                "POA Executed",
                "Has the power of attorney been signed (and witnessed or "
                "notarised where required)? Record the signing date and "
                "place once done; leave pending until then.",
                example="Signed 2026-03-01 at Polokwane before two witnesses",
                tier=TIER_FULL,
            ),
        ],
    ),
    Section(
        "Emergency Readiness",
        [
            Question(
                "Emergency Contacts",
                "Who should be called first in an emergency? One per line: "
                "name, relationship, phone.",
                tier=TIER_FULL,
            ),
            Question(
                "Primary Doctor",
                "Who is your primary doctor or practice? Name and phone.",
                tier=TIER_FULL,
            ),
            Question(
                "Allergies And Conditions",
                "Which allergies, chronic conditions and daily medications "
                "should an emergency responder know about? One per line.",
                tier=TIER_FULL,
            ),
            Question(
                "Key Document Locations",
                "Where do your key documents live — will, policies, identity "
                "document, medical aid details? One per line.",
                tier=TIER_FULL,
            ),
        ],
    ),
    Section(
        "Last Will & Testament",
        [
            Question(
                "Legal Full Name",
                "What is your full legal name, exactly as it appears on your "
                "identity document?",
                tier=TIER_FULL,
            ),
            Question(
                "Marital Status",
                "What is your marital status, and under which regime — e.g. "
                "married in community of property, married out of community "
                "with accrual, single, divorced, widowed?",
                tier=TIER_FULL,
            ),
            Question(
                "Spouse Or Partner Name",
                "What is your spouse or partner's full name, if any?",
                tier=TIER_FULL,
            ),
            Question(
                "Children",
                "List your children, one per line, marking each minor with "
                "the word 'minor' and their year of birth. Write 'None' if "
                "you have no children.",
                example="Thandi (2015, minor)",
                tier=TIER_FULL,
            ),
            Question(
                "Guardian Nomination",
                "Who should be guardian of any minor children, and who is "
                "the alternate?",
                tier=TIER_FULL,
            ),
            Question(
                "Specific Bequests",
                "Any specific gifts — one per line: the item or amount, then "
                "the recipient. Write 'None' to leave everything to the "
                "residue clause.",
                example="My watch: to my brother Sipho Dlamini",
                tier=TIER_FULL,
            ),
            Question(
                "Residue Beneficiaries",
                "Who inherits the rest of the estate (the residue), in what shares?",
                example="My spouse: 100%; failing them, my children equally",
                tier=TIER_FULL,
            ),
            Question(
                "Alternate Heirs",
                "If a named heir does not survive you, who inherits their "
                "share instead?",
                tier=TIER_FULL,
            ),
            Question(
                "Will Executed",
                "Has this will been formally signed and witnessed? Record the "
                "signing date and place once done; leave pending until then.",
                example="Signed 2026-03-01 at Polokwane before two witnesses",
                tier=TIER_FULL,
            ),
        ],
    ),
]


SCHEMAS = {"business": BUSINESS_SCHEMA, "life": LIFE_SCHEMA}


def schema_for(instance_type):
    return SCHEMAS.get(instance_type, [])


def schema_keys(instance_type, tier=None):
    """Every canonical key the schema collects, optionally filtered by tier."""
    return {
        question.key
        for section in schema_for(instance_type)
        for question in section.questions
        if tier is None or question.tier == tier
    }


def questions_by_key(instance_type):
    """Map canonical key -> Question, for lookups and migrations."""
    return {
        question.key: question
        for section in schema_for(instance_type)
        for question in section.questions
    }


def required_keys(instance_type):
    return {
        question.key
        for section in schema_for(instance_type)
        for question in section.questions
        if question.required
    }


def render_questions_md(instance_type, display_name, seed=None, include_full=False):
    """Render a fresh questions.md for a new profile.

    By default only `core` questions are written — enough for the one-page
    suite, without confronting a new user with fifty prompts. `include_full`
    adds the extended set the complete business-plan documents draw on.
    """
    seed = seed or {}
    sections = []
    for section in schema_for(instance_type):
        questions = [
            question
            for question in section.questions
            if include_full or question.tier == TIER_CORE
        ]
        if questions:
            sections.append(Section(section.title, questions))

    noun = "venture" if instance_type == "business" else "life"
    lines = [
        f"# {'Business' if instance_type == 'business' else 'Life'} "
        f"Strategic Questions: {display_name}",
        "",
        f"This file is the Single Source of Truth (SSOT) for {display_name}'s "
        f"{noun} variables. The StartupOS compiler reads only this file.",
        "",
        "> [!IMPORTANT]",
        "> Answers beginning with `Pending` are treated as unanswered and are",
        "> reported in the Completion Gaps section of every generated document.",
        "> No compliance status is ever assumed — regulated fields stay",
        "> unverified until a certificate is placed in the compliance folder.",
        "",
    ]

    for index, section in enumerate(sections, start=1):
        lines.append("---")
        lines.append("")
        lines.append(f"## {index}. {section.title}")
        for question in section.questions:
            answer = seed.get(question.key, question.default)
            if answer is None:
                hint = f" (e.g. {question.example})" if question.example else ""
                answer = f"Pending — {question.prompt.rstrip('?').lower()}{hint}"
            marker = " *(required)*" if question.required else ""
            lines.append(f"*   **{question.label}**{marker}: {question.prompt}")
            # Multi-line answers (a list of assets, of children, of bequests)
            # keep their continuation lines indented past the Answer bullet —
            # the exact shape the parser reads back. A flat write here would
            # silently truncate every seeded list to its first line.
            answer_lines = str(answer).splitlines() or [""]
            lines.append(f"    *   **Answer**: {answer_lines[0]}")
            for continuation in answer_lines[1:]:
                lines.append(f"        {continuation}")
        lines.append("")

    lines.append("---")
    lines.append("")
    lines.append("## Conversational Milestone Log (Living Ledger)")
    lines.append("")
    lines.append("<!-- Milestones logged by Hermes are appended below. -->")
    lines.append("")

    return "\n".join(lines)


def validate_schema_against_templates(
    instance_type, template_placeholders, engine_supplied=()
):
    """Report placeholders that no question collects, and questions no template uses.

    Returns `(uncollected, unused)`.
    """
    collected = schema_keys(instance_type)
    supplied = set(engine_supplied)

    uncollected = sorted(
        name
        for name in template_placeholders
        if name not in collected and name not in supplied
    )
    unused = sorted(key for key in collected if key not in template_placeholders)
    return uncollected, unused
