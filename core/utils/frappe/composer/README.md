# Composer Templates (Frappe)

The `.json` files in this folder (currently `rcore.json`) are **templates**, not active
configuration — the frappe analog of `core/utils/flutter/composer/*.json`.

To build a given backend shell:

1. Pick the template matching the shell you want to compose (e.g. `rcore.json` for the
   rcore tenant backend).
2. Copy it to that shell repo's root as `composer.json` — e.g. `rcore/composer.json`.
3. Run the compose script from that shell's root as normal
   (`python3 .rokct/skills/.rok/frappe/scripts/compose.py`, provisioned by
   `.rokct/initiate.py`).

**A shell with no `composer.json` at its root cannot compose.** `compose_backend.py`
exits early ("No composer.json found") — the shell keeps whatever composed output was
last committed, silently stale.

**These templates are the canonical module list.** A change to a shell's SDK set
(adding a module, disabling one, changing a source path) belongs HERE, mirrored to the
shell repo's committed `composer.json` — the same canonical-template model the flutter
side uses. Editing only the shell repo's copy leaves the protocol's record of the app
graph wrong.

**Sibling checkout layout.** The relative `path` entries inside each template (e.g.
`../core/base/frappe`) are written assuming the file sits at the shell repo root — one
level up from the shell reaches the other sibling repos under `RokctAI/`. When a
sibling checkout is absent, the composer clones the module's `git` repo instead (a full
40-char commit `ref` is then required unless `ROKCT_ALLOW_UNPINNED_SDKS=1`).

**Scaffolding a brand-new shell.** Copy a template (adjusting `"name"`) into an empty
repo as `composer.json` and run compose — when the target app package
(`<name-without-_app>/`) does not exist, `compose_backend.py` lays down the tokenized
shell skeleton from `core/utils/frappe/templates/shell/` before composing (also
available on demand via `--scaffold`; existing files are never overwritten). See
`core/utils/frappe/templates/shell/README.md`.

There is currently no automated script that performs the copy/rename step — it's
manual, matching the flutter composer templates.
