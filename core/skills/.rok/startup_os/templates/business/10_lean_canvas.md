# {{company_name}} — Lean Canvas

## 1. Lean Grid

| Problem | Solution | Unique Value Proposition | Unfair Advantage | Customer Segments |
| :--- | :--- | :--- | :--- | :--- |
| {{#if key_operational_risks}}{{key_operational_risks}}{{else}}_Not yet defined_{{/if}} | {{primary_products}} | {{core_value_proposition}} | {{unfair_advantage}} | {{customer_segments}} |

| Key Metrics | Channels |
| :--- | :--- |
| Revenue, gross margin, customer acquisition cost, retention | {{growth_strategy}} |

| Cost Structure | Revenue Streams |
| :--- | :--- |
| Personnel, suppliers, infrastructure, compliance | {{primary_products}} |

---

## 2. Lean Block Breakdown

### A. The Problem
{{#if key_operational_risks}}
{{key_operational_risks}}
{{else}}
_The problem this venture solves has not been recorded. Answer
**Key Operational Risks** and **Core Value Proposition** in questions.md._
{{/if}}

### B. The Solution
{{#if primary_products}}
{{primary_products}}
{{/if}}
{{#if business_continuity_strategy}}

**Continuity**: {{business_continuity_strategy}}
{{/if}}

### C. Unique Value Proposition
{{#if core_value_proposition}}
{{core_value_proposition}}
{{else}}
_Required field not yet answered._
{{/if}}

### D. Unfair Advantage
{{#if unfair_advantage}}
{{unfair_advantage}}
{{else}}
_No defensible advantage recorded yet. Investors will ask — answer
**Unfair Advantage** in questions.md._
{{/if}}

{{#if_feature bbee}}
{{#if bee_level}}
*   **Preferential procurement standing**: {{bee_level}}. Verified from the
    B-BBEE certificate on file; may support access to enterprise and supplier
    development programmes.
{{/if}}
{{/if_feature}}

{{#if_feature trademarks}}
{{#if trademarks_details}}
*   **Registered intellectual property**:
{{trademarks_details}}
{{/if}}
{{/if_feature}}

### E. Channels
{{#if growth_strategy}}
{{growth_strategy}}
{{else}}
_Customer acquisition loop not yet recorded._
{{/if}}

### F. Customer Segments
{{customer_segments}}
{{#if key_competitors}}

**Competitive set**: {{key_competitors}}
{{/if}}

### G. Key Metrics
Track these from first revenue:

*   **Revenue** — {{currency_note}}
*   **Gross margin** by product or service line
*   **Customer acquisition cost** and payback period
*   **Retention / churn** over a rolling 90 days
{{#if funding_requirement}}
*   **Runway** against the stated capital requirement: {{funding_requirement}}
{{/if}}
