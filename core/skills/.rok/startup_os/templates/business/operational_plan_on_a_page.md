# {{company_name}} — Operational Plan on a Page

## 1. What We Deliver
{{#if primary_products}}
{{primary_products}}
{{/if}}
{{#if service_levels}}

**Committed service levels**: {{service_levels}}
{{/if}}

---

## 2. How the Work Gets Done
{{#if key_processes}}
{{key_processes}}
{{else}}
_Not recorded. Answer **Key Processes** — the repeatable steps from order to
delivery. This is the section an operations hire is onboarded from._
{{/if}}

{{#if technical_architecture}}
### Systems & Infrastructure
{{technical_architecture}}
{{/if}}

{{#if hardware_or_equipment}}
### Equipment
{{hardware_or_equipment}}
{{/if}}

---

## 3. Supply
{{#if key_suppliers}}
{{key_suppliers}}

Record an alternate source for each critical input — supplier concentration is
the most common single point of failure in a small operation.
{{else}}
_No suppliers recorded._
{{/if}}
{{#if delivery_terms}}

**Delivery terms**: {{delivery_terms}}
{{/if}}

---

## 4. Capacity
{{#if capacity_constraints}}
{{capacity_constraints}}
{{else}}
_Not recorded. Answer **Capacity Constraints** — what limits output today._
{{/if}}
*   **Current team**: {{personnel_count}}

---

## 5. Quality
{{#if quality_standards}}
{{quality_standards}}
{{else}}
_No standards or certifications recorded._
{{/if}}
{{#if_jurisdiction ZA}}
{{#if quality_standards}}

Where SANS standards apply to the product or premises, keep test certificates
and inspection records in the compliance folder alongside the corporate documents.
{{/if}}
{{/if_jurisdiction}}

---

## 6. Continuity
{{#if business_continuity_strategy}}
{{business_continuity_strategy}}
{{else}}
_No continuity plan recorded._
{{/if}}
