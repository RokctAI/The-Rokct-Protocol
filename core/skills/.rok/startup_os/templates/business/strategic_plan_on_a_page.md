# {{company_name}} — Strategic Plan on a Page

## 1. Where We Are Going
{{#if vision_statement}}
**Vision**: {{vision_statement}}
{{/if}}
{{#if mission_statement}}

**Mission**: {{mission_statement}}
{{/if}}
{{#unless vision_statement}}
*No vision recorded. Answer **Vision Statement** in questions.md.*
{{/unless}}

---

## 2. Objectives This Year
{{#if strategic_objectives}}
{{strategic_objectives}}
{{else}}
*Not recorded. Answer **Strategic Objectives** — three to five, each one you
would be willing to be measured against.*
{{/if}}

---

## 3. Milestones

### Next 12 Months
{{#if milestones_12_month}}
{{milestones_12_month}}
{{else}}
*Not recorded.*
{{/if}}

### Next 36 Months
{{#if milestones_36_month}}
{{milestones_36_month}}
{{else}}
*Not recorded.*
{{/if}}

---

## 4. How We Win
{{#if unfair_advantage}}
{{unfair_advantage}}
{{/if}}
{{#if growth_strategy}}

**Growth strategy**: {{growth_strategy}}
{{/if}}
{{#if competitive_positioning}}

**Against the field**: {{competitive_positioning}}
{{/if}}

---

## 5. What Could Stop Us
{{#if key_operational_risks}}
{{key_operational_risks}}
{{else}}
*No risks recorded.*
{{/if}}

---

## 6. Resources Required
{{#if funding_requirement}}
*   **Capital**: {{funding_requirement}}
{{/if}}
{{#if hiring_plan}}
*   **People**: {{hiring_plan}}
{{/if}}
*   **Current team**: {{personnel_count}}
{{#if capacity_constraints}}
*   **Constraint to relieve**: {{capacity_constraints}}
{{/if}}
