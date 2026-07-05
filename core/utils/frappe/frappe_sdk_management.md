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
