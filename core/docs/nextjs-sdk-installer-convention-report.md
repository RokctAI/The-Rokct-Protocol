# Report: Next.js SDK Installer Convention

> Per `nextjs-sdk-installer-convention-brief.md`. Infrastructure only — the Polaris lending fork itself
> was not executed this session.

## What was built

- `The-Rokct-Protocol/core/utils/nextjs/sdk_installer_base.py` — per-SDK install engine (file sync,
  package.json dependency merge, marker-based integration injection).
- `The-Rokct-Protocol/core/utils/nextjs/sdk_composer.py` — composer.json-driven fetch/cache/orchestrate,
  mirroring `core/utils/flutter/sdk_composer.py`'s resolution strategy verbatim (that part has nothing
  Dart-specific in it) but ending in a single `npm install` instead of `flutter pub get` +
  `build_runner build` (no codegen step exists for Next.js SDK templates).
- `The-Rokct-Protocol/core/utils/nextjs/README.md` — the convention doc (manifest schema, on-disk shape,
  what carries over from Dart vs what doesn't and why, implementation-language rationale).

This gives every `<domain>/<sdk>/nextjs/` folder in the monorepo (30+, currently all empty) the same
`manifest.json` + `install.py` + `templates/` shape Dart SDKs already use, with a manifest schema suited
to Next.js instead of the Dart schema copied mechanically.

## Design decisions and why

**No route-registration step.** Confirmed by inspecting `RokctAI_frontend`'s real, currently-shipping
lending pages: none of them register themselves anywhere. Next.js App Router is filesystem-based —
`app/handson/all/lending/loan/[id]/page.tsx` existing on disk *is* the route. Dart's `routes` manifest
key and `update_router_table()` step (auto_route injection into `app_router.dart`) have no Next.js
counterpart. This was brief question #3 ("confirm this simplification is actually true before assuming
it") — confirmed, not assumed.

**No DI/main-file wiring, no `${package}` import-path substitution.** Dart substitutes
`package:${package}/...` because Dart packages are name-addressed and a copied file needs to know the
host's package name to import sibling copied files. Next.js has no package-name-addressed import scheme
for app-internal code — every host inspected (`RokctAI_frontend`, and the plain `create-next-app`
boilerplate at the workspace-root `nextjs/` repo) uses the standard `@/*` → `./*` tsconfig path alias, so
a file copied to the same relative path under the host's `app/` resolves its `@/app/...` imports
unchanged with zero rewriting. The installer asserts this alias exists (warns, doesn't fail, if missing)
rather than working around its absence.

**No database manifest section.** Checked whether the lending module (or any surveyed `nextjs/` SDK
candidate) has a client-side persistence layer analogous to Dart's Drift-backed `AppDatabase` — it
doesn't; `app/actions/handson/all/lending/*` call `BaseService.call(...)` directly per-request with
nothing cached locally. Omitted from the schema rather than included as unused/speculative structure.

**package.json dependency merging is genuinely new** (no Dart analogue — pubspec deps are declared once
at the package level, not per-copied-file). The manifest declares a flat `dependencies`/`devDependencies`
map; the installer merges additively into the host's `package.json` (host-pinned versions always win),
and `npm install` runs once, at the composer level, after all SDKs are installed — not per-SDK.

**Integrations (marker-comment injection)** carried over from Dart's `update_layout_integrations()`
essentially unchanged — it was never Dart-specific to begin with, just text-file marker replacement. Used
here for the one cross-cutting case the lending fork will actually need: adding a nav entry to the host's
shared sidebar.

**Implementation language: Python**, matching every other installer domain in `core/utils/`
(`flutter`, `frappe`, `agent_delegation`, `opportunities`, `startup_os`). The job is filesystem copy plus
JSON/text editing — nothing Node-specific — and keeping the compose step on one interpreter avoids
requiring Node to be present and correctly versioned at *install* time on top of *runtime*.

## Dry-run validation against the Polaris lending fork

Per the brief's explicit instruction to prove the convention against real content rather than design in
the abstract, and separately per the fork-execution brief's instruction not to touch
`corporate/polaris/nextjs/` this session: built a scratch host app and a scratch `polaris_sdk/nextjs/`
SDK (both outside the repo, in the session scratchpad) using **real files copied verbatim** from
`RokctAI_frontend/app/handson/all/lending/` — the `operations` page, its server action, its service, and
`Form20Template.tsx` (the NCR Form 20 template) — plus a manifest declaring `sonner` and `lucide-react`
as dependencies and one sidebar-nav integration.

Ran the installer (`python sdk/polaris_sdk/install.py`) three times against the scratch host:

1. **First run** — all four files copied correctly (directory entries walked and copied individually);
   the `"use server"` directive in the action file's banner-insertion point was respected — the banner
   landed *after* the directive, not before it (a naive "insert before first import" rule would have
   broken the directive-must-be-first-statement requirement; the installer specifically checks for
   `"use server"`/`"use client"` prologues first). `package.json` got `sonner` and `lucide-react` added.
   The sidebar file got the `Lending` nav entry appended after its placeholder marker.
2. **Second run (idempotency check)** — re-ran with no changes in between. All four files re-copied
   cleanly (hashes matched, no false "developer modified" warning), no duplicate dependency entries, no
   duplicate sidebar entry (integration injection checks for existing replacement text first).
3. **Third run (developer-edit protection check)** — hand-appended a line to the copied action file,
   then re-ran. The other three files re-copied normally; the hand-edited file was correctly skipped with
   the "modified by a developer" warning instead of being silently overwritten.

All three confirm the manifest schema and installer logic designed above actually work against the real
content set the Polaris fork brief scoped out, not just synthetic test files.

## What changes for the real fork (not done this session)

To actually execute `corporate/polaris/docs/fork-lending-nextjs-brief.md`'s fork using this convention:

1. Create `corporate/polaris/nextjs/manifest.json` + `install.py`, with `installs` entries for the full
   resolved file set from `fork-lending-nextjs-report.md` §6 (all `handson/all/lending/` pages, actions,
   services, and `app/templates/lending/*` — excluding the orphaned `platform/` scaffolding and unrelated
   HRMS loans, per that report's §2–§3).
2. Populate `corporate/polaris/nextjs/templates/` with those files (the actual fork/copy step).
3. Declare real npm dependencies in the manifest by diffing what the forked files import against a bare
   `create-next-app` `package.json` (this dry run used `sonner` + `lucide-react` as a representative
   sample, not the full set the real fork will need — e.g. whatever chart/PDF libs the NCR report pages
   pull in, if any, still needs checking).
4. Decide whether the lending nav entry belongs in a generic shared sidebar the way this dry run assumed,
   or Polaris's own — that's a Polaris-specific integration-target decision, not part of this
   infrastructure task.

This task (`nextjs-sdk-installer-convention-brief.md`) is complete: the installer convention exists,
is documented, and is validated against real content. Executing the actual Polaris fork is a separate,
already-written, still-pending task.
