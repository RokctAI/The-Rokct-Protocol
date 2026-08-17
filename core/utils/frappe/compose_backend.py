# Copyright (c) 2026 RokctAI
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import sys
import shutil
import json
import re
import subprocess

PROJECT_ROOT = os.getcwd()

COMPILED_DOCTYPES = {}  # maps doctype_name -> module_name

# Manifest hook values are interpolated into generated Python source
# (hooks.py). Before any value is written it is validated against a tight
# regex so a malicious or malformed manifest cannot inject arbitrary code
# through these fields (e.g. a doc_events handler of
# "x'; import os; os.system('id') #" used to land verbatim in hooks.py).
# Values are also embedded with repr()/!r for defense in depth.
#   - "dotted": a Python import path (handler / method / class path)
#   - "doctype": a frappe DocType name (word chars, spaces, hyphens), or the
#     literal "*" wildcard frappe accepts for doc_events registered against
#     every doctype (e.g. core/telemetry's trace-context injector).
#   - "event": a doc_event / scheduler bucket name (word chars)
#   - "cron": a cron expression key inside scheduler_events["cron"]
#     (croniter syntax: digits, *, /, ",", "-", spaces, month/day names)
_HOOK_VALUE_PATTERNS = {
    "dotted": re.compile(r"^[A-Za-z_][A-Za-z0-9_]*(\.[A-Za-z_][A-Za-z0-9_]*)*$"),
    "doctype": re.compile(r"^(\*|[\w \-]+)$"),
    "event": re.compile(r"^\w+$"),
    "cron": re.compile(r"^[\w*/,\- ]+$"),
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


def resolve_app_type():
    """This shell's own role marker (e.g. 'manager', 'customer', 'pos'), read
    from .rokct/config/app_type - a plain one-line text file checked into the
    shell's own repo, relative to the same root the shell's composer.json is
    read from. Mirrors core/utils/flutter/sdk_installer_base.py's
    resolve_app_type() - kept as a local copy rather than imported, since each
    stack's composer is fetched and used independently.

    Returns None when the file doesn't exist - manifests with no matching
    app_type block then behave exactly as before (nothing filtered, nothing
    extra merged). A tenant backend that deliberately serves ALL roles at
    once simply declares no marker: absence = all."""
    path = os.path.join(PROJECT_ROOT, ".rokct", "config", "app_type")
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


def find_target_app_dir(config):
    # Try to resolve app name from configuration or folder name
    app_name = config.get("name", "").replace("_app", "")
    if not app_name:
        app_name = os.path.basename(PROJECT_ROOT)

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

    dest_module_path = os.path.join(target_app_path, module_name)
    if os.path.exists(dest_module_path):
        shutil.rmtree(dest_module_path)
    os.makedirs(dest_module_path, exist_ok=True)

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

                if os.path.exists(dest_dt_path):
                    shutil.rmtree(dest_dt_path)
                shutil.copytree(src_dt_path, dest_dt_path)
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
                    if item.endswith((".py", ".js", ".html", ".json")):
                        with open(s_file, "r", encoding="utf-8") as sf:
                            content = sf.read()
                        content = content.replace("{app_name}", app_name)
                        with open(d_file, "w", encoding="utf-8") as df:
                            df.write(content)
                    else:
                        shutil.copy2(s_file, d_file)
                print(f"[+] Merged global www files from: {module_name}")
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
                        content = content.replace("{app_name}", app_name)
                        with open(d_file, "w", encoding="utf-8") as df:
                            df.write(content)
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
                # Copy file and replace {app_name} placeholders dynamically
                if src_file_path.endswith((".py", ".js", ".html", ".json")):
                    with open(src_file_path, "r", encoding="utf-8") as sf:
                        content = sf.read()
                    content = content.replace("{app_name}", app_name)
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
                            if s.endswith((".py", ".js", ".html", ".json")):
                                with open(s, "r", encoding="utf-8") as sf:
                                    content = sf.read()
                                content = content.replace("{app_name}", app_name)
                                with open(d, "w", encoding="utf-8") as df:
                                    df.write(content)
                            else:
                                shutil.copy2(s, d)

                copy_and_resolve(src_file_path, dest_file_path)
                print(f"[+] Copied Source Directory: {f} -> {module_name}")

    # 3. Create Frappe Module Package registration markers
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
                    api_key, "dotted", module_name, "whitelisted_methods"
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
            append_blocks.append(f"after_install = globals().get('after_install', [])")
            for ai in after_installs:
                _validate_hook_value(ai, "dotted", module_name, "after_install")
                append_blocks.append(
                    f"if {ai!r} not in after_install: after_install.append({ai!r})"
                )

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

    config = load_composer_config()
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

    print("\n[+] Frappe backend composition complete.")


if __name__ == "__main__":
    main()
