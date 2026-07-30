# {{company_name}} — People Plan on a Page

## 1. The Team Today
*   **Headcount**: {{personnel_count}}
{{#if executive_team}}

### Leadership
{{executive_team}}
{{else}}
{{#if board_directors}}
*   **Directors**: {{board_directors}}
{{/if}}
{{/if}}
{{#if shareholder_distribution}}
*   **Shareholding**: {{shareholder_distribution}}
{{/if}}

---

## 2. What We Are Building
{{#if hr_vision}}
{{hr_vision}}
{{else}}
_Not recorded. Answer **HR Vision** — the kind of team being built and how._
{{/if}}

{{#if organisational_culture}}
### Culture
{{organisational_culture}}
{{/if}}

---

## 3. Hiring
{{#if hiring_plan}}
{{hiring_plan}}
{{else}}
_No hiring plan recorded. Answer **Hiring Plan** — roles, timing and cost._
{{/if}}

---

## 4. Key-Person Risk
{{#if key_person_dependencies}}
{{key_person_dependencies}}
{{else}}
_Not assessed. Answer **Key Person Dependencies** — in a small team this is
usually the single largest operational risk, and a lender will ask about it._
{{/if}}

{{#if succession_arrangements}}
### Cover & Succession
{{succession_arrangements}}
{{/if}}

---

## 5. Employment Compliance
{{#if_feature company_registry}}
*   Employment contracts, payroll registration and statutory returns must be
    current in {{jurisdiction_name}}.
{{/if_feature}}
{{#if privacy_law}}
*   Employee personal data is subject to {{privacy_law}}.
{{/if}}
{{#if_feature bbee}}
{{#if bee_level}}
*   Skills development and employment equity contribute to the B-BBEE scorecard;
    keep training records aligned with the certificate on file.
{{/if}}
{{/if_feature}}
