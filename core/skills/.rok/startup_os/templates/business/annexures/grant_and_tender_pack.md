# {{company_name}} — Grant & Tender Application Pack

> [!IMPORTANT]
> Every registration and compliance value below carries the suite's
> evidence discipline: a value appears only when a certificate on file (or
> an explicit operator override) supports it. A field reading _Pending_ must
> be resolved **before** submission — a misstated compliance status in a
> tender is disqualifying at best.

## 1. Entity & Registration Block

{{#if_feature company_registry}}

| Field | Value |
| :--- | :--- |
| **{{company_name_status}}** | {{company_name}} |
| **Trading name** | {{trading_name}} |
| **{{registry_name}} registration number** | {{reg_number}} |
| **Registration date** | {{reg_date}} |
| **Registered office** | {{registered_office}} |
| **Postal address** | {{postal_address}} |

{{else}}
_No company-registry regime is configured for {{jurisdiction_name}}; attach
the local proof of legal existence the funder specifies._

{{/if_feature}}
{{#if_feature tax_clearance}}

### Tax standing

| Field | Value |
| :--- | :--- |
| **{{tax_authority}} tax reference** | {{tax_number}} |
| **Tax compliance PIN** | {{tax_pin}} |
| **PIN valid** | {{tax_pin_issue_date}} to {{tax_pin_expiry_date}} |
| **Compliance status** | {{tax_compliance_status}} |

{{/if_feature}}
{{#if_feature bbee}}
### B-BBEE status

{{#if bee_level}}

| Measure | Status |
| :--- | :--- |
| **Contribution level** | {{bee_level}} |
| **Procurement recognition** | {{bee_procurement_recognition}} |
| **Black ownership** | {{bee_black_ownership}} |
| **Certificate number** | {{bee_cert_number}} |
| **Valid until** | {{bee_expiry_date}} |

Verified from the certificate on file — check the expiry in the compliance
log before every submission.
{{else}}
> [!IMPORTANT]
> **No B-BBEE certificate is on file, so no contribution level is claimed.**
> Place `BEE.pdf` in the compliance folder and recompile before completing
> any tender's B-BBEE schedule. Stating a level without the certificate is
> fronting exposure, not paperwork.
{{/if}}
{{/if_feature}}

---

## 2. Company Profile Summary

{{#if core_value_proposition}}
{{core_value_proposition}}
{{else}}
_Answer **Core Value Proposition** in questions.md — funders read this line
first._
{{/if}}

{{#if primary_products}}
*   **Products and services**: {{primary_products}}
{{/if}}
{{#if industry}}
*   **Industry**: {{industry}}
{{/if}}
{{#if primary_base}}
*   **Base of operations**: {{primary_base}}
{{/if}}
{{#if personnel_count}}
*   **Headcount**: {{personnel_count}}
{{/if}}
{{#if quality_standards}}
*   **Standards and certifications**: {{quality_standards}}
{{/if}}

---

## 3. Track Record & References

{{#if achievements_to_date}}
{{achievements_to_date}}
{{else}}
_No track record recorded. Answer **Achievements To Date** in questions.md —
delivered contracts, grants, pilots and awards are what an adjudicator
scores._
{{/if}}

{{#if reference_contacts}}
### Contactable references

{{reference_contacts}}

_From **Reference Contacts** — confirm each person has agreed to be named
before every submission._
{{else}}
_No references recorded. Answer **Reference Contacts** — one per line:
organisation, contact person, role, phone or email. Most tenders score
references; an empty schedule scores zero._
{{/if}}

---

## 4. Key Personnel

{{#if executive_team}}
{{executive_team}}
{{else}}
_Not recorded. Answer **Executive Team** in questions.md — one line per
person with the role they own. Attach CVs and certified qualifications as
the funder requires._
{{/if}}

---

## 5. Returnables Checklist

The generic set most grant and tender packs require. The compiled suite
covers the first group; the rest are source documents to collect:

*   Entity registration block — section 1 of this pack{{#if_feature company_registry}} (backed by the {{registry_name}} certificate on file, or _Pending_ until it is){{/if_feature}}
{{#if_feature tax_clearance}}
*   Tax clearance / compliance PIN — current, unexpired (see the compliance log's expiry warnings)
{{/if_feature}}
{{#if_feature bbee}}
*   B-BBEE certificate or sworn affidavit — current, unexpired
{{/if_feature}}
*   Company profile — the Business Profile document in this suite
*   Pricing schedule — from the Price List annexure, restated on the funder's own forms
*   Banking confirmation letter — from the bank; not generated here
*   Signed declaration-of-interest and bid forms — from the tender pack itself
*   Financial statements or management accounts — as specified by the funder

_Check the specific bid document's returnables against this list — every
tender adds its own forms, and a missing returnable is an automatic
disqualification._
