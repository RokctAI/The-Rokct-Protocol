# Per-plan SDK modules — design (2026-10-18)

Status 2026-10-24: design only, EXCEPT the composer `sdk_requires` check (section 1), which is built and merged (protocol#507, lock repin #508). Everything else is still a plan. Ray's ask: each Frappe SDK module is enabled per subscription plan; inter-dependent modules go as a group so sites don't crash; one site can sell e.g. a studio plan and a hosting plan side by side.

## What exists today (checked in code)
- **Plan → module mapping already exists, but only as data.** `Subscription Plan Module` child table (agent `subscriptions/frappe/src/control/doctype/subscription_plan_module/`, one Link → `Module Def`). Read by `get_plan_module_names()` (`agent/subscriptions/frappe/src/control/utils/plan.py`) and returned as `modules` by `get_subscription_status` / `get_my_subscription`.
- **Nothing enforces it.** The only consumer on the tenant side is a commented-out check in `core/base/frappe/src/tenant/api/remote_config.py:32` ("Optionally check for paas module"). control `tasks.py:141` says "visibility is gated by the subscription plan instead" — that gate was never built.
- **The listed names don't match SDKs.** e.g. `corporate/polaris/.../Subscription_Plan/Lending-Yearly.json` lists `rokct, Memory, Synaptic Network, lending` — Frappe Module Defs/legacy names, not SDK module names (`polaris`, `gateways`, …). All 26 plan fixtures carry a `modules` list (control 10, hosting 6, telephony 4, lms/merchants/polaris 2 each).
- **Modules are switched at compose time, per site, not per plan.** Each compose template (`The-Rokct-Protocol/core/utils/frappe/composer/*.json`) lists modules with `"enabled": true`. Every module in the template is installed for every tenant on that docker.
- **No SDK-to-SDK dependency declaration on the Frappe side.** The 43 frappe `manifest.json` files have no dependency field (only `hosting` has `dependencies`, and those are pip packages). Next.js halves have `requires` (file-level, warn-only via `check_requires()`). Dependency order is implicit in template array order and in `_comment`s.
- **Cross-module coupling is by DocType name, not imports.** e.g. `orders` calls `frappe.get_doc("Product"/"Shop"/"Wallet")` (products, merchants, wallet). Some code guards with `frappe.db.exists("DocType", …)`, most does not.

## What would crash if a module is switched off
1. **Uninstalling a module's code** (removing it from the composed app): DocType controllers, hooks, scheduler jobs, patches and fixtures referencing it break; `migrate` fails on missing controllers; other modules' `get_doc("Product")` throw. **Never do this per plan.**
2. **Hiding a module but keeping its code** (proposed): nothing crashes, because tables and code stay. Only risk is a dependent module being shown while its dependency is hidden (e.g. orders without products) → the dependent's screens error. Groups solve that.

So the rule: **compose installs code (per docker, as today); the plan only grants access.**

## Proposal

### 1. Declare dependencies per layer (decided with Ray 10-23, BUILT in protocol#507)
Each layer (Frappe backend, Dart, Next.js) declares only its own requirements in its own manifest, key `sdk_requires` (names, `_sdk` suffix optional; also allowed inside an `app_type.<persona>` block). A Dart app using tasks does not need the projects module; the backend does. Each composer (`compose_backend.py`, Dart and Next.js `sdk_composer.py`) fails early, one line per gap, if a required module is not enabled. Separate from the existing file-path `requires`, which only warns.
Hard deps only (code calls their DocTypes unguarded). Next: fill `sdk_requires` per SDK; first case is Task and Note becoming generic records in productivity, with ERP projects and CRM requiring productivity on the backend (productivity must not require them).

### 2. Feature groups = what a plan sells
New protocol file `core/utils/frappe/feature_groups.json`, derived from the manifests (composer computes the closure):

| Group | Grants | Pulls in (deps) |
|---|---|---|
| core (always on) | base, auth, users, telemetry, comms, subscriptions, gateways | — |
| studio | studio | wallet (sales docs), productivity? (verify) |
| hosting | hosting | — (rpanel side) |
| commerce | marketplace, merchants, products, orders, promotions, loyalty | wallet, delivery, zones, map |
| kitchen / booking / water | each | merchants, products |
| lending | polaris | wallet, **erp** (Polaris needs ERP; its template lacks it today, so the compose template must add erp. Audit thread, 10-24) |
| erp | erp (+ hrms, crm, projects groups below) | every tenant docker gets erp, crm and hrms; HR only with ERP |
| hrms | hrms | erp |
| crm | crm | productivity (Task/Note) |
| projects | projects | productivity; erp projects also need it |
| lms | lms, radio, replay | agent, wallet |
| crm / projects / support | productivity halves | — |
| telephony | telephony | — |

Exact dep lists come from step 1 (a script over the manifests + DocType-name grep), not guessed here.

### 2b. ERP is one module with five groups inside (audit thread, 10-24)
Granting whole SDK modules is not enough for ERP: it is a single module holding five groups, and ERP desk screens bypass the gateway, so the gateway check cannot gate them. ERP groups need their own gate, fed by the **same grant list**:
- Each ERP group maps to a plan flag derived from the plan's feature groups (no second source of truth).
- The gate hides desk menu/workspace entries and enforces doctype permissions by that flag; the gateway check stays for gateway calls.
- Same log-only-first rollout (decided): log what would be blocked before enforcing.
- The five groups (Ray decided 10-23): 1 Accounting core (always on); 2 Trading (selling, buying, stock; warehouse stock is a setting inside, off for service businesses); 3 Manufacturing (turns warehouse stock on); 4 Assets and maintenance; 5 Advanced finance. HR (hrms), CRM and Projects are separate flags/modules, not ERP groups. Integrations and telephony were dropped.
- Menu: hide what the plan or role does not allow (Ray: hide, not grey out).
- Doctype lists per group: `/mnt/project-files/api-credit-run/erp-groups-doctypes-2026-10-24.md`. Caveat from the audit thread: first pass assigned by name rules over 461 doctypes, not by Link fields; the Link-target scan must confirm it. It also lists ~78 unconfirmed drop candidates and 10 doctypes that must stay for hrms.
- Open design point: Sales/Purchase Invoice and Payment Entry sit in Accounting core but link to Customer, Supplier and Item, so those masters must be always-on shared masters, not gated by the Trading flag.

### 3. Plans point at groups, not Module Defs
Replace the `Subscription Plan Module.module` Link → `Module Def` with Link → feature group name (or add a sibling `feature_group` field and keep `module` for back-compat while consumers move). Fix all 26 fixtures to name groups. `get_plan_module_names()` keeps returning a `modules` list (tenant agent code depends on the key), now the expanded SDK module list.

### 4. Enforcement on the site (one place)
- **Gateway**: the single `rokct.platform.api` dispatcher looks up which SDK owns `cmd` (from the manifest key) and refuses with a friendly error if that module isn't in the caller's active grants. One check covers Flutter, Next.js and workflows (fits the one-API rule).
- **Next.js / Flutter**: hide nav/pages for modules not granted (from the same `modules` list in `get_my_subscription`).
- **Scheduler**: module jobs skip tenants/companies without the grant.
- Grants are **per company subscription**, so one site (e.g. control) can hold a company on "Studio" and another on "Hosting" side by side — exactly Ray's case.

### 5. Safe enable / disable
- **Enable**: grant group + its closure; run that module's per-tenant setup (fixtures/seed) idempotently on first grant.
- **Disable / downgrade**: revoke access only; data and code stay (re-subscribe restores everything). Before revoking, compute what other granted groups still need it: a dep shared by another active group is kept.
- Never remove a module from the composed app because of a plan.

### 6. Plan knows when a module is missing from the site (Ray 10-18)
Existing plan modules are legacy (written for our own code before the ERP fork), so they are rewritten, not reused. A plan's group can name a module that the site's compose template did not install. Then:
- On site start/migrate, and on subscribe, the site compares the plan's expanded module list with its installed modules (`frappe.get_installed_apps` + composed module registry).
- Missing modules are **reported, never crashed on**: `get_my_subscription` returns `missing_modules: [...]`, telemetry logs it for admins, and the UI shows the feature as "not available on this site" with a friendly line.
- Control refuses to sell a plan on a storefront whose site lacks one of its modules (plan listing filters by what that site has installed).

### 7. Studio + hosting plan (Ray 10-18)
Hosting runs on **rokctapp** (a control hub); the hosting frontend only points at it. So studio needs to run on that control hub too (the `control` persona gap stays the blocker). Rename the hosting plan family to cover both, e.g. "Web & Design", with tiers:
- **Hosting**: hosting group only.
- **Studio**: studio group only.
- **Hosting + Studio**: both groups.
The tiers differ only in which groups they grant, so this is the first real test of per-plan modules.

## Rollout (contract first)
1. Contract: `sdk_requires` manifest field + `feature_groups.json` schema + gateway refusal shape.
2. Script: derive deps from manifests/DocType refs; fill `sdk_requires` across SDKs.
3. Composer validation (fail on missing hard dep).
4. Plans → groups; fix 26 fixtures (backward compatible `modules` key).
5. Gateway check (start in log-only mode, then enforce).
6. UI hiding in base SDK nav (Next.js + Dart).

## Decisions for Ray
1. ~~Hard enforcement at the gateway, or UI-hide only?~~ **Decided (Ray 2026-10-18): gateway check, log-only first, then block.** Still a plan; no build yet.
2. Grants per company subscription (recommended) or per whole site?
3. Studio needs a `control` persona to sell on the control site next to hosting (same blocker as the hosting plan).

## Plan tiers, docker placement and resources (Ray approved 10-25; numbers are PROPOSALS)
Rule: one database service per docker stack. Free, Basic, Pro and Team share a stack; Ultra and Hosting Enterprise get their own stack. In a shared stack higher tiers get more: weighted CPU/memory shares, guaranteed minimum and hard ceiling both rise with the tier, and idle capacity is free burst. Metered items (AI calls, outbound messages) get hard plan caps with no burst.

| Tier | Placement | Share weight | Guaranteed min (CPU / RAM) | Hard ceiling (CPU / RAM) |
|---|---|---|---|---|
| Free | shared | 1 | 0.05 / 128 MB | 0.25 / 512 MB |
| Basic | shared | 2 | 0.10 / 256 MB | 0.50 / 768 MB |
| Pro | shared | 4 | 0.25 / 512 MB | 1.0 / 1.5 GB |
| Team | shared | 8 | 0.50 / 1 GB | 2.0 / 3 GB |
| Ultra | own stack | n/a | sized per stack | per stack |
| Hosting Enterprise | own stack | n/a | sized per stack | per stack |

Other product plans (LMS, PaaS, Telephony, Hosting Basic/Pro, Lending) are shared, weighted like Basic/Pro by price. Needs: plan fields for placement, share weight and ceiling; the provisioner (control `tasks.py`) to write them as docker limits/reservations; today no such limits exist anywhere.
