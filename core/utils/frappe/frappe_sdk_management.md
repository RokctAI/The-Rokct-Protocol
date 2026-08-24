---
name: frappe-sdk-management
description: Standards and procedures for partitioning, manifest creation, and backend composition for modular Frappe SDKs.
---

# Frappe SDK Decoupling & Composition Standard

This skill/standard document governs modular SDK management in Frappe projects and compiling them dynamically into target app shells (e.g. PaaS).

---

## 1. Directory Structure Standards

Each decoupled SDK must live in its own repository/folder and implement the standard layout under a nested `frappe/` directory:

```text
SDKs/<sdk_name>/frappe/
├── manifest.json       # Dynamic configurations, hooks, fixtures, and dependencies
├── doctype/            # Isolated DocType folders
│   └── <doctype_name>/
└── src/                # Controller logic and APIs
    └── api/
        └── <module_name>/
```

---

## 2. Manifest Standards (`manifest.json`)

All path references in python code and hook values must be genericized using the **`{app_name}`** token placeholder. This enables the composer to dynamically resolve namespaces relative to the final target app shell.

### Template tokens

The composer recognizes exactly two tokens — only these literals are substituted (and
linted after compose); generic `{...}` braces such as Python format strings or Jinja
expressions are never touched:

| Token | Resolves to | Use it for |
|---|---|---|
| `{app_name}` | the target shell's app package name (e.g. `rcore`) | cross-module imports, dotted hook/handler paths, API alias keys |
| `{module_name}` | this SDK module's manifest `"name"` | the `"module"` key in DocType JSONs, module-scoped dotted paths |

Both tokens are substituted in `.py`, `.js`, `.html`, and `.json` files in **both** the
`src/` tree and the `doctype/` tree (doctype trees historically composed verbatim; they
now get the same substitution pass, with tokenless files still copied byte-for-byte).
Other extensions are always copied verbatim — don't put tokens in them.

DocType placement and the `"module"` key:

- **Module-root doctypes** (`doctype/<dt>/`) — the primary `<dt>.json`'s `"module"` key
  is always rewritten to the manifest `"name"` regardless of what it says, so
  `"module": "{module_name}"` is the self-documenting convention.
- **Src-nested doctypes** (`src/**/doctype/<dt>/`) — the `{module_name}` token resolves
  there too, and the composer additionally pins any src-nested primary JSON whose
  `"module"` still disagrees with the manifest name. Duplicate DocType dirs across
  modules are a hard error for module-root trees; collisions involving a src-nested
  doctype are a loud warning (escalating under `ROKCT_COMPOSE_STRICT=1`).

### Template Structure:
```json
{
  "name": "subscriptions",
  "description": "Modular backend package for subscriptions",
  "dependencies": [
    "croniter"
  ],
  "hooks": {
    "whitelisted_methods": {
      "{app_name}.api.subscription.create_subscription": "{app_name}.subscriptions.api.subscription.subscription.create_subscription"
    },
    "fixtures": [
      {
        "dt": "DocType",
        "filters": [["name", "=", "Subscription"]]
      }
    ],
    "doc_events": {
      "Item": {
        "on_update": "{app_name}.products.custom_fields.item.on_update"
      }
    }
  }
}
```

### Role-based composition (`app_type`)

Ported from the Dart composer (`core/utils/flutter/sdk_installer_base.py` /
`sdk_composer.py`) so all three composers share one design. Two pieces:

**The shell's role marker** — an optional plain one-line text file at
`.rokct/config/app_type` in the app shell's own repo (e.g. `manager`,
`customer`, `pos`), read relative to the same root as `composer.json`.
**Absence = all roles**: a tenant backend that deliberately serves every role
at once simply declares no marker and composes exactly as before. There is no
`"all"` pseudo-role.

The same one-line value ALSO doubles as the shell's composer **template
name** when it matches a registry template in `core/utils/frappe/composer/`
(the shared-namespace convention the flutter side established): the composer
then materializes `composer.json` from that template before composing, so a
product shell repo can commit just the marker file. A value matching no
template is a plain role marker as described here — see
`core/utils/frappe/composer/README.md` for the registry contract.

**The manifest's `app_type` block** — optional, keyed by persona name. Each
persona's value mirrors the manifest top level (`hooks`, `dependencies`), and
is merged in ONLY when the persona matches the shell's marker. Everything at
the manifest top level is common and always composes.

```json
{
  "name": "orders",
  "hooks": { "whitelisted_methods": { "...common...": "..." } },
  "app_type": {
    "manager": {
      "dependencies": ["some-manager-only-pip-dep"],
      "hooks": {
        "whitelisted_methods": { "{app_name}.api.manager.dashboard": "{app_name}.orders.manager.dashboard.get" },
        "scheduler_events": { "daily": ["{app_name}.orders.manager.tasks.daily_digest"] },
        "after_install": "{app_name}.orders.manager.setup.after_install",
        "commands": ["{app_name}.orders.manager.cli.commands"]
      }
    },
    "customer": { "hooks": { "...": "..." } }
  }
}
```

The matching flavor block flows through the exact same
`merge_hooks`/`merge_commands`/`merge_dependencies` machinery as a module's
top-level manifest (it appears in `hooks.py` under a
`# --- Module: <name> (<role>) ---` comment), so every hooks key those support
(`whitelisted_methods`, `doc_events`, `scheduler_events`, `fixtures`,
`auth_hooks`, `before_uninstall`, `after_install`, `on_login`, `commands`,
`doctype_js`, `doctype_list_js`, ...) can be role-scoped.

**Persona source folders** — persona-specific Python lives in sibling folders
directly under the SDK's `src/` (`src/manager/`, `src/customer/`, ...),
mirroring the Dart convention of `lib/src/<persona>/` siblings of
`lib/src/common/`. There is no literal `src/common/` folder: everything under
`src/` NOT named after a declared persona is common. During
`compose_module()`, a persona folder is skipped (never copied into the shell)
only when BOTH the folder's name is declared as an `app_type` persona in this
SDK's own manifest AND the shell's marker names a *different* declared
persona. Guardrails, matching Dart exactly: no marker, no `app_type` key in
the manifest, or a shell role the SDK doesn't declare all mean nothing is
skipped and nothing extra is merged — the composed output is byte-identical
to a role-less compose.

---

## 3. Relocation Workflow

When extraction/partitioning is required:
1. Move the DocType directory from the monolithic path or core SDK to `SDKs/<sdk_name>/frappe/doctype/<doctype_name>`.
2. Move the controller API folder/files to `SDKs/<sdk_name>/frappe/src/api/<module_name>/`.
3. Construct the `manifest.json` file inside the new SDK.
4. Clean up the source manifest (e.g. `core` manifest or `merchants` manifest) to remove the relocated whitelisted methods, events, and fixtures to prevent compilation conflicts.

---

## 4. Backend Composition Workflow

The composer pipeline (`compose_backend.py`) is responsible for compiling SDK packages into the active app shell:
1. **Modules Resolution**: Resolves target paths based on `composer.json`.
2. **Scaffold (when needed)**: If the target app package is missing entirely (a brand-new shell repo), or compose is invoked with `--scaffold`, lays down the tokenized shell skeleton (see §6). Strictly additive — existing files are never overwritten.
3. **Inject Modules**: Registers all active SDKs as modules in `modules.txt`.
4. **Copy Code & Assets**: Copies DocTypes and APIs into their modular subdirectories under the app package.
5. **Compile Placeholders**: Replaces `{app_name}` and `{module_name}` tokens with the target app shell name and the module's manifest name, in `src/` AND `doctype/` trees (`.py`/`.js`/`.html`/`.json`), and pins src-nested DocType JSON `"module"` keys.
6. **Merge Hooks**: Aggregates all `whitelisted_methods`, `fixtures`, `doc_events`, and `auth_hooks` from all active manifests and appends them dynamically to the end of `hooks.py`.
7. **Inject Dependencies**: Appends missing Python dependencies to the root `requirements.txt` and `pyproject.toml`.
8. **Token Lint**: Scans everything the run composed for leftover literal `{app_name}`/`{module_name}` tokens. A hit is a loud warning by default; `ROKCT_COMPOSE_STRICT=1` escalates it (and every other compose warning) to a hard, non-zero-exit error — same env-flag convention as the flutter installer.

### Endpoint alias registration (`override_whitelisted_methods`)

A manifest's `whitelisted_methods` map declares short client-facing dotted
paths (`{app_name}.api.<x>`, `{app_name}.tenant.api.<x>`) aliased to the real
composed module paths. Frappe's request dispatcher only rewrites incoming
`cmd` strings via the standard `override_whitelisted_methods` hook
(`frappe.override_whitelisted_method()` in `handler.execute_cmd`); it never
reads a `whitelisted_methods` hook. The composer therefore writes every alias
under **both** keys in the composed `hooks.py`:

- `whitelisted_methods` — the historical key, kept for back-compat with
  tooling that reads the composed hooks file.
- `override_whitelisted_methods` — the key that makes the aliases actually
  resolve at dispatch time.

Keys and values are emitted exactly as declared in the manifest (after
`{app_name}` placeholder substitution), so each composed shell exposes only
its own `{app_name}.*` alias names — no cross-shell prefixes are synthesized.
Keys may additionally carry a single gateway prefix
(e.g. `"control:claim_tender"`), the shape frappe's cmd registry accepts for
gateway-scoped commands; values must always remain plain dotted paths.

### Login hooks (`on_login`)

A manifest (top-level or persona block) may declare `hooks.on_login` as a
single dotted path or a list. Frappe's `LoginManager.run_trigger` calls
**every** handler `frappe.get_hooks("on_login")` returns, so the composer
accumulates handlers from all modules into a deduped list — and coerces a
shell `hooks.py` that declared `on_login = "app.path"` as a bare string
(standard Frappe style) to a list first, the same treatment as
`after_install`.

### Desk doctype JS (`doctype_js` / `doctype_list_js`)

A manifest (top-level or persona block) may register desk form scripts
(`doctype_js`) and list-view scripts (`doctype_list_js`) as a map of DocType
name to one path or a list of paths. Declare each path **relative to the
module's own `src/` tree** — mirroring where the file lands inside the
composed module, e.g. a file shipped at
`src/control/public/js/company_subscription_list.js` is declared as:

```json
"doctype_list_js": { "Company Subscription": "control/public/js/company_subscription_list.js" }
```

At compose time the path is rewritten to `<module_dir>/<path>` (Frappe
resolves these hooks via `frappe.get_app_path(...)`, i.e. relative to the app
package dir, and inlines the file server-side), entries accumulate as a
deduped list per DocType across modules, and each registered path is
existence-checked against the composed output — a missing file (typo, or a
path into a stripped persona folder) is a loud compose warning, escalating
under `ROKCT_COMPOSE_STRICT=1`. Form JS shipped **inside** a
`doctype/<dt>/` tree (`<dt>.js` / `<dt>_list.js`) needs no declaration:
Frappe auto-loads those from the doctype directory.

### Semantics of the git-clone fallback

Two behaviors of `resolve_module_sources()`'s clone path (used only when no
local sibling checkout of the SDK repo exists) — both were long-standing
caveats, now fixed:

1. **`ref` accepts a branch, tag, or commit SHA.** Branch and tag refs take
   the same shallow path as before (`git clone -b <ref> --depth 1`). When
   that fails — most notably because the ref is a raw commit SHA, which
   `git clone -b` does not accept — `clone_ref()` falls back to a full
   `git clone` followed by `git checkout <ref>`, so pinning a module to an
   exact commit works.
2. **A failed clone fails the build loudly.** If both clone strategies fail
   (typo'd git URL, expired token, nonexistent ref), the composer prints
   `[!] Failed to clone <url> (ref '<ref>') needed by module(s): ...` and
   raises `CRITICAL ERROR: Failed to clone ...` — same hard-failure idiom as
   duplicate-DocType collisions — so composition exits non-zero instead of
   soft-skipping the module and shipping a quietly incomplete app. (A missing
   `manifest.json` after a *successful* source resolution still soft-skips
   the module, as before.)

---

## 5. Composer Templates & Shell Scaffolding

Two template surfaces mirror the flutter side:

- **Per-shell composer manifests** — `core/utils/frappe/composer/*.json` (e.g.
  `rcore.json`), the frappe analog of `core/utils/flutter/composer/*.json`. Templates,
  not active configuration: copy the matching one to the shell repo root as
  `composer.json` and run compose. They are the canonical record of each shell's
  module graph — see `core/utils/frappe/composer/README.md`.
- **Shell skeleton** — `core/utils/frappe/templates/shell/`, a tokenized frappe app
  shell (hooks.py identity keys, minimal install.py, pyproject.toml/setup.py/
  MANIFEST.in, modules.txt, patches.txt, app + in-shell module packages).
  `compose_backend.py` lays it down automatically when the target app package is
  missing, or on `--scaffold`; existing files are never overwritten. The composer
  embeds these templates (it ships as a single pinned file), and
  `core/utils/frappe/tests/test_compose_backend.py` keeps the embedded and on-disk
  copies byte-identical — see `core/utils/frappe/templates/shell/README.md`.

Scaffolding a brand-new shell end to end:

```bash
mkdir mynewshell && cd mynewshell && git init
# copy core/utils/frappe/composer/<closest>.json here as composer.json, set "name"
python3 .rokct/skills/.rok/frappe/scripts/compose.py   # scaffolds, then composes
```

---

## 6. Development & Clean Restores

To keep the development workspace clean and easy to evaluate, enforce post-restore cleanliness:
1. **Restore Git State**:
   ```bash
   git clean -fd
   git restore .
   ```
2. **Clear Python Cache & Empty Directories**:
   Remove all `__pycache__` folders and empty directories remaining in the working tree.
