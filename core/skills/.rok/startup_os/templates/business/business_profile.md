# {{company_name}} — Business Profile

## 1. Corporate Registry

{{#if_feature company_registry}}

| Parameter | Detail |
| :--- | :--- |
| **{{company_name_status}}** | {{company_name}} |
| **Trading Name** | {{trading_name}} |
| **{{registry_name}} Registration Number** | {{reg_number}} |
| **Registration Date** | {{reg_date}} |
| **Registered Office** | {{registered_office}} |
| **Postal Address** | {{postal_address}} |
| **{{tax_authority}} Tax Reference** | {{tax_number}} |
| **Tax Compliance Status** | {{tax_compliance_status}} |
| **Head Office** | {{head_office}} |
| **Other Locations** | {{secondary_locations}} |
| **Established** | {{establishment_date}} |
| **Industry** | {{industry}} |
| **Target Sectors** | {{target_sectors}} |

*No company-registry regime is configured for {{jurisdiction_name}}, so no
registration details are asserted in this profile.*

{{/if_feature}}


{{#if_feature bbee}}
### B-BBEE Contribution Status
{{#if bee_level}}

| Measure | Status |
| :--- | :--- |
| **Contribution Level** | {{bee_level}} |
| **Procurement Recognition** | {{bee_procurement_recognition}} |
| **Black Ownership** | {{bee_black_ownership}} |
| **Youth Owned** | {{bee_youth_owned}} |
| **Disabled Owned** | {{bee_disabled_owned}} |
| **Rural Owned** | {{bee_rural_owned}} |
| **Certificate Number** | {{bee_cert_number}} |
| **Valid** | {{bee_issue_date}} to {{bee_expiry_date}} |

Verified from the certificate on file. Confirm the expiry date in the
compliance log before submitting this profile anywhere.
{{else}}
> [!IMPORTANT]
> **No B-BBEE certificate is on file, so no contribution level is claimed.**
> Place `BEE.pdf` in the compliance folder and recompile. Until a verified
> level appears here, do not state one in a tender, supplier application or
> enterprise-development submission.
{{/if}}
{{/if_feature}}

{{#if_feature trademarks}}
### Registered Marks
{{trademarks_details}}
{{/if_feature}}

{{#if intellectual_property}}
### Intellectual Property
{{intellectual_property}}
{{/if}}

---

## 2. What the Business Does

{{#if core_value_proposition}}
{{core_value_proposition}}
{{else}}
*Required field not yet answered — see **Core Value Proposition** in questions.md.*
{{/if}}

{{#if primary_products}}
**Products and services**: {{primary_products}}
{{/if}}

{{#if customer_segments}}
**Customers served**: {{customer_segments}}
{{/if}}

{{#if technical_architecture}}
**How it is delivered**: {{technical_architecture}}
{{/if}}

---

## 3. Leadership & Ownership

{{#if executive_team}}
{{executive_team}}
{{else}}
{{#if board_directors}}
*   **Directors**: {{board_directors}}
{{/if}}
{{/if}}
{{#if shareholder_distribution}}
*   **Shareholding**: {{shareholder_distribution}}
{{/if}}
{{#if cap_table}}
*   **Cap table**: {{cap_table}}
{{/if}}
*   **Headcount**: {{personnel_count}}
{{#if key_person_dependencies}}
*   **Key-person dependencies**: {{key_person_dependencies}}
{{/if}}

---

## 4. Track Record

{{#if achievements_to_date}}
{{achievements_to_date}}
{{else}}
*No achievements recorded. Grants, pilots, awards and signed contracts belong
here — this is the section a funder reads first. Answer **Achievements To
Date** in questions.md.*
{{/if}}

{{#if funding_history}}
**Capital raised to date**: {{funding_history}}
{{/if}}

---

## 5. Operating Basis

{{#if key_suppliers}}
*   **Key suppliers**: {{key_suppliers}}
{{/if}}
{{#if quality_standards}}
*   **Standards and certifications**: {{quality_standards}}
{{/if}}
{{#if service_levels}}
*   **Service commitments**: {{service_levels}}
{{/if}}
{{#if business_continuity_strategy}}
*   **Continuity**: {{business_continuity_strategy}}
{{/if}}
{{#if privacy_law}}
*   **Data protection**: operations are subject to {{privacy_law}}.
{{/if}}
