# {{full_name}} — Life Lean Canvas

## 1. The Life Lean Grid Layout

Each cell holds one concept, drawn from your own answers. An italic cell is a
prompt, not a fact — answer its question in questions.md and it fills in.

| **Core Bottlenecks** | **Key Interventions** | **High-Level Purpose** | **Unfair Advantages** | **Focus Areas** |
| :--- | :--- | :--- | :--- | :--- |
| {{#if key_bottlenecks}}{{key_bottlenecks}}{{else}}*Answer **Key Bottlenecks***{{/if}} | {{#if focus_blocks}}{{focus_blocks}}{{else}}*Answer **Focus Blocks***{{/if}} | {{#if life_purpose}}{{life_purpose}}{{else}}*Answer **Life Purpose***{{/if}} | {{#if skill_focus}}{{skill_focus}}{{else}}*Answer **Skill Focus***{{/if}} | {{#if wellness_focus}}{{wellness_focus}}{{else}}*Answer **Wellness Focus***{{/if}} |

| Key Habits / Metrics | Daily Routines |
| :--- | :--- |
| {{#if health_metrics}}{{health_metrics}}{{else}}*Answer **Health Metrics** — what you track decides what improves*{{/if}} | {{#if daily_rhythm}}{{daily_rhythm}}{{else}}*Answer **Daily Rhythm** — the loop that carries every intervention*{{/if}} |

| Sleep & Recovery | Legacy Harvest |
| :--- | :--- |
| {{#if sleep_target}}{{sleep_target}}{{else}}*Answer **Sleep Target** — recovery is the base layer*{{/if}} | {{#if legacy_vision}}{{legacy_vision}}{{else}}*Answer **Legacy Vision** — what the discipline is for*{{/if}} |

---

## 2. In-Depth Life Lean Breakdown

{{#if key_bottlenecks}}
### A. Core Bottlenecks

{{key_bottlenecks}}
{{/if}}
{{#if focus_blocks}}

### B. Key Interventions

Protected deep-focus time: {{focus_blocks}}
{{/if}}
{{#if training_routine}}

### C. Physical Base

{{training_routine}}
{{/if}}
{{#if business_ownership}}

### D. Venture Focus

{{business_ownership}}
{{/if}}
{{#unless key_bottlenecks}}
{{#unless focus_blocks}}
*This canvas is still empty. Answer **Key Bottlenecks** and **Focus Blocks**
in questions.md to begin filling it.*
{{/unless}}
{{/unless}}
