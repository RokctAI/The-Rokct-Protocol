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

"""Regression tests for sdk_installer_base.py's home_sdk precedence.

Background: composer profiles flag one sdks[] entry "home_sdk": true, but
the flag was inert. resolve_home_sdk() only scanned PROJECT_ROOT/sdk/ - a
directory the composer never populates (SDKs are extracted under
.rokct/cache/) - so it always answered "core_sdk", and which SDK's home
files landed was decided by compose order alone: install_sdk_files_and_
routes() lets the FIRST installer that writes a path keep it. These tests
pin the fix:

  * resolve_home_sdk() reads the composer.json flag, falls back to the
    composed SDKs' own manifests, and still answers "core_sdk" when no
    home_sdk is set anywhere
  * with two SDKs both installing the same home file, the flagged one
    wins in BOTH compose orders
  * the home SDK takes over an unmodified copy another SDK installed on
    an earlier compose (pre-fix state), but never a developer-modified one

Run:  python -m pytest core/utils/flutter/tests -q
  or: python core/utils/flutter/tests/test_home_sdk_precedence.py
"""

import hashlib
import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

_INSTALLER_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sdk_installer_base.py",
)

_module_counter = 0

HOME_REL = "lib/presentation/pages/home/home_page.dart"
ASSET_REL = "assets/logo.txt"


class HomeSdkTestBase(unittest.TestCase):
    """Throwaway host sandbox with two cached SDKs, alpha_sdk and beta_sdk,
    that both install the same home page and the same asset file."""

    def setUp(self):
        self.project_root = tempfile.mkdtemp(prefix="sdk_home_test_")
        self.addCleanup(shutil.rmtree, self.project_root, ignore_errors=True)
        self.rokct_dir = os.path.join(self.project_root, ".rokct")
        self.cache_dir = os.path.join(self.rokct_dir, "cache")
        os.makedirs(self.cache_dir)
        # A pubspec.yaml must exist or load_state() would try `flutter create`.
        with open(
            os.path.join(self.project_root, "pubspec.yaml"), "w", encoding="utf-8"
        ) as f:
            f.write("name: testapp\nflutter:\n  assets:\n")
        self._saved_strict = os.environ.pop("ROKCT_COMPOSE_STRICT", None)
        self.addCleanup(self._restore_strict)
        for name in ("alpha_sdk", "beta_sdk"):
            self.write_sdk(name)

    def _restore_strict(self):
        os.environ.pop("ROKCT_COMPOSE_STRICT", None)
        if self._saved_strict is not None:
            os.environ["ROKCT_COMPOSE_STRICT"] = self._saved_strict

    def import_installer(self):
        """Fresh module copy (the resolver memoizes per process, and a real
        compose runs one process per SDK installer)."""
        global _module_counter
        _module_counter += 1
        module_path = os.path.join(self.rokct_dir, "sdk_installer_base.py")
        shutil.copy2(_INSTALLER_SRC, module_path)
        spec = importlib.util.spec_from_file_location(
            f"sdk_installer_base_home_test_{_module_counter}", module_path
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def write_sdk(self, sdk_name, manifest_home_sdk=None):
        clean = sdk_name[:-4]
        sdk_dir = os.path.join(self.cache_dir, clean)
        os.makedirs(os.path.join(sdk_dir, "templates", "assets"), exist_ok=True)
        with open(
            os.path.join(sdk_dir, "templates", "home_page.dart"), "w", encoding="utf-8"
        ) as f:
            f.write(f"// {sdk_name} home\nimport 'x.dart';\nclass HomePage {{}}\n")
        with open(
            os.path.join(sdk_dir, "templates", "assets", "logo.txt"),
            "w",
            encoding="utf-8",
        ) as f:
            f.write(f"{sdk_name} logo\n")
        manifest = {
            "version": "1.0.0",
            "installs": [
                {"from": "templates/home_page.dart", "to": HOME_REL},
                {"from": "templates/assets", "to": "assets"},
            ],
        }
        if manifest_home_sdk is not None:
            manifest["home_sdk"] = manifest_home_sdk
        with open(os.path.join(sdk_dir, "manifest.json"), "w", encoding="utf-8") as f:
            json.dump(manifest, f)

    def write_composer(self, order, home=None):
        sdks = []
        for name in order:
            entry = {"name": name, "enabled": True, "source": "git"}
            if name == home:
                entry["home_sdk"] = True
            sdks.append(entry)
        with open(
            os.path.join(self.project_root, "composer.json"), "w", encoding="utf-8"
        ) as f:
            json.dump({"package_name": "testapp", "sdks": sdks}, f)

    def install(self, sdk_name):
        installer = self.import_installer()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            ok = installer.install_sdk_files_and_routes(sdk_name)
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


class TestResolveHomeSdk(HomeSdkTestBase):
    def test_composer_flag_wins(self):
        self.write_composer(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.assertEqual(self.import_installer().resolve_home_sdk(), "beta_sdk")

    def test_composer_flag_beats_manifest_claims(self):
        self.write_sdk("alpha_sdk", manifest_home_sdk=True)
        self.write_composer(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.assertEqual(self.import_installer().resolve_home_sdk(), "beta_sdk")

    def test_manifest_fallback_when_composer_has_no_flag(self):
        self.write_sdk("beta_sdk", manifest_home_sdk=True)
        self.write_composer(["alpha_sdk", "beta_sdk"])
        self.assertEqual(self.import_installer().resolve_home_sdk(), "beta_sdk")

    def test_ambiguous_manifest_claims_warn_and_keep_compose_order(self):
        self.write_sdk("alpha_sdk", manifest_home_sdk=True)
        self.write_sdk("beta_sdk", manifest_home_sdk=True)
        self.write_composer(["alpha_sdk", "beta_sdk"])
        installer = self.import_installer()
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            resolved = installer.resolve_home_sdk()
        self.assertEqual(resolved, "alpha_sdk")
        self.assertIn("WARNING", out.getvalue())
        self.assertIn("alpha_sdk, beta_sdk", out.getvalue())

    def test_default_unchanged_when_nothing_is_flagged(self):
        self.write_composer(["alpha_sdk", "beta_sdk"])
        self.assertEqual(self.import_installer().resolve_home_sdk(), "core_sdk")

    def test_default_unchanged_without_composer_json(self):
        self.assertEqual(self.import_installer().resolve_home_sdk(), "core_sdk")

    def test_disabled_entry_is_never_home(self):
        self.write_composer(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        with open(
            os.path.join(self.project_root, "composer.json"), "r+", encoding="utf-8"
        ) as f:
            config = json.load(f)
            config["sdks"][1]["enabled"] = False
            f.seek(0)
            f.truncate()
            json.dump(config, f)
        self.assertEqual(self.import_installer().resolve_home_sdk(), "core_sdk")


class TestFlaggedHomeWinsRegardlessOfOrder(HomeSdkTestBase):
    def test_home_listed_last(self):
        outputs = self.compose(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.assert_home_is("beta_sdk")
        self.assertIn("owned by the home SDK beta_sdk", outputs["alpha_sdk"])

    def test_home_listed_first(self):
        outputs = self.compose(["beta_sdk", "alpha_sdk"], home="beta_sdk")
        self.assert_home_is("beta_sdk")
        self.assertIn("owned by the home SDK beta_sdk", outputs["alpha_sdk"])

    def test_other_flag_flips_the_winner(self):
        self.compose(["alpha_sdk", "beta_sdk"], home="alpha_sdk")
        self.assert_home_is("alpha_sdk")

    def test_recompose_is_stable(self):
        self.compose(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.compose(["beta_sdk", "alpha_sdk"], home="beta_sdk")
        self.assert_home_is("beta_sdk")

    def test_no_flag_keeps_first_writer_wins(self):
        self.compose(["alpha_sdk", "beta_sdk"])
        self.assert_home_is("alpha_sdk")
        self.compose(["beta_sdk", "alpha_sdk"])
        self.assert_home_is("alpha_sdk")


class TestHomeTakesOverEarlierInstalls(HomeSdkTestBase):
    def test_unmodified_copy_from_previous_compose_is_taken_over(self):
        # A shell composed before the fix: alpha's copy is on disk and
        # recorded under alpha's package state.
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
        self.assertIn("not installed by this SDK", outputs["beta_sdk"])
        self.assertNotIn(HOME_REL, self.state()["packages"]["beta_sdk"]["files"])
        # The asset file was untouched, so that one is taken over as usual.
        self.assertEqual(self.read(ASSET_REL), "beta_sdk logo\n")

    def test_host_owned_file_is_never_overwritten(self):
        host_file = os.path.join(self.project_root, HOME_REL)
        os.makedirs(os.path.dirname(host_file))
        with open(host_file, "w", encoding="utf-8") as f:
            f.write("// hand-written host home\n")
        self.compose(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        self.assertEqual(self.read(HOME_REL), "// hand-written host home\n")
        self.assertEqual(self.file_owners(HOME_REL), [])


class TestOwnedFileSet(HomeSdkTestBase):
    def test_directory_installs_expand_to_files(self):
        self.write_composer(["alpha_sdk", "beta_sdk"], home="beta_sdk")
        installer = self.import_installer()
        self.assertEqual(
            installer.home_sdk_owned_files("beta_sdk"), {HOME_REL, ASSET_REL}
        )

    def test_unresolvable_home_protects_nothing(self):
        installer = self.import_installer()
        self.assertEqual(installer.home_sdk_owned_files("core_sdk"), set())

    def test_hash_takeover_requires_exact_match(self):
        installer = self.import_installer()
        digest = hashlib.sha256(b"x").hexdigest()
        state = {"packages": {"alpha_sdk": {"files": {HOME_REL: digest}}}}
        self.assertEqual(
            installer._installed_file_owner(state, HOME_REL, digest, "beta_sdk"),
            "alpha_sdk",
        )
        self.assertIsNone(
            installer._installed_file_owner(state, HOME_REL, "other", "beta_sdk")
        )
        self.assertIsNone(
            installer._installed_file_owner(state, HOME_REL, digest, "alpha_sdk")
        )


if __name__ == "__main__":
    unittest.main()
