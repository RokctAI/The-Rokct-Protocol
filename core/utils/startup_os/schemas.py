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

from core.parser import canonical_key


# Question tiers. `core` is what a fresh profile collects by default — enough to
# produce the one-page suite. `full` adds what the complete business-plan set
# needs (market sizing, technical architecture, terms of sale, succession).
# Both tiers are always part of the schema so the linter can check every
# template; the tier only decides what a newly provisioned file writes out.
TIER_CORE = "core"
TIER_FULL = "full"


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
]


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
            lines.append(f"    *   **Answer**: {answer}")
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
