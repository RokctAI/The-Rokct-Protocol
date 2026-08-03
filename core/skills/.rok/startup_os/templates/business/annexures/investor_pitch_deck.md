# {{company_name}} — Investor Pitch Deck

> [!NOTE]
> One slide per section. Figures are management projections from
> `questions.md` — unaudited, and unverified where marked *Pending*.

---

## Slide 1 — {{company_name}}
{{#if brand_positioning}}
{{brand_positioning}}
{{else}}
{{#if vision_statement}}
{{vision_statement}}
{{/if}}
{{/if}}

{{industry}} · {{primary_base}}{{#if establishment_date}} · founded {{establishment_date}}{{/if}}

---

## Slide 2 — The Problem
{{#if problem_statement}}
{{problem_statement}}
{{else}}
*Required for this deck. Answer **Problem Statement** in questions.md.*
{{/if}}

---

## Slide 3 — The Solution
{{#if core_value_proposition}}
{{core_value_proposition}}
{{/if}}
{{#if product_components}}

{{product_components}}
{{/if}}

---

## Slide 4 — Market
{{#if market_size_tam}}
*   **TAM**: {{market_size_tam}}
*   **SAM**: {{market_size_sam}}
*   **SOM (36 months)**: {{market_size_som}}
{{else}}
*Required for this deck. Answer **Market Size TAM / SAM / SOM** — with sources.*
{{/if}}
{{#if market_trends}}

**Why now**: {{market_trends}}
{{/if}}

---

## Slide 5 — Business Model
{{#if revenue_streams}}
{{revenue_streams}}
{{else}}
*Required for this deck. Answer **Revenue Streams**.*
{{/if}}
{{#if pricing_tiers}}

{{pricing_tiers}}
{{/if}}

---

## Slide 6 — Traction
{{#if achievements_to_date}}
{{achievements_to_date}}
{{else}}
*No traction recorded. This is the slide investors read most carefully.*
{{/if}}
{{#if funding_history}}

**Raised to date**: {{funding_history}}
{{/if}}

---

## Slide 7 — Competition
{{#if competitive_positioning}}
{{competitive_positioning}}
{{else}}
{{#if key_competitors}}
{{key_competitors}}
{{else}}
*No competitive analysis recorded.*
{{/if}}
{{/if}}

{{#if unfair_advantage}}
**Our advantage**: {{unfair_advantage}}
{{/if}}

---

## Slide 8 — Go To Market
{{#if acquisition_channels}}
{{acquisition_channels}}
{{else}}
{{growth_strategy}}
{{/if}}

---

## Slide 9 — Financials
{{currency_note}}

{{fin_grid_rev}}

{{fin_summary}}
{{#if gross_margin_target}}

**Gross margin target**: {{gross_margin_target}}
{{/if}}
{{#if break_even_point}}

**Break-even**: {{break_even_point}}
{{/if}}

---

## Slide 10 — Team
{{#if executive_team}}
{{executive_team}}
{{else}}
{{#if board_directors}}
{{board_directors}}
{{/if}}
{{/if}}

**Headcount**: {{personnel_count}}
{{#if hiring_plan}}

**Hiring next**: {{hiring_plan}}
{{/if}}

---

## Slide 11 — The Ask
{{#if funding_requirement}}
{{funding_requirement}}
{{else}}
*No capital requirement recorded. Answer **Funding Requirement**.*
{{/if}}
{{#if capital_allocation}}

### Use of Funds
{{capital_allocation}}
{{/if}}

---

## Slide 12 — Corporate Standing
{{#if_feature company_registry}}
*   **{{company_name_status}}**: {{company_name}}
*   **{{registry_name}} Number**: {{reg_number}}
{{#if_feature tax_clearance}}
*   **Tax compliance**: {{tax_compliance_status}}
{{/if_feature}}
{{/if_feature}}
{{#if_feature bbee}}
{{#if bee_level}}
*   **B-BBEE**: {{bee_level}}, {{bee_procurement_recognition}} procurement
    recognition. Certificate {{bee_cert_number}}, valid to {{bee_expiry_date}}.
{{else}}
*   **B-BBEE**: no certificate on file; no level is claimed.
{{/if}}
{{/if_feature}}
{{#if intellectual_property}}
*   **IP**: {{intellectual_property}}
{{/if}}
