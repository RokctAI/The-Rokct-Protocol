---
name: pr-gatekeeper-check
description: The PR gatekeeper's script for the mechanical checks (merge, named files, versions, tests, secrets, notes, art); a tool, the gatekeeper still makes every flip.
version: 1.0.0
---

# PR gatekeeper check
**When:** the PR gatekeeper verifies a PR (see `pr-gate-flow`). Authors do not run this to flip anything; they may run it to see what the gatekeeper will see.

The script is the gatekeeper's tool, not its replacement (Ray, 2026-10-26). It
gathers proof the same way every time and keeps fetch, merge, version and test
output out of the model's context. The gatekeeper reads its table, reads what
a script cannot prove, and decides. The script never flips, merges or comments.

## Run

```
python3 gatekeeper_check.py --repo <checkout> --head <ref> [--base origin/main] \
    [--body-file pr_body.md] [--name <repo>] [--pr control#192] [--fetch] [--no-run]
```

One line per rule: `PASS`, `FAIL`, `NEEDS-READ`, `NEEDS-RAY`, `NOT RUN`, `INFO`.
Exit 0 when nothing FAILs, 1 when something does, 2 on bad usage.

## What it proves

- `merge`: `git merge-tree` exit code and every CONFLICT line, with file names.
- `bullet-files`: files the PR body names in backticks appear in the diff.
- `versions`: version files agree with the CHANGELOG top entry, no version goes down, and code changes carry a bump in repos that require one.
- `secrets`: key and token patterns in added lines.
- `pr-notes`: "next time", follow-up and note-for-Ray wording. Ray acts on no PR notes: send it back or have the PR say plainly what is unproven.
- `merge-order`: "stacks on #N" and what that means for versions.
- `art`: images and media need Ray's own approval attached (`NEEDS-RAY`).
- `tour-with-ui`: a UI change in an app shell carries a tour.
- test commands from the checklist, run in a throwaway worktree of the head; the pass count is compared with the PR body's claim.

## What stays with the gatekeeper

Does the caller really invoke the function; does the test exercise the claim or
only a stub; is the unproven list honest; every `NEEDS-READ`. A `NOT RUN` line
goes into the verdict and the PR in plain words, e.g. "Dart not tested: Flutter
is not installed". Never write "unproven" without saying what was not run.

## Rules: checklist.json

One rule is one line in `checklist.json`: `id`, `check` (a built-in), optional
`repos`, `when_touches` (globs), and for `command` rules `cmd`, `cwd`, `requires`
(tools that must exist, else `NOT RUN` with `not_run_text`), `allow_errors`.
A new ruling is one new line. A new kind of check is a function in the script
plus a test in `tests/test_gatekeeper_check.py`.

## Self-improvement

The gatekeeper watches the script as it uses it. Each run appends a line to
`/mnt/project-files/gatekeeper/runs.jsonl` (PR, repo, head, result per rule).
The gatekeeper fixes a wrong or incomplete script itself when the fix is small
(a checklist line, a tighter pattern, a dropped noisy line, a parser fix), as a
PR that names the run that showed it and adds a replay test. Anything that
loosens a rule or removes a blocking check goes to the coordinator first. A
false PASS on a PR already flipped is reported at once, naming the PR.
Proposal: `/mnt/project-files/gatekeeper/script-first-gatekeeper-proposal.md`.
