# {{trading_name}} — Monthly Investor Update

> [!NOTE]
> **This update recompiles fresh from `questions.md` each time — by
> design.** Update the financial answers and log the month's milestones,
> recompile, and the Document Control block below carries the generation
> date. A stale figure here means a stale answer there, never a stale
> template.

## 1. Headline

{{#if core_value_proposition}}
{{core_value_proposition}}
{{else}}
_No value proposition recorded — answer **Core Value Proposition** in
questions.md so this update opens with what the venture does._
{{/if}}

---

## 2. The Numbers This Month

{{fin_unit_economics}}

{{#if fin_consistency}}
### Consistency checks

{{fin_consistency}}
{{/if}}

{{#if fin_projection_table}}
### Projection trajectory

{{fin_projection_table}}
{{/if}}

---

## 3. Milestones Logged

{{#if business_milestone_ledger}}
{{business_milestone_ledger}}

_From the milestone ledger in questions.md — log each win as it happens
(`startupos milestone --type business`) and it appears here at the next
compile._
{{else}}
_No milestones logged yet. Log them as they happen —
`startupos milestone --type business --name <Instance> --category "Sales"
--entry "Signed the first paying clinic."` — and this section becomes the
month-by-month record investors actually read._
{{/if}}

---

## 4. Asks & Needs

{{#if funding_requirement}}
*   **Capital**: {{funding_requirement}}
{{#if capital_allocation}}
*   **How it would be deployed**: {{capital_allocation}}
{{/if}}
{{else}}
_No open ask recorded. If there is one — capital, introductions, hires —
answer **Funding Requirement** in questions.md; an update without an ask
wastes the reader's attention._
{{/if}}
{{#if hiring_plan}}
*   **Hiring**: {{hiring_plan}}
{{/if}}

---

## 5. Deep KPIs (Level 3)

{{#if fin_cac_by_channel_table}}
### Acquisition cost by channel

{{fin_cac_by_channel_table}}

### Cohorts & retention

{{fin_cohort_analysis}}
{{else}}
_These sections unlock at depth Level 3 (diligence-grade). The Depth line in
Document Control names the exact answers still missing — typically
**CAC By Channel**, **Retention Cohorts**, **Customer Churn Rate** and their
Level 3 siblings._
{{/if}}
