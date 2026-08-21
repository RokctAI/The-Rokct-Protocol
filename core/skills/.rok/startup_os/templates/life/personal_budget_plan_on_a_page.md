# {{full_name}} — Personal Budget Plan on a Page

{{#if financial_philosophy}}
> **Operating principle**: _{{financial_philosophy}}_
{{/if}}

## 1. Monthly Cash Flow

{{budget_cash_flow_table}}

_Every figure above is computed from your own answers — **Monthly Income**,
**Monthly Expenses**, **Monthly Savings**, **Liquid Savings** — and each row
names its basis. A row that reads "Pending" unlocks when its question is
answered with an amount. Nothing is estimated for you._

{{#if budget_flags}}

### Checks

{{budget_flags}}
{{/if}}

---

## 2. Inputs on Record

{{#if monthly_income}}
*   **Monthly Income (after tax)**: {{monthly_income}}
{{/if}}
{{#if monthly_expenses}}
*   **Monthly Expenses**: {{monthly_expenses}}
{{/if}}
{{#if monthly_savings}}
*   **Monthly Savings**: {{monthly_savings}}
{{/if}}
{{#if liquid_savings}}
*   **Liquid Savings (emergency fund)**: {{liquid_savings}}
{{/if}}

---

## 3. Position Behind the Budget

The wider balance sheet — total assets, liabilities, net worth and life
cover — is computed in the Financial Legacy Plan on a Page from the same
answers, so the two pages can never disagree.

{{#if assets}}
*   **Assets**: {{assets}}
{{/if}}
{{#if liabilities}}
*   **Liabilities**: {{liabilities}}
{{/if}}
