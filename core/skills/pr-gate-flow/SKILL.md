---
name: pr-gate-flow
description: Use for any code change that must go through the draft PR and PR gatekeeper gate.
version: 1.0.0
---

# Driving a PR through this project's gate
**When:** any code change.

1. Work on a draft PR. Comment once on billing-wall CI with the local results.
2. Leave the PR draft and message the PR gatekeeper thread, naming the PR and listing what it claims (each bullet names a file the diff touches). The gatekeeper verifies against main and cites callers, not just functions.
3. Fix what the gatekeeper flags on the same PR, then ask for a re-check.
4. Never flip a PR to ready yourself: it stays draft until the PR gatekeeper verifies it. Only the gatekeeper flips to ready, and ready means auto-merge. If a PR gets flipped while work is still landing, move it back to draft and tell Ray.
5. After a merge, follow-ups go on a fresh branch from main and a new PR. If the local branch only holds merged history, point it at origin/main.
