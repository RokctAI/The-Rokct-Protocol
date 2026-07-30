# {{company_name}} — Standard Terms of Sale

> [!IMPORTANT]
> This is a working draft assembled from `questions.md`, not a legal document.
> Terms of sale are enforceable contract language and vary by jurisdiction and
> sector. Have a qualified professional in {{jurisdiction_name}} review this
> before it is issued to a customer.

---

## 1. Parties
{{#if_feature company_registry}}
These terms apply to all sales by **{{company_name}}**{{#if reg_number}}, registration number {{reg_number}}{{/if}}{{#if registered_office}}, of {{registered_office}}{{/if}} ("the Supplier").
{{else}}
These terms apply to all sales by **{{trading_name}}** ("the Supplier").
{{/if_feature}}

---

## 2. Goods and Services Supplied
{{#if primary_products}}
{{primary_products}}
{{else}}
_Not recorded. Answer **Primary Products** in questions.md._
{{/if}}

---

## 3. Price
{{#if pricing_tiers}}
{{pricing_tiers}}
{{else}}
_Pricing not recorded. Answer **Pricing Tiers**._
{{/if}}

{{currency_note}}
{{#if_feature vat}}

Prices are stated exclusive of VAT unless expressly marked otherwise. VAT is
charged at the prevailing rate where the Supplier is registered.
{{/if_feature}}

---

## 4. Payment
{{#if payment_terms}}
{{payment_terms}}
{{else}}
_Not recorded. Answer **Payment Terms** — deposit, credit period and what
happens on late payment. This clause decides your working capital._
{{/if}}

---

## 5. Delivery
{{#if delivery_terms}}
{{delivery_terms}}
{{else}}
_Not recorded. Answer **Delivery Terms** — lead time, who bears delivery cost,
and the point at which risk passes to the customer._
{{/if}}

---

## 6. Warranty
{{#if warranty_terms}}
{{warranty_terms}}
{{else}}
_Not recorded. Answer **Warranty Terms** — what is warranted, for how long, and
what remedy applies._
{{/if}}

{{#if_jurisdiction ZA}}
Nothing in these terms limits any right the customer has under the Consumer
Protection Act 68 of 2008 where that Act applies to the transaction.
{{/if_jurisdiction}}

---

## 7. Returns
{{#if returns_policy}}
{{returns_policy}}
{{else}}
_Not recorded. Answer **Returns Policy**._
{{/if}}

---

## 8. Service Levels
{{#if service_levels}}
{{service_levels}}
{{else}}
_No service commitments recorded._
{{/if}}

---

## 9. Data Protection
{{#if privacy_law}}
The Supplier processes customer personal data in accordance with
{{privacy_law}}. Data is used to fulfil the order and meet legal obligations,
and is retained only as long as those purposes require.
{{else}}
Record how customer personal data is collected, used, retained and deleted.
{{/if}}

---

## 10. Disputes
{{#if dispute_resolution}}
{{dispute_resolution}}
{{else}}
_Not recorded. Answer **Dispute Resolution** — the process and the governing
law. Absent agreement, the default rules of {{jurisdiction_name}} apply._
{{/if}}
