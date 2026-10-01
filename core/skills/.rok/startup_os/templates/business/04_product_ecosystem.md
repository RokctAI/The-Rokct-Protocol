# {{company_name}} — Products & Services

## 1. What We Offer
{{#if primary_products}}
{{primary_products}}
{{else}}
*Required. Answer **Primary Products** in questions.md.*
{{/if}}

{{#if core_value_proposition}}
{{core_value_proposition}}
{{/if}}

---

## 2. Components
{{#if product_components}}
{{product_components}}
{{else}}
*Not broken down yet. Answer **Product Components** — name each part of the
offering and what it does.*
{{/if}}

{{#if hardware_or_equipment}}
### Hardware & Equipment
{{hardware_or_equipment}}
{{/if}}

---

## 3. Roadmap
{{#if product_roadmap}}
{{product_roadmap}}
{{else}}
*No roadmap recorded. Answer **Product Roadmap** — what ships over the next
12-24 months.*
{{/if}}

---

## 4. Pricing
{{#if pricing_tiers}}
{{pricing_tiers}}
{{else}}
*Pricing not recorded. Answer **Pricing Tiers** in questions.md.*
{{/if}}

{{currency_note}}

---

## 5. Protection
{{#if intellectual_property}}
{{intellectual_property}}
{{/if}}
{{#if_feature trademarks}}

**Registered marks**:
{{trademarks_details}}
{{/if_feature}}
{{#unless intellectual_property}}
*No intellectual property recorded.*
{{/unless}}
