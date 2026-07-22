# Fork Dependency Ledger

> Tracks what each forked-away-from-a-third-party app/SDK in this workspace still depends on externally,
> so future fork decisions (which apps to fork next, what to budget for) are informed by what's already
> been found — not re-discovered from scratch each time. Add an entry whenever a fork audit (like the ones
> below) surfaces a real external dependency, resolved or not.
>
> **Standing decision (2026-07)**: Frappe and ERPNext themselves will never be forked away — they're
> permanent, accepted foundational dependencies for this whole workspace. Entries below that note
> ERPNext-doctype coupling (`Customer`, `Company`, `Employee`) are **not** gaps to close — they're expected
> and fine. What's worth tracking here is coupling to *other* third-party feature apps (Frappe CRM, HRMS,
> the original `lending`/`LMS` apps themselves) that genuinely are fork/no-fork decisions.

## Polaris Lending (`corporate/polaris/frappe`, forked from `Frappenize/lending`)

Audited in `corporate/polaris/docs/erpnext-hrms-dependency-audit-report.md` (2026-07). Backend Python has
zero `lending.`/`erpnext.` imports, but real doctype-level dependency remains:

| Dependency | App | Status | Notes |
|---|---|---|---|
| `Customer` | ERPNext | **Accepted, permanent** | Applicant-identity model assumes ERPNext's `Customer` doctype throughout. Not a gap — ERPNext is a permanent dependency by standing decision. |
| `Company` | ERPNext | **Accepted, permanent** | Every forked doctype has a `company: Link -> Company` field (multi-tenant scoping). Same status as `Customer`. |
| `Employee` | ERPNext | Declared, dormant | Second `applicant_type` option, zero real usage found. Not a concern given ERPNext's permanent-dependency status. |
| `CRM Lead` | Frappe CRM | **Open — genuine fork/no-fork decision** | A third, previously undisclosed external app (not ERPNext) — live in `loan_application.py`'s KYC gate, inherited from the pre-fork original. Worth a real decision on whether to fork this small doctype's worth of KYC logic away from Frappe CRM specifically. |
| `Account` (ERPNext) | ERPNext | **Resolved** (2026-07) | Was feeding a pledged-asset-realization picker; replaced with free-text matching the field Phase 3 already made text-based. No fake account logic invented. |
| HRMS (any doctype) | HRMS | **Confirmed zero dependency** | Audited directly, nothing found. |
| Pledged-collateral/security valuation | — (never existed upstream in usable form for Polaris's model) | **Real near-term business need** (2026-07) | Not a fork gap — Polaris will offer secured lending against single physical assets (e.g. financed appliances) with repossession on default. This is genuinely simpler than upstream's formal multi-asset margined-securities system; likely worth purpose-building narrow rather than forking the original engine. Not yet scoped. |
| Term-loan interest accrual / Loan Repayment Schedule | — | **Deliberately deferred** | Business is currently focused on once-off (bullet) loans, not term loans. Fine to leave unbuilt until that changes. |
| GL/IRAC provisioning rates | ERPNext-style GL accounting | **Not applicable** | Polaris has no GL/ledger concept by design (the decision that made this fork fast). This whole category of upstream logic doesn't apply to Polaris's accounting model at all. |

**Net assessment for future lending-adjacent forks**: the doctype/business-logic fork is genuinely clean of
`lending`/`erpnext` Python coupling. The real open item is `CRM Lead` (Frappe CRM, not ERPNext) — worth a
deliberate fork/no-fork call. Secured lending (pledged-asset repossession) is a real near-term feature to
scope, not a "gap."

## LMS (`agent/lms/frappe`, forked from `Frappenize/lms`)

Per the original fork decision (`agent/lms/docs/fork-frappe-lms-backend-report.md`): **zero dependency by
design** — Frappe LMS's `hooks.py` only requires `frappe/payments`, no ERPNext, no doctype controller
imports anything outside frappe core. Confirmed clean at fork time; no further audit needed unless the
scope grows beyond the original 6 forked doctypes.

## `launch_sdk` (`core/launch/dart`) — not a third-party fork, but a real internal-dependency finding

Not forked from an external app, but worth recording here since it surfaced during the GlanceCard hoist
work (2026-07): `launch_sdk` had been silently broken since `core_sdk`'s retirement — dead path
dependencies (`core_sdk`, a `productivity_sdk` path pointing at a nonexistent directory), a reference to a
widget (`ThemeWrapper`) that no longer exists anywhere in the codebase, and its own DI class was never
exported from its barrel. All fixed. Worth checking any other SDK that hasn't been touched since the
`core_sdk` retirement for the same class of silent breakage before assuming it still works.

---
*Add new entries above as future forks/audits happen. Keep each entry evidence-cited (file:line or a
linked report), not a guess.*
