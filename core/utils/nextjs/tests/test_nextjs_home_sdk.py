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

"""Regression tests for the Next.js composer's home_sdk flag - parity with
core/utils/flutter/tests/test_home_sdk_precedence.py.

Background: the Dart composer profiles flag one sdks[] entry "home_sdk":
true; the Next.js templates had no such key, so which SDK's app/page.tsx
served `/` was decided by list order alone (install_sdk_files() let the
LAST installer that wrote a path keep it) and base_sdk's single-answer
landing registries (header-menu, hero-form, plans-query, site-metadata)
answered whichever SDK's line was injected first. These tests pin:

  * resolve_home_sdk() answers the one flagged entry, None (with an [i]
    line) when nothing is flagged, and refuses two flagged entries - in
    both the installer base and the composer
  * order_sdks_for_install() moves the home SDK to the front, behind the
    kernel entries (telemetry_sdk, base_sdk) listed ahead of it
  * a non-home SDK skips every path the home SDK's manifest installs, so
    the flagged home wins in BOTH compose orders
  * the home SDK takes over an unmodified copy another SDK installed on an
    earlier compose, but never a developer-modified one
  * only the home SDK injects at a single-answer registry marker: another
    package's line there is skipped with a log line, never a failure;
    without a home SDK the lines append in order with a warning, and
    multi-contributor markers (hero-copy) stay open to everyone
  * the composer records "home_sdk" in .rokct/cache/install_state.json
  * without composer.json (an offline compose from the committed cache) the
    installer base reads the flag from the shell lock's .rokct/lock.json
    sdks[] entries instead, with the same one-flag rule; composer.json wins
    when both exist, and a lock without the flag composes as before

Run:  python -m pytest core/utils/nextjs/tests -q
  or: python core/utils/nextjs/tests/test_nextjs_home_sdk.py
"""

import importlib.util
import io
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

_NEXTJS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_INSTALLER_SRC = os.path.join(_NEXTJS_DIR, "sdk_installer_base.py")
_COMPOSER_SRC = os.path.join(_NEXTJS_DIR, "sdk_composer.py")

_module_counter = 0

HOME_REL = "app/page.tsx"
ASSET_REL = "public/brand/logo.txt"
HEADER_MENU_REL = "components/custom/landing/header-menu.ts"
HERO_COPY_REL = "components/custom/landing/hero-copy.ts"
HEADER_MENU_MARKER = "// @rokct-sdk-header-menu-start"
HERO_COPY_MARKER = "// @rokct-sdk-hero-copy-start"


def _load_module(src, name):
    spec = importlib.util.spec_from_file_location(name, src)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class HomeSdkTestBase(unittest.TestCase):
    """Throwaway host sandbox with two cached SDKs, alpha_sdk and beta_sdk,
    that both install the same home page and the same asset file and both
    register a header-menu (single-answer) and hero-copy (merged) line."""

    def setUp(self):
        self.project_root = tempfile.mkdtemp(prefix="nextjs_home_test_")
        self.addCleanup(shutil.rmtree, self.project_root, ignore_errors=True)
        self.rokct_dir = os.path.join(self.project_root, ".rokct")
        self.cache_dir = os.path.join(self.rokct_dir, "cache")
        os.makedirs(self.cache_dir)
        with open(
            os.path.join(self.project_root, "package.json"), "w", encoding="utf-8"
        ) as f:
            json.dump({"name": "testapp", "dependencies": {}}, f)
        with open(
            os.path.join(self.project_root, "tsconfig.json"), "w", encoding="utf-8"
        ) as f:
            f.write('{"compilerOptions": {"paths": {"@/*": ["./*"]}}}\n')
        for rel, marker in (
            (HEADER_MENU_REL, HEADER_MENU_MARKER),
            (HERO_COPY_REL, HERO_COPY_MARKER),
        ):
            path = os.path.join(self.project_root, rel)
            os.makedirs(os.path.dirname(path), exist_ok=True)
            with open(path, "w", encoding="utf-8") as f:
                f.write(
                    "export const REGISTRY = [\n"
                    f"  {marker}\n"
                    f"  {marker.replace('-start', '-end')}\n"
                    "];\n"
                )
        for name in ("alpha_sdk", "beta_sdk"):
            self.write_sdk(name)

    def import_installer(self):
        """Fresh module copy (the resolver memoizes per process, and a real
        compose runs one process per SDK installer). PROJECT_ROOT is derived
        from the module's own location, so it is copied into .rokct/."""
        global _module_counter
        _module_counter += 1
        module_path = os.path.join(self.rokct_dir, "sdk_installer_base.py")
        shutil.copy2(_INSTALLER_SRC, module_path)
        return _load_module(
            module_path, f"nextjs_installer_home_test_{_module_counter}"
        )

    def import_composer(self):
        """The composer keyed to this sandbox (its PROJECT_ROOT is the cwd at
        import time, so it is repointed after loading)."""
        global _module_counter
        _module_counter += 1
        module = _load_module(
            _COMPOSER_SRC, f"nextjs_composer_home_test_{_module_counter}"
        )
        module.PROJECT_ROOT = self.project_root
        module.INSTALL_STATE_FILE = os.path.join(self.cache_dir, "install_state.json")
        module.LEGACY_INSTALL_STATE_FILE = os.path.join(
            self.rokct_dir, "install_state.json"
        )
        return module

    def write_sdk(self, sdk_name, single_answer=True):
        clean = sdk_name[:-4]
        sdk_dir = os.path.join(self.cache_dir, clean)
        os.makedirs(os.path.join(sdk_dir, "templates", "brand"), exist_ok=True)
        with open(
            os.path.join(sdk_dir, "templates", "page.tsx"), "w", encoding="utf-8"
        ) as f:
            f.write(f"// {sdk_name} home\nexport default function Page() {{}}\n")
        with open(
            os.path.join(sdk_dir, "templates", "brand", "logo.txt"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(f"{sdk_name} logo\n")
        integrations = [
            {
                "target": HERO_COPY_REL,
                "placeholder": HERO_COPY_MARKER,
                "replacement": f'  {{ id: "{clean}-hero-copy" }},',
            }
        ]
        if single_answer:
            integrations.append(
                {
                    "target": HEADER_MENU_REL,
                    "placeholder": HEADER_MENU_MARKER,
                    "replacement": f'  {{ id: "{clean}-header-menu" }},',
                }
            )
        manifest = {
            "name": sdk_name,
            "version": "1.0.0",
            "installs": [
                {"from": "templates/page.tsx", "to": HOME_REL},
                {"from": "templates/brand", "to": "public/brand"},
            ],
            "integrations": integrations,
        }
        with open(os.path.join(sdk_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)

    def composer_sdks(self, order, home=None, extra_home=()):
        sdks = []
        for name in order:
            entry = {"name": name, "enabled": True, "source": "git"}
            entry["home_sdk"] = name == home or name in extra_home
            sdks.append(entry)
        return sdks

    def write_composer(self, order, home=None, extra_home=()):
        with open(
            os.path.join(self.project_root, "composer.json"), "w", encoding="utf-8"
        ) as f:
            json.dump({"sdks": self.composer_sdks(order, home, extra_home)}, f)

    def lock_sdks(self, order, home=None, extra_home=()):
        """sdks[] entries the way a shell's scripts/compose.sh build_lock()
        writes them: no "enabled" key (only enabled entries are locked),
        "home_sdk" copied from the composer profile."""
        return [
            {
                "name": name,
                "home_sdk": name == home or name in extra_home,
                "cache": f".rokct/cache/{name[:-4]}",
                "version": "1.0.0",
            }
            for name in order
        ]

    def write_lock(self, order, home=None, extra_home=(), with_flag=True):
        sdks = self.lock_sdks(order, home, extra_home)
        if not with_flag:
            for entry in sdks:
                del entry["home_sdk"]
        with open(
            os.path.join(self.rokct_dir, "lock.json"), "w", encoding="utf-8"
        ) as f:
            json.dump({"generated_from": "scripts/compose.sh refresh", "sdks": sdks}, f)

    def install(self, sdk_name):
        installer = self.import_installer()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            ok = installer.install_sdk_files(sdk_name)
        self.assertTrue(ok, out.getvalue() + err.getvalue())
        return out.getvalue()

    def compose(self, order, home=None):
        self.write_composer(order, home)
        return {name: self.install(name) for name in order}

    def read(self, rel):
        with open(os.path.join(self.project_root, rel), "r", encoding="utf-8") as f:
            return f.read()

    def state(self):
        with open(
            os.path.join(self.cache_dir, "install_state.json"), "r", encoding="utf-8"
        ) as f:
            return json.load(f)

    def file_owners(self, rel):
        return sorted(
            name
            for name, pkg in self.state()["packages"].items()
            if rel in (pkg.get("files") or {})
        )

    def assert_home_is(self, sdk_name):
        self.assertIn(f"// {sdk_name} home", self.read(HOME_REL))
        self.assertEqual(self.read(ASSET_REL), f"{sdk_name} logo\n")
        self.assertEqual(self.file_owners(HOME_REL), [sdk_name])
        self.assertEqual(self.file_owners(ASSET_REL), [sdk_name])


class TestResolveHomeSdkInstaller(HomeSdkTestBase):
    def test_one_flagged_entry_is_the_home(self):
        self.write_composer(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.assertEqual(self.import_installer().resolve_home_sdk(), "beta_sdk")

    def test_explicit_sdks_argument_is_read_instead_of_composer_json(self):
        installer = self.import_installer()
        sdks = self.composer_sdks(["alpha_sdk", "beta_sdk"], home="alpha_sdk")
        self.assertEqual(installer.resolve_home_sdk(sdks), "alpha_sdk")

    def test_none_flagged_is_none_with_an_info_line(self):
        self.write_composer(["alpha_sdk", "beta_sdk"])
        installer = self.import_installer()
        out = io.StringIO()
        with redirect_stdout(out):
            resolved = installer.resolve_home_sdk()
        self.assertIsNone(resolved)
        self.assertIn("[i] no home SDK", out.getvalue())

    def test_missing_key_is_none(self):
        with open(
            os.path.join(self.project_root, "composer.json"), "w", encoding="utf-8"
        ) as f:
            json.dump({"sdks": [{"name": "alpha_sdk"}, {"name": "beta_sdk"}]}, f)
        with redirect_stdout(io.StringIO()):
            self.assertIsNone(self.import_installer().resolve_home_sdk())

    def test_without_composer_json_is_none(self):
        with redirect_stdout(io.StringIO()):
            self.assertIsNone(self.import_installer().resolve_home_sdk())

    def test_two_flagged_entries_raise(self):
        self.write_composer(
            ["alpha_sdk", "beta_sdk"], home="alpha_sdk", extra_home=("beta_sdk",)
        )
        installer = self.import_installer()
        with self.assertRaises(installer.HomeSdkConflict) as ctx:
            installer.resolve_home_sdk()
        self.assertIn("alpha_sdk, beta_sdk", str(ctx.exception))
        self.assertIn("exactly one", str(ctx.exception))

    def test_disabled_entry_is_never_home(self):
        sdks = self.composer_sdks(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        sdks[1]["enabled"] = False
        with redirect_stdout(io.StringIO()):
            self.assertIsNone(self.import_installer().resolve_home_sdk(sdks))


class TestResolveHomeSdkFromLock(HomeSdkTestBase):
    """An offline compose (a Next.js shell's scripts/compose.sh at Vercel)
    runs the cached installers with composer.json gone - it was a
    refresh-time scratch copy of the registry template - so the installer
    base falls back to the flag the shell lock copied from it."""

    def test_lock_is_read_when_composer_json_is_absent(self):
        self.write_lock(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.assertEqual(self.import_installer().resolve_home_sdk(), "beta_sdk")

    def test_composer_json_wins_over_the_lock(self):
        self.write_composer(["alpha_sdk", "beta_sdk"], home="alpha_sdk")
        self.write_lock(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.assertEqual(self.import_installer().resolve_home_sdk(), "alpha_sdk")

    def test_lock_without_the_flag_is_none_with_an_info_line(self):
        self.write_lock(["alpha_sdk", "beta_sdk"], with_flag=False)
        out = io.StringIO()
        with redirect_stdout(out):
            resolved = self.import_installer().resolve_home_sdk()
        self.assertIsNone(resolved)
        self.assertIn("[i] no home SDK", out.getvalue())

    def test_lock_with_every_flag_false_is_none(self):
        self.write_lock(["alpha_sdk", "beta_sdk"])
        with redirect_stdout(io.StringIO()):
            self.assertIsNone(self.import_installer().resolve_home_sdk())

    def test_two_flagged_lock_entries_raise(self):
        self.write_lock(
            ["alpha_sdk", "beta_sdk"], home="alpha_sdk", extra_home=("beta_sdk",)
        )
        installer = self.import_installer()
        with self.assertRaises(installer.HomeSdkConflict) as ctx:
            installer.resolve_home_sdk()
        self.assertIn("alpha_sdk, beta_sdk", str(ctx.exception))

    def test_unreadable_lock_warns_and_is_none(self):
        with open(
            os.path.join(self.rokct_dir, "lock.json"), "w", encoding="utf-8"
        ) as f:
            f.write("{not json")
        out = io.StringIO()
        with redirect_stdout(out):
            resolved = self.import_installer().resolve_home_sdk()
        self.assertIsNone(resolved)
        self.assertIn("[!] WARNING: unreadable lock.json", out.getvalue())
        self.assertIn("[i] no home SDK", out.getvalue())

    def test_lock_that_is_not_an_object_is_none(self):
        with open(
            os.path.join(self.rokct_dir, "lock.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(["alpha_sdk"], f)
        with redirect_stdout(io.StringIO()):
            self.assertIsNone(self.import_installer().resolve_home_sdk())

    def compose_from_lock(self, order, home=None):
        self.assertFalse(
            os.path.exists(os.path.join(self.project_root, "composer.json"))
        )
        self.write_lock(order, home)
        return {name: self.install(name) for name in order}

    def test_flagged_home_wins_from_the_lock_when_listed_first(self):
        logs = self.compose_from_lock(["beta_sdk", "alpha_sdk"], home="beta_sdk")
        self.assert_home_is("beta_sdk")
        self.assertIn(
            "[~] skipped app/page.tsx (owned by home SDK beta_sdk)", logs["alpha_sdk"]
        )
        self.assertIn('{ id: "beta-header-menu" }', self.read(HEADER_MENU_REL))
        self.assertNotIn('{ id: "alpha-header-menu" }', self.read(HEADER_MENU_REL))
        self.assertIn('{ id: "alpha-hero-copy" }', self.read(HERO_COPY_REL))

    def test_flagged_home_wins_from_the_lock_when_listed_last(self):
        self.compose_from_lock(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.assert_home_is("beta_sdk")
        self.assertIn('{ id: "beta-header-menu" }', self.read(HEADER_MENU_REL))
        self.assertNotIn('{ id: "alpha-header-menu" }', self.read(HEADER_MENU_REL))

    def test_lock_without_the_flag_keeps_last_writer_wins(self):
        self.write_lock(["alpha_sdk", "beta_sdk"], with_flag=False)
        logs = {name: self.install(name) for name in ["alpha_sdk", "beta_sdk"]}
        self.assertIn("// beta_sdk home", self.read(HOME_REL))
        self.assertEqual(self.file_owners(HOME_REL), ["alpha_sdk", "beta_sdk"])
        self.assertNotIn("[~] skipped", logs["alpha_sdk"] + logs["beta_sdk"])
        self.assertIn('{ id: "alpha-header-menu" }', self.read(HEADER_MENU_REL))
        self.assertIn('{ id: "beta-header-menu" }', self.read(HEADER_MENU_REL))
        self.assertIn("[!]", logs["beta_sdk"])


class TestResolveHomeSdkComposer(HomeSdkTestBase):
    def test_one_flagged_entry(self):
        composer = self.import_composer()
        sdks = self.composer_sdks(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.assertEqual(composer.resolve_home_sdk(sdks), "beta_sdk")

    def test_none_flagged(self):
        composer = self.import_composer()
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertIsNone(
                composer.resolve_home_sdk(self.composer_sdks(["alpha_sdk", "beta_sdk"]))
            )
        self.assertIn("[i] no home SDK", out.getvalue())

    def test_two_flagged_entries_raise(self):
        composer = self.import_composer()
        sdks = self.composer_sdks(
            ["alpha_sdk", "beta_sdk"], home="alpha_sdk", extra_home=("beta_sdk",)
        )
        with self.assertRaises(ValueError) as ctx:
            composer.resolve_home_sdk(sdks)
        self.assertIn("alpha_sdk, beta_sdk", str(ctx.exception))


class TestOrderSdksForInstall(HomeSdkTestBase):
    def names(self, entries):
        return [e["name"] for e in entries]

    def test_home_moves_behind_the_kernel_entries(self):
        composer = self.import_composer()
        sdks = self.composer_sdks(
            ["telemetry_sdk", "base_sdk", "auth_sdk", "lms_sdk"], home="lms_sdk"
        )
        self.assertEqual(
            self.names(composer.order_sdks_for_install(sdks)),
            ["telemetry_sdk", "base_sdk", "lms_sdk", "auth_sdk"],
        )

    def test_home_moves_to_the_front_without_kernel_entries(self):
        composer = self.import_composer()
        sdks = self.composer_sdks(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.assertEqual(
            self.names(composer.order_sdks_for_install(sdks)), ["beta_sdk", "alpha_sdk"]
        )

    def test_kernel_listed_after_the_home_stays_put(self):
        composer = self.import_composer()
        sdks = self.composer_sdks(
            ["base_sdk", "auth_sdk", "products_sdk", "telemetry_sdk"],
            home="products_sdk",
        )
        self.assertEqual(
            self.names(composer.order_sdks_for_install(sdks)),
            ["base_sdk", "products_sdk", "auth_sdk", "telemetry_sdk"],
        )

    def test_no_flag_keeps_composer_order(self):
        composer = self.import_composer()
        sdks = self.composer_sdks(["alpha_sdk", "beta_sdk"])
        self.assertEqual(
            self.names(composer.order_sdks_for_install(sdks)), ["alpha_sdk", "beta_sdk"]
        )
        self.assertIsNot(composer.order_sdks_for_install(sdks), sdks)


class TestFlaggedHomeWinsRegardlessOfOrder(HomeSdkTestBase):
    def setUp(self):
        super().setUp()
        # Only the home registers a header-menu line in these composes so
        # the ownership rule, not the registry rule, is what is exercised.
        self.write_sdk("alpha_sdk", single_answer=False)

    def test_home_listed_last(self):
        outputs = self.compose(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.assert_home_is("beta_sdk")
        self.assertIn(
            f"[~] skipped {HOME_REL} (owned by home SDK beta_sdk)", outputs["alpha_sdk"]
        )
        self.assertIn(
            f"[~] skipped {ASSET_REL} (owned by home SDK beta_sdk)",
            outputs["alpha_sdk"],
        )

    def test_home_listed_first(self):
        outputs = self.compose(["beta_sdk", "alpha_sdk"], home="beta_sdk")
        self.assert_home_is("beta_sdk")
        self.assertIn("owned by home SDK beta_sdk", outputs["alpha_sdk"])

    def test_recompose_is_stable(self):
        self.compose(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.compose(["beta_sdk", "alpha_sdk"], home="beta_sdk")
        self.assert_home_is("beta_sdk")

    def test_owned_set_expands_directory_installs(self):
        self.write_composer(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        installer = self.import_installer()
        self.assertEqual(
            installer.home_sdk_owned_files("beta_sdk"), {HOME_REL, ASSET_REL}
        )
        self.assertEqual(installer.home_sdk_owned_files(None), set())

    def test_no_flag_keeps_last_writer_wins(self):
        # Pre-flag behaviour, unchanged: the last installer to write a path
        # keeps it, every writer keeps its own record of the file, and no
        # path is skipped as home-owned.
        with redirect_stdout(io.StringIO()):
            outputs = self.compose(["alpha_sdk", "beta_sdk"])
        self.assertIn("// beta_sdk home", self.read(HOME_REL))
        self.assertEqual(self.read(ASSET_REL), "beta_sdk logo\n")
        self.assertEqual(self.file_owners(HOME_REL), ["alpha_sdk", "beta_sdk"])
        self.assertNotIn(
            "owned by home SDK", outputs["alpha_sdk"] + outputs["beta_sdk"]
        )


class TestHomeTakesOverEarlierInstalls(HomeSdkTestBase):
    def setUp(self):
        super().setUp()
        self.write_sdk("alpha_sdk", single_answer=False)

    def test_unmodified_copy_from_previous_compose_is_taken_over(self):
        self.compose(["alpha_sdk"])
        self.assert_home_is("alpha_sdk")
        outputs = self.compose(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.assert_home_is("beta_sdk")
        self.assertIn("takes it over", outputs["beta_sdk"])

    def test_developer_modified_copy_is_never_overwritten(self):
        self.compose(["alpha_sdk"])
        edited = self.read(HOME_REL) + "// local edit\n"
        with open(
            os.path.join(self.project_root, HOME_REL), "w", encoding="utf-8"
        ) as f:
            f.write(edited)
        outputs = self.compose(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.assertEqual(self.read(HOME_REL), edited)
        self.assertIn("modified by a developer", outputs["beta_sdk"])
        self.assertNotIn(HOME_REL, self.state()["packages"]["beta_sdk"]["files"])
        # The asset file was untouched, so that one is taken over as usual.
        self.assertEqual(self.read(ASSET_REL), "beta_sdk logo\n")


class TestSingleAnswerRegistries(HomeSdkTestBase):
    def test_non_home_line_is_skipped_when_it_arrives_second(self):
        self.write_composer(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.install("beta_sdk")
        out = self.install("alpha_sdk")
        self.assertIn(
            "[~] skipped @rokct-sdk-header-menu-start from alpha_sdk: registry owned by home SDK beta_sdk",
            out,
        )
        header_menu = self.read(HEADER_MENU_REL)
        self.assertIn('{ id: "beta-header-menu" },', header_menu)
        self.assertNotIn("alpha-header-menu", header_menu)

    def test_non_home_line_is_skipped_when_it_arrives_first(self):
        self.write_composer(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        out = self.install("alpha_sdk")
        self.assertIn("[~] skipped @rokct-sdk-header-menu-start from alpha_sdk", out)
        self.assertNotIn("alpha-header-menu", self.read(HEADER_MENU_REL))
        self.install("beta_sdk")
        header_menu = self.read(HEADER_MENU_REL)
        self.assertIn('{ id: "beta-header-menu" },', header_menu)
        self.assertNotIn("alpha-header-menu", header_menu)

    def test_skip_never_fails_the_compose(self):
        self.write_composer(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        installer = self.import_installer()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            ok = installer.install_sdk_files("alpha_sdk")
        self.assertTrue(ok)
        self.assertNotIn("FAILED", out.getvalue() + err.getvalue())

    def test_home_alone_at_a_single_answer_marker_is_injected(self):
        self.write_sdk("alpha_sdk", single_answer=False)
        self.compose(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.assertIn('{ id: "beta-header-menu" },', self.read(HEADER_MENU_REL))
        self.assertNotIn("alpha-header-menu", self.read(HEADER_MENU_REL))

    def test_merged_markers_stay_multi_contributor(self):
        self.compose(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        hero_copy = self.read(HERO_COPY_REL)
        self.assertIn('{ id: "alpha-hero-copy" },', hero_copy)
        self.assertIn('{ id: "beta-hero-copy" },', hero_copy)

    def test_no_home_only_warns_and_appends_in_order(self):
        outputs = self.compose(["alpha_sdk", "beta_sdk"])
        self.assertIn("WARNING", outputs["beta_sdk"])
        self.assertIn("@rokct-sdk-header-menu-start", outputs["beta_sdk"])
        self.assertIn("alpha_sdk, beta_sdk", outputs["beta_sdk"])
        self.assertNotIn(
            "[~] skipped @rokct", outputs["alpha_sdk"] + outputs["beta_sdk"]
        )
        header_menu = self.read(HEADER_MENU_REL)
        self.assertLess(
            header_menu.index("alpha-header-menu"),
            header_menu.index("beta-header-menu"),
        )


class TestRecordHomeSdk(HomeSdkTestBase):
    def test_home_is_recorded_and_survives_the_installers(self):
        composer = self.import_composer()
        composer.record_home_sdk("beta_sdk")
        self.assertEqual(self.state()["home_sdk"], "beta_sdk")
        self.write_sdk("alpha_sdk", single_answer=False)
        self.compose(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        state = self.state()
        self.assertEqual(state["home_sdk"], "beta_sdk")
        self.assertEqual(sorted(state["packages"]), ["alpha_sdk", "beta_sdk"])

    def test_no_home_is_recorded_as_null_without_losing_packages(self):
        self.write_sdk("alpha_sdk", single_answer=False)
        self.compose(["alpha_sdk"])
        composer = self.import_composer()
        composer.record_home_sdk(None)
        state = self.state()
        self.assertIsNone(state["home_sdk"])
        self.assertIn("alpha_sdk", state["packages"])

    def test_legacy_state_location_is_migrated_first(self):
        legacy = os.path.join(self.rokct_dir, "install_state.json")
        with open(legacy, "w", encoding="utf-8") as f:
            json.dump({"packages": {"alpha_sdk": {"version": "0.9.0", "files": {}}}}, f)
        composer = self.import_composer()
        composer.record_home_sdk("beta_sdk")
        self.assertFalse(os.path.exists(legacy))
        state = self.state()
        self.assertEqual(state["home_sdk"], "beta_sdk")
        self.assertIn("alpha_sdk", state["packages"])


if __name__ == "__main__":
    unittest.main()
