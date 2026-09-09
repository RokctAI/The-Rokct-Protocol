# Composer Templates (Product Registry)

The `.json` files in this folder are **templates**, not active
configuration — the frappe analog of `core/utils/flutter/composer/*.json`.
This folder is the protocol's product template registry for BOTH backend
(frappe) and Next.js shells: one template per product, whose `modules` array
is read by the frappe engine (`compose_backend.py`) and whose optional `sdks`
array is read by the Next.js composer (`core/utils/nextjs/sdk_composer.py`).
Each composer reads only its own key.

## Thin shells: `.rokct/config/app_type`

A shell repo no longer needs a hand-copied `composer.json`: committing a
one-line `.rokct/config/app_type` file naming a template here (e.g. `rcore`,
`rokctapp`) makes the composer materialize `composer.json` from the registry
template before composing — the same model the flutter side uses
(`universal-flutter-build.yml` overwrites `composer.json` from
`core/utils/flutter/composer/<app_type>.json`). The template is looked up in,
in order: `ROKCT_COMPOSER_TEMPLATES_DIR`, `ROKCT_PROTOCOL_DIR`, the protocol
checkout the composer runs from, the sibling `../The-Rokct-Protocol/`
checkout, and (only when no local registry exists at all) a data-only fetch
from this repo's `main`. A resolved template **wins over** a committed
`composer.json`.

The same one-line value doubles as the shell's role/persona marker (the
shared-namespace convention the flutter side established). A value that names
no template here is a plain role marker: the shell composes from its
committed `composer.json` exactly as before. A shell with no
`.rokct/config/app_type` file behaves byte-identically to the pre-registry
behavior.

**New product = one new template file here + a thin shell repo carrying just
the one-line `app_type` file.**

## Home SDK (`"home_sdk"` on `sdks[]` entries)

Every `sdks[]` entry carries `"home_sdk": true|false`, the same flag the flutter
templates set: exactly one entry per product template is the shell's home SDK —
it owns `app/page.tsx` and base_sdk's single-answer landing registries
(`header-menu`, `hero-form`, `plans-query`, `site-metadata`; `hero-copy` and
`page-sections` merge every contributor). The Next.js composer installs the home
SDK directly behind the kernel entries (`telemetry_sdk`, `base_sdk`), other SDKs
never write the paths its manifest installs, only the home SDK's line is injected
at a single-answer marker (another SDK's line there is skipped with a log line,
never a failure), and the resolved name is recorded as `"home_sdk"` in
`.rokct/cache/install_state.json`. `base_sdk`, `auth_sdk` and
`telemetry_sdk` are never home. Today: `supacharge.json` → `lms_sdk`,
`rokctapp.json` → `agent_sdk`, `deliveryplatform.json` → `delivery_sdk` (zones
`delivery/nextjs`, the storefront that sells the delivery platform and the door
to the tenant portal; `products_sdk`, which carried the flag provisionally, is a
portal part), `telephony.json` → none
(kernel seam only), `hosting.json` → `hosting_sdk` (hardware `hosting/nextjs`, the
storefront on the control site; no `agent_sdk`). A template without the key still composes as before: lines
append in order at a contested marker, with a warning.

## Per-product templates

One template per docker product. **Every tenant product composes an app named
`rcore`** (the tenant templates share `"name": "rcore_app"`); products differ only
by module set. The one exception is the hub: `control.json` is named
`"control_app"` and composes an app named `control` (per the owner ruling of
2026-08-20 — matching the live hub's existing app name, so no rename migration).
`rcore.json` remains the current full composition and stays authoritative until
the image build switches to the per-product targets below.

Common to all products: `base`, `auth`, `users`, `subscriptions`, `gateways`,
`telemetry`, `comms`, `wallet` (`gateways` + `wallet` replaced the retired
`pay` module — `pay/payments/frappe` no longer exists). On top of that:

| Template | Extra modules |
| --- | --- |
| `supacharge.json` | `lms`, `agent` |
| `startupos.json` | `studio`, `productivity`, `agent` |
| `telephony.json` | — (telephony module pending extraction from control) |
| `hosting.json` | — (hosting module pending extraction from rpanel; `hardware/hosting/frappe` is fixtures-only, no `manifest.json` yet) |
| `rokctapp.json` | `erp`, `hrms`, `crm` (erp+hrms pinned to the pay head carrying the fleet doctype-collision exclusion, pay#35; hrms composes only alongside erp) |
| `deliveryplatform.json` | `merchants`, `products`, `orders`, `promotions`, `loyalty`, `booking`, `kitchen`, `delivery`, `map`, `zones`, `weather`, `hardware`, `builder` |
| `polaris.json` | `polaris`, `crm` (polaris `loan_application` reads CRM Lead.kyc_status) |
| `control.json` | `tender`, `weather` (hub/control docker; composes an app named `control`, not `rcore`; tender is control-only per owner ruling 2026-08-18; weather composes its hub-side `src/control/` persona tree here — zones#54/#55; the `control` module itself joins when the control repo's SDK-ification lands) |

To build a given backend shell:

1. Commit `.rokct/config/app_type` in the shell repo containing the template
   name (e.g. `rcore`) — or, legacy path, copy the template to the shell
   repo's root as `composer.json` by hand.
2. Run the compose script from that shell's root as normal
   (`python3 .rokct/skills/.rok/frappe/scripts/compose.py`, provisioned by
   `.rokct/initiate.py`).

**A shell with no `composer.json` at its root and no template-naming
`app_type` marker cannot compose.** `compose_backend.py` exits early ("No
composer.json found") — the shell keeps whatever composed output was last
committed, silently stale.

**These templates are the canonical module list.** A change to a shell's SDK set
(adding a module, disabling one, changing a source path) belongs HERE, mirrored to the
shell repo's committed `composer.json` — the same canonical-template model the flutter
side uses. Editing only the shell repo's copy leaves the protocol's record of the app
graph wrong.

**Sibling checkout layout.** The relative `path` entries inside each template (e.g.
`../core/base/frappe`) are written assuming the file sits at the shell repo root — one
level up from the shell reaches the other sibling repos under `RokctAI/`. When a
sibling checkout is absent, the composer clones the module's `git` repo instead (a full
40-char commit `ref` is then required unless `ROKCT_ALLOW_UNPINNED_SDKS=1`).

**Scaffolding a brand-new shell.** Copy a template (adjusting `"name"`) into an empty
repo as `composer.json` and run compose — when the target app package
(`<name-without-_app>/`) does not exist, `compose_backend.py` lays down the tokenized
shell skeleton from `core/utils/frappe/templates/shell/` before composing (also
available on demand via `--scaffold`; existing files are never overwritten). See
`core/utils/frappe/templates/shell/README.md`.

There is currently no automated script that performs the copy/rename step — it's
manual, matching the flutter composer templates.
