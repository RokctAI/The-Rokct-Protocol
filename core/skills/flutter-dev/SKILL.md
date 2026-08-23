---
name: Flutter Developer
description: Day-to-day Flutter/Dart best practices for the composed SDK + app-shell fleet.
version: 1.0.0
---

# Flutter Developer Skill

## Context
You are a **Senior Flutter Engineer** working in the RokctAI fleet, where apps are thin shells composed from Dart SDKs. This skill covers day-to-day development practice; for the layer architecture (Domain/Infrastructure/Application/Presentation), defer to the `flutter-architect` skill.

## 1. Safety Gates (Critical)
*   **Am I in an app shell or an SDK repo?** Check for a root `composer.json` with a non-empty `sdks[]` array.
    *   **App shell** (e.g. `supacharge`, `paas_manager`, `paas_driver`): its `lib/` is **regenerated on every compose**. NEVER hand-edit composed `lib/` code — the fix belongs in the SDK that owns it (find it via the shell's `composer.json`). Shell-side edits are limited to shell-owned files (composer manifest, platform folders, CI callers).
    *   **SDK monorepo** (`core`, `zones`, `commerce`, `Users`, `pay`, `productivity`, `agent`): edit under `<sdk>/dart/` normally.
*   **Version truth**: `dart/manifest.json` is authoritative. The `version` in `pubspec.yaml` is frequently stale — when they disagree, the manifest wins. Read `SDK_README.md` in the `agent` repo before authoring SDK code (DDD layout, ADR-005 imports, offline doctrine).

## 2. Shipping an SDK Change (The Loop)
1.  Make the change in the SDK's `dart/` directory, honoring the layer rules.
2.  Bump the SDK's `dart/manifest.json` semver **in the same commit**, and add a `CHANGELOG.md` entry.
3.  Merge to `main`. Shells consume SDKs at `ref: main`; the `sdk-bump-poller` workflow auto-dispatches dependent shell builds — no per-repo hookup needed.
4.  Verify a dependent shell recomposed cleanly before calling the task done.

## 3. Networking (Single-Gateway Rule)
*   **All backend calls go through the gateway**: `POST /api/v1/method/rokct.platform.api` with a prefix-free `cmd`.
*   NEVER build app-prefixed method URLs like `/api/method/paas.<module>...` in client code.
*   Network code lives only in `infrastructure/` (services/repositories). Widgets never touch Dio/HTTP.

## 4. Dart/Flutter Best Practices
*   **Null safety**: no `!` bang operators to silence the analyzer — restructure or use pattern matching. `late` only when initialization is provably guaranteed.
*   **Immutability**: `const` constructors wherever possible; models are immutable with `copyWith`.
*   **State**: follow the app's existing state solution (Riverpod/Bloc); do not introduce a second one. Providers/blocs live in `presentation/`/`application/`, never in widgets' build methods.
*   **Widgets**: prefer composition over inheritance; extract a widget class (not a helper method returning `Widget`) once a build method nests ~3 levels deep. Use keys on list items backed by data.
*   **Async**: no `async` gaps holding `BuildContext` — check `context.mounted` after awaits. Streams and controllers are disposed.
*   **Errors**: fail loudly in debug, degrade gracefully in release; error states are real UI states, not empty screens. Honor the offline doctrine — infrastructure repositories decide cache-vs-network, not widgets.

## 5. Quality Bar Before "Done"
*   `dart analyze` clean (no downgraded lints to make it pass).
*   `dart format` applied; no commented-out code left behind.
*   Unit tests for application-layer logic and model serialization (`fromJson`/`toJson` round-trip).
*   No secrets, endpoints, or AI model IDs hardcoded in Dart source — configuration flows in via the SDK's manifest/templates mechanism.
