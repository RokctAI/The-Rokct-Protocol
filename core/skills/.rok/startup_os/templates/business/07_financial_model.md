# {{company_name}} — Financial Model

{{currency_note}}

> [!NOTE]
> These are management projections compiled from `questions.md`. They are
> unaudited and unreviewed. Any figure not stated below has not been supplied.

## 1. Revenue Streams
{{#if revenue_streams}}
{{revenue_streams}}
{{else}}
_Not recorded. Answer **Revenue Streams** — every way the venture earns, with
the rate or fee for each._
{{/if}}

{{#if pricing_tiers}}
### Pricing
{{pricing_tiers}}
{{/if}}

---

## 2. Three-Year Projections

{{#if fin_projection_table}}
{{fin_projection_table}}
{{else}}
{{fin_grid_rev}}

_No numeric projection could be read from the answers. State a figure in
**Projected Year 1**, **Projected Year 2** and **Projected Year 3**
(e.g. "R 4,800,000 revenue") and the compiler will build the projection
table, growth rates and cross-checks from them._
{{/if}}

### As stated in questions.md
{{fin_summary}}

---

## 3. Cost Structure
{{#if cost_structure}}
{{cost_structure}}
{{else}}
_Not recorded. Answer **Cost Structure** — the main fixed and variable lines._
{{/if}}

{{#if gross_margin_target}}
**Gross margin target**: {{gross_margin_target}}
{{/if}}
{{#if break_even_point}}
**Break-even**: {{break_even_point}}
{{/if}}

---

## 4. Unit Economics

Every derived figure below names the answers it was computed from; anything
not derivable says which question would unlock it.

{{fin_unit_economics}}

---

## 5. Consistency Checks

{{#if fin_consistency}}
{{fin_consistency}}
{{else}}
_No cross-checks are possible yet. Give numeric answers to
**Projected Year 1**, **Average Revenue Per Customer** and
**Customer Count Year 1** in questions.md and the compiler will reconcile
them against each other here._
{{/if}}

---

## 6. Funding
{{#if funding_requirement}}
**Sought**: {{funding_requirement}}
{{/if}}
{{#if capital_allocation}}

**Use of funds**: {{capital_allocation}}
{{/if}}
{{#if funding_history}}

**Raised to date**: {{funding_history}}
{{/if}}
{{#unless funding_requirement}}
_No capital requirement recorded._
{{/unless}}

---

## 7. Statutory Cost Lines
{{#if_feature company_registry}}
*   {{registry_name}} annual returns and filing fees
{{/if_feature}}
{{#if_feature tax_clearance}}
*   {{tax_authority}} provisional tax and compliance renewals
{{/if_feature}}
{{#if_feature vat}}
*   VAT registration and periodic returns once the threshold is crossed
{{/if_feature}}
{{#if_feature bbee}}
*   B-BBEE verification agency fees (annual)
{{/if_feature}}
{{#if_feature trademarks}}
*   Trademark filing and renewal fees
{{/if_feature}}
{{#if privacy_law}}
*   {{privacy_law}} compliance controls and record-keeping
{{/if}}
