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
| `rokctapp.json` | `crm` (erp SDK joins when the erpnext fork lands) |
| `deliveryplatform.json` | `merchants`, `products`, `orders`, `promotions`, `loyalty`, `booking`, `kitchen`, `delivery`, `map`, `zones`, `weather`, `hardware`, `builder` |
| `polaris.json` | `polaris`, `crm` (polaris `loan_application` reads CRM Lead.kyc_status) |
| `control.json` | `tender` (hub/control docker; composes an app named `control`, not `rcore`; tender is control-only per owner ruling 2026-08-18; the `control` module itself joins when the control repo's SDK-ification lands) |

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
