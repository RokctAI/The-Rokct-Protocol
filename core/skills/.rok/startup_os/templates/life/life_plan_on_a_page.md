# {{full_name}} — Life Plan on a Page

## 1. Core Purpose & Values

{{#if life_purpose}}
> **Core Purpose**: {{life_purpose}}
{{else}}
_No purpose recorded. Answer **Life Purpose** in questions.md — every other
plan in this suite hangs off it._
{{/if}}

{{#if personal_values}}
{{personal_values}}
{{else}}
_No values recorded. Answer **Personal Values** — the values you refuse to
trade away, one per line._
{{/if}}

---

## 2. Dynamic Personal Profile & Metrics

*   **Full Name**: {{full_name}}
*   **Primary Base**: {{primary_base}}
{{#if current_role}}
*   **Current Role**: {{current_role}}
{{/if}}
{{#if key_relationships}}
*   **Key Relationships**: {{key_relationships}}
{{/if}}
{{#if dependants}}
*   **Dependants**: {{dependants}}
{{/if}}
{{#if wellness_focus}}
*   **Current Wellness Focus**: {{wellness_focus}}
{{/if}}
{{#if business_ownership}}
*   **Venture & Career Integration**: {{business_ownership}}
{{/if}}

---

## 3. The Ideal Daily Rhythm (The OS Loop)

{{#if daily_rhythm}}
{{daily_rhythm}}
{{else}}

_No daily rhythm recorded yet. Answer **Daily Rhythm** in questions.md and this
section fills with your own schedule. The four-cycle shape below is a starting
suggestion, not a description of how you currently spend your day:_

| Cycle | Purpose |
| :--- | :--- |
| **Sowing** | Deep work: the hardest, highest-leverage task of the day, done first. |
| **Harvest** | Operations: meetings, collaboration, client and business execution. |
| **Stewardship** | Upkeep: admin, training, food, errands. |
| **Relational** | People and wind-down: family, reading, sleep preparation. |

{{/if}}

---

## 4. Focus for the Year Ahead

One line per plan; each links to its own page in this suite.

{{#if wellness_focus}}
*   **Health**: {{wellness_focus}}
{{else}}
*   **Health**: _answer **Wellness Focus** to set the year's health focus._
{{/if}}
{{#if skill_focus}}
*   **Craft**: {{skill_focus}}
{{else}}
*   **Craft**: _answer **Skill Focus** — the capability you are deliberately
    building._
{{/if}}
{{#if legacy_vision}}
*   **Legacy**: {{legacy_vision}}
{{else}}
*   **Legacy**: _answer **Legacy Vision** — the long-term stewardship goal._
{{/if}}
{{#if daily_rhythm}}
*   **Rhythm**: protected by the daily loop above.
{{/if}}
