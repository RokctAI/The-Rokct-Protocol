# {{company_name}} — Sales Plan

## 1. Targets
{{currency_note}}

{{fin_summary}}

{{#if strategic_objectives}}
### Objectives These Serve
{{strategic_objectives}}
{{/if}}

---

## 2. What Is Being Sold
{{#if primary_products}}
{{primary_products}}
{{/if}}
{{#if pricing_tiers}}

### Price Points
{{pricing_tiers}}
{{/if}}
{{#if gross_margin_target}}

**Margin to protect**: {{gross_margin_target}}
{{/if}}

---

## 3. To Whom
{{#if customer_segment_primary}}
### Primary
{{customer_segment_primary}}
{{/if}}
{{#if customer_segment_secondary}}
### Secondary
{{customer_segment_secondary}}
{{/if}}
{{#unless customer_segment_primary}}
{{customer_segments}}
{{/unless}}

---

## 4. Pipeline Sources
{{#if acquisition_channels}}
{{acquisition_channels}}
{{else}}
{{growth_strategy}}
{{/if}}

---

## 5. The Sales Process
{{#if sales_process}}
{{sales_process}}
{{else}}
_Not recorded. Answer **Sales Process** — the stages, who owns each, and what
moves a deal from one to the next._
{{/if}}

---

## 6. Terms Sales May Agree
{{#if payment_terms}}
*   **Payment**: {{payment_terms}}
{{/if}}
{{#if delivery_terms}}
*   **Delivery**: {{delivery_terms}}
{{/if}}
{{#if warranty_terms}}
*   **Warranty**: {{warranty_terms}}
{{/if}}
{{#if returns_policy}}
*   **Returns**: {{returns_policy}}
{{/if}}
{{#unless payment_terms}}
_No standard terms recorded. Without them each deal is negotiated from
scratch, and margin leaks._
{{/unless}}

Anything outside these terms needs approval before it is offered.

---

## 7. Capacity Check
{{#if capacity_constraints}}
{{capacity_constraints}}

Sell within this. A signed order the operation cannot deliver costs more than
the order was worth.
{{else}}
_Capacity limits not recorded._
{{/if}}
*   **Team**: {{personnel_count}}

---

## 8. Tracking
Review weekly: pipeline value by stage, win rate, average deal size, sales
cycle length, and revenue against the targets above.
