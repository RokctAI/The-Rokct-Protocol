# {{company_name}} — Market Analysis

## 1. The Opportunity
{{#if problem_statement}}
{{problem_statement}}
{{/if}}

{{#if market_trends}}
### Why Now
{{market_trends}}
{{/if}}

### Market Sizing
| Layer | Size | Meaning |
| :--- | :--- | :--- |
| **TAM** | {{market_size_tam}} | The whole category |
| **SAM** | {{market_size_sam}} | Reachable with the current model |
| **SOM** | {{market_size_som}} | Realistic capture over 36 months |

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

{{#if competitive_positioning}}
### Positioning Against Each
{{competitive_positioning}}
{{else}}
_No competitor comparison recorded. Answer **Competitive Positioning** —
"we have no competitors" is read as "we have not looked"._
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
