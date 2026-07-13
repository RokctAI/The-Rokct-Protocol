# Next.js SDK Installer Convention

> Mirrors `agent/SDK_README.md`'s role for the Dart side. Read this before writing or installing any
> `<domain>/nextjs/` SDK. Designed per `core/docs/nextjs-sdk-installer-convention-brief.md`, validated by
> dry-run against the Polaris lending fork (`corporate/polaris/docs/fork-lending-nextjs-brief.md`).

## Why this isn't a copy of the Dart convention

Dart SDKs are consumed two ways at once: a `pubspec.yaml` path-dependency for importable code, plus a
`templates/` folder of files physically copied into the host app. **Next.js SDKs only do the second
thing.** A Next.js SDK is a tree of `app/` files that gets copied into a host Next.js app to become part
of that app — there is no npm-package-dependency mode, because App Router pages/actions/services aren't
designed to be imported across a package boundary the way a Dart repository interface is.

Three specific simplifications follow from that, each confirmed against the live Dart implementation
and the actual Polaris lending content before assuming they hold:

1. **No route-registration step.** Dart needs `auto_route` entries injected into `app_router.dart`
   because Flutter routing is centrally declared. Next.js App Router is filesystem-based — a file at
   `app/handson/all/lending/loan/[id]/page.tsx` *is* the route the moment it exists on disk. Confirmed by
   inspecting how `RokctAI_frontend`'s existing lending pages register themselves: they don't, anywhere;
   placement is the only registration.
2. **No DI/main-file wiring step.** Dart's `update_main_dependencies()` registers each SDK's
   `GetIt`-based dependency container in `main.dart`. Next.js has no equivalent central registry each
   page must be wired into — a copied page imports its copied server actions directly
   (`import { getLoan } from "@/app/actions/handson/all/lending/loan"`), which resolves immediately via
   the standard `@/*` → `./*` tsconfig path alias. This is also why there's no `${package}` placeholder
   substitution on import paths: Dart substitutes because Dart packages are name-addressed
   (`package:${package}/...`); Next.js files copied to the same relative path under the host's `app/`
   just resolve through the alias unchanged.
3. **No database/offline-storage manifest section.** Dart's `manifest.json` has a `database` block for
   injecting Drift tables into a shared `AppDatabase`. The Next.js lending module (and every other
   `nextjs/` SDK candidate surveyed) talks to the backend directly per-request via `BaseService.call(...)`
   with no local persistence layer to register into — so this section is omitted from the schema, not
   deferred. Add it back only if a concrete SDK actually needs client-side persistence; don't
   pre-build unused schema.

What *does* carry over, because it isn't Dart-specific: file-copy with SHA-256-based
developer-modification detection (skip overwrite, don't clobber hand edits), the `[GENERATED TEMPLATE
FILE]` banner comment, and marker-based text injection for cross-cutting host files (`integrations`).

What's genuinely new (no Dart analogue): **package.json dependency merging** — Dart declares SDK deps
once at the package level via `pubspec.yaml`; a Next.js SDK's copied files can need npm packages
(`sonner`, `lucide-react`, ...) the host doesn't have yet, and there's no package-level pubspec-style
declaration point for that, so the manifest declares them directly and the installer merges them into
the host's `package.json`.

## On-disk convention

```
<domain>/<sdk>/nextjs/
  manifest.json
  install.py
  templates/
    app/<path matching where files land in the host>/...
```

Mirrors the Dart `<domain>/<sdk>/dart/` shape exactly (`manifest.json` + `install.py` + `templates/`)
for consistency across the two client SDK kinds — same shape, different manifest semantics.

## `manifest.json` schema

```json
{
  "name": "polaris_sdk",
  "version": "1.0.0",
  "installs": [
    { "from": "templates/app/handson/all/lending", "to": "app/handson/all/lending" }
  ],
  "dependencies": {
    "sonner": "^2.0.7"
  },
  "devDependencies": {},
  "integrations": [
    {
      "target": "app/handson/sidebar-client.tsx",
      "placeholder": "// @rokct-sdk-nav-start",
      "replacement": "  { href: \"/handson/all/lending\", label: \"Lending\" },"
    }
  ],
  "requires": [
    "app/lib/roles.ts",
    "app/services/common/base.ts"
  ]
}
```

- **`installs`**: `{from, to}` pairs, `from` relative to the SDK's `templates/`, `to` relative to the host
  app root. Directories are walked and copied file-by-file (so partial developer edits to one file in a
  copied folder don't block re-installing the rest). No `routes` key — see simplification (1) above.
- **`dependencies` / `devDependencies`**: flat npm package → version-range map. Merged additively into the
  host's `package.json`; an existing host-pinned version always wins (the SDK asserts a package must
  exist, not which exact version the host must run). `npm install` is **not** run per-SDK — the composer
  runs it once after all SDKs are installed.
- **`integrations`**: marker-comment injection into a shared host file the SDK doesn't own outright (e.g.
  appending a nav entry to a shared sidebar array). Idempotent — skipped if the replacement text is
  already present. The host file must contain the literal `placeholder` string already; the installer
  does not create the marker itself. If no cross-cutting file needs touching, omit `integrations` (or
  leave it `[]`) rather than forcing an empty stub in every SDK's manifest.
- **`requires`**: host-app-relative paths the SDK's copied files import but does not itself provide or
  install — a shared UI-kit component, another domain's server action, a host-wide lib helper. Purely
  informational: the installer warns per missing path but still copies the files (they may just not
  compile until the host supplies the prerequisite). Exists because forking a real feature can surface
  genuine cross-domain coupling (discovered on the Polaris lending fork: one page imports an accounting
  SDK's `sales_order` action and an HRMS `companies` action) that the fork can't silently absorb or
  silently drop — it has to be declared. Not a substitute for a real cross-SDK dependency mechanism if
  one becomes necessary later; just makes today's coupling visible instead of a silent broken import.

## Installer scripts

- `The-Rokct-Protocol/core/utils/nextjs/sdk_installer_base.py` — per-SDK install logic (file sync,
  package.json merge, integration injection). Gets copied to a host's `.rokct/sdk_installer_base.py` the
  same way the Flutter one does (see `supacharge/.rokct/compose.py` for the live fetch-and-run bootstrap
  pattern; a Next.js host's `.rokct/compose.py` is the same wrapper pointed at
  `core/utils/nextjs/sdk_composer.py` / `sdk_installer_base.py` instead of the `flutter/` paths — write
  that wrapper when the first real Next.js host adopts this convention, not speculatively here).
- `The-Rokct-Protocol/core/utils/nextjs/sdk_composer.py` — reads the host's `composer.json` (same shape as
  the Dart one: `{package_name, sdks: [{name, source, git, path, ref, enabled}]}`, `path` pointing at each
  SDK's `nextjs/` folder instead of `dart/`), fetches/caches each SDK, runs each `install.py`, then runs
  `npm install` once at the end.
- Each SDK's own `install.py` (same pattern as `agent/lms/dart/install.py`):

  ```python
  import sys, os
  sys.path.append(os.path.join(os.getcwd(), '.rokct'))
  import sdk_installer_base
  if __name__ == '__main__':
      sdk_installer_base.install_sdk_files('polaris_sdk')
  ```

## Implementation language

Python, matching every other installer domain (`flutter`, `frappe`, `agent_deligation`, `opportunities`,
`startup_os`) — not Node/TypeScript. The installer's job is filesystem copy plus JSON/text editing, none
of which needs the Node runtime; using Python keeps one interpreter dependency for the whole
`sdk_composer.py`-driven compose step across every SDK kind, rather than requiring Node to be present and
correctly versioned at *compose* time on top of at *runtime*. Node is still required to actually run the
resulting Next.js app afterward — that's unrelated to how the SDK gets installed into it.

## Validated against

Dry-run only (per the infrastructure brief, not an execution of the actual fork): a scratch host app
(package.json + tsconfig.json with the `@/*` alias + a `sidebar-client.tsx` nav stub) and a scratch
`polaris_sdk/nextjs/` built from real files copied out of `RokctAI_frontend/app/handson/all/lending/`
(the `operations` page + its action + service, plus `Form20Template.tsx`). Confirmed: file copy with
correct banner placement (after `"use server"`/`"use client"` directives, before imports), hash-based
skip-on-developer-edit, `package.json` dependency merge (additive, host-pinned versions preserved), and
sidebar integration injection all work end-to-end, including on repeated runs (idempotent, no duplicate
integration text) and against a hand-edited file (skipped with a warning, not clobbered). See
`core/docs/nextjs-sdk-installer-convention-report.md` for the run transcript and what would change for the
real fork.
