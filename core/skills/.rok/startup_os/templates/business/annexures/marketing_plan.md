# {{company_name}} — Marketing Plan

## 1. Objective
{{#if strategic_objectives}}
Marketing exists to serve these objectives:

{{strategic_objectives}}
{{else}}
*No strategic objectives recorded. Marketing without a business objective
becomes activity for its own sake — answer **Strategic Objectives**.*
{{/if}}

---

## 2. Positioning & Message
{{#if brand_positioning}}
{{brand_positioning}}
{{else}}
{{#if core_value_proposition}}
{{core_value_proposition}}
{{/if}}
{{/if}}

{{#if problem_statement}}
### The Problem We Lead With
{{problem_statement}}
{{/if}}

{{#if unfair_advantage}}
### What Makes the Claim Credible
{{unfair_advantage}}
{{/if}}

---

## 3. Audience
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
{{customer_segments}}
{{/unless}}

---

## 4. Channels & Activity
{{#if acquisition_channels}}
{{acquisition_channels}}
{{else}}
{{#if growth_strategy}}
{{growth_strategy}}
{{else}}
*No channels recorded.*
{{/if}}
{{/if}}

{{#if market_trends}}
### Market Context
{{market_trends}}
{{/if}}

---

## 5. Budget
{{#if marketing_budget}}
{{marketing_budget}}
{{else}}
*No budget recorded. Answer **Marketing Budget** — amount and period.*
{{/if}}

---

## 6. Measurement

| Metric | Target | Review |
| :--- | :--- | :--- |
| Cost per lead | *set* | Monthly |
| Cost per acquired customer | *set* | Monthly |
| Lead-to-customer conversion | *set* | Monthly |
| Revenue by channel | *set* | Monthly |
| Payback period | *set* | Quarterly |

---

## 7. Claims Discipline
{{#if_feature bbee}}
{{#unless bee_level}}
> [!IMPORTANT]
> No B-BBEE certificate is on file. Do not use a contribution level in any
> marketing material, tender response or supplier application until a verified
> level appears in the compliance log.
{{/unless}}
{{/if_feature}}
{{#if quality_standards}}
Certification claims in marketing must match the certificates on file:
{{quality_standards}}
{{/if}}

Every factual claim in marketing material should trace to something in
`questions.md` or a document in the compliance folder.
