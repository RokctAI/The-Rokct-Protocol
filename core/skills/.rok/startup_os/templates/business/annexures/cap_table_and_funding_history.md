# {{company_name}} — Cap Table & Funding History

> [!NOTE]
> Every row below renders an owner-supplied answer or a figure computed from
> one — nothing is normalised, estimated or invented. The registered share
> register and signed instruments remain the legal record; this annexure is
> the working summary a diligence pass starts from.

## 1. Ownership

{{#if cap_table_ownership_table}}
{{cap_table_ownership_table}}

{{cap_table_ownership_check}}
{{else}}
_No percentage split recorded. Answer **Shareholder Distribution** in
questions.md — one holder per line, with the stated percentage
(e.g. `Ray Sinyage: 60%`). The compiler then sums the stated shares and
flags an allocation that does not reach 100%._
{{/if}}

---

## 2. Instruments, Classes & Pool

{{#if cap_table}}
{{cap_table}}

_Stated in **Cap Table** — share classes, option pool, outstanding notes or
SAFEs, and special investor rights, as supplied by the owner. Verify against
the signed instruments before relying on it._
{{else}}
_Not recorded. Answer **Cap Table** in questions.md — beyond the percentage
split: share classes, option pool size, outstanding notes or SAFEs, and any
special investor rights. This is a Level 3 (diligence-grade) answer; an
investor's counsel will ask for exactly this._
{{/if}}

---

## 3. Funding History

{{#if funding_history}}
{{funding_history}}

_Stated in **Funding History** — for each round or grant, record the
instrument, the date, the amount and the counterparty so this section reads
as a round-by-round ledger._
{{else}}
_Nothing recorded. Answer **Funding History** in questions.md — what has been
raised or granted so far, from whom, one round or grant per line with the
instrument, date and amount. If nothing has been raised, say so explicitly:
"bootstrapped, no external capital" is a real answer._
{{/if}}

---

## 4. The Ask Against This Table

{{#if funding_requirement}}
*   **Current funding requirement**: {{funding_requirement}}
{{#if capital_allocation}}
*   **Planned allocation**: {{capital_allocation}}
{{/if}}
{{else}}
_No open ask recorded. If capital is being sought, answer
**Funding Requirement** — the amount and what it buys — so a reader can see
what this cap table looks like after the round._
{{/if}}
