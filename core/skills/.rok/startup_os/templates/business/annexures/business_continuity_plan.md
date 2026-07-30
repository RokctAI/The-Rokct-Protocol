# {{company_name}} — Business Continuity Plan

## 1. Scope
This plan covers how {{company_name}} keeps operating, and recovers, when a
core dependency fails.

{{#if key_processes}}
**Processes that must survive**: {{key_processes}}
{{/if}}
{{#if service_levels}}

**Commitments to hold**: {{service_levels}}
{{/if}}

---

## 2. Continuity Strategy
{{#if business_continuity_strategy}}
{{business_continuity_strategy}}
{{else}}
_Not recorded. Answer **Business Continuity Strategy** in questions.md — this
document is a required annexure for most tenders and insurance applications._
{{/if}}

---

## 3. Identified Threats
{{#if key_operational_risks}}
{{key_operational_risks}}
{{else}}
_No risks recorded._
{{/if}}

{{#if capacity_constraints}}
**Capacity exposure**: {{capacity_constraints}}
{{/if}}

---

## 4. Dependencies

### Suppliers
{{#if key_suppliers}}
{{key_suppliers}}

For each: record the alternate source, the lead time to switch, and the cost
difference. An untested alternate is not an alternate.
{{else}}
_No suppliers recorded._
{{/if}}

### People
{{#if key_person_dependencies}}
{{key_person_dependencies}}
{{/if}}
{{#if succession_arrangements}}

**Cover arrangements**: {{succession_arrangements}}
{{/if}}

### Systems & Equipment
{{#if technical_architecture}}
{{technical_architecture}}
{{/if}}
{{#if hardware_or_equipment}}

{{hardware_or_equipment}}
{{/if}}

---

## 5. Recovery Targets
Set and record these — an untested target is an assumption:

| Measure | Target |
| :--- | :--- |
| Recovery time objective (how long until service resumes) | _to be set_ |
| Recovery point objective (how much data or work may be lost) | _to be set_ |
| Backup frequency and location | _to be set_ |
| Last restore test | _to be recorded_ |

---

## 6. Data & Records
{{#if privacy_law}}
Personal data held by {{company_name}} is subject to {{privacy_law}}. Backups
and recovery copies carry the same obligations as production data: access
control, retention limits and breach notification.
{{else}}
Record where business records are held, how they are backed up, and who may
access them.
{{/if}}
