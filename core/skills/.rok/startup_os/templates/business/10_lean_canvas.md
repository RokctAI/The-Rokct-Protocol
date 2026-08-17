# {{company_name}} — Lean Canvas

## 1. Lean Grid

| Problem | Solution | Unique Value Proposition | Unfair Advantage | Customer Segments |
| :--- | :--- | :--- | :--- | :--- |
| {{#if problem_statement}}{{problem_statement}}{{else}}_Not yet defined — answer **Problem Statement**_{{/if}} | {{primary_products}} | {{core_value_proposition}} | {{unfair_advantage}} | {{customer_segments}} |

| Key Metrics | Channels |
| :--- | :--- |
| Revenue, gross margin, customer acquisition cost, retention | {{#if sales_channels}}{{sales_channels}}{{else}}{{#if acquisition_channels}}{{acquisition_channels}}{{else}}{{growth_strategy}}{{/if}}{{/if}} |

| Cost Structure | Revenue Streams |
| :--- | :--- |
| Personnel, suppliers, infrastructure, compliance | {{#if revenue_streams}}{{revenue_streams}}{{else}}{{primary_products}}{{/if}} |

---

## 2. Lean Block Breakdown

### A. The Problem
{{#if problem_statement}}
{{problem_statement}}
{{else}}
_The customer problem this venture solves has not been recorded. Answer
**Problem Statement** in questions.md — who has the problem, and what it
costs them today. (Internal operational risks belong in the risk register,
not here.)_
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
{{#if sales_channels}}
{{sales_channels}}
{{else}}
{{#if acquisition_channels}}
{{acquisition_channels}}
{{else}}
{{#if growth_strategy}}
No dedicated channel answer yet — showing the acquisition loop as a stand-in:
{{growth_strategy}}

_Answer **Sales Channels** in questions.md to state how the product reaches
the customer._
{{else}}
_Path to the customer not yet recorded. Answer **Sales Channels** in
questions.md._
{{/if}}
{{/if}}
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
