# Composer Templates

The `.json` files in this folder (`betassist.json`, `customer.json`, `driver.json`,
`launch_deliver.json`, `launch_manager.json`, `launcher.json`, `manager.json`, `polaris.json`,
`pos.json`, `supacharge.json`) are **templates**, not active configuration.

To build a given app variant:

1. Pick the template matching the variant you want to build.
2. Copy it to `RokctApp/composer.json` (the app root), replacing whatever is currently there.
3. Run the compose/install scripts from `RokctApp/` as normal.

The relative paths inside each template (e.g. `../core/core/dart`) are written assuming the file
sits at `RokctApp/composer.json` — one level up from the `RokctApp/` folder reaches the other
sibling repos under `RokctAI/`. They will look "broken" if resolved from inside this `composer/`
folder directly (which is one level too deep) — that's expected; they are not meant to be run from
here.

There is currently no automated script that performs the copy/rename step — it's manual.
