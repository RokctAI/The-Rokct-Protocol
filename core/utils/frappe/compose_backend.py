# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

import os
import sys
import shutil
import json
import re
import subprocess
import urllib.error
import urllib.request

PROJECT_ROOT = os.getcwd()

COMPILED_DOCTYPES = {}  # maps doctype_name -> module_name (module-root doctype/ trees)

# DocType dirs found nested under a module's src/ tree (src/**/doctype/<dt>/).
# Tracked separately from COMPILED_DOCTYPES: module-root duplicates have
# always been hard errors, but src-nested doctypes were historically
# unguarded, so a collision involving one only WARNS (escalating under
# ROKCT_COMPOSE_STRICT) instead of breaking composes that succeed today.
SRC_NESTED_DOCTYPES = {}  # maps doctype_name -> module_name

# Directories/files this compose run wrote into the app shell. Scanned by
# lint_composed_tokens() after composition for unresolved template tokens.
COMPOSED_PATHS = []

# File extensions whose content gets template-token substitution when copied
# (everything else is byte-copied verbatim).
SUBSTITUTABLE_EXTENSIONS = (".py", ".js", ".html", ".json")

# The composer's template tokens. Only these two exact literals are ever
# substituted or linted — generic {...} braces (Python format strings, Jinja,
# JS template literals) are none of the composer's business.
TOKEN_APP_NAME = "{app_name}"
TOKEN_MODULE_NAME = "{module_name}"

# Strict compose mode: every compose_warning() below escalates from a printed
# warning to a hard error, so CI can refuse a compose whose output is known to
# be degraded. Same env-flag convention as the flutter installer
# (core/utils/flutter/sdk_installer_base.py) and ROKCT_ALLOW_UNPINNED_SDKS.
# Default (unset) keeps warn-and-continue so currently-green composes stay
# green.
COMPOSE_STRICT_ENV = "ROKCT_COMPOSE_STRICT"


def _compose_strict():
    return os.environ.get(COMPOSE_STRICT_ENV, "").lower() in ("1", "true", "yes")


def compose_warning(message):
    """Loudly surface a compose step that did not fully apply.

    Prints to BOTH stdout (the composer's existing logging stream) and stderr
    (so wrappers that only surface stderr still show it). With
    ROKCT_COMPOSE_STRICT=1/true/yes the warning is escalated to a hard error
    instead, failing the compose with a non-zero exit.
    """
    line = f"  [!] WARNING: {message}"
    print(line)
    if sys.stderr is not sys.stdout:
        print(line, file=sys.stderr)
    if _compose_strict():
        raise RuntimeError(
            f"{COMPOSE_STRICT_ENV} is set: escalating compose warning to error: {message}"
        )


def resolve_tokens(content, app_name, module_name=None):
    """Replace the composer's template tokens in text content.

    {app_name} -> the target shell's app package name (as always).
    {module_name} -> the composing module's manifest "name" (the value the
    primary DocType JSON "module" key is rewritten to), when provided.
    """
    content = content.replace(TOKEN_APP_NAME, app_name)
    if module_name is not None:
        content = content.replace(TOKEN_MODULE_NAME, module_name)
    return content


def copy_doctype_tree_resolving(src, dst, app_name, module_name):
    """Copy a DocType directory, substituting template tokens where present.

    DocType trees used to be shutil.copytree'd verbatim, which shipped
    literal {app_name} strings into composed controllers (invalid imports at
    best, silently broken runtime dotted paths at worst — e.g. the pay SDK's
    gateway_controller values). Substitutable extensions whose content
    actually contains a token are rewritten; every other file is byte-copied
    with shutil.copy2, so tokenless files stay byte-identical to the old
    copytree behavior.
    """
    os.makedirs(dst, exist_ok=True)
    for item in os.listdir(src):
        s = os.path.join(src, item)
        d = os.path.join(dst, item)
        if os.path.isdir(s):
            copy_doctype_tree_resolving(s, d, app_name, module_name)
            continue
        copy_file_resolving(s, d, app_name, module_name)


def copy_file_resolving(s, d, app_name, module_name):
    """Copy ONE file, substituting template tokens only where present.

    A substitutable file whose content actually carries a token is
    rewritten; every other file is byte-copied with shutil.copy2, so
    tokenless files stay byte-identical to a plain copy.
    """
    if s.endswith(SUBSTITUTABLE_EXTENSIONS):
        with open(s, "rb") as sf:
            raw = sf.read()
        if TOKEN_APP_NAME.encode() in raw or TOKEN_MODULE_NAME.encode() in raw:
            text = resolve_tokens(raw.decode("utf-8"), app_name, module_name)
            # newline="" keeps the source file's own line endings intact.
            with open(d, "w", encoding="utf-8", newline="") as df:
                df.write(text)
            return
    shutil.copy2(s, d)


def merge_global_templates_tree(src, dst, app_name, module_label, module_name, rel=""):
    """Merge a module's src/templates/ tree into the app-level templates/ dir.

    Frappe resolves portal pages from {app}/templates/pages/<route>.html (with
    an optional sibling <route>.py context controller), so an SDK module ships
    portal pages under a top-level src/templates/ carve-out — exactly like
    src/www/ and src/patches/, it composes into the APP shell rather than the
    module package, and composes for every persona (top-level src/ entries are
    never persona-stripped; do not nest templates under a persona folder).

    Unlike the flat www/ merge above, templates trees are nested
    (templates/pages/, templates/includes/, ...), so this merges recursively:
    directories UNION across modules and the shell, while a duplicate
    destination FILE path is a hard error — the same collision policy as the
    www/ and patches/ merges. Substitutable extensions get token resolution;
    everything else is byte-copied. No __init__.py is scaffolded, matching the
    www/ redirect: Python 3 imports {app}.templates.pages.<route> controllers
    through implicit namespace subpackages of the regular app package.
    """
    os.makedirs(dst, exist_ok=True)
    for item in sorted(os.listdir(src)):
        s_path = os.path.join(src, item)
        d_path = os.path.join(dst, item)
        rel_item = f"{rel}{item}"
        if os.path.isdir(s_path):
            merge_global_templates_tree(
                s_path, d_path, app_name, module_label, module_name, rel=f"{rel_item}/"
            )
            continue
        if os.path.exists(d_path):
            raise ValueError(
                f"CRITICAL ERROR: Duplicate global templates file '{rel_item}' "
                f"detected! (Attempted by: '{module_name}'). Failing build."
            )
        if item.endswith(SUBSTITUTABLE_EXTENSIONS):
            with open(s_path, "r", encoding="utf-8") as sf:
                content = sf.read()
            content = resolve_tokens(content, app_name, module_label)
            with open(d_path, "w", encoding="utf-8") as df:
                df.write(content)
        else:
            shutil.copy2(s_path, d_path)
        COMPOSED_PATHS.append(d_path)


def rewrite_src_nested_doctype_modules(dest_dir, module_label, module_name):
    """Rewrite the "module" key of DocType JSONs nested under a src/ tree.

    The primary-JSON module rewrite has always applied to module-root
    doctype/<dt>/<dt>.json files, but doctypes shipped under
    src/**/doctype/<dt>/<dt>.json escaped it — the agent SDK composed 13 such
    JSONs with a literal "module": "{module_name}". The {module_name} token
    substitution now resolves those; this pass additionally pins any
    src-nested primary JSON whose "module" still disagrees with the manifest
    name, and registers the doctype for duplicate detection (warn-only — see
    SRC_NESTED_DOCTYPES).
    """
    for root, dirs, _files in os.walk(dest_dir):
        if os.path.basename(root) != "doctype":
            continue
        for dt in sorted(dirs):
            dt_dir = os.path.join(root, dt)
            if dt in COMPILED_DOCTYPES and COMPILED_DOCTYPES[dt] != module_name:
                compose_warning(
                    f"src-nested DocType '{dt}' in module '{module_name}' collides "
                    f"with module '{COMPILED_DOCTYPES[dt]}'s doctype/ tree."
                )
            elif dt in SRC_NESTED_DOCTYPES and SRC_NESTED_DOCTYPES[dt] != module_name:
                compose_warning(
                    f"src-nested DocType '{dt}' in module '{module_name}' collides "
                    f"with module '{SRC_NESTED_DOCTYPES[dt]}'s src/ tree."
                )
            else:
                SRC_NESTED_DOCTYPES[dt] = module_name
            json_file = os.path.join(dt_dir, f"{dt}.json")
            if not os.path.exists(json_file):
                continue
            try:
                with open(json_file, "r", encoding="utf-8") as jf:
                    data = json.load(jf)
                if data.get("module") != module_label:
                    data["module"] = module_label
                    with open(json_file, "w", encoding="utf-8") as jf:
                        json.dump(data, jf, indent=2)
                    print(
                        f"[+] Pinned src-nested DocType module: {dt} -> {module_label}"
                    )
            except Exception as je:
                compose_warning(
                    f"Failed to inject module into src-nested {dt}.json: {je}"
                )


def relocate_persona_doctypes(
    dest_persona_dir, dest_module_path, persona, module_label, module_name
):
    """Relocate DocType dirs composed under a persona folder to the module root.

    Persona-scoped doctypes ship at src/<persona>/doctype/<dt>/ in an SDK
    module. Frappe only model-syncs and imports doctypes living at
    {app}/{module}/doctype/<dt>/, so a doctype left under the composed persona
    subtree ({app}/{module}/<persona>/doctype/<dt>/) is invisible to
    `bench migrate` and unimportable as a controller. Persona scoping itself
    already happened before this runs: excluded personas' folders were never
    copied at all, so every doctype found here belongs in this compose.

    Each */doctype/<dt>/ dir found under the copied persona folder is MOVED to
    {app}/{module}/doctype/<dt>/ and given the exact module-root doctype
    treatment:

      * registration in COMPILED_DOCTYPES with the HARD duplicate error —
        warn-only is no longer safe once relocation makes collisions real
        (two personas' same-named doctypes would land in the same directory,
        which also means a role-less compose of both personas hard-errors on
        a cross-persona duplicate);
      * the primary <dt>.json "module" key rewrite to the manifest name.

    Token substitution already happened when copy_and_resolve wrote the
    persona tree, so the move ships fully resolved content. The emptied
    nested doctype/ dir is removed so no duplicate class files remain in the
    persona subtree.
    """
    doctype_dirs = []
    for root, dirs, _files in os.walk(dest_persona_dir):
        if os.path.basename(root) == "doctype":
            doctype_dirs.append(root)
            dirs[:] = []  # never descend into a doctype tree itself
    dest_doctype_root = os.path.join(dest_module_path, "doctype")
    for dt_parent in doctype_dirs:
        for dt in sorted(os.listdir(dt_parent)):
            dt_dir = os.path.join(dt_parent, dt)
            if not os.path.isdir(dt_dir):
                continue
            if dt in COMPILED_DOCTYPES:
                raise ValueError(
                    f"CRITICAL ERROR: Duplicate DocType '{dt}' detected! "
                    f"Persona folder '{persona}' of module '{module_name}' "
                    f"collides with module '{COMPILED_DOCTYPES[dt]}'. "
                    f"Failing build."
                )
            COMPILED_DOCTYPES[dt] = module_name
            if dt in SRC_NESTED_DOCTYPES and SRC_NESTED_DOCTYPES[dt] != module_name:
                compose_warning(
                    f"Persona DocType '{dt}' in module '{module_name}' collides "
                    f"with module '{SRC_NESTED_DOCTYPES[dt]}'s src/ tree."
                )
            os.makedirs(dest_doctype_root, exist_ok=True)
            dest_dt_path = os.path.join(dest_doctype_root, dt)
            shutil.move(dt_dir, dest_dt_path)
            # Overwrite the DocType module property to match composition
            # target — same semantics as the module-root doctype/ pass.
            json_file = os.path.join(dest_dt_path, f"{dt}.json")
            if os.path.exists(json_file):
                try:
                    with open(json_file, "r", encoding="utf-8") as jf:
                        data = json.load(jf)
                    data["module"] = module_label
                    with open(json_file, "w", encoding="utf-8") as jf:
                        json.dump(data, jf, indent=2)
                    print(
                        f"[+] Relocated persona DocType: {persona}/{dt} -> "
                        f"{module_name}/doctype/{dt} (module: {module_label})"
                    )
                except Exception as je:
                    compose_warning(
                        f"Failed to inject module into relocated {dt}.json: {je}"
                    )
            else:
                print(
                    f"[+] Relocated persona DocType: {persona}/{dt} -> "
                    f"{module_name}/doctype/{dt}"
                )
        # Drop the emptied nested doctype/ dir (an __init__.py scaffold file
        # is part of the relocated tree's old home, not persona code).
        if not [e for e in os.listdir(dt_parent) if e != "__init__.py"]:
            shutil.rmtree(dt_parent)


def lint_composed_tokens(paths, project_root):
    """Post-compose token lint over everything this run wrote.

    Scans the composed output (module trees, app-level www/, templates/ and
    patches/ files) for the composer's two literal tokens in substitutable-extension
    files. Only the exact literals {app_name} and {module_name} are flagged —
    generic {...} braces (Python format strings, Jinja templates) are
    legitimate and ignored. Any hit is a loud warning naming every offending
    file, escalating to a hard error under ROKCT_COMPOSE_STRICT=1.
    """
    tokens = (TOKEN_APP_NAME.encode(), TOKEN_MODULE_NAME.encode())
    offenders = []
    for base in paths:
        if os.path.isfile(base):
            candidates = [base]
        elif os.path.isdir(base):
            candidates = [
                os.path.join(root, name)
                for root, _dirs, files in os.walk(base)
                for name in files
            ]
        else:
            continue
        for fp in candidates:
            if not fp.endswith(SUBSTITUTABLE_EXTENSIONS):
                continue
            try:
                with open(fp, "rb") as fh:
                    raw = fh.read()
            except OSError:
                continue
            found = [t.decode() for t in tokens if t in raw]
            if found:
                offenders.append((os.path.relpath(fp, project_root), found))
    if offenders:
        detail = "; ".join(f"{rel} ({', '.join(found)})" for rel, found in offenders)
        compose_warning(
            f"{len(offenders)} composed file(s) still contain literal template "
            f"tokens: {detail}"
        )
    else:
        print("[+] Token lint: no unresolved template tokens in composed output.")
    return offenders


# Manifest hook values are interpolated into generated Python source
# (hooks.py). Before any value is written it is validated against a tight
# regex so a malicious or malformed manifest cannot inject arbitrary code
# through these fields (e.g. a doc_events handler of
# "x'; import os; os.system('id') #" used to land verbatim in hooks.py).
# Values are also embedded with repr()/!r for defense in depth.
#   - "dotted": a Python import path (handler / method / class path)
#   - "gateway_key": a whitelisted_methods KEY - a dotted path optionally
#     carrying a single "<gateway>:" prefix (e.g. "control:claim_tender"),
#     the shape frappe's cmd registry accepts for gateway-scoped commands.
#     Values stay strictly "dotted"; only keys may carry the prefix.
#   - "doctype": a frappe DocType name (word chars, spaces, hyphens), or the
#     literal "*" wildcard frappe accepts for doc_events registered against
#     every doctype (e.g. core/telemetry's trace-context injector).
#   - "event": a doc_event / scheduler bucket name (word chars)
#   - "cron": a cron expression key inside scheduler_events["cron"]
#     (croniter syntax: digits, *, /, ",", "-", spaces, month/day names)
#   - "js_path": a doctype_js / doctype_list_js file path — slash-separated
#     word/hyphen segments ending in ".js". Segments admit no dots, so a
#     manifest can never smuggle "../" traversal into the emitted hooks.py.
_HOOK_VALUE_PATTERNS = {
    "dotted": re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$"),
    "gateway_key": re.compile(
        r"^([A-Za-z_][A-Za-z0-9_]*:)?[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$"
    ),
    "doctype": re.compile(r"^(\*|[\w \-]+)$"),
    "event": re.compile(r"^\w+$"),
    "cron": re.compile(r"^[\w*/,\- ]+$"),
    "js_path": re.compile(r"^[\w\-]+(/[\w\-]+)*\.js$"),
}

# Manifest hook keys that map a DocType name to desk JS file path(s):
# doctype_js (form scripts) and doctype_list_js (list-view scripts).
DOCTYPE_JS_HOOK_KEYS = ("doctype_js", "doctype_list_js")


def rewrite_doctype_js_hook_paths(manifest, module_name):
    """Prefix manifest doctype_js / doctype_list_js paths with the composed
    module folder name.

    Frappe resolves each doctype_js / doctype_list_js hook value with
    frappe.get_app_path(app, *path.split("/")) and inlines the file
    server-side, so the registered path must be relative to the APP package
    dir. A module manifest cannot know which shell it will compose into, so
    it declares each path relative to its OWN src/ tree — mirroring where the
    file lands inside the composed module, e.g.
    "control/public/js/company_subscription_list.js" for a file shipped at
    src/control/public/js/. This pass rewrites every entry to
    "<module_dir>/<path>" once the composed module folder name is known, so
    merge_hooks can emit the values verbatim. It runs over the top-level
    hooks block AND every app_type persona block (harmless for personas that
    do not merge — their blocks are never emitted), and normalizes a single
    path string to a one-element list. NOTE: form JS shipped INSIDE a
    doctype/<dt>/ tree (<dt>.js / <dt>_list.js) needs no declaration at all —
    Frappe auto-loads those from the doctype directory."""
    blocks = [manifest.get("hooks") or {}]
    for flavor in (manifest.get("app_type") or {}).values():
        blocks.append((flavor or {}).get("hooks") or {})
    for hooks_block in blocks:
        for key in DOCTYPE_JS_HOOK_KEYS:
            mapping = hooks_block.get(key)
            if not isinstance(mapping, dict):
                continue
            hooks_block[key] = {
                dt: [
                    f"{module_name}/{p}"
                    for p in ([paths] if isinstance(paths, str) else list(paths))
                ]
                for dt, paths in mapping.items()
            }


def _validate_hook_value(value, kind, module_name, key):
    """Fail the compose loudly if a manifest hook value doesn't match its
    expected shape, naming the offending module and hook key. Returns the
    value unchanged when valid so it can be used inline."""
    pattern = _HOOK_VALUE_PATTERNS[kind]
    if not isinstance(value, str) or not pattern.match(value):
        print(
            f"[-] Composition aborted: invalid {kind} value {value!r} in module "
            f"'{module_name}' hook '{key}'. Refusing to write it into generated "
            f"hooks.py (possible code injection or malformed manifest)."
        )
        sys.exit(1)
    return value


def load_composer_config():
    composer_path = os.path.join(PROJECT_ROOT, "composer.json")
    if not os.path.exists(composer_path):
        print(f"[-] No composer.json found in {PROJECT_ROOT}. Skipping.")
        sys.exit(0)
    with open(composer_path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Composer template registry.
#
# The protocol keeps one composer.json template per product in
# core/utils/frappe/composer/ (rcore.json, supacharge.json, ...). A shell repo
# can stay THIN: instead of committing a hand-copied composer.json, it commits
# only the one-line .rokct/config/app_type file naming the template to
# compose. This is the exact model the flutter side already uses
# (universal-flutter-build.yml overwrites the shell's composer.json from
# core/utils/flutter/composer/<app_type>.json) — the same one-line value
# doubles as the shell's role/persona marker and as its template name; the
# two have shared a namespace on the flutter side since role-based
# composition landed (supacharge/manager/driver are both personas and
# template file names).
#
# Resolution is shared with the Next.js composer: core/utils/nextjs/
# sdk_composer.py imports this module and calls resolve_composer_config(), so
# both stacks resolve WHAT to compose from this one registry with this one
# implementation. A product template may carry BOTH a "modules" array (read
# by this frappe engine) and an "sdks" array (read by the Next.js composer);
# each composer reads only its own key.
#
# Backward compatibility is absolute: a shell with no app_type file, or with
# an app_type value that names no template in the registry (a plain role
# marker like "manager"), composes from its committed composer.json exactly
# as before — resolve_composer_config() is then a no-op.
# ---------------------------------------------------------------------------

COMPOSER_TEMPLATES_DIR_ENV = "ROKCT_COMPOSER_TEMPLATES_DIR"
PROTOCOL_DIR_ENV = "ROKCT_PROTOCOL_DIR"
PROTOCOL_REPO_NAME = "The-Rokct-Protocol"
COMPOSER_TEMPLATES_REL = "core/utils/frappe/composer"
COMPOSER_TEMPLATES_RAW_BASE = (
    "https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/"
    + COMPOSER_TEMPLATES_REL
)

# Template names are plain registry file basenames — anything else (path
# separators, dots, uppercase) is treated as "not a template name" so a role
# marker can never be turned into a path traversal or a surprise fetch.
_TEMPLATE_NAME_RE = re.compile(r"^[a-z0-9_-]+$")


def _local_template_dirs(project_root):
    """Candidate registry directories, most explicit first: the env override,
    an explicitly named protocol checkout, the checkout this file itself sits
    in (when running from a protocol clone rather than a standalone fetch),
    and the standard sibling-checkout workspace layout that
    resolve_module_sources() already relies on."""
    dirs = []
    env_dir = os.environ.get(COMPOSER_TEMPLATES_DIR_ENV)
    if env_dir:
        dirs.append(env_dir)
    protocol_dir = os.environ.get(PROTOCOL_DIR_ENV)
    if protocol_dir:
        dirs.append(os.path.join(protocol_dir, *COMPOSER_TEMPLATES_REL.split("/")))
    here = os.path.dirname(os.path.abspath(__file__))
    dirs.append(os.path.join(here, "composer"))
    dirs.append(
        os.path.join(
            os.path.dirname(os.path.abspath(project_root)),
            PROTOCOL_REPO_NAME,
            *COMPOSER_TEMPLATES_REL.split("/"),
        )
    )
    return dirs


def fetch_composer_template(name, project_root=None):
    """Look up registry template <name>.json.

    Returns (template_text, source_description), or (None, None) when no
    template by that name exists — the caller then treats the app_type value
    as a plain role marker, exactly the legacy semantics.

    A locally available registry directory is authoritative: when one exists,
    a missing name is a definitive miss and no network is touched (so
    role-marker shells in a normal workspace stay fully offline). Only when
    no local registry can be found at all does this fall back to fetching the
    template from raw.githubusercontent.com — data-only, mirroring the
    flutter CI's curl of composer/<app_type>.json; no fetched code is ever
    executed."""
    root = project_root or PROJECT_ROOT
    if not name or not _TEMPLATE_NAME_RE.match(name):
        return None, None
    filename = f"{name}.json"
    saw_local_registry = False
    for d in _local_template_dirs(root):
        if not os.path.isdir(d):
            continue
        saw_local_registry = True
        candidate = os.path.join(d, filename)
        if os.path.isfile(candidate):
            with open(candidate, "r", encoding="utf-8") as fh:
                return fh.read(), candidate
    if saw_local_registry:
        return None, None
    url = f"{COMPOSER_TEMPLATES_RAW_BASE}/{filename}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "rokct-composer"})
        with urllib.request.urlopen(req, timeout=30) as resp:
            if resp.status == 200:
                return resp.read().decode("utf-8"), url
    except Exception as e:
        if isinstance(e, urllib.error.HTTPError) and e.code == 404:
            # No such template — a plain role marker. Quiet, legacy path.
            return None, None
        compose_warning(
            f"composer template lookup for '{name}' failed ({url}): {e}. "
            f"Falling back to the committed composer.json."
        )
    return None, None


def resolve_composer_config(project_root=None):
    """Materialize composer.json from the registry template this shell's
    .rokct/config/app_type names, when it names one.

    Returns True when composer.json was (re)written from a template, False
    when the legacy path applies (no marker, or a marker that is a role, not
    a template). When a template resolves it WINS over a committed
    composer.json — the registry templates are canonical (same clobber
    semantics as the flutter CI's manifest-selection step)."""
    root = project_root or PROJECT_ROOT
    name = resolve_app_type(root)
    if not name:
        return False
    text, source = fetch_composer_template(name, root)
    composer_path = os.path.join(root, "composer.json")
    if text is None:
        if not os.path.exists(composer_path):
            print(
                f"[!] .rokct/config/app_type is '{name}' but no composer template "
                f"'{name}.json' was found in the registry ({COMPOSER_TEMPLATES_REL}/) "
                f"and no composer.json is committed — nothing to compose."
            )
        return False
    try:
        json.loads(text)
    except Exception as e:
        compose_warning(
            f"composer template '{name}' from {source} is not valid JSON: {e}. "
            f"Falling back to the committed composer.json."
        )
        return False
    action = "overwritten" if os.path.exists(composer_path) else "written"
    with open(composer_path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)
    print(f"[+] composer.json {action} from registry template '{name}' ({source})")
    return True


def resolve_app_type(project_root=None):
    """This shell's own role marker (e.g. 'manager', 'customer', 'pos'), read
    from .rokct/config/app_type - a plain one-line text file checked into the
    shell's own repo, relative to the same root the shell's composer.json is
    read from. Mirrors core/utils/flutter/sdk_installer_base.py's
    resolve_app_type() - kept as a local copy rather than imported, since each
    stack's composer is fetched and used independently.

    Returns None when the file doesn't exist - manifests with no matching
    app_type block then behave exactly as before (nothing filtered, nothing
    extra merged). A tenant backend that deliberately serves ALL roles at
    once simply declares no marker: absence = all.

    The same one-line value is also the shell's composer TEMPLATE name when
    it matches a registry template (see resolve_composer_config above) —
    the shared-namespace convention the flutter side established."""
    path = os.path.join(project_root or PROJECT_ROOT, ".rokct", "config", "app_type")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            value = f.read().strip().lower()
            return value or None
    return None


def extract_repo_name(git_url):
    url_path = git_url.rstrip("/")
    if url_path.endswith(".git"):
        url_path = url_path[:-4]
    return os.path.basename(url_path)


def get_subpath_in_repo(local_path, repo_name):
    normalized = local_path.replace("\\", "/").strip("/")
    parts = normalized.split("/")
    for idx, part in enumerate(parts):
        if part.lower() == repo_name.lower():
            return "/".join(parts[idx + 1 :])
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return normalized


def remove_readonly(func, path, excinfo):
    import stat

    os.chmod(path, stat.S_IWRITE)
    func(path)


def authenticated_git_url(git_url):
    """Inject MONOREPO_PAT for github.com HTTPS clones so private SDK repos
    (all SDKs are now private) resolve without ambient git credentials —
    same token/URL shape universal-frappe-ci.yml already uses for its
    own private-repo clone path."""
    token = os.environ.get("MONOREPO_PAT")
    if token and git_url.startswith("https://github.com/"):
        return git_url.replace(
            "https://github.com/", f"https://x-access-token:{token}@github.com/"
        )
    return git_url


def clone_ref(git_url, ref, dest_dir):
    """Clone git_url at ref into dest_dir. Branch and tag refs take the exact
    shallow path used before (`git clone -b <ref> --depth 1`); when that
    fails - most notably because ref is a commit SHA, which `git clone -b`
    does not accept - fall back to a full clone followed by
    `git checkout <ref>`. Raises on failure (subprocess.CalledProcessError,
    or subprocess.TimeoutExpired when a clone stalls on the network);
    the caller decides how to fail the build.

    git has no network-stall timeout of its own, so a dead TCP connection
    mid-clone hangs forever - in CI that squats a runner for hours (see the
    universal lint/build "Compose SDK Modules" steps). The 10-minute cap
    turns a stall into a loud, retryable failure."""
    try:
        subprocess.run(
            ["git", "clone", "-b", ref, "--depth", "1", git_url, dest_dir],
            check=True,
            timeout=600,
        )
        return
    except subprocess.CalledProcessError:
        print(
            f"[*] `git clone -b {ref}` failed (ref is not a branch/tag?). Retrying as full clone + checkout, which also accepts commit SHAs..."
        )
    if os.path.exists(dest_dir):
        shutil.rmtree(dest_dir, onerror=remove_readonly)
    subprocess.run(["git", "clone", git_url, dest_dir], check=True, timeout=600)
    subprocess.run(["git", "-C", dest_dir, "checkout", ref], check=True)


def resolve_module_sources(modules):
    """Resolve each module's source directory for modules declared with the
    rich (source/git/ref) schema, mirroring core/utils/flutter/sdk_composer.py's
    git-group caching: a module is served from an already-checked-out sibling
    repo when present (the normal monorepo dev layout, where "path" already
    resolves relative to PROJECT_ROOT), and only cloned into .rokct/cache when
    no local copy exists (e.g. a CI checkout of a single repo). Modules using
    the plain {name, enabled, path} schema are left alone; compose_module()
    resolves their path directly, as before.
    """
    cache_base = os.path.join(PROJECT_ROOT, ".rokct", "cache")
    git_groups = {}
    for m in modules:
        if m.get("source") == "git" and m.get("git"):
            git_groups.setdefault(m["git"], []).append(m)

    resolved = {}
    if not git_groups:
        return resolved

    workspace_parent = os.path.dirname(PROJECT_ROOT)

    for git_url, group in git_groups.items():
        repo_name = extract_repo_name(git_url)
        local_repo_path = os.path.join(workspace_parent, repo_name)

        if os.path.exists(local_repo_path):
            print(
                f"[*] Found local repository for {repo_name} at {local_repo_path}. Using local copy."
            )
            repo_source_dir = local_repo_path
        else:
            ref = group[0].get("ref", "main")
            # No install.py is executed here (frappe modules are copy-based),
            # but a mutable ref still means the composed app's content cannot
            # be reproduced or verified. Require a full commit SHA, with the
            # same explicit ROKCT_ALLOW_UNPINNED_SDKS escape hatch as the
            # flutter/nextjs composers.
            if not re.fullmatch(r"[0-9a-f]{40}", (ref or "").lower()):
                if os.environ.get("ROKCT_ALLOW_UNPINNED_SDKS", "").lower() in (
                    "1",
                    "true",
                    "yes",
                ):
                    print(
                        f"[!] WARNING: cloning {git_url} at mutable ref '{ref}'; proceeding "
                        "because ROKCT_ALLOW_UNPINNED_SDKS is set. Content is UNVERIFIED."
                    )
                else:
                    module_names = ", ".join(str(m.get("name")) for m in group)
                    print(
                        f"[!] Module(s) {module_names} use mutable ref '{ref}' for {git_url}.",
                        file=sys.stderr,
                    )
                    print(
                        '[!] Pin "ref" to a full commit SHA, or set ROKCT_ALLOW_UNPINNED_SDKS=1 '
                        "to run unpinned anyway.",
                        file=sys.stderr,
                    )
                    raise ValueError(
                        f"CRITICAL ERROR: refusing to clone {git_url} at mutable ref '{ref}' "
                        f"for module(s) '{module_names}' without a pin. Failing build."
                    )
            temp_repo_dir = os.path.join(cache_base, f"{repo_name}_frappe")
            print(
                f"[*] Fetching repository {git_url} (ref {ref}) into {temp_repo_dir}..."
            )
            try:
                os.makedirs(cache_base, exist_ok=True)
                if os.path.exists(temp_repo_dir):
                    shutil.rmtree(temp_repo_dir, onerror=remove_readonly)
                clone_ref(authenticated_git_url(git_url), ref, temp_repo_dir)
                repo_source_dir = temp_repo_dir
            except Exception as e:
                # A failed clone must fail the compose loudly. The old
                # `continue` soft-skipped the group, so the modules later fell
                # through to "[-] No manifest.json found ... Skipping." and a
                # typo'd URL (or expired token) composed a quietly incomplete
                # app that still exited 0.
                module_names = ", ".join(str(m.get("name")) for m in group)
                print(
                    f"[!] Failed to clone {git_url} (ref '{ref}') needed by module(s): {module_names}: {e}"
                )
                raise ValueError(
                    f"CRITICAL ERROR: Failed to clone {git_url} (ref '{ref}') for module(s) '{module_names}'! Failing build."
                ) from e

        for m in group:
            subpath = get_subpath_in_repo(m.get("path", ""), repo_name)
            resolved[id(m)] = os.path.join(repo_source_dir, *subpath.split("/"))

    return resolved


# ---------------------------------------------------------------------------
# Frappe shell skeleton templates.
#
# The canonical, human-readable copies live in this repository at
# core/utils/frappe/templates/shell/ (mirroring core/base/dart/templates/ on
# the flutter side). They are ALSO embedded here because the frappe skill
# wrapper (core/skills/.rok/frappe/scripts/compose.py) fetches and executes
# compose_backend.py as a single standalone file — at scaffold time inside an
# app shell there is no protocol checkout to read the template files from.
# core/utils/frappe/tests/test_compose_backend.py pins the embedded copies
# byte-identical to the files on disk so the two can never drift.
#
# Keys are destination paths relative to the shell repo root; {app_name} and
# {module_name} tokens in both keys and content are resolved at scaffold time
# ({module_name} = the shell's own in-shell module, which is named after the
# app, matching the rcore layout).
# ---------------------------------------------------------------------------

_SHELL_PY_HEADER = """\
# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.
"""

SHELL_TEMPLATES = {
    "pyproject.toml": """\
[project]
name = "{app_name}"
version = "0.0.1"
description = "Composed Frappe app shell for {app_name}"
authors = [
    { name = "RokctAI", email = "admin@rokct.ai"}
]
dependencies = []


[build-system]
requires = ["flit_core >=3.4,<4"]
build-backend = "flit_core.buildapi"
""",
    "setup.py": _SHELL_PY_HEADER
    + """

from setuptools import setup, find_packages

name = "{app_name}"
version = "0.0.1"
description = "Composed Frappe app shell for {app_name}"
author = "RokctAI"
author_email = "admin@rokct.ai"
packages = find_packages()
zip_safe = False
include_package_data = True
install_requires = []

setup(
    name=name,
    version=version,
    description=description,
    author=author,
    author_email=author_email,
    packages=packages,
    zip_safe=zip_safe,
    include_package_data=include_package_data,
    install_requires=install_requires,
)
""",
    "MANIFEST.in": """\
include *.txt
include *.md
recursive-include {app_name} *.html
recursive-include {app_name} *.txt
recursive-include {app_name} *.js
recursive-include {app_name} *.css
recursive-include {app_name} *.png
recursive-include {app_name} *.svg
recursive-include {app_name} *.json
recursive-include {app_name} *.md
""",
    "{app_name}/__init__.py": _SHELL_PY_HEADER
    + """
__version__ = "0.0.1"
""",
    "{app_name}/hooks.py": _SHELL_PY_HEADER
    + """
# Shell-owned identity and hooks. The backend composer appends its generated
# fence (dynamic SDK hooks) at the END of this file on every compose — keep
# hand-written content above it and never edit the fenced block by hand.

app_name = "{app_name}"
app_title = "{app_name}"
app_publisher = "ROKCT INTELLIGENCE (PTY) LTD"
app_description = "Composed Frappe app shell"
app_email = "admin@rokct.ai"
app_license = "AGPL-3.0-only"

# Installation
# ------------
before_install = "{app_name}.install.before_install"
after_install = "{app_name}.install.after_install"

# Website Route Rules
# -------------------
# Shell-owned website routes go here, e.g.:
# website_route_rules = [
#     {
#         "from_route": "/.well-known/assetlinks.json",
#         "to_route": "{app_name}.api.app_links.get_assetlinks",
#     },
# ]
""",
    "{app_name}/install.py": _SHELL_PY_HEADER
    + """
# Minimal install surface for a freshly scaffolded shell, referenced from
# hooks.py. Grow it with site-role checks, seeders, or database extension
# setup as the shell matures (rcore/install.py is the reference example).


def before_install():
    # Runs before `bench install-app {app_name}`.
    pass


def after_install():
    # Runs after `bench install-app {app_name}`.
    pass
""",
    "{app_name}/modules.txt": """\
{module_name}
""",
    "{app_name}/patches.txt": "",
    "{app_name}/{module_name}/__init__.py": _SHELL_PY_HEADER,
    "{app_name}/{module_name}/doctype/__init__.py": _SHELL_PY_HEADER,
}


def derive_app_name(config):
    """The target shell's app package name, from composer.json or the cwd."""
    app_name = config.get("name", "").replace("_app", "")
    if not app_name:
        app_name = os.path.basename(PROJECT_ROOT)
    return app_name


def scaffold_shell(app_name, explicit=False):
    """Lay down the tokenized frappe shell skeleton for a missing app shell.

    Runs when the target app shell package does not exist yet, or on an
    explicit --scaffold flag. STRICTLY additive: a destination file that
    already exists is NEVER touched — existing shells (and any hand-edited
    file in a partially scaffolded one) are left exactly as they are.
    """
    reason = "--scaffold flag" if explicit else "target app shell missing"
    print(f"[*] Scaffolding frappe shell skeleton for '{app_name}' ({reason})...")
    written = 0
    for rel_template in sorted(SHELL_TEMPLATES):
        rel_dest = resolve_tokens(rel_template, app_name, app_name)
        dest = os.path.join(PROJECT_ROOT, *rel_dest.split("/"))
        if os.path.exists(dest):
            print(f"[*] Scaffold: kept existing {rel_dest}")
            continue
        os.makedirs(os.path.dirname(dest) or ".", exist_ok=True)
        content = resolve_tokens(SHELL_TEMPLATES[rel_template], app_name, app_name)
        with open(dest, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        print(f"[+] Scaffold: wrote {rel_dest}")
        written += 1
    if written:
        print(f"[+] Scaffolded {written} shell file(s) for '{app_name}'.")
    else:
        print("[*] Scaffold: nothing to do (all shell files already present).")


def find_target_app_dir(config):
    # Try to resolve app name from configuration or folder name
    app_name = derive_app_name(config)

    # Frappe apps are nested as apps/app_name/app_name
    target_path = os.path.join(PROJECT_ROOT, "apps", app_name, app_name)
    if not os.path.exists(target_path):
        # Fallback to local package directory in case of simple workspace
        target_path = os.path.join(PROJECT_ROOT, app_name)

    if not os.path.exists(target_path):
        print(
            f"[!] Target app package directory not found for: {app_name}. Tried: {target_path}"
        )
        sys.exit(1)

    return app_name, target_path


def compose_module(module_config, target_app_path, app_name, resolved_src_dir=None):
    module_name = module_config["name"]
    raw_path = module_config.get("path")

    if resolved_src_dir:
        src_sdk_path = resolved_src_dir
    elif raw_path:
        src_sdk_path = os.path.abspath(os.path.join(PROJECT_ROOT, raw_path))
    else:
        print(f"[-] No path defined for module: {module_name}. Skipping.")
        return None

    manifest_path = os.path.join(src_sdk_path, "manifest.json")

    if not os.path.exists(manifest_path):
        print(
            f"[-] No manifest.json found for module {module_name} at {src_sdk_path}. Skipping."
        )
        return None

    with open(manifest_path, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    # The module's canonical name: the manifest's "name" (the same value the
    # primary DocType JSON "module" key is rewritten to). This is what the
    # {module_name} token resolves to in copied content.
    module_label = manifest.get("name", module_name)

    dest_module_path = os.path.join(target_app_path, module_name)
    if os.path.exists(dest_module_path):
        shutil.rmtree(dest_module_path)
    os.makedirs(dest_module_path, exist_ok=True)
    COMPOSED_PATHS.append(dest_module_path)

    # 1. Copy DocTypes
    src_doctype = os.path.join(src_sdk_path, "doctype")
    dest_doctype = os.path.join(dest_module_path, "doctype")
    if os.path.isdir(src_doctype):
        os.makedirs(dest_doctype, exist_ok=True)
        for dt in os.listdir(src_doctype):
            src_dt_path = os.path.join(src_doctype, dt)
            dest_dt_path = os.path.join(dest_doctype, dt)
            if os.path.isdir(src_dt_path):
                if dt in COMPILED_DOCTYPES:
                    raise ValueError(
                        f"CRITICAL ERROR: Duplicate DocType '{dt}' detected! Already compiled by module '{COMPILED_DOCTYPES[dt]}'. Failing build."
                    )
                COMPILED_DOCTYPES[dt] = module_name
                if dt in SRC_NESTED_DOCTYPES and SRC_NESTED_DOCTYPES[dt] != module_name:
                    compose_warning(
                        f"DocType '{dt}' in module '{module_name}'s doctype/ tree "
                        f"collides with module '{SRC_NESTED_DOCTYPES[dt]}'s src/ tree."
                    )

                if os.path.exists(dest_dt_path):
                    shutil.rmtree(dest_dt_path)
                copy_doctype_tree_resolving(
                    src_dt_path, dest_dt_path, app_name, module_label
                )
                # Overwrite the DocType module property to match composition target
                json_file = os.path.join(dest_dt_path, f"{dt}.json")
                if os.path.exists(json_file):
                    try:
                        with open(json_file, "r", encoding="utf-8") as jf:
                            data = json.load(jf)
                        data["module"] = manifest.get("name", module_name)
                        with open(json_file, "w", encoding="utf-8") as jf:
                            json.dump(data, jf, indent=2)
                        print(
                            f"[+] Compiled DocType: {dt} -> {manifest.get('name', module_name)} (Module injected from manifest)"
                        )
                    except Exception as je:
                        print(
                            f"[!] Warning: Failed to inject module into {dt}.json: {je}"
                        )
                else:
                    print(f"[+] Copied DocType: {dt} -> {module_name}")

    # Role-based composition, strip side (ported from the Dart composer's
    # strip_unused_role_folders() in core/utils/flutter/sdk_composer.py):
    # persona folders live as siblings directly under the SDK's src/
    # (src/manager/, src/customer/, ...) and everything NOT named after a
    # declared persona is common. A persona folder is only excluded when it
    # is declared as an app_type persona in this SDK's own manifest AND the
    # shell's own role is also declared there - same guardrails as Dart: no
    # role marker, no app_type in the manifest, or a role this SDK doesn't
    # declare all mean nothing is excluded and the copy is exactly as before.
    # Frappe copies whole trees rather than vendoring a cache, so the
    # equivalent of Dart's cache-strip is to skip copying the other
    # personas' subtrees in the src/ loop below - the observable result
    # matches: other personas' folders are absent from the composed app.
    current_app_type = resolve_app_type()
    declared_personas = list((manifest.get("app_type") or {}).keys())
    excluded_personas = set()
    if current_app_type and current_app_type in declared_personas:
        excluded_personas = {p for p in declared_personas if p != current_app_type}

    # 2. Copy Source Code Files (api.py, tasks.py, etc.)
    src_code = os.path.join(src_sdk_path, "src")
    if os.path.isdir(src_code):
        for f in os.listdir(src_code):
            src_file_path = os.path.join(src_code, f)

            if f in excluded_personas and os.path.isdir(src_file_path):
                print(
                    f"[*] Skipped unused role folder src/{f}/ from {module_name} (app role: {current_app_type})"
                )
                continue

            # Special redirects for global folders
            if f == "www":
                dest_www = os.path.join(target_app_path, "www")
                os.makedirs(dest_www, exist_ok=True)
                for item in os.listdir(src_file_path):
                    s_file = os.path.join(src_file_path, item)
                    d_file = os.path.join(dest_www, item)
                    if os.path.exists(d_file):
                        raise ValueError(
                            f"CRITICAL ERROR: Duplicate global www file '{item}' detected! (Attempted by: '{module_name}'). Failing build."
                        )
                    if item.endswith(SUBSTITUTABLE_EXTENSIONS):
                        with open(s_file, "r", encoding="utf-8") as sf:
                            content = sf.read()
                        content = resolve_tokens(content, app_name, module_label)
                        with open(d_file, "w", encoding="utf-8") as df:
                            df.write(content)
                    else:
                        shutil.copy2(s_file, d_file)
                    COMPOSED_PATHS.append(d_file)
                print(f"[+] Merged global www files from: {module_name}")
                continue

            if f == "templates":
                # Portal page templates (templates/pages/, templates/includes/,
                # ...) belong at the APP level, where Frappe's website router
                # actually resolves them — not inside the module package.
                dest_templates = os.path.join(target_app_path, "templates")
                merge_global_templates_tree(
                    src_file_path, dest_templates, app_name, module_label, module_name
                )
                print(f"[+] Merged global templates files from: {module_name}")
                continue

            if f == "patches":
                dest_patches = os.path.join(target_app_path, "patches")
                os.makedirs(dest_patches, exist_ok=True)
                # Ensure __init__.py exists in patches
                with open(
                    os.path.join(dest_patches, "__init__.py"), "w", encoding="utf-8"
                ) as init_f:
                    init_f.write("")
                for item in os.listdir(src_file_path):
                    if item.endswith(".py") and item != "__init__.py":
                        s_file = os.path.join(src_file_path, item)
                        d_file = os.path.join(dest_patches, item)
                        if os.path.exists(d_file):
                            raise ValueError(
                                f"CRITICAL ERROR: Duplicate global patch file '{item}' detected! (Attempted by: '{module_name}'). Failing build."
                            )
                        with open(s_file, "r", encoding="utf-8") as sf:
                            content = sf.read()
                        content = resolve_tokens(content, app_name, module_label)
                        with open(d_file, "w", encoding="utf-8") as df:
                            df.write(content)
                        COMPOSED_PATHS.append(d_file)
                        patch_name = item[:-3]
                        # Register in patches.txt
                        patches_txt_path = os.path.join(target_app_path, "patches.txt")
                        existing_patches = []
                        if os.path.exists(patches_txt_path):
                            with open(patches_txt_path, "r", encoding="utf-8") as pf:
                                existing_patches = [
                                    line.strip()
                                    for line in pf.readlines()
                                    if line.strip()
                                ]
                        full_patch_path = f"{app_name}.patches.{patch_name}"
                        if full_patch_path not in existing_patches:
                            with open(patches_txt_path, "a", encoding="utf-8") as pf:
                                pf.write(f"{full_patch_path}\n")
                            print(
                                f"[+] Registered patch: '{full_patch_path}' -> patches.txt"
                            )
                print(f"[+] Merged global patches from: {module_name}")
                continue

            dest_file_path = os.path.join(dest_module_path, f)
            if os.path.exists(dest_file_path):
                raise ValueError(
                    f"CRITICAL ERROR: Duplicate source file/folder '{f}' in module '{module_name}'! Failing build."
                )
            if os.path.isfile(src_file_path):
                # Copy file and replace {app_name}/{module_name} placeholders
                if src_file_path.endswith(SUBSTITUTABLE_EXTENSIONS):
                    with open(src_file_path, "r", encoding="utf-8") as sf:
                        content = sf.read()
                    content = resolve_tokens(content, app_name, module_label)
                    with open(dest_file_path, "w", encoding="utf-8") as df:
                        df.write(content)
                else:
                    shutil.copy2(src_file_path, dest_file_path)
                print(f"[+] Copied Source File: {f} -> {module_name}")
            elif os.path.isdir(src_file_path):
                if os.path.exists(dest_file_path):
                    shutil.rmtree(dest_file_path)

                # Copy tree and compile placeholders for text files
                def copy_and_resolve(src, dst):
                    os.makedirs(dst, exist_ok=True)
                    for item in os.listdir(src):
                        s = os.path.join(src, item)
                        d = os.path.join(dst, item)
                        if os.path.isdir(s):
                            copy_and_resolve(s, d)
                        else:
                            if s.endswith(SUBSTITUTABLE_EXTENSIONS):
                                with open(s, "r", encoding="utf-8") as sf:
                                    content = sf.read()
                                content = resolve_tokens(
                                    content, app_name, module_label
                                )
                                with open(d, "w", encoding="utf-8") as df:
                                    df.write(content)
                            else:
                                shutil.copy2(s, d)

                copy_and_resolve(src_file_path, dest_file_path)
                if f in declared_personas:
                    # Persona folders (src/<persona>/) may ship persona-scoped
                    # doctypes (src/<persona>/doctype/<dt>/). Scoping already
                    # happened above (excluded personas were skipped, and with
                    # no role marker EVERY declared persona composes — absence
                    # of marker = serve all roles), so relocate whatever
                    # doctypes were copied into the Frappe-conventional
                    # module-root doctype/ destination, with module-root
                    # semantics (hard-error dupes, "module" key injection).
                    relocate_persona_doctypes(
                        dest_file_path,
                        dest_module_path,
                        f,
                        module_label,
                        module_name,
                    )
                else:
                    # DocTypes shipped under non-persona src/ dirs escape the
                    # module-root doctype/ machinery and stay at their nested
                    # composed path: pin their primary JSON "module" keys and
                    # register them for (warn-only) duplicate detection.
                    rewrite_src_nested_doctype_modules(
                        dest_file_path, module_label, module_name
                    )
                print(f"[+] Copied Source Directory: {f} -> {module_name}")

    # 3. Copy Fixtures
    # Frappe imports fixtures from ONE place only: the app package's own
    # <app>/fixtures/*.json, walked by import_fixtures() (frappe/utils/
    # fixtures.py) on every `bench migrate`. It is a flat, app-level scan --
    # module-level fixtures/ dirs are never read, and hooks.fixtures governs
    # only the EXPORT side (bench export-fixtures), not the import. So an
    # SDK's fixtures/ tree has to land at the app root to apply at all;
    # copied into the module folder alongside doctype/ and src/ it would be
    # inert. Merged like www/ and patches/: app-level destination, exact
    # duplicate filenames are a hard build error rather than a silent
    # last-writer-wins overwrite of another SDK's records.
    src_fixtures = os.path.join(src_sdk_path, "fixtures")
    if os.path.isdir(src_fixtures):
        dest_fixtures = os.path.join(target_app_path, "fixtures")
        os.makedirs(dest_fixtures, exist_ok=True)
        for item in os.listdir(src_fixtures):
            s_path = os.path.join(src_fixtures, item)
            d_path = os.path.join(dest_fixtures, item)
            if os.path.exists(d_path):
                raise ValueError(
                    f"CRITICAL ERROR: Duplicate fixture '{item}' detected! "
                    f"(Attempted by: '{module_name}'). Failing build."
                )
            if os.path.isdir(s_path):
                copy_doctype_tree_resolving(s_path, d_path, app_name, module_label)
            else:
                copy_file_resolving(s_path, d_path, app_name, module_label)
            COMPOSED_PATHS.append(d_path)
        print(f"[+] Merged fixtures from: {module_name}")

    # 4. Create Frappe Module Package registration markers
    with open(
        os.path.join(dest_module_path, "__init__.py"), "w", encoding="utf-8"
    ) as f:
        f.write("# Generated by Rokct Backend Composer\n")

    # Append to root modules.txt of the app shell if not present
    root_modules_path = os.path.join(target_app_path, "modules.txt")
    existing_modules = []
    if os.path.exists(root_modules_path):
        with open(root_modules_path, "r", encoding="utf-8") as f:
            existing_modules = [line.strip() for line in f.readlines() if line.strip()]

    if module_name not in existing_modules:
        with open(root_modules_path, "a", encoding="utf-8") as f:
            f.write(f"{module_name}\n")
        print(f"[+] Injected module registration: '{module_name}' -> root modules.txt")

    # Doctype JS hook paths (doctype_js / doctype_list_js) are declared
    # module-relative in the manifest; rewrite them app-package-relative now
    # that the composed module folder name is known, so merge_hooks (which
    # also sees persona flavor blocks detached from their manifest) can emit
    # and existence-check them verbatim.
    rewrite_doctype_js_hook_paths(manifest, module_name)

    print(f"[+] Module {module_name} registration files written.")
    return manifest


def merge_hooks(target_app_path, app_name, compiled_manifests):
    hooks_file = os.path.join(target_app_path, "hooks.py")
    if not os.path.exists(hooks_file):
        print(f"[-] No hooks.py found in {target_app_path}. Creating a default one.")
        with open(hooks_file, "w", encoding="utf-8") as hf:
            hf.write(f"app_name = '{app_name}'\n")

    # Read original content
    with open(hooks_file, "r", encoding="utf-8") as f:
        content = f.read()

    # Strip any previously appended blocks to ensure idempotent builds
    split_marker = "# --- BEG OF DYNAMIC SDK HOOKS ---"
    if split_marker in content:
        content = content.split(split_marker)[0].strip()

    append_blocks = []

    for module_name, manifest in compiled_manifests.items():
        hooks = manifest.get("hooks", {})
        # Dynamically inject the app_name into placeholders
        hooks_str = json.dumps(hooks)
        hooks_str = hooks_str.replace("{app_name}", app_name)
        hooks = json.loads(hooks_str)
        if not hooks:
            continue

        append_blocks.append(f"\n# --- Module: {module_name} ---")

        # 1. Merge scheduler events (deduped like the other hook lists: two
        #    modules registering the same task under the same bucket used to
        #    both land, running it twice per tick).
        scheduler_events = hooks.get("scheduler_events", {})
        for event_type, tasks in scheduler_events.items():
            if isinstance(tasks, dict):
                # frappe's "cron" bucket: {cron expression: [dotted job paths]}.
                # The keys are cron expressions, not dotted paths - validate
                # them as such and only dotted-validate the jobs inside each
                # expression's list. Expressions union across modules and each
                # job list extends deduped, like the plain list buckets.
                append_blocks.append(
                    f"scheduler_events = globals().get('scheduler_events', {{}})"
                )
                append_blocks.append(
                    f"scheduler_events.setdefault({event_type!r}, {{}})"
                )
                for cron_expr, jobs in tasks.items():
                    _validate_hook_value(
                        cron_expr, "cron", module_name, "scheduler_events"
                    )
                    job_list = [jobs] if isinstance(jobs, str) else list(jobs)
                    for j in job_list:
                        _validate_hook_value(
                            j, "dotted", module_name, "scheduler_events"
                        )
                    append_blocks.append(
                        f"_cron_jobs = scheduler_events[{event_type!r}].setdefault({cron_expr!r}, [])"
                    )
                    append_blocks.append(f"for _t in {job_list!r}:")
                    append_blocks.append(
                        f"    if _t not in _cron_jobs: _cron_jobs.append(_t)"
                    )
                continue
            task_list = [tasks] if isinstance(tasks, str) else list(tasks)
            for t in task_list:
                _validate_hook_value(t, "dotted", module_name, "scheduler_events")
            append_blocks.append(
                f"scheduler_events = globals().get('scheduler_events', {{}})"
            )
            append_blocks.append(f"scheduler_events.setdefault({event_type!r}, [])")
            append_blocks.append(f"for _t in {task_list!r}:")
            append_blocks.append(
                f"    if _t not in scheduler_events[{event_type!r}]: scheduler_events[{event_type!r}].append(_t)"
            )

        # 2. Merge override doctype class
        overrides = hooks.get("override_doctype_class", {})
        for doc_type, class_path in overrides.items():
            _validate_hook_value(
                doc_type, "doctype", module_name, "override_doctype_class"
            )
            _validate_hook_value(
                class_path, "dotted", module_name, "override_doctype_class"
            )
            append_blocks.append(
                f"override_doctype_class = globals().get('override_doctype_class', {{}})"
            )
            append_blocks.append(
                f"override_doctype_class[{doc_type!r}] = {class_path!r}"
            )

        # 3. Merge whitelisted methods. The alias map is written under two
        #    hook keys: "whitelisted_methods" (the historical key, kept for
        #    back-compat with anything reading the composed hooks.py) and
        #    "override_whitelisted_methods" — the only key frappe's request
        #    dispatcher actually consults (frappe.override_whitelisted_method()
        #    in handler.execute_cmd), so aliases resolve at dispatch time.
        #    Keys are emitted exactly as declared (after the {app_name}
        #    placeholder substitution above): each shell exposes only its
        #    own "{app_name}.*" names.
        whitelisted = hooks.get("whitelisted_methods", {})
        if whitelisted:
            append_blocks.append(
                f"whitelisted_methods = globals().get('whitelisted_methods', {{}})"
            )
            append_blocks.append(
                f"override_whitelisted_methods = globals().get('override_whitelisted_methods', {{}})"
            )
            for api_key, api_val in whitelisted.items():
                _validate_hook_value(
                    api_key, "gateway_key", module_name, "whitelisted_methods"
                )
                _validate_hook_value(
                    api_val, "dotted", module_name, "whitelisted_methods"
                )
                append_blocks.append(f"whitelisted_methods[{api_key!r}] = {api_val!r}")
                append_blocks.append(
                    f"override_whitelisted_methods[{api_key!r}] = {api_val!r}"
                )

        # 4. Merge doc events. Accumulate handlers into a LIST per (doctype,
        #    event): frappe natively supports a list of handlers for a single
        #    doc_event, so two modules registering the same (doctype, event)
        #    both run. Plain assignment (the old behavior) silently dropped
        #    every handler but the last one to be composed. Handles both a
        #    single handler string and a list of handlers in the manifest.
        events = hooks.get("doc_events", {})
        if events:
            append_blocks.append(f"doc_events = globals().get('doc_events', {{}})")
            for doc_type, evt_dict in events.items():
                _validate_hook_value(doc_type, "doctype", module_name, "doc_events")
                append_blocks.append(f"doc_events.setdefault({doc_type!r}, {{}})")
                for evt, handler in evt_dict.items():
                    _validate_hook_value(evt, "event", module_name, "doc_events")
                    handler_list = (
                        [handler] if isinstance(handler, str) else list(handler)
                    )
                    for h in handler_list:
                        _validate_hook_value(h, "dotted", module_name, "doc_events")
                    append_blocks.append(
                        f"_ev = doc_events[{doc_type!r}].get({evt!r}) or []"
                    )
                    append_blocks.append(
                        f"_ev = [_ev] if isinstance(_ev, str) else list(_ev)"
                    )
                    append_blocks.append(f"for _h in {handler_list!r}:")
                    append_blocks.append(f"    if _h not in _ev: _ev.append(_h)")
                    append_blocks.append(f"doc_events[{doc_type!r}][{evt!r}] = _ev")

        # 5. Merge fixtures
        fixs = hooks.get("fixtures", [])
        if fixs:
            append_blocks.append(f"fixtures = globals().get('fixtures', [])")
            for f in fixs:
                append_blocks.append(f"fixtures.append({repr(f)})")

        # 6. Merge auth hooks
        auths = hooks.get("auth_hooks", [])
        if auths:
            append_blocks.append(f"auth_hooks = globals().get('auth_hooks', [])")
            for a in auths:
                _validate_hook_value(a, "dotted", module_name, "auth_hooks")
                append_blocks.append(
                    f"if {a!r} not in auth_hooks: auth_hooks.append({a!r})"
                )

        # 7. Merge before_uninstall hooks
        before_uninstalls = hooks.get("before_uninstall", [])
        if before_uninstalls:
            append_blocks.append(
                f"before_uninstall = globals().get('before_uninstall', [])"
            )
            for bu in before_uninstalls:
                _validate_hook_value(bu, "dotted", module_name, "before_uninstall")
                append_blocks.append(
                    f"if {bu!r} not in before_uninstall: before_uninstall.append({bu!r})"
                )

        # 8. Merge after_install hooks
        after_installs = hooks.get("after_install", [])
        if isinstance(after_installs, str):
            after_installs = [after_installs]
        if after_installs:
            # The shell's own hooks.py may declare after_install as a bare
            # string (standard Frappe style, and what the scaffold template
            # emits), so coerce it to a list in the EMITTED code before
            # appending — otherwise importing the composed hooks module would
            # raise AttributeError on str.append.
            append_blocks.append(f"after_install = globals().get('after_install', [])")
            append_blocks.append(
                "if isinstance(after_install, str): after_install = [after_install]"
            )
            for ai in after_installs:
                _validate_hook_value(ai, "dotted", module_name, "after_install")
                append_blocks.append(
                    f"if {ai!r} not in after_install: after_install.append({ai!r})"
                )

        # 9. Merge on_login hooks. Frappe's LoginManager.run_trigger calls
        #    EVERY handler frappe.get_hooks("on_login") returns, and
        #    get_hooks coerces a bare string to a list — so on_login is a
        #    list hook and modules' handlers accumulate deduped. The shell's
        #    own hooks.py normally declares on_login as a bare string
        #    (standard Frappe style), so the emitted block coerces it to a
        #    list first — the exact after_install treatment above.
        on_logins = hooks.get("on_login", [])
        if isinstance(on_logins, str):
            on_logins = [on_logins]
        if on_logins:
            append_blocks.append(f"on_login = globals().get('on_login', [])")
            append_blocks.append("if isinstance(on_login, str): on_login = [on_login]")
            for ol in on_logins:
                _validate_hook_value(ol, "dotted", module_name, "on_login")
                append_blocks.append(
                    f"if {ol!r} not in on_login: on_login.append({ol!r})"
                )

        # 10. Merge desk doctype JS registrations (doctype_js form scripts /
        #    doctype_list_js list-view scripts). Frappe resolves each value
        #    via frappe.get_app_path(app, *path.split("/")) and inlines the
        #    file server-side, and add_code_via_hook accepts a LIST of files
        #    per doctype — so entries accumulate as a deduped list per
        #    doctype, the doc_events idiom. Paths arrive here already
        #    rewritten app-package-relative by rewrite_doctype_js_hook_paths
        #    at compose time; each is existence-checked against the composed
        #    output so a typo'd path (or one pointing into a stripped persona
        #    folder) warns loudly at compose time instead of 404ing on the
        #    desk at runtime.
        for js_key in DOCTYPE_JS_HOOK_KEYS:
            js_map = hooks.get(js_key, {})
            if not js_map:
                continue
            append_blocks.append(f"{js_key} = globals().get({js_key!r}, {{}})")
            for doc_type, js_paths in js_map.items():
                _validate_hook_value(doc_type, "doctype", module_name, js_key)
                path_list = [js_paths] if isinstance(js_paths, str) else list(js_paths)
                for p in path_list:
                    _validate_hook_value(p, "js_path", module_name, js_key)
                    if not os.path.exists(os.path.join(target_app_path, *p.split("/"))):
                        compose_warning(
                            f"{js_key} entry for '{doc_type}' in module "
                            f"'{module_name}' points at '{p}', which was not "
                            f"composed into the app."
                        )
                append_blocks.append(f"_js = {js_key}.get({doc_type!r}) or []")
                append_blocks.append(
                    f"_js = [_js] if isinstance(_js, str) else list(_js)"
                )
                append_blocks.append(f"for _p in {path_list!r}:")
                append_blocks.append(f"    if _p not in _js: _js.append(_p)")
                append_blocks.append(f"{js_key}[{doc_type!r}] = _js")

    if append_blocks:
        new_content = (
            content
            + "\n\n"
            + split_marker
            + "\n"
            + "\n".join(append_blocks)
            + "\n# --- END OF DYNAMIC SDK HOOKS ---\n"
        )
        with open(hooks_file, "w", encoding="utf-8") as f:
            f.write(new_content)
        print("[+] Merged dynamic Hooks successfully into hooks.py")


def merge_commands(target_app_path, app_name, compiled_manifests):
    """Wire manifest-declared bench commands into the composed app.

    Bench discovers an app's CLI commands by importing ``{app}.commands`` and
    reading its module-level ``commands`` list, so every dotted path declared
    under a manifest's ``hooks.commands`` is imported into a generated
    commands.py and appended to that list. The generated block is fenced with
    markers (mirroring merge_hooks) so rebuilds stay idempotent and any
    hand-written shell commands.py content above the marker is preserved.
    """
    entries = []
    for module_name, manifest in compiled_manifests.items():
        cmds = manifest.get("hooks", {}).get("commands", [])
        if isinstance(cmds, str):
            cmds = [cmds]
        for cmd_path in cmds:
            cmd_path = cmd_path.replace("{app_name}", app_name)
            if cmd_path not in [e[0] for e in entries]:
                entries.append((cmd_path, module_name))

    commands_file = os.path.join(target_app_path, "commands.py")
    split_marker = "# --- BEG OF DYNAMIC SDK COMMANDS ---"

    content = ""
    if os.path.exists(commands_file):
        with open(commands_file, "r", encoding="utf-8") as f:
            content = f.read()
        # Strip any previously appended block to ensure idempotent builds
        if split_marker in content:
            content = content.split(split_marker)[0].rstrip() + "\n"

    if not entries:
        # Nothing to wire; leave any hand-written commands.py untouched
        return

    if not content:
        content = "# Generated by Rokct Backend Composer\n"

    lines = ["", split_marker]
    lines.append("commands = globals().get('commands', [])")
    for idx, (cmd_path, module_name) in enumerate(entries):
        module_path, attr = cmd_path.rsplit(".", 1)
        # These land inside a generated import STATEMENT
        # (`from {module_path} import {attr} as ...`), so repr() can't quote
        # them defensively the way it does for the merge_hooks assignments.
        # Strict dotted-path / identifier validation is the only guard: the
        # "dotted" pattern forbids newlines, semicolons, spaces, '#', etc.,
        # so a crafted `hooks.commands` value can't smuggle extra statements
        # into commands.py. Validated after {app_name} substitution, matching
        # merge_hooks' ordering, and aborts loudly naming module + hook.
        _validate_hook_value(module_path, "dotted", module_name, "commands")
        _validate_hook_value(attr, "dotted", module_name, "commands")
        alias = f"_sdk_command_{idx}"
        lines.append(f"# --- Module: {module_name} ---")
        lines.append(f"from {module_path} import {attr} as {alias}")
        lines.append(f"if {alias} not in commands: commands.append({alias})")
    lines.append("# --- END OF DYNAMIC SDK COMMANDS ---")

    with open(commands_file, "w", encoding="utf-8") as f:
        f.write(content + "\n".join(lines) + "\n")
    print(f"[+] Merged {len(entries)} bench command(s) into commands.py")


def _dep_name(dep):
    """Extract the bare package name (lowercased) from a PEP 508-ish
    dependency string, ignoring any version specifier or extras — so
    'requests==2.0', 'requests>=1', 'requests[security]' and 'requests' all
    resolve to 'requests'. Used to dedupe by NAME rather than full string,
    consistently across requirements.txt and pyproject.toml."""
    return re.split(r"[=<>!~;\[\s]", dep.strip(), 1)[0].strip().lower()


def merge_dependencies(project_root, compiled_manifests):
    # Collect all dependencies from manifests, deduped by package NAME so the
    # same package pinned differently by two manifests doesn't get injected
    # twice. Iterate deterministically (sorted) and keep the first occurrence.
    all_deps = []
    seen_names = set()
    raw_deps = set()
    for manifest in compiled_manifests.values():
        for d in manifest.get("dependencies", []):
            raw_deps.add(d.strip())
    for d in sorted(raw_deps):
        name = _dep_name(d)
        if name in seen_names:
            existing = next((x for x in all_deps if _dep_name(x) == name), None)
            if existing and existing != d:
                print(
                    f"[!] Dependency version conflict for '{name}': keeping '{existing}', ignoring manifest's '{d}'."
                )
            continue
        seen_names.add(name)
        all_deps.append(d)

    if not all_deps:
        return

    # 1. Update requirements.txt (dedupe by package NAME, warn on conflict)
    req_file = os.path.join(project_root, "requirements.txt")
    existing_reqs = {}
    if os.path.exists(req_file):
        with open(req_file, "r", encoding="utf-8") as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    existing_reqs[_dep_name(stripped)] = stripped

    new_reqs_to_add = []
    for d in all_deps:
        name = _dep_name(d)
        if name in existing_reqs:
            if existing_reqs[name] != d:
                print(
                    f"[!] '{name}' already in requirements.txt as '{existing_reqs[name]}', skipping manifest's '{d}' (version conflict)."
                )
            continue
        new_reqs_to_add.append(d)
    if new_reqs_to_add:
        with open(req_file, "a", encoding="utf-8") as f:
            # Add a newline if file doesn't end with one
            f.write("\n# Composed SDK Dependencies\n")
            for req in new_reqs_to_add:
                f.write(f"{req}\n")
        print(
            f"[+] Injected Python requirements into requirements.txt: {new_reqs_to_add}"
        )

    # 2. Update pyproject.toml (dedupe by package NAME, warn on conflict — a
    #    bare 'requests' from a manifest must not land alongside an existing
    #    'requests==2.0')
    toml_file = os.path.join(project_root, "pyproject.toml")
    if os.path.exists(toml_file):
        with open(toml_file, "r", encoding="utf-8") as f:
            toml_content = f.read()

        # Locate the dependencies array block
        match = re.search(r"dependencies\s*=\s*\[([^\]]*)\]", toml_content)
        if match:
            deps_block = match.group(1)
            # Parse existing TOML dependency strings
            existing_toml_deps = [
                d.replace('"', "").replace("'", "").strip()
                for d in deps_block.split(",")
                if d.strip()
            ]
            existing_toml_names = {_dep_name(d): d for d in existing_toml_deps}

            new_toml_deps_to_add = []
            for d in all_deps:
                name = _dep_name(d)
                if name in existing_toml_names:
                    if existing_toml_names[name] != d:
                        print(
                            f"[!] '{name}' already in pyproject.toml as '{existing_toml_names[name]}', skipping manifest's '{d}' (version conflict)."
                        )
                    continue
                existing_toml_names[name] = d
                new_toml_deps_to_add.append(d)
            if new_toml_deps_to_add:
                updated_deps_list = existing_toml_deps + new_toml_deps_to_add
                toml_deps_str = ",\n    ".join([f'"{d}"' for d in updated_deps_list])
                new_dependencies_field = f"dependencies = [\n    {toml_deps_str}\n]"
                toml_content = toml_content.replace(
                    match.group(0), new_dependencies_field
                )
                with open(toml_file, "w", encoding="utf-8") as f:
                    f.write(toml_content)
                print(
                    f"[+] Injected dependencies into pyproject.toml: {new_toml_deps_to_add}"
                )


def main():
    print("[*] Starting Frappe App Backend Composition...")

    # Clean and restore target app shell workspace using Git
    print("[*] Cleaning and restoring target app shell workspace using Git...")
    try:
        subprocess.run(["git", "restore", "."], check=True, capture_output=True)
        subprocess.run(["git", "clean", "-fd"], check=True, capture_output=True)
        print("[+] Workspace cleaned successfully.")
    except Exception as e:
        print(
            f"[!] Warning: Git clean/restore failed (perhaps not a git repo or git not in PATH): {e}"
        )

    # Template-registry resolution: a thin shell that names a registry
    # template in .rokct/config/app_type gets its composer.json materialized
    # from the protocol's canonical template before anything is read. Runs
    # AFTER the git clean above so the materialized file survives this run.
    # No-op (and byte-identical legacy behavior) when the marker is absent or
    # is a plain role name.
    resolve_composer_config()

    config = load_composer_config()

    # Scaffold mode: lay down the tokenized shell skeleton when the target
    # app shell package is missing entirely (a brand-new shell repo), or when
    # explicitly requested with --scaffold. Strictly additive either way —
    # scaffold_shell() never overwrites an existing file, so existing shells
    # are untouched.
    scaffold_requested = "--scaffold" in sys.argv[1:]
    shell_app_name = derive_app_name(config)
    shell_present = os.path.exists(
        os.path.join(PROJECT_ROOT, "apps", shell_app_name, shell_app_name)
    ) or os.path.exists(os.path.join(PROJECT_ROOT, shell_app_name))
    if scaffold_requested or not shell_present:
        scaffold_shell(shell_app_name, explicit=scaffold_requested)

    app_name, target_app_path = find_target_app_dir(config)

    modules = config.get("modules", [])
    compiled_manifests = {}

    resolved_sources = resolve_module_sources(modules)

    # Role-based composition, install side (ported from the Dart installer's
    # flavor_block handling in core/utils/flutter/sdk_installer_base.py):
    # everything at a manifest's top level always composes regardless of role
    # ("common gets installed regardless"). A manifest can additionally
    # declare an "app_type" block keyed by persona (manager/customer/pos/...)
    # whose value mirrors the manifest top-level schema - its "hooks"
    # (whitelisted_methods, doc_events, scheduler_events, fixtures,
    # after_install, commands, ...) and "dependencies" are merged in ONLY
    # when the persona matches this shell's own .rokct/config/app_type
    # marker. The matching flavor block is registered as its own compiled
    # manifest entry so it flows through the existing merge_hooks/
    # merge_commands/merge_dependencies machinery unchanged - all three are
    # already additive per key. With no marker (a tenant backend serving all
    # roles at once) or no app_type key, nothing extra is registered and the
    # output is identical to a role-less compose.
    current_app_type = resolve_app_type()

    for m in modules:
        if m.get("enabled", False):
            print(f"\n[*] Pouring module: {m['name']}...")
            manifest = compose_module(
                m, target_app_path, app_name, resolved_sources.get(id(m))
            )
            if manifest:
                compiled_manifests[m["name"]] = manifest
                flavor_block = (
                    (manifest.get("app_type") or {}).get(current_app_type)
                    if current_app_type
                    else None
                )
                if flavor_block:
                    compiled_manifests[f"{m['name']} ({current_app_type})"] = (
                        flavor_block
                    )

    if compiled_manifests:
        merge_hooks(target_app_path, app_name, compiled_manifests)
        merge_commands(target_app_path, app_name, compiled_manifests)
        merge_dependencies(PROJECT_ROOT, compiled_manifests)

    # Post-compose token lint: composed output must not carry unresolved
    # {app_name}/{module_name} literals (warn; hard error under
    # ROKCT_COMPOSE_STRICT=1).
    lint_composed_tokens(COMPOSED_PATHS, PROJECT_ROOT)

    print("\n[+] Frappe backend composition complete.")


if __name__ == "__main__":
    main()
