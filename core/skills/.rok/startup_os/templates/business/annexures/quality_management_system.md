# {{company_name}} — Quality Management System

## 1. Scope
{{#if primary_products}}
This system covers the delivery of: {{primary_products}}
{{/if}}
{{#if industry}}

Sector: {{industry}}.
{{/if}}

---

## 2. Standards Applied
{{#if quality_standards}}
{{quality_standards}}
{{else}}
_Not recorded. Answer **Quality Standards** in questions.md — the standards,
certifications or inspections that apply. Most tenders and many customers ask
for this document by name._
{{/if}}
{{#if standards_body}}

**National standards body**: {{standards_body}}
{{/if}}

---

## 3. Controlled Processes
{{#if key_processes}}
{{key_processes}}
{{else}}
_Not recorded. Answer **Key Processes** — quality control needs a defined
process to control._
{{/if}}

{{#if capacity_constraints}}
**Known capacity limits**: {{capacity_constraints}}
{{/if}}

---

## 4. Inputs & Suppliers
{{#if key_suppliers}}
{{key_suppliers}}

For each supplier, record: specification agreed, incoming inspection method,
and what happens when a batch fails.
{{else}}
_No suppliers recorded._
{{/if}}

---

## 5. Service Commitments
{{#if service_levels}}
{{service_levels}}
{{else}}
_No service levels recorded._
{{/if}}

---

## 6. Records to Maintain
Keep these current — they are what an auditor or customer asks to see:

| Record | Where held | Review frequency |
| :--- | :--- | :--- |
| Incoming inspection results | _to be recorded_ | Per delivery |
| Non-conformance and corrective actions | _to be recorded_ | Per incident |
| Customer complaints and resolution | _to be recorded_ | Monthly |
| Calibration and maintenance logs | _to be recorded_ | Per schedule |
| Staff training records | _to be recorded_ | Annually |
| Certificates and licences | Compliance folder | Before expiry |



{{#if_jurisdiction ZA}}
Where SANS standards or a Certificate of Acceptability apply to the product or
premises, keep laboratory reports and health inspection records in the
compliance folder alongside the corporate documents.
{{/if_jurisdiction}}

---

## 7. Continuous Improvement
{{#if key_operational_risks}}
Known weaknesses being worked on: {{key_operational_risks}}
{{/if}}

Review this system at least annually, and after any customer complaint that
reaches a second occurrence.
