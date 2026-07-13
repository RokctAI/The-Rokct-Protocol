# Task Brief: Design the Next.js SDK Installer Convention

> Self-contained brief for a fresh session. Confirmed gap from `corporate/polaris/docs/fork-lending-nextjs-report.md`:
> every `nextjs/` folder across all 30+ SDK domains in the RokctAI monorepo is empty (just `.gitignore`) —
> there is no installer convention for Next.js SDKs anywhere. This blocks not just the Polaris lending
> frontend fork but every future Next.js SDK. Design the convention now, as its own piece of
> infrastructure — don't invent it ad hoc inside a single SDK's fork.

## What already exists (the pattern to mirror, confirmed real)

The Dart SDK installer convention (`The-Rokct-Protocol/core/utils/flutter/sdk_installer_base.py` +
`sdk_composer.py`, each SDK's own `install.py` + `manifest.json`):
- `manifest.json` declares `installs` ({from, to} template-file copies into the host app),
  `routes` (auto_route registration), `database` (Drift table injection via marker comments), and
  `integrations` (placeholder-marker text injection into host files).
- `sdk_composer.py` fetches each SDK (git or local), caches it flat under `.rokct/cache/<clean_name>/`,
  then runs the SDK's `install.py` which reads `manifest.json` and performs the installs/route
  registration/database injection/integrations against the host app.
- Host apps declare their active SDK set in a `composer.json` (see `supacharge/composer.json` for a live
  example) — `{name, enabled, source, git, path, ref}` per SDK.

`sdk_installer_base.py` also has 5 sibling installer domains under `core/utils/`:
`agent_deligation`, `flutter`, `frappe`, `opportunities`, `startup_os` — confirmed via investigation, none
of them is `nextjs`/`react`/`web`. This convention needs to be built from scratch, following the *shape*
of the Flutter one where it makes sense, not copying it mechanically (Next.js's install model is
fundamentally different — see below).

## Why this can't just copy the Dart convention directly

Per the earlier Next.js fork brief's own critical-fact warning (still true, worth restating): **Next.js
SDKs are installed into a folder to form a whole app — they are not consumed as an npm package
dependency**, unlike Dart's mixed pattern (pubspec path-dependency for importable code + templates/ for
copied files). A Next.js SDK is closer to "clone this file tree into the host app's `app/` directory and
wire up routes" than "add a package dependency." Design accordingly — figure out what a Next.js
`manifest.json`-equivalent needs to express (probably: file/folder copy destinations, route registration
if Next.js App Router needs any manifest-level wiring beyond file placement, environment/config merging,
package.json dependency merging since the copied code will have its own npm deps the host needs too).

## What to actually design

1. Decide the on-disk convention for a Next.js SDK: where does its source live relative to the SDK's git
   repo (mirroring Dart's `<sdk_repo>/<domain>/nextjs/` pattern already scaffolded-but-empty), what goes
   in its manifest, what an `install.py`-equivalent (or JS/TS equivalent — decide the implementation
   language, don't assume Python without checking whether that's appropriate for a JS-target installer)
   does.
2. Decide how `package.json` dependency merging works when a Next.js SDK's copied code needs npm packages
   the host app doesn't have yet — this has no Dart-side analogue (pubspec deps are declared once at the
   package level, not per-file) and needs its own answer.
3. Decide how routing/page registration works — Next.js App Router is filesystem-based routing, so
   "installing" a page might just be a file-copy with no separate route-registration step at all, simpler
   than Dart's auto_route requirement. Confirm this simplification is actually true before assuming it.
4. Write the installer script(s) (likely `The-Rokct-Protocol/core/utils/nextjs/` mirroring the `flutter/`
   folder's shape) and a minimal `manifest.json` schema doc.
5. Validate the design against the concrete, already-scoped real case waiting on it: Polaris's lending
   Next.js fork (`corporate/polaris/docs/fork-lending-nextjs-brief.md` and its report) — don't design in
   the abstract, prove the convention works by using it (or at least dry-running it) against that real
   content set.

## Deliverable

A working (or at minimum, concretely dry-run-validated) Next.js SDK installer convention: the
installer script(s), the manifest schema, and a short doc explaining the convention (mirroring
`agent/SDK_README.md`'s role for the Dart side). Report back before executing the actual Polaris lending
fork using it — that fork is a separate, already-written brief, this task is infrastructure only.
