# {{company_name}} — Delivery Architecture

## 1. How the Offering Is Built and Delivered
{{#if technical_architecture}}
{{technical_architecture}}
{{else}}
_Not recorded. Answer **Technical Architecture** in questions.md. For a
software venture this is stack and infrastructure; for a manufacturer it is
plant, equipment and process flow; for a service business it is systems and
people._
{{/if}}

{{#if product_components}}
### Components
{{product_components}}
{{/if}}

{{#if hardware_or_equipment}}
### Hardware & Equipment
{{hardware_or_equipment}}
{{/if}}

---

## 2. Operating Processes
{{#if key_processes}}
{{key_processes}}
{{else}}
_Core processes not recorded. Answer **Key Processes** — order to delivery._
{{/if}}

{{#if capacity_constraints}}
### Capacity Limits
{{capacity_constraints}}
{{/if}}

---

## 3. Resilience
{{#if business_continuity_strategy}}
{{business_continuity_strategy}}
{{else}}
_No continuity plan recorded. Answer **Business Continuity Strategy** — what
happens when the main dependency fails._
{{/if}}

{{#if service_levels}}
### Service Commitments
{{service_levels}}
{{/if}}

---

## 4. Standards & Data
{{#if quality_standards}}
{{quality_standards}}
{{/if}}
{{#if privacy_law}}

**Data protection**: personal data handled by this venture is subject to
{{privacy_law}}. Retention, access control and breach procedures must be
documented to match.
{{/if}}
{{#if standards_body}}

**National standards body**: {{standards_body}}
{{/if}}
