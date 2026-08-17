# {{company_name}} — Marketing & Sales

## 1. Positioning
{{#if brand_positioning}}
{{brand_positioning}}
{{else}}
{{#if core_value_proposition}}
{{core_value_proposition}}
{{else}}
*Not recorded. Answer **Brand Positioning** in questions.md.*
{{/if}}
{{/if}}

{{#if customer_segments}}
**Who we sell to**: {{customer_segments}}
{{/if}}

---

## 2. Acquisition Channels
{{#if acquisition_channels}}
{{acquisition_channels}}
{{else}}
{{#if growth_strategy}}
{{growth_strategy}}
{{else}}
*No channels recorded. Answer **Acquisition Channels** — list where customers
actually come from, not where you hope they will.*
{{/if}}
{{/if}}

{{#if growth_strategy}}
### Growth Loop
{{growth_strategy}}
{{/if}}

---

## 3. Sales Process
{{#if sales_process}}
{{sales_process}}
{{else}}
*Not recorded. Answer **Sales Process** — first contact through to signature.*
{{/if}}
{{#if sales_cycle_length}}

**Average sales cycle**: {{sales_cycle_length}}
{{/if}}

---

## 4. Pricing
{{#if pricing_tiers}}
{{pricing_tiers}}
{{/if}}
{{currency_note}}
{{#if payment_terms}}

**Payment terms**: {{payment_terms}}
{{/if}}

---

## 5. Budget & Measurement
{{#if marketing_budget}}
**Committed spend**: {{marketing_budget}}
{{/if}}

Track per channel:

*   Cost per lead and cost per acquired customer
*   Conversion rate at each stage of the sales process
*   Payback period against average customer value
*   Share of revenue by channel
