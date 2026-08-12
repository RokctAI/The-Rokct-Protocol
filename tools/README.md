# Protocol pinning and integrity tools

The protocol fetches parts of its own repository at runtime (the
`agent_delegation` scaffold wrappers, the `.rok` skill composers, the StartupOS
engine loader, the installers and bootstrappers) and executes what it
downloads. Left unpinned, that means "run whatever is on `main` right now" —
anyone who can move `main` or tamper with the transport owns every consumer.

## The pin model

- `protocol.lock.json` (repo root) records a single commit SHA (`ref`) and the
  SHA-256 of every fetched-and-executed file **at that commit**.
- Every consumer file carries embedded copies of those pins
  (`PROTOCOL_REF`, `DELEGATE_SHA256` / `COMPOSER_SHA256` /
  `MAINTENANCE_SHA256`, or an `EXPECTED_SHA256` dict). Consumers embed the
  constants because skill folders are installed standalone into host apps with
  no repo context — they cannot read the repo-root lockfile at runtime.
- At runtime, every fetch goes to
  `https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/<PROTOCOL_REF>/...`
  and the downloaded bytes are SHA-256 verified against the embedded hash
  **before** anything is executed (or written where it will be executed).
  A mismatch or a failed fetch aborts loudly with exit 1 — there is no
  unverified fallback. Cached fallbacks (e.g. `.rokct/tmp/delegate_cache/`,
  the StartupOS engine cache) are verified against the same hashes, which is
  what makes offline operation safe.

## Bumping the pin

After a change to any fetched file lands on `main`:

1. Merge the change.
2. `git fetch origin main && python tools/gen_protocol_lock.py --ref origin/main`
   (or pass the exact merge commit SHA). This rewrites `protocol.lock.json`
   and every embedded constant in one shot, idempotently.
3. Open and merge the resulting lock-bump PR.

Until the bump merges, consumers keep fetching the previous pinned commit —
old-but-verified, never unverified.

## Tools

- `tools/gen_protocol_lock.py` — generates the lockfile and rewrites the
  embedded constants. Hashes come from `git show <ref>:<path>`, never the
  working tree.
- `tools/verify_protocol_lock.py` — CI check (`.github/workflows/verify_lock.yml`).
  Default (network) mode checks embedded constants against the lockfile and
  re-downloads every target from raw.githubusercontent.com at the pinned ref
  to verify its hash. `--offline` skips the download; `--git` verifies against
  the local git object store instead of the network.

## Development escape hatch (StartupOS)

`STARTUPOS_PROTOCOL_REF=<ref>` still lets developers run the engine from
another ref, but since the embedded hashes cannot vouch for other refs it
bypasses verification: it warns loudly and requires an explicit
`STARTUPOS_ALLOW_UNPINNED=1` to proceed.
