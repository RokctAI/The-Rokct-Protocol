# {{company_name}} — Project Plan on a Page

## 1. Projects In Flight
{{#if key_projects}}
{{key_projects}}
{{else}}
_Not recorded. Answer **Key Projects** — name, owner and due date for each.
A project without a named owner and a date is a wish._
{{/if}}

---

## 2. What They Serve
{{#if strategic_objectives}}
{{strategic_objectives}}
{{/if}}
{{#if milestones_12_month}}

### 12-Month Milestones
{{milestones_12_month}}
{{/if}}

---

## 3. Product Delivery
{{#if product_roadmap}}
{{product_roadmap}}
{{else}}
_No product roadmap recorded._
{{/if}}

---

## 4. Resourcing
*   **Team available**: {{personnel_count}}
{{#if hiring_plan}}
*   **Hiring against these projects**: {{hiring_plan}}
{{/if}}
{{#if capacity_constraints}}
*   **Known constraint**: {{capacity_constraints}}
{{/if}}
{{#if funding_requirement}}
*   **Funding dependency**: {{funding_requirement}}
{{/if}}

---

## 5. Risks to Delivery
{{#if key_operational_risks}}
{{key_operational_risks}}
{{else}}
_No delivery risks recorded._
{{/if}}
{{#if key_person_dependencies}}

**Key-person exposure**: {{key_person_dependencies}}
{{/if}}
