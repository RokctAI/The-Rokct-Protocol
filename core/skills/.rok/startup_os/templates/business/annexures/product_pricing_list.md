# {{company_name}} — Price List

{{currency_note}}
{{#if establishment_date}}
Issued by {{company_name}}.
{{/if}}

---

## 1. Products & Services
{{#if primary_products}}
{{primary_products}}
{{/if}}

{{#if product_components}}
### Components
{{product_components}}
{{/if}}

---

## 2. Pricing
{{#if pricing_tiers}}
{{pricing_tiers}}
{{else}}
_Not recorded. Answer **Pricing Tiers** in questions.md — one line per product
or tier, with the price and what is included._
{{/if}}

{{#if_feature vat}}
> [!NOTE]
> State clearly on every quote whether prices include or exclude VAT. Ambiguity
> here is the most common cause of invoice disputes.
{{/if_feature}}

---

## 3. Margin Position
{{#if gross_margin_target}}
**Target gross margin**: {{gross_margin_target}}
{{/if}}
{{#if cost_structure}}

**Cost basis**: {{cost_structure}}
{{/if}}
{{#unless gross_margin_target}}
_No margin target recorded. Answer **Gross Margin Target** — a price list
without a known margin is a guess._
{{/unless}}

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
{{#if returns_policy}}
*   **Returns**: {{returns_policy}}
{{/if}}

Full terms of sale apply — see `sales_terms_and_conditions.md`.

---

## 5. Validity
Prices are valid until superseded. Review at least quarterly against input
costs{{#if key_suppliers}}, particularly from {{key_suppliers}}{{/if}}.
