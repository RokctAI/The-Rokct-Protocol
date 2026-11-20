# Agent Memory & Lessons Learned

**Rule**: Before asking a question or starting a task, the Agent **MUST** read
this file to check for past lessons or user preferences.

## User Profiles

* **[Name]**:
  * **Safe ID**: [ray.dev.9ac2b1] (Used for filenames)
  * **Role/Preferences**: [Details]
* *(Agent: Add new users here as they appear)*

## Global Preferences

* **Session Retention**: [Forever] (Options: Forever, 1 Month, 1 Week)
* **Checkpoint Policy**: [Value] (Options: Frequent, Manual) -> *Set 'Frequent'
  for Cloud Agents*
* [Active] Prefer "Frappe" for backend.
* [Active] Prefer "Next.js + AI SDK" for frontend.
* [Active] Prefer "Flutter" for mobile.
* [Active] "Premium" design aesthetic is non-negotiable.

## Report PR (every thread)

* Every thread or agent session opens ONE draft PR in the repo it works on,
  off main, before it starts work. The PR is never flipped to ready and is
  never merged: it only holds the report.
* First write the task for this repo in the PR description, then update the
  description as the work goes (done, in progress, blocked, links to the
  real PRs). No file named "report" is needed; the PR description is enough.
* Detailed working notes go in `.rokct/sessions/` (the repo's scratchpad).
  Sessions stay in the repo: they are not copied to the parent workspace and
  are not deleted by cleanup. Old ones are pruned only when
  **Session Retention** above is set to 1 Month or 1 Week.

## Lessons Learned

> Note: Agent to append new lessons here when a mistake is made or a
> correction is received.

* **[Date]** - [Lesson]
