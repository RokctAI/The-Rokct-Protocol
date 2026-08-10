import os
import sys
import subprocess
import json
import shutil

PROJECT_ROOT = os.getcwd()
NL = chr(10)

def clean_sdk_name(name):
    if name.endswith("_sdk"):
        return name[:-4]
    if name.endswith("_sdks"):
        return name[:-5]
    return name

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
            return "/".join(parts[idx+1:])
    if len(parts) >= 2:
        return "/".join(parts[-2:])
    return normalized

def authenticated_git_url(git_url):
    """Inject MONOREPO_PAT for github.com HTTPS clones so private SDK repos
    (all SDKs are now private) resolve without ambient git credentials —
    same token/URL shape universal-flutter-build.yml already uses for its
    own private-repo clone path."""
    token = os.environ.get("MONOREPO_PAT")
    if token and git_url.startswith("https://github.com/"):
        return git_url.replace(
            "https://github.com/", f"https://x-access-token:{token}@github.com/"
        )
    return git_url

def check_git_availability(git_url):
    try:
        result = subprocess.run(
            ["git", "ls-remote", "--exit-code", "-h", git_url, "HEAD"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=5
        )
        return result.returncode == 0
    except Exception:
        return False

def resolve_app_type():
    """This host app's own flavor marker ('driver', 'manager', ...), read from
    .rokct/config/app_type. Mirrors sdk_installer_base.py's resolve_app_type()
    - kept as a local copy here rather than imported, since sdk_composer.py and
    sdk_installer_base.py are fetched and used independently by compose.py."""
    path = os.path.join(PROJECT_ROOT, ".rokct", "config", "app_type")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            value = f.read().strip().lower()
            return value or None
    return None

def strip_unused_role_folders(target_dir, sdk_name):
    """After vendoring an SDK's full source into .rokct/cache/, remove role
    folders under lib/src/ that don't apply to this host app - keep common/
    and this app's own role only, matching the sibling-folder convention
    (lib/src/common/, lib/src/driver/, lib/src/manager/, ...).

    Why: the cache is intentionally tracked (not gitignored) so developers
    can actually read the code their app is built against, since CI composes
    fresh and never leaves a browsable copy anywhere else. Vendoring every
    role's code in unstripped defeats that purpose for the roles that don't
    apply - a driver app's cache showing manager's business logic is exactly
    the clutter this exists to avoid, and once cache is committed, an
    unstripped copy would carry other-role code into that app's own repo
    history, not just a local developer's working copy.

    Only strips a role folder that's a genuine sibling of common/ under
    lib/src/ AND is declared as an app_type persona in this SDK's own
    manifest.json (see sdk_validator.py's parse_manifests() for the same
    read). Safe no-op if the app's own role can't be resolved, or this SDK
    doesn't declare that role at all - stripping without that confirmation
    risks deleting something the app actually needs.
    """
    current_role = resolve_app_type()
    if not current_role:
        return

    manifest_path = os.path.join(target_dir, "manifest.json")
    if not os.path.exists(manifest_path):
        return
    try:
        with open(manifest_path, "r", encoding="utf-8-sig") as f:
            manifest = json.load(f)
    except Exception:
        return

    declared_personas = list((manifest.get("app_type") or {}).keys())
    if current_role not in declared_personas:
        # This SDK doesn't declare the app's role as a persona - nothing to
        # strip; stripping blind here could remove code the app actually uses.
        return

    lib_src = os.path.join(target_dir, "lib", "src")
    if not os.path.isdir(lib_src):
        return

    for persona in declared_personas:
        if persona == current_role:
            continue
        persona_dir = os.path.join(lib_src, persona)
        if os.path.isdir(persona_dir):
            shutil.rmtree(persona_dir)
            print(f"[*] Stripped unused role folder lib/src/{persona}/ from {sdk_name} (app role: {current_role})")

def resolve_and_cache_sdks(sdks):
    cache_base = os.path.join(PROJECT_ROOT, ".rokct", "cache")
    os.makedirs(cache_base, exist_ok=True)
    
    git_groups = {}
    local_sdks = []
    
    for sdk in sdks:
        if not isinstance(sdk, dict):
            local_sdks.append({
                "name": sdk,
                "path": f"../SDKs/{clean_sdk_name(sdk)}/dart"
            })
            continue
            
        source = sdk.get("source", "local")
        if source == "git" and sdk.get("git"):
            git_url = sdk["git"]
            if git_url not in git_groups:
                git_groups[git_url] = []
            git_groups[git_url].append(sdk)
        else:
            local_sdks.append(sdk)
            
    # Process Git Groups
    for git_url, group_sdks in git_groups.items():
        repo_name = extract_repo_name(git_url)
        temp_repo_dir = os.path.join(cache_base, f"{repo_name}_sdk")
        
        # Check if repo exists locally in the parent folder of PROJECT_ROOT
        workspace_parent = os.path.dirname(PROJECT_ROOT)
        local_repo_path = os.path.join(workspace_parent, repo_name)
        
        is_local_available = os.path.exists(local_repo_path)
        
        if is_local_available:
            print(f"[*] Found local repository for {repo_name} at {local_repo_path}. Using local copy.")
            repo_source_dir = local_repo_path
        else:
            ref = group_sdks[0].get("ref", "main")
            print(f"[*] Fetching repository {git_url} into {temp_repo_dir}...")
            try:
                def remove_readonly(func, path, excinfo):
                    import stat
                    os.chmod(path, stat.S_IWRITE)
                    func(path)
                if os.path.exists(temp_repo_dir):
                    shutil.rmtree(temp_repo_dir, onerror=remove_readonly)
                subprocess.run(["git", "clone", "-b", ref, "--depth", "1", authenticated_git_url(git_url), temp_repo_dir], check=True)
                repo_source_dir = temp_repo_dir
            except Exception as e:
                print(f"[!] Failed to clone {git_url}: {e}")
                sys.exit(1)
            
        # Extract each SDK
        for sdk in group_sdks:
            sdk_name = sdk["name"]
            clean_name = clean_sdk_name(sdk_name)
            target_dir = os.path.join(cache_base, clean_name)
            
            local_path = sdk.get("path", "")
            subpath = get_subpath_in_repo(local_path, repo_name)
            src_dir = os.path.join(repo_source_dir, *subpath.split("/"))
            
            if os.path.exists(src_dir):
                print(f"[+] Extracting {sdk_name} from {subpath} to {target_dir}...")
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                shutil.copytree(src_dir, target_dir)
                strip_unused_role_folders(target_dir, sdk_name)
            else:
                print(f"[!] Error: Path {subpath} not found in repository {repo_source_dir}")
                
        # Clean up temp repo folder if it was cloned
        if not is_local_available and os.path.exists(temp_repo_dir):
            def remove_readonly(func, path, excinfo):
                import stat
                os.chmod(path, stat.S_IWRITE)
                func(path)
            shutil.rmtree(temp_repo_dir, onerror=remove_readonly)
            
    # Process Local SDKs
    for sdk in local_sdks:
        sdk_name = sdk["name"]
        clean_name = clean_sdk_name(sdk_name)
        target_dir = os.path.join(cache_base, clean_name)
        
        local_path = sdk.get("path")
        if local_path:
            src_dir = os.path.abspath(os.path.join(PROJECT_ROOT, local_path))
            if os.path.exists(src_dir):
                print(f"[+] Copying local {sdk_name} from {local_path} to {target_dir}...")
                if os.path.exists(target_dir):
                    shutil.rmtree(target_dir)
                shutil.copytree(src_dir, target_dir)
                strip_unused_role_folders(target_dir, sdk_name)
            else:
                print(f"[-] Local path {local_path} for {sdk_name} does not exist. Skipping.")

def resolve_active_path(sdk_config):
    sdk_name = sdk_config["name"] if isinstance(sdk_config, dict) else sdk_config
    clean_name = clean_sdk_name(sdk_name)
    return os.path.abspath(os.path.join(PROJECT_ROOT, ".rokct", "cache", clean_name))

def run_installer(sdk_config):
    sdk_name = sdk_config["name"] if isinstance(sdk_config, dict) else sdk_config
    sdk_path = resolve_active_path(sdk_config)
    
    installer_script = os.path.join(sdk_path, "install.py")
    
    if not os.path.exists(installer_script):
        print(f"[-] No install.py found for SDK: {sdk_name} at {sdk_path}. Skipping.")
        return
        
    print(f"\n[*] Executing Installer for {sdk_name}...")
    try:
        result = subprocess.run(
            [sys.executable, installer_script],
            cwd=PROJECT_ROOT,
            capture_output=True,
            text=True,
            check=True
        )
        print(f"[+] Installer for {sdk_name} completed successfully.")
    except subprocess.CalledProcessError as e:
        log_dir = os.path.join(PROJECT_ROOT, ".rokct", "agent", "logs")
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{sdk_name}_install_error.log")
        with open(log_file, "w", encoding="utf-8") as lf:
            lf.write(f"Command: {' '.join(e.cmd)}\n")
            lf.write(f"Exit Code: {e.returncode}\n")
            lf.write(f"Stdout:\n{e.stdout}\n")
            lf.write(f"Stderr:\n{e.stderr}\n")
        print(f"[!] Installer for {sdk_name} failed. Error log written to: .rokct/agent/logs/{sdk_name}_install_error.log")
        sys.exit(1)

def update_pubspec_name(package_name):
    pubspec_path = os.path.join(PROJECT_ROOT, "pubspec.yaml")
    if not os.path.exists(pubspec_path):
        return
    
    try:
        with open(pubspec_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        updated = False
        with open(pubspec_path, "w", encoding="utf-8") as f:
            for line in lines:
                if line.startswith("name:"):
                    f.write(f"name: {package_name}\n")
                    updated = True
                else:
                    f.write(line)
        if updated:
            print(f"[*] Updated pubspec.yaml name to: {package_name}")
    except Exception as e:
        print(f"[!] Error updating pubspec.yaml name: {e}")

def update_pubspec_dependencies(sdks):
    pubspec_path = os.path.join(PROJECT_ROOT, "pubspec.yaml")
    if not os.path.exists(pubspec_path):
        return
    
    try:
        with open(pubspec_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        
        dependencies_start = -1
        for i, line in enumerate(lines):
            if line.strip() == "dependencies:":
                dependencies_start = i
                break
        
        if dependencies_start == -1:
            print("[!] Could not find 'dependencies:' section in pubspec.yaml")
            return
        
        new_lines = lines[:dependencies_start + 1]
        
        i = dependencies_start + 1
        while i < len(lines):
            line = lines[i]
            if line.startswith(" "):
                stripped = line.strip()
                if stripped and stripped.endswith("_sdk:"):
                    # Only skip this entry's OWN sub-lines (e.g. its "path:"
                    # line), not every indented line after it - a prior
                    # version kept skipping past subsequent _sdk: entries
                    # and the app's real dependencies (flutter:,
                    # cupertino_icons:, etc.) that follow them in the file,
                    # silently dropping them on every compose after the
                    # first _sdk: entry existed to trigger this branch.
                    entry_indent = len(line) - len(line.lstrip(" "))
                    i += 1
                    while i < len(lines):
                        next_line = lines[i]
                        if next_line.strip() == "":
                            i += 1
                            continue
                        next_indent = len(next_line) - len(next_line.lstrip(" "))
                        if next_indent > entry_indent:
                            i += 1
                            continue
                        break
                    continue
                else:
                    new_lines.append(line)
            elif line.strip() == "":
                new_lines.append(line)
            else:
                new_lines.extend(lines[i:])
                i = len(lines)
                break
            i += 1
        
        sdk_deps = []
        for sdk in sdks:
            sdk_name = sdk["name"] if isinstance(sdk, dict) else sdk
            resolved_path = resolve_active_path(sdk)
            
            pubspec_path_val = resolved_path
            try:
                pubspec_path_val = os.path.relpath(resolved_path, PROJECT_ROOT).replace("\\", "/")
            except ValueError:
                pass
            
            if os.path.exists(os.path.join(resolved_path, "pubspec.yaml")):
                sdk_deps.append(f"  {sdk_name}:\n    path: {pubspec_path_val}\n")
            else:
                print(f"  [-] Skipping {sdk_name} as pubspec.yaml is missing at {resolved_path}.")
        
        if sdk_deps:
            new_lines.insert(dependencies_start + 1, "".join(sdk_deps))
            
        with open(pubspec_path, "w", encoding="utf-8") as f:
            f.writelines(new_lines)
        print(f"[*] Updated SDK dependencies in pubspec.yaml")
    except Exception as e:
        print(f"[!] Error updating pubspec.yaml dependencies: {e}")

# Dependency overrides every composed app needs, regardless of which SDKs it
# installs. Asserted idempotently on every compose run (added if missing,
# left alone if already present) rather than relying on a one-off manual
# pubspec.yaml edit, which does not survive later reruns.
#
# sqlite3 >=3.x ships a package-root hook/build.dart (native asset build
# hook). Combined with Dart 3.10+'s native-assets support being on by
# default, build_runner's internal build-script precompile step hard-fails
# with "'dart compile' does not support build hooks, use 'dart build'
# instead." Pinning below the version that introduced the root-level hook
# avoids it; 2.9.4 only has a hook inside its example/ folder, which is not
# part of the real dependency graph.
REQUIRED_DEPENDENCY_OVERRIDES = {
    "sqlite3": "2.9.4",
}


# `flutter create` scaffolds a boilerplate counter-app smoke test at
# test/widget_test.dart referencing a `MyApp` widget that never exists in a
# composed app (the real entry widget comes from whichever SDK is home_sdk).
# Left in place, it fails `flutter analyze` with "The name 'MyApp' isn't a
# class" on every composed app. Only delete it if it still looks like the
# untouched scaffold — never clobber a real test someone wrote at that path.
STALE_WIDGET_TEST_SIGNATURE = "Counter increments smoke test"

def remove_stale_widget_test():
    test_path = os.path.join(PROJECT_ROOT, "test", "widget_test.dart")
    if not os.path.exists(test_path):
        return
    try:
        with open(test_path, "r", encoding="utf-8") as f:
            content = f.read()
        if STALE_WIDGET_TEST_SIGNATURE in content:
            os.remove(test_path)
            print(f"[*] Removed stale flutter-create scaffold test: {test_path}")
    except Exception as e:
        print(f"[!] Error checking/removing stale widget_test.dart: {e}")

def ensure_lib_gitignore():
    """Ensure the app ignores its generated lib/ - all of it, main.dart included.

    Owner decision (2026-08-02): "run compose fresh at build time, don't
    special-case main.dart as a tracked exception."

    Everything under lib/ is produced by compose, so none of it is tracked and
    a fresh checkout regenerates it. main.dart is NOT an exception: it is
    generated from base_sdk's template, and anything app-specific belongs in a
    manifest - `app_routes` for navigation, `host_routes` in composer.json for
    host-composed pages - all of which ARE tracked and are the real source of
    truth.

    An earlier version of this wrote `lib/*` plus `!lib/main.dart` to keep
    main.dart tracked. That was wrong, and the evidence is what treating
    main.dart as hand-authored actually cost: minilauncher, paas_manager and
    paas_pos each kept a main.dart with no @generated markers, so compose
    injected no SDK wiring and reported success while producing an app that
    registered nothing. Protecting one file does not stop hand-edits being lost
    in generated locations - it institutionalises the exception and hides the
    breakage.

    NOT retroactive by design. An app that already carries the `lib/*` +
    `!lib/main.dart` pair keeps it, because supacharge's main.dart still
    hand-authors an EmbeddedWidgets implementation (`introPage`) that has
    nowhere declarative to live yet. Rewriting its rule here would not delete
    that code, but it would stop tracking the only copy of it. Once
    EmbeddedWidgets has a declarative home and supacharge's is migrated, drop
    the pair from that app and this function will keep it plain thereafter.

    Also ensures `.rokct/__pycache__/` is ignored: compose.py writes
    sdk_installer_base.py into .rokct/ and every cached SDK's install.py
    imports it, so running compose leaves Python bytecode there that hosts
    were accidentally committing (supacharge tracked a .pyc). Checked
    independently of the lib/ rule so legacy lib/* apps still gain it.
    """
    path = os.path.join(PROJECT_ROOT, ".gitignore")
    try:
        lines = []
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                lines = f.read().split(NL)

        has_plain = any(l.strip() in ("lib/", "lib") for l in lines)
        has_star = any(l.strip() == "lib/*" for l in lines)
        has_pycache = any(
            l.strip() in (".rokct/__pycache__/", ".rokct/__pycache__")
            for l in lines
        )

        # Leave a legacy lib/* + !lib/main.dart app alone - see docstring.
        needs_lib = not (has_star or has_plain)
        if not needs_lib and has_pycache:
            return

        while lines and lines[-1].strip() == "":
            lines.pop()
        if needs_lib:
            lines += [
                "",
                "# lib/ is generated by compose on every build - main.dart included -",
                "# so none of it is tracked. Anything app-specific belongs in a manifest",
                "# (app_routes, or host_routes in composer.json), which IS tracked.",
                "lib/",
            ]
            print("[*] .gitignore: ensured lib/ is ignored")
        if not has_pycache:
            lines += [
                "",
                "# Python bytecode from running the .rokct compose/install scripts.",
                ".rokct/__pycache__/",
            ]
            print("[*] .gitignore: ensured .rokct/__pycache__/ is ignored")
        lines.append("")

        with open(path, "w", encoding="utf-8", newline=NL) as f:
            f.write(NL.join(lines))
    except Exception as e:
        print("[!] Could not update .gitignore: %s" % e)


README_RECOMPOSE_START = "<!-- @generated-recompose-start -->"
README_RECOMPOSE_END = "<!-- @generated-recompose-end -->"

def ensure_host_readme():
    """Maintain a marker-delimited 'Recomposing this app' section in the host
    README.md, so anyone opening the repo learns that lib/ is disposable and
    how to regenerate it.

    Same idiom as sdk_installer_base.py's @generated-*-start/-end blocks, in
    Markdown-comment form: the composer owns everything between the markers
    and regenerates it on every run; prose outside the markers is the host's
    own and is never touched. Creates README.md if the host has none.
    Idempotent - when the block already matches, the file is not rewritten.
    """
    section = NL.join([
        README_RECOMPOSE_START,
        "## Recomposing this app",
        "",
        "`lib/` is fully installer-generated and disposable - it is safe to delete",
        "and is gitignored. Anything app-specific lives in tracked manifests",
        "(`app_routes`, or `host_routes` in `composer.json`), never in `lib/` itself.",
        "",
        "To regenerate it:",
        "",
        "```sh",
        "python3 .rokct/initiate.py   # provisions the composer under .rokct/skills/",
        "python3 .rokct/skills/.rok/flutter/scripts/compose.py",
        "```",
        "",
        "Session cleanup (`python3 .rokct/end_protocol.py`) wipes the provisioned",
        "tools again.",
        README_RECOMPOSE_END,
    ])
    path = os.path.join(PROJECT_ROOT, "README.md")
    try:
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                content = f.read()
        else:
            content = "# %s%s" % (os.path.basename(PROJECT_ROOT) or "App", NL)

        start = content.find(README_RECOMPOSE_START)
        end = content.find(README_RECOMPOSE_END)
        if start != -1 and end != -1 and end >= start:
            end += len(README_RECOMPOSE_END)
            updated = content[:start] + section + content[end:]
        else:
            updated = content.rstrip(NL) + NL + NL + section + NL

        if updated != content:
            with open(path, "w", encoding="utf-8", newline=NL) as f:
                f.write(updated)
            print("[*] README.md: refreshed 'Recomposing this app' section")
    except Exception as e:
        print("[!] Could not update README.md: %s" % e)


def ensure_pubspec_overrides():
    pubspec_path = os.path.join(PROJECT_ROOT, "pubspec.yaml")
    if not os.path.exists(pubspec_path):
        return

    try:
        with open(pubspec_path, "r", encoding="utf-8") as f:
            lines = f.readlines()

        overrides_start = -1
        for i, line in enumerate(lines):
            if line.strip() == "dependency_overrides:":
                overrides_start = i
                break

        existing_keys = set()
        if overrides_start != -1:
            i = overrides_start + 1
            while i < len(lines) and (lines[i].startswith(" ") or lines[i].strip() == ""):
                stripped = lines[i].strip()
                if stripped and not stripped.startswith("#") and ":" in stripped:
                    existing_keys.add(stripped.split(":", 1)[0].strip())
                i += 1

        missing = {k: v for k, v in REQUIRED_DEPENDENCY_OVERRIDES.items() if k not in existing_keys}
        if not missing:
            return

        new_override_lines = [f"  {k}: {v}\n" for k, v in missing.items()]

        if overrides_start == -1:
            # No dependency_overrides section at all yet: append one.
            if lines and not lines[-1].endswith("\n"):
                lines[-1] += "\n"
            lines.append("dependency_overrides:\n")
            lines.extend(new_override_lines)
        else:
            lines[overrides_start + 1:overrides_start + 1] = new_override_lines

        with open(pubspec_path, "w", encoding="utf-8") as f:
            f.writelines(lines)
        print(f"[*] Ensured required dependency_overrides in pubspec.yaml: {list(missing.keys())}")
    except Exception as e:
        print(f"[!] Error ensuring pubspec.yaml dependency_overrides: {e}")

def _run_build_runner(cwd, label):
    """build_runner in `cwd`, with the same --force-jit/fallback dance as the
    host run. Returns True on success."""
    build = subprocess.run(
        ["dart", "run", "build_runner", "build", "--force-jit"],
        cwd=cwd, shell=(os.name == "nt"), capture_output=True, text=True,
    )
    if build.returncode != 0 and "Could not find an option named" in (
            build.stdout + build.stderr):
        build = subprocess.run(
            ["dart", "run", "build_runner", "build",
             "--delete-conflicting-outputs"],
            cwd=cwd, shell=(os.name == "nt"), capture_output=True, text=True,
        )
    if build.returncode == 0:
        print(f"[+] Regenerated code for {label}.")
        return True
    print(f"[!] Code generation failed for {label} (exit {build.returncode}).")
    print((build.stdout or "")[-2000:], end="")
    print((build.stderr or "")[-2000:], end="")
    return False


import re

def _fix_cache_dependency_override_paths(sdk_dir, pubspec):
    """Rewrite dependency_overrides path: entries that still point at an
    SDK's OWN repo location (e.g. `../../../core/base/dart`) so they match
    the already-correct `dependencies:` path for the same package once
    copied into `.rokct/cache/<sdk>` (e.g. `../base`).

    Source pubspec.yaml files declare both a `dependencies.<pkg>.path`
    (correct relative to the cache layout, where every SDK cache sits as a
    sibling under `.rokct/cache/`) and a `dependency_overrides.<pkg>.path`
    (correct only relative to the SDK's own standalone repo, for local dev
    codegen there). The installer copies the file verbatim, so the override
    silently breaks `pub get` inside the cache even though the matching
    dependency entry is fine — previously misread as "this SDK can't
    resolve standalone" and skipped rather than fixed.
    """
    try:
        with open(pubspec, "r", encoding="utf-8") as f:
            content = f.read()
    except Exception:
        return
    if "dependency_overrides:" not in content:
        return
    deps_part, _, overrides_part = content.partition("dependency_overrides:")
    changed = False
    for pkg, dep_path in re.findall(r"^  (\w+):\n    path:\s*(\S+)\s*$", deps_part, re.MULTILINE):
        new_overrides_part, n = re.subn(
            rf"(^  {pkg}:\n    path:\s*)\S+\s*$",
            rf"\g<1>{dep_path}",
            overrides_part,
            flags=re.MULTILINE,
        )
        if n and new_overrides_part != overrides_part:
            overrides_part = new_overrides_part
            changed = True
    if changed:
        try:
            with open(pubspec, "w", encoding="utf-8") as f:
                f.write(deps_part + "dependency_overrides:" + overrides_part)
            print(f"[*] Fixed dependency_overrides path(s) in {os.path.basename(sdk_dir)}/pubspec.yaml to match cache layout")
        except Exception as e:
            print(f"[!] Could not fix dependency_overrides in {pubspec}: {e}")


def run_sdk_code_generation():
    """Regenerate codegen INSIDE each composed SDK cache that needs it.

    Table/TrKeys injection rewrites sources in `.rokct/cache/<sdk>` — most
    consequentially the drift `AppDatabase` in base_sdk, whose companion
    `.g.dart` then no longer matches (missing table getters, entity types
    that "aren't defined"). The host's own build_runner run does NOT fix
    this: build_runner only generates for the package it runs in, and each
    cache is a separate path-dependency package.

    Without this step a from-scratch compose (CI, or any clean checkout)
    produces a tree that cannot compile, and the only recovery is running
    build_runner by hand in each cache — which is exactly the kind of
    undocumented manual step composing is supposed to remove.

    Only caches that actually declare build_runner are touched, so SDKs with
    no generated code cost nothing.
    """
    cache_root = os.path.join(PROJECT_ROOT, ".rokct", "cache")
    if not os.path.isdir(cache_root):
        return
    print("\n[*] Regenerating code inside composed SDK caches...")
    for name in sorted(os.listdir(cache_root)):
        sdk_dir = os.path.join(cache_root, name)
        pubspec = os.path.join(sdk_dir, "pubspec.yaml")
        if not os.path.isfile(pubspec):
            continue
        try:
            with open(pubspec, "r", encoding="utf-8") as f:
                needs_codegen = "build_runner" in f.read()
        except Exception:
            continue
        if not needs_codegen:
            continue
        # Some caches carry a dependency_overrides path that's broken
        # relative to the cache layout (see _fix_cache_dependency_override_paths)
        # even though the matching dependencies path is fine; fix it before
        # attempting pub get so those SDKs resolve standalone instead of
        # being (wrongly) treated as unable to.
        _fix_cache_dependency_override_paths(sdk_dir, pubspec)
        pub = subprocess.run(["flutter", "pub", "get"], cwd=sdk_dir,
                             shell=(os.name == "nt"), capture_output=True, text=True)
        if pub.returncode != 0:
            print(f"[*] {name}_sdk does not resolve standalone; skipping "
                  f"its codegen (it ships generated sources).")
            continue
        _run_build_runner(sdk_dir, f"{name}_sdk")


def run_code_generation():
    """Runs `flutter pub get` then `build_runner build`.

    --force-jit avoids a real failure mode: AOT builder compilation invokes
    `dart compile`, which refuses to run when any resolved package (e.g.
    objective_c, pulled in transitively by path_provider_foundation) ships a
    native-asset build hook, failing with "'dart compile' does not support
    build hooks, use 'dart build' instead." JIT mode uses `dart run` instead,
    which has no such restriction. This is slower than AOT but is the only
    mode that works while any dependency in the graph has a hook/build.dart.

    --force-jit is not universally available, though: it's a newer
    build_runner flag, and some dependency graphs resolve an older
    build_runner (observed: 2.5.4) that doesn't recognize it at all
    ("Could not find an option named --force-jit") and exits non-zero before
    running anything. So: try --force-jit first; if it fails specifically
    because the flag itself is unrecognized, retry with
    --delete-conflicting-outputs instead (supported by older versions,
    fine as long as no native-asset-hook package is actually in the graph
    for that project — e.g. sqlite3 pinned below the version that added its
    package-root hook, as this project already does).

    Generation failures are reported but do not abort the script — SDK
    installation already completed successfully at this point, and a
    codegen problem is a separate, visible-in-output concern the caller
    should look at, not a reason to make the whole compose run look failed.
    """
    print("\n[*] Running flutter pub get...")
    pub_get = subprocess.run(["flutter", "pub", "get"], cwd=PROJECT_ROOT, shell=(os.name == "nt"))
    if pub_get.returncode != 0:
        print("[!] flutter pub get failed; skipping code generation.")
        return

    print("[*] Running build_runner (--force-jit, required for packages with native-asset build hooks)...")
    build = subprocess.run(
        ["dart", "run", "build_runner", "build", "--force-jit"],
        cwd=PROJECT_ROOT,
        shell=(os.name == "nt"),
        capture_output=True,
        text=True,
    )
    if build.returncode != 0 and "Could not find an option named" in (build.stdout + build.stderr):
        print("[*] This build_runner version doesn't support --force-jit; retrying with --delete-conflicting-outputs...")
        build = subprocess.run(
            ["dart", "run", "build_runner", "build", "--delete-conflicting-outputs"],
            cwd=PROJECT_ROOT,
            shell=(os.name == "nt"),
        )
    else:
        # Either it succeeded or failed for a real reason - show the output either way.
        print(build.stdout, end="")
        print(build.stderr, end="")

    if build.returncode == 0:
        print("[+] Code generation completed successfully.")
    else:
        print(f"[!] Code generation failed (exit {build.returncode}). Check output above for the specific error.")

def main():
    composer_path = os.path.join(PROJECT_ROOT, "composer.json")
    package_name = None
    sdks_to_install = []
    
    if os.path.exists(composer_path):
        try:
            with open(composer_path, "r", encoding="utf-8") as f:
                config = json.load(f)
            sdks_to_install = [s for s in config.get("sdks", []) if isinstance(s, dict) and s.get("enabled", True)]
            package_name = config.get("package_name")
            print(f"[*] Reading active SDK list from composer.json: {sdks_to_install}")
        except Exception as e:
            print(f"[!] Error reading composer.json: {e}.")
            sys.exit(1)

    # The FULL enabled set from composer.json — pubspec.yaml must always
    # reflect every enabled SDK, never just whichever subset this run is
    # scoped to refresh. A scoped run (e.g. `compose.py auth_sdk`) used to
    # filter sdks_to_install BEFORE it reached update_pubspec_dependencies(),
    # silently dropping every other SDK's pubspec entry and breaking the
    # whole app until a full unscoped recompose restored it.
    all_enabled_sdks = list(sdks_to_install)

    if len(sys.argv) < 2:
        if not sdks_to_install:
            print("[-] No SDKs found to install.")
            sys.exit(1)
    else:
        requested_names = sys.argv[1:]
        sdks_to_install = [s for s in sdks_to_install if s["name"] in requested_names]
        
    if "core_sdk" in [s["name"] if isinstance(s, dict) else s for s in sdks_to_install]:
        core_idx = -1
        for i, s in enumerate(sdks_to_install):
            if (isinstance(s, dict) and s["name"] == "core_sdk") or s == "core_sdk":
                core_idx = i
                break
        if core_idx != -1:
            core_sdk = sdks_to_install.pop(core_idx)
            sdks_to_install.insert(0, core_sdk)
            
    # Cache all SDKs in one consolidated fetch pass
    resolve_and_cache_sdks(sdks_to_install)
    
    # Run the installers. An SDK entry can set "skip_install": true in
    # composer.json to stay fully composed - cached (with role-stripping),
    # listed as a pubspec path dependency, and covered by per-SDK codegen -
    # while its install.py never runs, so none of its manifest installs/
    # routes enter the host app. For apps that consume an SDK's library
    # code but deliberately keep that SDK's pages/routes host-owned
    # (e.g. the host's own page already generates the same route name).
    for sdk in sdks_to_install:
        if isinstance(sdk, dict) and sdk.get("skip_install"):
            print(f"\n[*] Skipping installer for {sdk['name']} (skip_install in composer.json); its cache, pubspec dependency and codegen still apply.")
            continue
        run_installer(sdk)
        
    if package_name:
        update_pubspec_name(package_name)
    
    if all_enabled_sdks:
        update_pubspec_dependencies(all_enabled_sdks)

    ensure_pubspec_overrides()
    ensure_lib_gitignore()
    ensure_host_readme()
    remove_stale_widget_test()
    run_sdk_code_generation()
    run_code_generation()

if __name__ == "__main__":
    main()
