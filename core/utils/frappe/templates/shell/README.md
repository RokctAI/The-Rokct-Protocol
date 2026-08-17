# Frappe Shell Skeleton Templates

The files in this folder are the tokenized skeleton of a frappe app shell — the
backend analog of the dart app-shell templates in `RokctAI/core`'s
`base/dart/templates/`. They are **templates, not an installable app**: `{app_name}`
and `{module_name}` tokens (in file contents AND in the `{app_name}/`,
`{module_name}/` directory names) are resolved at scaffold time by
`compose_backend.py`.

## What's here

```text
pyproject.toml                      # flit packaging, name = {app_name}
setup.py                            # setuptools mirror of the same identity
MANIFEST.in                         # asset include rules for the app package
{app_name}/__init__.py              # app package marker + __version__
{app_name}/hooks.py                 # shell-owned identity keys + website-rules
                                    # placeholder; the composer appends its
                                    # dynamic-hooks fence at the end
{app_name}/install.py               # minimal before_install/after_install
{app_name}/modules.txt              # pre-seeded with the in-shell module
{app_name}/patches.txt              # empty; compose appends patch entries
{app_name}/{module_name}/__init__.py        # the in-shell module package
{app_name}/{module_name}/doctype/__init__.py
```

`{module_name}` here is the shell's own in-shell module, which is named after the app
(the rcore layout: app package `rcore/` containing module package `rcore/rcore/`), so
scaffolding resolves both tokens to the same value.

## How scaffolding runs

`compose_backend.py` lays these files down (tokens resolved) when either:

- the target app package derived from `composer.json` (`"name"` minus a trailing
  `_app`) does not exist in the shell repo — a brand-new shell; or
- compose is invoked with an explicit `--scaffold` flag.

Scaffolding is **strictly additive**: a destination file that already exists is never
touched, so running `--scaffold` against an existing shell is a no-op for every file
the shell already has. Derived from rcore's real shell but kept generic — no
rcore-specific content (no legacy `paas.*` aliases, no database-extension install
steps).

## Keeping the embedded copies in sync

The frappe skill wrapper fetches `compose_backend.py` as a single standalone file, so
at scaffold time inside a shell there is no protocol checkout to read this folder
from. The composer therefore embeds these templates verbatim (`SHELL_TEMPLATES` in
`compose_backend.py`); this folder is the canonical, reviewable copy.
`core/utils/frappe/tests/test_compose_backend.py` fails if the two ever differ —
edit both together (or edit `SHELL_TEMPLATES` and regenerate this folder from it).
