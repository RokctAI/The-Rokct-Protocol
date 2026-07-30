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

{{fin_grid_rev}}

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
Complete these for the model to be reviewable by a lender or investor:

| Metric | Value |
| :--- | :--- |
| Gross margin % | {{gross_margin_target}} |
| Break-even revenue | {{break_even_point}} |
| Average revenue per customer | _to be supplied_ |
| Customer acquisition cost | _to be supplied_ |
| CAC payback period | _to be supplied_ |
| Monthly fixed cost base | _to be supplied_ |
| Cash runway | _to be supplied_ |

---

## 5. Funding
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

## 6. Statutory Cost Lines
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
