# {{full_name}} — Life Lean Canvas

## 1. The Life Lean Grid Layout

Each cell holds one concept, drawn from your own answers. An italic cell is a
prompt, not a fact — answer its question in questions.md and it fills in.

| **Core Bottlenecks** | **Key Interventions** | **High-Level Purpose** | **Unfair Advantages** | **Focus Areas** |
| :--- | :--- | :--- | :--- | :--- |
| {{#if key_bottlenecks}}{{key_bottlenecks}}{{else}}_Answer **Key Bottlenecks**_{{/if}} | {{#if focus_blocks}}{{focus_blocks}}{{else}}_Answer **Focus Blocks**_{{/if}} | {{#if life_purpose}}{{life_purpose}}{{else}}_Answer **Life Purpose**_{{/if}} | {{#if skill_focus}}{{skill_focus}}{{else}}_Answer **Skill Focus**_{{/if}} | {{#if wellness_focus}}{{wellness_focus}}{{else}}_Answer **Wellness Focus**_{{/if}} |

| Key Habits / Metrics | Daily Routines |
| :--- | :--- |
| {{#if health_metrics}}{{health_metrics}}{{else}}_Answer **Health Metrics** — what you track decides what improves_{{/if}} | {{#if daily_rhythm}}{{daily_rhythm}}{{else}}_Answer **Daily Rhythm** — the loop that carries every intervention_{{/if}} |

| Sleep & Recovery | Legacy Harvest |
| :--- | :--- |
| {{#if sleep_target}}{{sleep_target}}{{else}}_Answer **Sleep Target** — recovery is the base layer_{{/if}} | {{#if legacy_vision}}{{legacy_vision}}{{else}}_Answer **Legacy Vision** — what the discipline is for_{{/if}} |

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
_This canvas is still empty. Answer **Key Bottlenecks** and **Focus Blocks**
in questions.md to begin filling it._
{{/unless}}
{{/unless}}
