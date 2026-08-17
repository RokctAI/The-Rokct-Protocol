# {{company_name}} — Investor Pitch Deck

> [!NOTE]
> One slide per section. Figures are management projections from
> `questions.md` — unaudited, and unverified where marked *Pending*.
> The italic line under each heading is what a strong version of that
> slide contains; delete these lines before presenting.

---

## Slide 1 — {{company_name}}
*A strong title slide is one sentence a stranger repeats correctly afterwards: who you serve and what changes for them.*

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
*A strong problem slide names who has the pain and prices it in money or hours — not "X is broken", but what it costs this customer today.*

{{#if problem_statement}}
{{problem_statement}}
{{else}}
*Required for this deck. Answer **Problem Statement** in questions.md.*
{{/if}}

---

## Slide 3 — The Solution
*A strong solution slide shows the before/after for one customer, not a feature list — the demo screenshot beats the architecture diagram.*

{{#if core_value_proposition}}
{{core_value_proposition}}
{{/if}}
{{#if product_components}}

{{product_components}}
{{/if}}

---

## Slide 4 — Market
*A strong market slide shows a sourced funnel and defends the SOM — investors fund the obtainable slice, not the category headline.*

{{#if market_funnel_table}}
{{market_funnel_table}}
{{#if market_sizing_flags}}

{{market_sizing_flags}}
{{/if}}
{{else}}
{{#if market_size_tam}}
*   **TAM**: {{market_size_tam}}
*   **SAM**: {{market_size_sam}}
*   **SOM (36 months)**: {{market_size_som}}
{{else}}
*Required for this deck. Answer **Market Size TAM / SAM / SOM** — with sources.*
{{/if}}
{{/if}}
{{#if market_trends}}

**Why now**: {{market_trends}}
{{/if}}

---

## Slide 5 — Business Model
*A strong model slide states who pays, how much, how often — one line per stream, with the price on the line.*

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
*A strong traction slide is a rising number over time — revenue, customers or usage — with the one metric you steer by.*

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
*A strong competition slide names real alternatives (including "do nothing") and states the one axis where you win — never an empty quadrant.*

{{#if competitor_table}}
{{competitor_table}}
{{else}}
{{#if competitive_positioning}}
{{competitive_positioning}}
{{else}}
{{#if key_competitors}}
{{key_competitors}}
{{else}}
*No competitive analysis recorded.*
{{/if}}
{{/if}}
{{/if}}

{{#if unfair_advantage}}
**Our advantage**: {{unfair_advantage}}
{{/if}}

---

## Slide 8 — Go To Market
*A strong GTM slide names the channel that already works, its acquisition cost, and what each new unit of spend buys.*

{{#if acquisition_channels}}
{{acquisition_channels}}
{{else}}
{{growth_strategy}}
{{/if}}

---

## Slide 9 — Financials
*A strong financials slide fits on one screen: three years of revenue, the unit economics that make growth affordable, and the runway the raise buys.*

{{currency_note}}

{{#if fin_projection_table}}
{{fin_projection_table}}
{{else}}
{{fin_grid_rev}}
{{/if}}

{{fin_unit_economics}}
{{#if break_even_point}}

**Break-even**: {{break_even_point}}
{{/if}}
{{#if fin_consistency}}

{{fin_consistency}}
{{/if}}

---

## Slide 10 — Team
*A strong team slide answers "why these people win this market" — one proof point per person beats a wall of logos.*

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
*A strong ask slide states the amount, the runway it buys, and the two or three milestones it reaches — investors fund milestones, not months.*

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
*A strong closing slide preempts due diligence: registration, tax standing and IP in one glance, each claim document-backed.*

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
