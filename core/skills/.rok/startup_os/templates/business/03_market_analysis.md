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
_No figures could be read from the sizing answers, so no funnel shares are
computed. State each layer with a number (e.g. "R 1.9 billion — 8,000
practices reachable...") and the compiler will show SAM as a share of TAM,
SOM as a share of SAM, and flag incoherent values._
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

_Built from **Competitive Positioning**{{#unless competitive_positioning}} — each named competitor still needs its one-line comparison{{/unless}}._
{{else}}
{{#if competitive_positioning}}
### Positioning Against Each
{{competitive_positioning}}
{{else}}
_No competitor comparison recorded. Answer **Competitive Positioning** —
"we have no competitors" is read as "we have not looked"._
{{/if}}
{{/if}}

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
_Customer segments not recorded._
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
_No acquisition channels recorded._
{{/if}}
{{/if}}
