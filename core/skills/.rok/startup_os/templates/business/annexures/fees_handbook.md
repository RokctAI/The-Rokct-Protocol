# {{company_name}} — Fees Handbook

{{currency_note}}
{{#if establishment_date}}
Issued by {{company_name}}.
{{/if}}

> [!NOTE]
> This handbook is the customer-facing summary of what {{company_name}}
> charges and how billing works. It supplements — and never replaces — the
> full terms of sale in `sales_terms_and_conditions.md`.

---

## 1. About {{company_name}}
{{#if core_value_proposition}}
{{core_value_proposition}}
{{else}}
_Not recorded. Answer **Core Value Proposition** in questions.md — one line on
what the customer gets and why it is worth paying for._
{{/if}}
{{#if mission_statement}}

{{mission_statement}}
{{/if}}
{{#if customer_segments}}

**Who this handbook is for**: {{customer_segments}}
{{/if}}

---

## 2. Fee Schedule
{{#if primary_products}}
{{primary_products}}
{{/if}}

{{#if pricing_tiers}}
{{pricing_tiers}}
{{else}}
_Not recorded. Answer **Pricing Tiers** in questions.md — one line per product
or tier, with the price and what is included. Include any discounted rates
(annual prepayment, bundles, promotions) and the conditions attached to each._
{{/if}}

{{#if_feature vat}}
> [!NOTE]
> State clearly against every fee whether it includes or excludes VAT.
> Ambiguity here is the most common cause of billing disputes.
{{/if_feature}}

---

## 3. Payment Options & Billing
{{#if payment_terms}}
{{payment_terms}}

Where an account falls into arrears, the payment terms above and the full
terms of sale govern what happens next; unless agreed otherwise,
{{company_name}} may suspend delivery or access until the account is settled.
{{else}}
_Not recorded. Answer **Payment Terms** in questions.md — accepted payment
methods, billing frequency, whether fees are billed in advance or in arrears,
and what happens on late or failed payment._
{{/if}}

---

## 4. Delivery & Access
{{#if delivery_terms}}
{{delivery_terms}}
{{else}}
_Not recorded. Answer **Delivery Terms** in questions.md — how and when the
customer receives the product or gains access, who bears any delivery cost,
and any preconditions (for example, payment received)._
{{/if}}
{{#if service_levels}}

**Service levels**: {{service_levels}}
{{/if}}

---

## 5. Cancellation & Refunds
{{#if returns_policy}}
{{returns_policy}}
{{else}}
_Not recorded. Answer **Returns Policy** in questions.md — notice period for
cancellation, when a refund applies, how it is calculated, and how long it
takes to process._
{{/if}}
{{#if warranty_terms}}

**Warranty**: {{warranty_terms}}
{{/if}}

---

## 6. Disputes
{{#if dispute_resolution}}
{{dispute_resolution}}
{{else}}
_Not recorded. Answer **Dispute Resolution** in questions.md — the process a
customer follows to query a fee or invoice, and the governing law. Absent
agreement, the default rules of {{jurisdiction_name}} apply._
{{/if}}

---

## 7. Legal & Contact
{{#if_feature company_registry}}
This handbook is issued by **{{company_name}}**{{#if reg_number}}, registration number {{reg_number}}{{/if}}{{#if registered_office}}, of {{registered_office}}{{/if}}.
{{else}}
This handbook is issued by **{{trading_name}}**.
{{/if_feature}}
{{#if head_office}}

**Head office**: {{head_office}}
{{/if}}

Full terms of sale apply — see `sales_terms_and_conditions.md`. Where this
handbook and the terms of sale differ, the terms of sale prevail. Internal
price points and margins are maintained in `product_pricing_list.md`.
