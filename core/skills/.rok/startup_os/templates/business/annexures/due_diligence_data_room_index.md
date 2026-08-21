# {{company_name}} — Due-Diligence Data-Room Index

> [!NOTE]
> A readiness index, not a claim of readiness. Certificate rows are read
> from the compliance evidence on disk with the same fail-closed rule as
> every other document: _Document-backed_ means a certificate was parsed,
> _Operator-asserted_ means `compliance_overrides.json` says so, and
> _Unverified_ means no status is claimed anywhere in this suite.

## 1. Corporate & Compliance Evidence

{{#if dd_evidence_table}}
{{dd_evidence_table}}
{{else}}
_No jurisdiction declared, so no compliance regime can be evaluated. Answer
**Jurisdiction** in questions.md with an ISO country code to activate this
section._
{{/if}}

---

## 2. Financial

| Item | Where it stands in this suite |
| :--- | :--- |
| Projections & unit economics | Compiled into the Financial Model chapter from the answered financial questions |
| Historical turnover | {{#if historical_turnover_2025}}Stated in **Historical Turnover** answers — bring the annual financial statements that back them{{else}}_Not recorded — answer the **Historical Turnover** questions, then bring the annual financial statements that back them_{{/if}} |
| Cash position & runway | {{#if cash_on_hand}}Stated in **Cash On Hand** — bring the bank statements that back it{{else}}_Not recorded — answer **Cash On Hand** and **Monthly Operating Costs**_{{/if}} |
| Funding history & instruments | {{#if funding_history}}Summarised in the Cap Table & Funding History annexure — bring the signed instruments{{else}}_Not recorded — answer **Funding History**_{{/if}} |

_A data room needs the source documents, not only this suite's summaries:
annual financial statements, management accounts, bank statements and the
signed investment instruments._

---

## 3. Ownership & Governance

| Item | Where it stands |
| :--- | :--- |
| Shareholder split | {{#if shareholder_distribution}}Stated in **Shareholder Distribution**; the Cap Table annexure checks the sum{{else}}_Not recorded — answer **Shareholder Distribution**_{{/if}} |
| Cap-table detail (classes, pool, notes) | {{#if cap_table}}Stated in **Cap Table** — bring the share register and instruments{{else}}_Not recorded — answer **Cap Table** (Level 3 diligence answer)_{{/if}} |
| Directors | {{#if board_directors}}Stated in **Board Directors** — bring the registry's director records{{else}}_Not recorded — answer **Board Directors**_{{/if}} |
| Executive team | {{#if executive_team}}Stated in **Executive Team**{{else}}_Not recorded — answer **Executive Team**_{{/if}} |

---

## 4. Intellectual Property

{{#if intellectual_property}}
*   **On record** (from **Intellectual Property**): {{intellectual_property}}
*   _Bring the registration certificates, assignments and licence agreements
    that back each item._
{{else}}
_Nothing recorded. Answer **Intellectual Property** in questions.md — patents,
trademarks, software, methods, licences. A diligence pass will also ask who
owns work done by contractors; have assignment agreements ready._
{{/if}}

---

## 5. Contracts & Commercial Terms

| Item | Where it stands |
| :--- | :--- |
| Standard terms of sale | Compiled in the Sales Terms & Conditions annexure{{#if payment_terms}} from the answered **Payment Terms** and related questions{{else}} — _its inputs (**Payment Terms**, **Delivery Terms**, **Warranty Terms**) are not yet answered_{{/if}} |
| Pricing | {{#if pricing_tiers}}Stated in **Pricing Tiers** and compiled into the Price List annexure{{else}}_Not recorded — answer **Pricing Tiers**_{{/if}} |
| Key supplier arrangements | {{#if key_suppliers}}Named in **Key Suppliers** — bring the signed agreements{{else}}_Not recorded — answer **Key Suppliers**_{{/if}} |

_Customer contracts, supplier contracts and leases live outside this suite —
collect the signed originals into the data room folder by counterparty._

---

## 6. People

| Item | Where it stands |
| :--- | :--- |
| Headcount | {{#if personnel_count}}Stated in **Personnel Count**{{else}}_Not recorded — answer **Personnel Count**_{{/if}} |
| Key-person dependencies | {{#if key_person_dependencies}}Stated in **Key Person Dependencies**; succession is covered in the Succession Plan annexure{{else}}_Not recorded — answer **Key Person Dependencies**_{{/if}} |
| Hiring plan | {{#if hiring_plan}}Stated in **Hiring Plan**{{else}}_Not recorded — answer **Hiring Plan** (Level 3 diligence answer)_{{/if}} |

_Employment contracts, incentive agreements and policies are source documents
for the data room itself._
