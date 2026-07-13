import os
import json
import shutil
import hashlib

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_FILE = os.path.join(PROJECT_ROOT, ".rokct", "install_state.json")
PACKAGE_JSON_FILE = os.path.join(PROJECT_ROOT, "package.json")
TSCONFIG_FILE = os.path.join(PROJECT_ROOT, "tsconfig.json")

TEXT_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs", ".json", ".md", ".css")
CODE_EXTENSIONS = (".ts", ".tsx", ".js", ".jsx", ".mjs", ".cjs")


def file_hash(path):
    if not os.path.exists(path):
        return None
    hasher = hashlib.sha256()
    with open(path, "rb") as f:
        while chunk := f.read(8192):
            hasher.update(chunk)
    return hasher.hexdigest()


def load_state():
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {"packages": {}}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(state, f, indent=2)


def check_app_alias():
    """Next.js SDK templates import via the '@/*' -> './*' tsconfig path alias
    (the create-next-app default), not a package name placeholder like Dart's
    ${package} — a file copied to app/handson/all/lending/page.tsx importing
    '@/app/lib/roles' resolves correctly in any host that has this alias,
    with zero string rewriting needed. Warn (don't fail) if it's missing,
    since the host may use a differently-configured but equivalent alias.
    """
    if not os.path.exists(TSCONFIG_FILE):
        print("[!] WARNING: no tsconfig.json found at project root. SDK templates assume the "
              "'@/*' -> './*' path alias (create-next-app default); imports may not resolve.")
        return
    try:
        with open(TSCONFIG_FILE, "r", encoding="utf-8-sig") as f:
            raw = f.read()
        # tsconfig.json commonly has comments; do a light substring check rather than a strict
        # JSON parse so this doesn't false-fail on a valid-but-commented file.
        if '"@/*"' not in raw:
            print("[!] WARNING: tsconfig.json does not declare the '@/*' path alias. "
                  "SDK templates use '@/app/...' imports and will not resolve without it.")
    except Exception:
        pass


def check_requires(sdk_name, requires):
    """Some SDKs' copied files import host-app paths the SDK doesn't itself
    provide (a shared UI kit component, another domain's server action, a
    host-wide lib helper) - e.g. Polaris lending's application/new page
    importing an accounting SDK's sales_order action and lib/roles.ts's
    verifyLendingRole. These aren't installable file-copies (there's no
    sibling SDK to draw them from yet in most cases), just a declared
    prerequisite the host must already satisfy. Warn per missing path rather
    than failing the install - the file still gets copied either way, it
    just may not compile until the prerequisite exists.
    """
    missing = [r for r in requires if not os.path.exists(os.path.join(PROJECT_ROOT, r))]
    if missing:
        print(f"  [!] WARNING: {sdk_name} expects these host-app paths to already exist "
              f"(not provided by this SDK): {', '.join(missing)}")


def resolve_sdk_path(sdk_name):
    # 1. Local monorepo dev convention: sdk/<name> relative to project root
    #    (mirrors the Dart installer's equivalent fallback tier).
    local_path = os.path.join(PROJECT_ROOT, "sdk", sdk_name)
    if os.path.exists(local_path):
        return local_path

    # 2. .rokct/cache/<clean_name>, populated by sdk_composer.py's git-based
    #    compose flow. Strip a trailing "_sdk"/"_sdks" suffix to mirror the
    #    cache folder naming sdk_composer.py uses.
    clean_name = sdk_name
    if clean_name.endswith("_sdks"):
        clean_name = clean_name[:-5]
    elif clean_name.endswith("_sdk"):
        clean_name = clean_name[:-4]
    cache_path = os.path.join(PROJECT_ROOT, ".rokct", "cache", clean_name)
    if os.path.exists(cache_path):
        return cache_path

    return None


def install_sdk_files(sdk_name):
    """Install a Next.js SDK's templates into the host app.

    Unlike the Dart installer, there is no route-registration or DI-wiring
    step: Next.js App Router is filesystem-based routing, so placing a page
    file under app/<path>/page.tsx *is* the route registration. The only
    non-file-copy steps are package.json dependency merging (installs
    section) and marker-based text injection for cross-cutting host files
    such as a shared nav/sidebar (integrations section).
    """
    sdk_path = resolve_sdk_path(sdk_name)
    if not sdk_path:
        print(f"[-] Could not resolve path for SDK: {sdk_name}")
        return False

    manifest_path = os.path.join(sdk_path, "manifest.json")
    if not os.path.exists(manifest_path):
        print(f"[-] No manifest found for {sdk_name}")
        return False

    with open(manifest_path, "r", encoding="utf-8-sig") as f:
        manifest = json.load(f)

    version = manifest.get("version", "1.0.0")
    installs = manifest.get("installs", [])

    check_app_alias()
    check_requires(sdk_name, manifest.get("requires", []))

    state = load_state()
    package_state = state["packages"].get(sdk_name, {"version": "0.0.0", "files": {}})
    package_state["version"] = version

    print(f"\n[*] Installing SDK: {sdk_name} (v{version})")

    # 1. Sync files
    for entry in installs:
        from_rel = entry.get("from")
        to_rel = entry.get("to")
        if not from_rel or not to_rel:
            continue

        src_path = os.path.join(sdk_path, from_rel)
        dest_path = os.path.join(PROJECT_ROOT, to_rel)

        if not os.path.exists(src_path):
            print(f"  [-] Template source not found: {from_rel}")
            continue

        files_to_sync = []
        if os.path.isdir(src_path):
            for root, _, filenames in os.walk(src_path):
                for filename in filenames:
                    abs_src = os.path.join(root, filename)
                    rel_to_src = os.path.relpath(abs_src, src_path)
                    abs_dest = os.path.join(dest_path, rel_to_src)
                    rel_dest = os.path.relpath(abs_dest, PROJECT_ROOT).replace("\\", "/")
                    files_to_sync.append((abs_src, abs_dest, rel_dest))
        else:
            rel_dest = to_rel.replace("\\", "/")
            files_to_sync.append((src_path, dest_path, rel_dest))

        for file_src, file_dest, rel_dest in files_to_sync:
            # Check if file already exists in host and was hand-modified since last install
            if os.path.exists(file_dest):
                current_dest_hash = file_hash(file_dest)
                last_known_hash = package_state.get("files", {}).get(rel_dest)
                if last_known_hash and current_dest_hash != last_known_hash:
                    print(f"  [!] WARNING: {rel_dest} has been modified by a developer. "
                          f"Skipping overwrite to prevent data loss. Please merge changes manually.")
                    continue

            os.makedirs(os.path.dirname(file_dest), exist_ok=True)

            is_text = file_dest.endswith(TEXT_EXTENSIONS)
            if is_text:
                with open(file_src, "r", encoding="utf-8", errors="ignore") as fs:
                    content = fs.read()

                if file_dest.endswith(CODE_EXTENSIONS):
                    banner = (
                        "// ==========================================\n"
                        "// [GENERATED TEMPLATE FILE]\n"
                        f"// This file was installed from: {sdk_name}\n"
                        "// Feel free to modify and customize this code.\n"
                        "// Note: If you edit this file, the SDK installer will detect your changes\n"
                        "// and automatically skip overwriting it during future upgrades.\n"
                        "// ==========================================\n\n"
                    )
                    lines = content.splitlines(keepends=True)
                    insert_idx = 0
                    for idx, line in enumerate(lines):
                        trimmed = line.strip()
                        if trimmed == '"use server";' or trimmed == "'use server';" \
                                or trimmed == '"use client";' or trimmed == "'use client';":
                            # Directive prologues must stay the first statement in the file.
                            insert_idx = idx + 1
                            break
                        if trimmed.startswith("import ") or trimmed.startswith("export "):
                            insert_idx = idx
                            break
                    lines.insert(insert_idx, banner)
                    content = "".join(lines)

                with open(file_dest, "w", encoding="utf-8") as fd:
                    fd.write(content)
            else:
                shutil.copy2(file_src, file_dest)

            package_state.setdefault("files", {})[rel_dest] = file_hash(file_dest)
            print(f"  [+] COPY: {rel_dest}")

    # 2. Track dependencies/integrations for this package, then apply across all installed packages
    deps_config = manifest.get("dependencies")
    if deps_config:
        package_state["dependencies"] = deps_config
    dev_deps_config = manifest.get("devDependencies")
    if dev_deps_config:
        package_state["devDependencies"] = dev_deps_config

    integrations_config = manifest.get("integrations")
    if integrations_config:
        package_state["integrations"] = integrations_config

    state["packages"][sdk_name] = package_state
    save_state(state)

    update_package_json_dependencies()
    update_integrations()
    return True


def update_package_json_dependencies():
    """Merge each installed SDK's declared npm dependencies into the host's
    package.json. Additive and non-destructive: an existing pinned version in
    the host always wins (the host app owns its own dependency resolution;
    the SDK only asserts "this package needs to exist somewhere in the tree
    at roughly this version"). Does not run `npm install` — that is
    sdk_composer.py's job, once, after all SDKs have been installed.
    """
    if not os.path.exists(PACKAGE_JSON_FILE):
        print(f"[-] package.json not found: {PACKAGE_JSON_FILE}")
        return

    state = load_state()
    with open(PACKAGE_JSON_FILE, "r", encoding="utf-8-sig") as f:
        pkg = json.load(f)

    pkg.setdefault("dependencies", {})
    pkg.setdefault("devDependencies", {})

    added = []
    for pkg_name, pkg_data in state.get("packages", {}).items():
        for dep_name, dep_version in pkg_data.get("dependencies", {}).items():
            if dep_name not in pkg["dependencies"]:
                pkg["dependencies"][dep_name] = dep_version
                added.append(f"{dep_name}@{dep_version}")
        for dep_name, dep_version in pkg_data.get("devDependencies", {}).items():
            if dep_name not in pkg["devDependencies"] and dep_name not in pkg["dependencies"]:
                pkg["devDependencies"][dep_name] = dep_version
                added.append(f"{dep_name}@{dep_version} (dev)")

    if not added:
        return

    with open(PACKAGE_JSON_FILE, "w", encoding="utf-8") as f:
        json.dump(pkg, f, indent=2)
        f.write("\n")
    print(f"[*] Added to package.json: {', '.join(added)} (run npm install to fetch)")


def update_integrations():
    """Marker-based text injection into shared host files (e.g. a nav/sidebar
    array), mirroring the Dart installer's update_layout_integrations().
    Idempotent: skips if the replacement text is already present.
    """
    state = load_state()
    file_changes = {}

    for pkg_name, pkg_data in state.get("packages", {}).items():
        for integration in pkg_data.get("integrations", []):
            target_rel = integration.get("target")
            placeholder = integration.get("placeholder")
            replacement = integration.get("replacement")
            if not target_rel or not placeholder or not replacement:
                continue

            target_abs = os.path.join(PROJECT_ROOT, target_rel)
            if not os.path.exists(target_abs):
                print(f"  [-] Integration target not found: {target_rel}")
                continue

            content = file_changes.get(target_abs)
            if content is None:
                with open(target_abs, "r", encoding="utf-8") as f:
                    content = f.read()

            if replacement in content:
                continue
            if placeholder not in content:
                print(f"  [!] WARNING: placeholder not found in {target_rel}, skipping integration for {pkg_name}")
                continue

            content = content.replace(placeholder, f"{placeholder}\n{replacement}")
            file_changes[target_abs] = content

    for path, content in file_changes.items():
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        rel_path = os.path.relpath(path, PROJECT_ROOT).replace("\\", "/")
        print(f"[*] Applied integration in: {rel_path}")
