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
`auth_hooks`, `before_uninstall`, `after_install`, `commands`, ...) can be
role-scoped.

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
2. **Inject Modules**: Registers all active SDKs as modules in `modules.txt`.
3. **Copy Code & Assets**: Copies DocTypes and APIs into their modular subdirectories under the app package.
4. **Compile Placeholders**: Replaces `{app_name}` tokens with the actual target app shell name.
5. **Merge Hooks**: Aggregates all `whitelisted_methods`, `fixtures`, `doc_events`, and `auth_hooks` from all active manifests and appends them dynamically to the end of `hooks.py`.
6. **Inject Dependencies**: Appends missing Python dependencies to the root `requirements.txt` and `pyproject.toml`.

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

**Canonical-prefix duplicates.** Shipped client SDKs hardcode dotted paths
under the canonical wire prefix `paas` (e.g. `/api/method/paas.api.auth.refresh`),
but the same manifests can compose into an app with a different name (e.g.
`rcore`). When the composed app name differs from the canonical prefix, every
`{app_name}.<rest>` alias key is additionally registered as
`<canonical_prefix>.<rest>` under `override_whitelisted_methods`, so existing
client call strings work unchanged against any composed backend. The prefix
defaults to `paas` and can be overridden with an optional
`"canonical_api_prefix"` field in the shell's `composer.json`.

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

## 5. Development & Clean Restores

To keep the development workspace clean and easy to evaluate, enforce post-restore cleanliness:
1. **Restore Git State**:
   ```bash
   git clean -fd
   git restore .
   ```
2. **Clear Python Cache & Empty Directories**:
   Remove all `__pycache__` folders and empty directories remaining in the working tree.
