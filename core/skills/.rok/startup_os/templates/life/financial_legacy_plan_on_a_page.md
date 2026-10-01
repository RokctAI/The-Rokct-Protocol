# {{full_name}} — Financial Legacy Plan on a Page

## 1. Stewardship Philosophy

{{#if financial_philosophy}}
{{financial_philosophy}}
{{else}}
*No philosophy recorded. Answer **Financial Philosophy** in questions.md — the
principles that govern how you earn, spend and invest, one per line. Without
them this plan is arithmetic with no compass.*
{{/if}}

---

## 2. Computed Financial Position

{{life_financial_summary}}

*Every figure above is computed from your own answers; nothing is estimated
for you. A line that reads "Pending" unlocks when its question is answered
with an amount.*

---

## 3. Foundations on Record

{{#if assets}}
*   **Assets**: {{assets}}
{{/if}}
{{#if liabilities}}
*   **Liabilities**: {{liabilities}}
{{/if}}
{{#if life_cover_policies}}
*   **Life Cover Policies**: {{life_cover_policies}}
{{/if}}
{{#if monthly_income}}
*   **Monthly Income (after tax)**: {{monthly_income}}
{{/if}}
{{#if monthly_savings}}
*   **Monthly Savings**: {{monthly_savings}}
{{/if}}
{{#if beneficiaries}}
*   **Beneficiaries**: {{beneficiaries}}
{{else}}
*   **Beneficiaries**: *not recorded — answer **Beneficiaries**; cover with no
    named beneficiary is settled by default rules, not by you.*
{{/if}}
{{#if key_relationships}}
*   **Trusted Circle**: {{key_relationships}}
{{/if}}
{{#if dependants}}
*   **Dependants Provided For**: {{dependants}}
{{/if}}

---

## 4. Passing It On

*   **Will**: the draft in this suite assembles your bequests and residue
    wishes — see the linked Last Will & Testament. It has no legal force
    until formally executed.
{{#if executor}}
*   **Executor**: {{executor}}{{#if alternate_executor}} (alternate: {{alternate_executor}}){{/if}}
{{else}}
*   **Executor**: *not recorded — answer **Executor** in questions.md.*
{{/if}}
{{#if legacy_vision}}
*   **Legacy Vision**: {{legacy_vision}}
{{/if}}
