# The protocol lock, in plain language

`protocol.lock.json` (repo root) pins **this repository's own code** — the
scripts the protocol fetches from GitHub and executes at runtime (the skill
wrappers' backends, the compose scripts, the StartupOS engine, the installers
and `initiate.py`). It records one commit SHA (`ref`) plus the SHA-256 of every
one of those files at that commit. Every fetch at runtime goes to that exact
commit and the bytes are hash-checked before anything runs.

**The lock does NOT pin SDKs.** SDK code (for example `lms_sdk` in the
`RokctAI/agent` repo) is fetched from the SDK's own repository by the composer
at compose time, controlled by each app's `composer.json` — the lock never
sees it. The lock only pins the composer *machinery* that does the fetching.

Three everyday scenarios:

## 1. "I updated an SDK" (code or version in the SDK repo)

The lock is not involved. Do not run `gen_protocol_lock.py`, do not touch
`protocol.lock.json`, do not re-run `initiate.py`.

1. Make your change in the SDK's repo (e.g. `RokctAI/agent`).
2. Bump `"version"` in that SDK stack's `manifest.json` (e.g.
   `lms/dart/manifest.json`). This matters: the composer compares the incoming
   manifest version against its cache, and only a **newer** version makes apps
   throw away the cached copy and re-extract. Same version = cached copy kept.
3. Merge in the SDK repo. Apps pick the change up on their next compose.
4. Only if a consuming app's `composer.json` pins that SDK — by a 40-character
   commit `"ref"`, or by a `"sha256"` of its `install.py` — update that pin in
   the **app's** repo (new commit SHA, or new hash if `install.py` changed).
   An entry that just says `"ref": "main"` with no `sha256` needs nothing,
   but the composer will refuse to run its installer unpinned.

## 2. "I changed the composer / protocol tools" (any file this repo fetches and runs)

Changing a locked file (e.g. `core/utils/flutter/sdk_composer.py`,
`profiles/local/initiate.py`, `workflows/maintenance.yml`) always takes **two
PRs**, because the lock can only point at a commit that already exists on
`main`:

1. Open a PR with your change. The **Verify Protocol Lock** check goes red on
   it. That is expected — it is telling you the file no longer matches the
   pinned hash, i.e. "a lock bump is needed after this merges". It is not a
   reason to fix anything in that PR.
2. Merge it. `main` shows the same red for the same reason.
3. Regenerate the lock. A Claude session normally opens this repin PR
   automatically; to do it by hand:

   ```bash
   git fetch origin main
   python tools/gen_protocol_lock.py --ref origin/main
   ```

   This rewrites `protocol.lock.json` and every embedded pin constant in one
   shot, and running it twice is harmless (zero diff).
4. Commit the result as its own PR (`fix(lock): repin ...`) and merge it.
   Verify goes green.

Until step 4 merges, everything out there keeps fetching the previous pinned
commit — old but verified, never unverified. A PR that touches **no** locked
file stays green throughout (except while `main` itself is between steps 2
and 4, in which case the red is inherited from `main`, not caused by the PR —
re-run the check after the repin merges).

## 3. "I want new workflows distributed to apps"

Distributed workflows (`workflows/.rok/*` such as `agent.yml`, plus
`maintenance.yml` and `sync_workspace.yml`) reach a repo's
`.github/workflows/` only when `initiate.py` runs **locally** in that repo —
CI runs skip this on purpose (the CI token cannot write workflows).

1. If you changed the canonical workflow in this repo, land it first — and if
   it is a locked file (`maintenance.yml` is), follow scenario 2 so the lock
   is repinned.
2. In each app repo where you want it, re-run the installer
   (`curl -sSL https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.sh | bash`)
   or run `initiate.py` from an up-to-date clone of this repo. Re-running the
   installer is also what refreshes the repo's `.rokct/initiate.py` to the
   newest pinned protocol version — running the repo's own `.rokct/initiate.py`
   deliberately never updates itself (it prints "a newer protocol version is
   available" instead).
3. Which variant a repo gets is decided by `workflows/.rok/distribution.json`:
   repos listed under `full_trigger_repos` get the full workflow; every other
   repo gets the trimmed variant under the same name. RokctAI repos only.
4. Commit the updated `.github/workflows/` files in the app repo.

You do **not** need to re-run `initiate.py` after SDK updates (scenario 1) or
after lock bumps you don't want to roll out yet — apps keep working, pinned to
the version they already have.

For the full mechanics (what exactly is pinned, verifier modes, the escape
hatch), see [tools/README.md](../tools/README.md).
