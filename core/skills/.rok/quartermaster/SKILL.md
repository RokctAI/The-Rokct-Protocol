---
name: quartermaster
description: Gate every new thread's model and effort through the Quartermaster before it is opened; it approves or overrides only model and effort and keeps a history per task.
version: 1.0.0
---

# Quartermaster: the model and effort gate
**When:** the coordinator is about to open a thread, re-task one, or a thread asks to change its own model or effort.

The Quartermaster decides exactly two things: which model a task runs on and at
what effort. It never touches scope, priority, branch, or who does the work.
It runs itself on Fable 5.1 low (default) or Opus 5.5 high when the
judgment call is hard.

## Flow

1. The coordinator sends the Quartermaster thread one request per task:
   task id, one-line task, the kind of work (`judgment`, `code`, `plan`,
   `batch`, `verify`, `design`), and the proposed model and effort.
2. The Quartermaster runs `python3 quartermaster.py decide` with those fields
   (see below). The script applies Ray's standing policy deterministically
   and prints `approve` or `override` with the model and effort to use.
3. The Quartermaster adds its own judgment only where the policy leaves room
   (for example choosing between Fable 5.1 and Sonnet 5.5 for a judgment
   task) and never to loosen a hard rule.
4. It replies to the coordinator in one line: `approve <model> <effort>` or
   `override <model> <effort>: <reason>`. The coordinator passes exactly that
   model and effort when it opens the thread and checks the thread confirms
   them.
5. `xhigh` and `max` are never approved by the Quartermaster. A request for
   them is answered `hold`, and the coordinator asks Ray in one line. Ray's
   yes is recorded with `python3 quartermaster.py record --approved-by ray`.
6. Every decision is appended to the history file, one line per decision,
   keyed by task id. `python3 quartermaster.py history <task-id>` shows a
   task's past decisions so a re-task does not repeat a bad pick.

## Policy the script encodes (Ray, 2026-09-28 and 2026-10-19)

- Default effort is `low`.
- Allowed models: Fable 5.1, Opus 5.5, Sonnet 5.5, Haiku 5.5. Anything else
  is overridden to Sonnet 5.5.
- Haiku 5.5 only for `batch` (mechanical) work; there `high` is fine.
  Haiku on any other kind is overridden to Sonnet 5.5 low.
- `judgment` and `verify` work runs Sonnet 5.5 low unless Fable 5.1 or
  Opus 5.5 was proposed; the PR gatekeeper is Sonnet 5.5 high.
- `plan` work may run Fable 5.1 or Opus 5.5 at low or medium; `high` on a
  plan is overridden to medium (a plan thread at high cost Ray 4% of his
  Fable usage on 2026-10-24).
- `xhigh` and `max` are never approved here; they need Ray's word.
- Wednesday and Thursday before the Friday reset are not an exception for
  the Quartermaster: it still holds for Ray.

## History

The history file is JSON Lines, one decision per line:
`{"ts", "task_id", "task", "kind", "proposed": {"model", "effort"},
"decision", "model", "effort", "reason", "approved_by"}`.
Default path is `.rokct/quartermaster-history.jsonl` in the project's
workspace; override with `--history <path>` or `QUARTERMASTER_HISTORY`.
In the ROKCT project the shared copy lives at
`/mnt/project-files/quartermaster/history.jsonl` so every coordinator sees
the same record.

## Examples

```
python3 quartermaster.py decide --task-id cmsg_abc --task "Audit zones weather" \
  --kind judgment --model "Sonnet 5.5" --effort high
override Sonnet 5.5 low: judgment work runs at low effort

python3 quartermaster.py decide --task-id cmsg_def --task "Rename 300 keys" \
  --kind batch --model "Haiku 5.5" --effort high
approve Haiku 5.5 high

python3 quartermaster.py decide --task-id cmsg_ghi --task "Hubs spec" \
  --kind plan --model "Fable 5.1" --effort max
hold Fable 5.1 max: xhigh/max need Ray's word
```
