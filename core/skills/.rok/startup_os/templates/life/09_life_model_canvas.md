# {{full_name}} — Life Model Canvas

## 1. The Personal Life Model Canvas Grid

Each cell holds one concept, drawn from your own answers. An italic cell is a
prompt, not a fact — answer its question in questions.md and it fills in.

| **Key Partners** | **Key Activities** | **Core Value Proposition** | **Accountability** | **Life Recipients** |
| :--- | :--- | :--- | :--- | :--- |
| {{#if key_relationships}}{{key_relationships}}{{else}}*Answer **Key Relationships***{{/if}} | {{#if skill_focus}}{{skill_focus}}{{else}}*Answer **Skill Focus***{{/if}} | {{#if life_purpose}}{{life_purpose}}{{else}}*Answer **Life Purpose***{{/if}} | {{#if accountability_partner}}{{accountability_partner}}{{else}}*Answer **Accountability Partner***{{/if}} | {{#if dependants}}{{dependants}}{{else}}*Answer **Dependants***{{/if}} |

| Key Resources | Channels |
| :--- | :--- |
| {{#if wellness_focus}}{{wellness_focus}}{{else}}*Answer **Wellness Focus** — the body is the first resource*{{/if}} | {{#if current_role}}{{current_role}}{{else}}*Answer **Current Role** — where your work meets the world*{{/if}} |

| Relational & Energetic Costs | Legacy Harvest |
| :--- | :--- |
| {{#if key_bottlenecks}}{{key_bottlenecks}}{{else}}*Answer **Key Bottlenecks** — what your current life costs you in energy and attention*{{/if}} | {{#if legacy_vision}}{{legacy_vision}}{{else}}*Answer **Legacy Vision** — what all of this is meant to yield*{{/if}} |

---

## 2. In-Depth Life Block Breakdown

{{#if key_relationships}}
### A. Key Partners

{{key_relationships}}
{{/if}}
{{#if skill_focus}}

### B. Key Activities

Deliberate capability building: {{skill_focus}}
{{/if}}
{{#if business_ownership}}

### C. Venture & Career Integration

{{business_ownership}}
{{/if}}
{{#if life_purpose}}

### D. Core Value Proposition

{{life_purpose}}
{{/if}}
{{#if legacy_vision}}

### E. Legacy Harvest

{{legacy_vision}}
{{/if}}
{{#unless key_relationships}}
{{#unless skill_focus}}
{{#unless life_purpose}}
*This canvas is still empty. Answer **Key Relationships**, **Skill Focus** and
**Life Purpose** in questions.md to begin filling it.*
{{/unless}}
{{/unless}}
{{/unless}}
