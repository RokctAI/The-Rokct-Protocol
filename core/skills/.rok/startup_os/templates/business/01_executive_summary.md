# {{company_name}} — Executive Summary

## 1. The Venture
{{#if vision_statement}}
{{vision_statement}}
{{else}}
_Required. Answer **Vision Statement** in questions.md._
{{/if}}

{{#if mission_statement}}
{{mission_statement}}
{{/if}}

*   **Sector**: {{industry}}
*   **Base**: {{primary_base}}{{#if_feature company_registry}} ({{jurisdiction_name}}){{/if_feature}}
*   **Team**: {{personnel_count}}
{{#if establishment_date}}
*   **Trading since**: {{establishment_date}}
{{/if}}

---

## 2. The Problem
{{#if problem_statement}}
{{problem_statement}}
{{else}}
_Not recorded. Answer **Problem Statement** in questions.md — name who has the
problem and what it costs them. Every reader judges the rest of this document
against it._
{{/if}}

---

## 3. The Solution
{{#if core_value_proposition}}
{{core_value_proposition}}
{{/if}}

{{#if product_components}}
{{product_components}}
{{/if}}

{{#if unfair_advantage}}
**Why this is hard to copy**: {{unfair_advantage}}
{{/if}}

---

## 4. Market
{{#if market_size_tam}}
*   **Total addressable market**: {{market_size_tam}}
{{/if}}
{{#if market_size_sam}}
*   **Serviceable addressable market**: {{market_size_sam}}
{{/if}}
{{#if market_size_som}}
*   **Obtainable in 36 months**: {{market_size_som}}
{{/if}}
{{#if customer_segments}}
*   **Customers**: {{customer_segments}}
{{/if}}
{{#unless market_size_tam}}
_Market sizing not recorded. Answer **Market Size TAM / SAM / SOM** — an
unsized market reads as an unresearched one._
{{/unless}}

---

## 5. Business Model
{{#if revenue_streams}}
{{revenue_streams}}
{{else}}
{{#if primary_products}}
Revenue comes from: {{primary_products}}
{{/if}}
{{/if}}

{{currency_note}}

{{fin_summary}}

{{#if funding_requirement}}
### Capital Sought
{{funding_requirement}}
{{#if capital_allocation}}

**Use of funds**: {{capital_allocation}}
{{/if}}
{{/if}}

---

## 6. Traction
{{#if achievements_to_date}}
{{achievements_to_date}}
{{else}}
_No traction recorded._
{{/if}}
{{#if funding_history}}

**Raised to date**: {{funding_history}}
{{/if}}
