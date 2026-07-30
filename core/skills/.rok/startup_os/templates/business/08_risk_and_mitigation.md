# {{company_name}} — Risk & Mitigation

## 1. Operational Risks
{{#if key_operational_risks}}
{{key_operational_risks}}
{{else}}
_Not recorded. Answer **Key Operational Risks** — name each risk and its
mitigation. A plan with no risk section reads as one that has not been
stress-tested._
{{/if}}

{{#if capacity_constraints}}
### Capacity
{{capacity_constraints}}
{{/if}}

---

## 2. Continuity
{{#if business_continuity_strategy}}
{{business_continuity_strategy}}
{{else}}
_No continuity plan recorded._
{{/if}}

---

## 3. Concentration Risk
{{#if key_suppliers}}
**Supplier dependency**: {{key_suppliers}}

Single-supplier dependency is a financial risk as much as an operational one.
Record an alternate source for every critical input.
{{/if}}

{{#if key_person_dependencies}}
**Key-person dependency**: {{key_person_dependencies}}
{{#if succession_arrangements}}

**Cover**: {{succession_arrangements}}
{{/if}}
{{/if}}

---

## 4. Regulatory & Compliance Risk
{{#if_feature company_registry}}
*   **Corporate standing**: {{registry_name}} filings must stay current. Lapsed
    filings can invalidate contracts and disqualify tender submissions.
{{/if_feature}}
{{#if_feature tax_clearance}}
*   **Tax compliance**: an expired {{tax_authority}} compliance status blocks
    most tender and supplier applications. Current status: {{tax_compliance_status}}
{{/if_feature}}
{{#if_feature bbee}}
{{#if bee_level}}
*   **B-BBEE**: certificate on file, valid to {{bee_expiry_date}}. An expired
    certificate cannot be used in a submission.
{{else}}
*   **B-BBEE**: no certificate on file. No level may be stated anywhere until
    one is verified — misstating B-BBEE status is an offence, not a technicality.
{{/if}}
{{/if_feature}}
{{#if privacy_law}}
*   **Data protection**: {{privacy_law}} exposure on personal data held. A
    breach carries both penalty and reputational cost.
{{/if}}
{{#if quality_standards}}
*   **Standards**: {{quality_standards}}
{{/if}}

See `compliance_log.md` for current certificate status and expiry warnings.
