# {{company_name}} — Marketing Plan on a Page

## 1. Position
{{#if brand_positioning}}
{{brand_positioning}}
{{else}}
{{#if core_value_proposition}}
{{core_value_proposition}}
{{else}}
*Not recorded. Answer **Brand Positioning**.*
{{/if}}
{{/if}}

---

## 2. Audience
{{#if customer_segment_primary}}
**Primary**: {{customer_segment_primary}}
{{else}}
**Segments**: {{customer_segments}}
{{/if}}
{{#if customer_segment_secondary}}

**Secondary**: {{customer_segment_secondary}}
{{/if}}

---

## 3. Channels
{{#if acquisition_channels}}
{{acquisition_channels}}
{{else}}
{{#if growth_strategy}}
{{growth_strategy}}
{{else}}
*Not recorded.*
{{/if}}
{{/if}}

---

## 4. Message
{{#if core_value_proposition}}
{{core_value_proposition}}
{{/if}}
{{#if problem_statement}}

**The problem we lead with**: {{problem_statement}}
{{/if}}

---

## 5. Budget & Targets
{{#if marketing_budget}}
**Budget**: {{marketing_budget}}
{{else}}
*No marketing budget recorded.*
{{/if}}

Measure monthly:

| Metric | Target |
| :--- | :--- |
| Cost per lead | *set a target* |
| Cost per acquired customer | *set a target* |
| Lead-to-customer conversion | *set a target* |
| Revenue attributed by channel | *set a target* |
