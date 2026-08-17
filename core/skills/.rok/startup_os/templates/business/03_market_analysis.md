# {{company_name}} — Market Analysis

## 1. The Opportunity
{{#if problem_statement}}
{{problem_statement}}
{{/if}}

{{#if market_trends}}
### Why Now
{{market_trends}}
{{/if}}

### Market Sizing: TAM / SAM / SOM

{{#if market_funnel_table}}
{{market_funnel_table}}
{{#if market_sizing_flags}}

{{market_sizing_flags}}
{{/if}}

**As stated in questions.md** — with sources:

*   **TAM**: {{market_size_tam}}
*   **SAM**: {{market_size_sam}}
*   **SOM**: {{market_size_som}}
{{else}}
| Layer | Size | Meaning |
| :--- | :--- | :--- |
| **TAM** | {{market_size_tam}} | The whole category |
| **SAM** | {{market_size_sam}} | Reachable with the current model |
| **SOM** | {{market_size_som}} | Realistic capture over 36 months |

{{#if market_size_tam}}
*No figures could be read from the sizing answers, so no funnel shares are
computed. State each layer with a number (e.g. "R 1.9 billion — 8,000
practices reachable...") and the compiler will show SAM as a share of TAM,
SOM as a share of SAM, and flag incoherent values.*
{{/if}}
{{/if}}

{{#unless market_size_tam}}
> [!WARNING]
> Market sizing is unanswered. Each figure should carry a source — a reader
> will check.
{{/unless}}

---

## 2. Competition
{{#if key_competitors}}
**Who else serves this customer**: {{key_competitors}}
{{/if}}

{{#if competitor_table}}
### Positioning Against Each
{{competitor_table}}

*Built from **Competitive Positioning**{{#unless competitive_positioning}} — each named competitor still needs its one-line comparison{{/unless}}.*
{{else}}
{{#if competitive_positioning}}
### Positioning Against Each
{{competitive_positioning}}
{{else}}
*No competitor comparison recorded. Answer **Competitive Positioning** —
"we have no competitors" is read as "we have not looked".*
{{/if}}
{{/if}}

{{#if competitor_pricing_table}}
### Named-Competitor Pricing
{{competitor_pricing_table}}
{{/if}}
{{#unless competitor_pricing_table}}
*A named-competitor pricing table unlocks at Level 3 (diligence-grade). The
Depth line in Document Control lists the exact answers still needed.*
{{/unless}}

{{#if unfair_advantage}}
### Defensibility
{{unfair_advantage}}
{{/if}}

---

## 3. Customer Segments

{{#if customer_segment_primary}}
### Primary
{{customer_segment_primary}}
{{/if}}
{{#if customer_segment_secondary}}
### Secondary
{{customer_segment_secondary}}
{{/if}}
{{#if customer_segment_tertiary}}
### Tertiary
{{customer_segment_tertiary}}
{{/if}}
{{#unless customer_segment_primary}}
{{#if customer_segments}}
{{customer_segments}}
{{else}}
*Customer segments not recorded.*
{{/if}}
{{/unless}}

---

## 4. Route to Market
{{#if acquisition_channels}}
{{acquisition_channels}}
{{else}}
{{#if growth_strategy}}
{{growth_strategy}}
{{else}}
*No acquisition channels recorded.*
{{/if}}
{{/if}}

---

## 5. Porter's Five Forces

*Each force is filled from the venture's own answers. An empty force is a
research gap, not a safe assumption — the coaching cell names the question
that fills it.*

| Force | Assessment |
| :--- | :--- |
| **Competitive rivalry** | {{#if competitive_positioning}}{{competitive_positioning}}{{else}}{{#if key_competitors}}{{key_competitors}}{{else}}Pending — answer **Key Competitors** and **Competitive Positioning**{{/if}}{{/if}} |
| **Threat of new entrants** | {{#if unfair_advantage}}Barriers an entrant must clear: {{unfair_advantage}}{{else}}Pending — answer **Unfair Advantage**: what slows a new entrant down?{{/if}} |
| **Buyer power** | {{#if customer_segment_primary}}Who holds the pen: {{customer_segment_primary}}{{else}}{{#if customer_segments}}Who holds the pen: {{customer_segments}}{{else}}Pending — answer **Customer Segments**{{/if}}{{/if}} |
| **Supplier power** | {{#if key_suppliers}}Dependency on: {{key_suppliers}}{{else}}Pending — answer **Key Suppliers**{{/if}} |
| **Threat of substitutes** | {{#if substitute_solutions}}{{substitute_solutions}}{{else}}Pending — answer **Substitute Solutions**: what do customers use instead of buying from this category at all?{{/if}} |
