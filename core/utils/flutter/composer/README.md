# Composer Templates

The `.json` files in this folder (`betassist.json`, `customer.json`, `drive.json`, `driver.json`, `forex.json`,
`launcher.json`, `manager.json`, `photos.json`, `polaris.json`, `radio.json`, `rokct.json`, `sticks.json`, `supacharge.json`) are
**templates**, not active configuration.

There is no `launch_manager.json` or `launch_deliver.json`: no shell ever copied either as its
`composer.json`, and `launcher.json` is the one launcher template (owner ruling, 2026-09-21:
"delete other launch_* in protocol").

There is no `pos.json`: pos became manager, so the pos and manager profiles were merged and
`manager.json` is the only template for that role (owner ruling: "delete pos.json" / "pos became
manager. we drop pos/ by merging pos and manager").

To build a given app variant:

1. Pick the template matching the variant you want to build.
2. Copy it to that app's root as `composer.json` — e.g. `supacharge/composer.json`,
   `paas_driver/composer.json`. (This step used to read "copy to `RokctApp/composer.json`", from when
   there was one app directory whose manifest you swapped per variant. Each variant now has its own
   repo, so the copy is once per app rather than once per build.)
3. Run the compose/install scripts from that app's directory as normal.

**An app with no `composer.json` at its root cannot compose, and nothing says so.** CI gates the whole
compose step on the file existing (`universal-flutter-build.yml`, `if [ -f "composer.json" ]`), so a
missing one means compose is skipped silently and the build proceeds against whatever is already in
the repo. As of 2026-08-02 `minilauncher` had a template here and no `composer.json` — it is not
wired, and this is how that happens unnoticed. (`paas_pos` was in the same state until its
profile was folded into `manager.json`.)

**Check the `package_name` before copying.** Compose calls `update_pubspec_name()`, so the value in
the template REWRITES the app's `pubspec.yaml` name. If they disagree the app's Dart package is
renamed and every `package:` import must follow. `launcher.json` says `launcher` while
`minilauncher/pubspec.yaml` says `minimal_launcher` — copying as-is would rename the package.

**Extra roles (`roles`).** An SDK entry may carry `"roles": ["manager"]` (a list of role names). The
marker `.rokct/config/app_type` stays the app's primary role; the listed roles are added for that one
SDK only: the SDK keeps those roles' `lib/src/<role>/` folders and merges their `app_type` flavor
blocks (the marker's own role wins where a key cannot be combined). Without `roles` nothing changes.
`rokct.json` uses it: the ROKCT app has its own marker (`rokct`, so its Play package key is
`ROKCT_ANDROID_PACKAGE_NAME`) and takes the manager role from every SDK.

**Why the copy is per-app rather than derived** (e.g. from `.rokct/config/app_type`): an app can pin
an SDK set that differs from the template's current state. `app_type` is a different mechanism
entirely — it selects which file variants an SDK installs, via `app_type` blocks inside SDK
manifests. It does not choose a composer manifest (and `roles` above only adds roles per SDK).

The relative paths inside each template (e.g. `../core/core/dart`) are written assuming the file
sits at `RokctApp/composer.json` — one level up from the `RokctApp/` folder reaches the other
sibling repos under `RokctAI/`. They will look "broken" if resolved from inside this `composer/`
folder directly (which is one level too deep) — that's expected; they are not meant to be run from
here.

There is currently no automated script that performs the copy/rename step — it's manual.
