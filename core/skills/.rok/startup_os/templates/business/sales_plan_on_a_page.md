# {{company_name}} — Sales Plan on a Page

## 1. What We Sell
{{#if primary_products}}
{{primary_products}}
{{/if}}
{{#if pricing_tiers}}

### Pricing
{{pricing_tiers}}
{{/if}}
{{currency_note}}

---

## 2. Who We Sell To
{{#if customer_segment_primary}}
{{customer_segment_primary}}
{{else}}
{{customer_segments}}
{{/if}}

---

## 3. How We Sell
{{#if sales_process}}
{{sales_process}}
{{else}}
_Not recorded. Answer **Sales Process** — the steps from first contact to
signature, and who owns each._
{{/if}}

{{#if acquisition_channels}}
### Where Leads Come From
{{acquisition_channels}}
{{/if}}

---

## 4. Commercial Terms
{{#if payment_terms}}
*   **Payment**: {{payment_terms}}
{{/if}}
{{#if delivery_terms}}
*   **Delivery**: {{delivery_terms}}
{{/if}}
{{#if warranty_terms}}
*   **Warranty**: {{warranty_terms}}
{{/if}}
{{#unless payment_terms}}
_No commercial terms recorded. Answer **Payment Terms**, **Delivery Terms** and
**Warranty Terms** — a sales conversation stalls without them._
{{/unless}}

---

## 5. Targets
{{fin_summary}}

Track weekly: pipeline value, win rate, average deal size, sales cycle length.
