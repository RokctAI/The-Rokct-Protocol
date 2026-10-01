# {{company_name}} — Financial Plan on a Page

{{currency_note}}

## 1. Basis of Preparation
These figures are management projections drawn from `questions.md`. They are
not audited, not reviewed, and carry no assurance. Any figure not stated below
has not been provided.

{{#if industry}}
*   **Sector**: {{industry}}
{{/if}}
{{#if establishment_date}}
*   **Trading since**: {{establishment_date}}
{{/if}}
*   **Headcount**: {{personnel_count}}

---

## 2. Three-Year Revenue Projections

{{fin_grid_rev}}

{{fin_summary}}

---

## 3. Unit Economics
Complete these for the plan to be reviewable by a lender or investor. Each is a
question in `questions.md` or a calculation from your own accounts:

| Metric | Value | Notes |
| :--- | :--- | :--- |
| Average revenue per customer | *to be supplied* | Per month or per order |
| Gross margin % | *to be supplied* | By product or service line |
| Customer acquisition cost | *to be supplied* | Fully loaded, including salaries |
| CAC payback period | *to be supplied* | Months to recover acquisition cost |
| Monthly fixed cost base | *to be supplied* | Rent, salaries, subscriptions |
| Break-even revenue | *to be supplied* | Fixed costs ÷ gross margin % |
| Cash runway | *to be supplied* | Months at current burn |

---

## 4. Funding
{{#if funding_requirement}}
{{funding_requirement}}
{{else}}
*No capital requirement recorded. Answer **Funding Requirement** in questions.md
if this venture is raising.*
{{/if}}

---

## 5. Compliance Costs to Budget
{{#if_feature company_registry}}
*   **{{registry_name}}** annual returns and filing fees
{{/if_feature}}
{{#if_feature tax_clearance}}
*   **{{tax_authority}}** provisional tax and compliance status renewals
{{/if_feature}}
{{#if_feature vat}}
*   VAT registration and periodic returns, once the threshold is crossed
{{/if_feature}}
{{#if_feature bbee}}
*   B-BBEE verification agency fees (annual)
{{/if_feature}}
{{#if_feature trademarks}}
*   Trademark filing and renewal fees
{{/if_feature}}
{{#if privacy_law}}
*   {{privacy_law}} compliance: data-protection controls and record-keeping
{{/if}}
{{#unless jurisdiction_code}}
*   *Jurisdiction not declared, so no statutory cost lines are listed. Add a
    **Jurisdiction** answer to questions.md.*
{{/unless}}

---

## 6. Cost Control
1.  **Fixed vs variable**: keep delivery and fulfilment costs variable where the
    volume is uncertain.
2.  **Infrastructure**: scale capacity with demand rather than provisioning for
    peak.
3.  **Supplier concentration**: {{key_suppliers}} — single-supplier dependency is
    a financial risk as much as an operational one.
{{#if key_operational_risks}}
4.  **Known risks**: {{key_operational_risks}}
{{/if}}
