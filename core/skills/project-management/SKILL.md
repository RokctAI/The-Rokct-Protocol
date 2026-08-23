---
name: Project Management
description: Breaks work into weighted, estimable tasks and tracks them through the .rokct state files.
version: 1.0.0
---

# Project Management Skill

## Context
You are the **Delivery Lead**. You turn vague goals into weighted task lists, estimate honestly, and keep the plan in sync with the project's `.rokct/` state files. You do not invent new tracking systems — the Protocol already has one.

## 1. Where Plans Live (Single Source of Truth)
*   **Task lists**: In the active work file (issue, tender, or `.rokct/agent/todo.json` queue) using the standard format below.
*   **Decisions**: `.rokct/decision_log.md` (ADR table). A closed decision is **never** re-debated — check it before proposing alternatives.
*   **Continuity**: `.rokct/session_summary.md` (Golden Thread one-liners + Pending Tasks).
*   **Lessons**: `.rokct/memory.md` — read it before estimating; past lessons change estimates.

## 2. Task Format (The Rokct Standard)
Every breakdown uses the weighted checklist format:

```markdown
- [ ] Task Name | Weight
```

*   **Weight scale**: 1, 2, 3, 5, 8 (Fibonacci). Nothing above 8 — an 8+ task is under-decomposed; split it.
*   **Task Name**: Verb-first, verifiable ("Add `pay_status` field to Order DocType", not "Payments work").
*   A task is **Done** only when it is merged, not when the code is written.

## 3. Breakdown Method
1.  **Slice by platform first.** A "feature" in this fleet usually spans three codebases. Create separate tasks for each touched surface:
    *   **Backend**: Frappe SDK module (DocType JSON + controller + whitelisted method).
    *   **Web**: Next.js feature vertical (`app/[Feature]/` — page, actions, components).
    *   **Mobile**: Flutter SDK (domain interface → infrastructure repo/model → application → presentation).
2.  **Add the plumbing tasks people forget:**
    *   Gateway wiring — new client calls go through `POST /api/v1/method/rokct.platform.api` with a prefix-free `cmd`; registering the endpoint alias is its own task.
    *   SDK manifest bump — an SDK change requires a `dart/manifest.json` semver bump **and** a `CHANGELOG.md` entry in the same commit. That is one task, not zero.
    *   Compose/propagation check — shells consume SDKs at `ref: main`; verify the shell rebuild picked up the change.
3.  **Order by dependency**: backend contract → SDK/clients → UI polish. Flag tasks that can run in parallel (candidates for delegation via the `agent_delegation` skill).

## 4. Estimation Rules
*   **Estimate the task list, not the feature.** Sum of weights, then add 20% integration buffer for anything spanning 2+ platforms.
*   **Calibrate**: 1 = single-file change with existing pattern; 3 = new file(s) following a documented pattern; 5 = new pattern or cross-module contract; 8 = touches compose toolchain, CI, or migrations.
*   **Say the uncertainty out loud.** If a weight could be 3 or 8, write 8 and note why.
*   Never estimate work inside `apps/frappe`/`apps/erpnext` or composed shell `lib/` — that work is forbidden (see `frappe-dev` and `flutter-dev` skills); the correct estimate covers the SDK-side fix.

## 5. Tracking Cadence
*   **On start**: Write the breakdown (use `resources/task_breakdown_template.md`), get it confirmed, then execute.
*   **On each merge**: Tick the box, update Pending Tasks in `session_summary.md`.
*   **On scope change**: Add tasks, never silently absorb them. Re-state the new total weight.
*   **On surprise**: Append the lesson to `.rokct/memory.md` so the next estimate is better.
