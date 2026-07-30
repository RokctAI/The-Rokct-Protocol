# {{company_name}} — Business Plan on a Page

## 1. Executive Summary
{{#if vision_statement}}
{{company_name}}{{#if industry}} operates in {{industry}}{{/if}}{{#if primary_base}}, based in {{primary_base}}{{/if}}. {{vision_statement}}
{{else}}
_No vision statement recorded. Answer **Vision Statement** in questions.md —
this paragraph is the first thing a lender or investor reads._
{{/if}}

{{#if core_value_proposition}}
**What we offer**: {{core_value_proposition}}
{{/if}}

{{#if board_directors}}
**Led by**: {{board_directors}}
{{/if}}

---

## 2. Business Profile

### Legal & Registration
{{#if_feature company_registry}}
*   **{{company_name_status}}**: {{company_name}}
*   **Trading Name**: {{trading_name}}
*   **{{registry_name}} Registration Number**: {{reg_number}}
*   **Registration Date**: {{reg_date}}
*   **Registered Office**: {{registered_office}}
{{#if_feature tax_clearance}}
*   **{{tax_authority}} Tax Reference**: {{tax_number}}
*   **Tax Compliance Status**: {{tax_compliance_status}}
{{/if_feature}}
{{else}}
*   **Trading Name**: {{trading_name}}
*   **Jurisdiction**: {{jurisdiction_name}}
*   _No company-registry regime is configured for this jurisdiction, so no
    registration details are asserted._
{{/if_feature}}
{{#if establishment_date}}
*   **Established**: {{establishment_date}}
{{/if}}

{{#if_feature bbee}}
### B-BBEE Status
{{#if bee_level}}
*   **Contribution Level**: {{bee_level}}
*   **Procurement Recognition**: {{bee_procurement_recognition}}
*   **Black Ownership**: {{bee_black_ownership}}
*   **Youth Owned**: {{bee_youth_owned}}
*   **Certificate Number**: {{bee_cert_number}}
*   **Valid**: {{bee_issue_date}} to {{bee_expiry_date}}
{{else}}
> [!IMPORTANT]
> **No B-BBEE certificate is on file for this venture, so no contribution level
> is claimed.** Place `BEE.pdf` in the compliance folder and recompile to have a
> verified status appear here. Do not state a level in any submission until it
> appears above.
{{/if}}
{{/if_feature}}

### Team & Ownership
*   **Headcount**: {{personnel_count}}
*   **Board**: {{board_directors}}
*   **Shareholding**: {{shareholder_distribution}}

### Commercial Anchors
*   **Products / Services**: {{primary_products}}
*   **Customer Segments**: {{customer_segments}}
*   **Key Suppliers**: {{key_suppliers}}
*   **Growth Strategy**: {{growth_strategy}}
{{#if unfair_advantage}}
*   **Unfair Advantage**: {{unfair_advantage}}
{{/if}}
{{#if key_competitors}}
*   **Competitors**: {{key_competitors}}
{{/if}}

---

## 3. Financial Outlook

{{currency_note}}

{{fin_summary}}

{{#if funding_requirement}}
**Capital requirement**: {{funding_requirement}}
{{/if}}

---

## 4. Risks & Continuity
{{#if key_operational_risks}}
{{key_operational_risks}}
{{else}}
_No operational risks recorded. Every plan reviewed by a lender is expected to
name its top risks and their mitigations — answer **Key Operational Risks**._
{{/if}}

{{#if business_continuity_strategy}}
**Continuity plan**: {{business_continuity_strategy}}
{{/if}}

---

## 5. Next 12 Months
*   Close the unanswered fields listed under **Completion Gaps** below.
{{#if_feature company_registry}}
*   Keep registry filings current with {{registry_name}}.
{{/if_feature}}
{{#if_feature tax_clearance}}
*   Maintain a valid {{tax_authority}} tax compliance status.
{{/if_feature}}
{{#if_feature bbee}}
*   Keep the B-BBEE verification current; an expired certificate cannot be used
    in a tender or supplier submission.
{{/if_feature}}
*   Review projections against actuals each quarter and recompile this plan.
