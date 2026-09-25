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



"""Tests for sdk_composer.py's version-aware cache reconciliation.

The recorded fingerprint is a hash of the SDK SOURCE (not the cache), and
cache_dir_hash() only counts files git would keep. These tests pin:

  * a fresh checkout (gitignored cache files gone, installer churn in the
    cache) still matches and the cache is kept
  * a manifest version bump re-extracts
  * a same-version source change re-extracts (no "local modifications"
    branch any more), as does a state entry with no source fingerprint
  * a cache that lost lib/ re-extracts
  * gitignored files do not count toward cache_dir_hash inside a git repo,
    and everything counts outside git

Run:  python -m pytest core/utils/flutter/tests -q
"""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest

_COMPOSER_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sdk_composer.py",
)
_MOD_NAME = "sdk_composer_under_cache_test"


def _import_composer():
    spec = importlib.util.spec_from_file_location(_MOD_NAME, _COMPOSER_SRC)
    module = importlib.util.module_from_spec(spec)
    sys.modules[_MOD_NAME] = module
    spec.loader.exec_module(module)
    return module


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _git(cwd, *args):
    subprocess.run(
        ["git", *args],
        cwd=cwd,
        check=True,
        capture_output=True,
        env={
            **os.environ,
            "GIT_AUTHOR_NAME": "t",
            "GIT_AUTHOR_EMAIL": "t@example.com",
            "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@example.com",
        },
    )


class CacheReconcileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.mod = _import_composer()

    @classmethod
    def tearDownClass(cls):
        sys.modules.pop(_MOD_NAME, None)

    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.host = os.path.join(self.tmp, "host")
        self.src = os.path.join(self.tmp, "sdks", "auth_sdk")
        self.target = os.path.join(self.host, ".rokct", "cache", "auth")
        os.makedirs(self.host)
        self._old_root = self.mod.PROJECT_ROOT
        self._old_state = self.mod.STATE_FILE
        self.mod.PROJECT_ROOT = self.host
        self.mod.STATE_FILE = os.path.join(
            self.host, ".rokct", "cache", "install_state.json"
        )
        self.mod.SOURCE_HASHES.clear()
        self._make_source("1.0.0")

    def tearDown(self):
        self.mod.PROJECT_ROOT = self._old_root
        self.mod.STATE_FILE = self._old_state
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _make_source(self, version, body="class A {}\n"):
        _write(
            os.path.join(self.src, "manifest.json"),
            json.dumps({"name": "auth_sdk", "version": version}),
        )
        _write(os.path.join(self.src, "lib", "auth.dart"), body)

    def _compose(self):
        """One reconcile + extract + installer churn + record pass."""
        state = self.mod.load_install_state()
        decisions = {}
        extract = self.mod.should_extract(
            "auth_sdk", self.src, self.target, state, decisions
        )
        if extract:
            shutil.rmtree(self.target, ignore_errors=True)
            shutil.copytree(self.src, self.target)
        # What the installers/compose do to the cache afterwards.
        _write(os.path.join(self.target, "pubspec_overrides.yaml"), "x: 1\n")
        _write(os.path.join(self.target, "lib", "gen.g.dart"), "// gen\n")
        self.mod.record_sdk_cache_state(decisions)
        return extract, decisions["auth"]

    def test_first_compose_extracts(self):
        self.assertEqual(self._compose(), (True, "extracted"))

    def test_fresh_checkout_matches_and_keeps(self):
        _write(
            os.path.join(self.host, ".gitignore"),
            ".rokct/cache/*/pubspec_overrides.yaml\n",
        )
        _git(self.host, "init", "-q")
        self._compose()
        _git(self.host, "add", "-A")
        _git(self.host, "commit", "-qm", "composed")
        # Fresh checkout: drop everything git does not track.
        _git(self.host, "clean", "-fdqx")
        self.assertFalse(
            os.path.exists(os.path.join(self.target, "pubspec_overrides.yaml"))
        )
        self.assertEqual(self._compose(), (False, "left-unmodified"))

    def test_rerun_unchanged_keeps(self):
        self._compose()
        self.assertEqual(self._compose(), (False, "left-unmodified"))

    def test_version_bump_reextracts(self):
        self._compose()
        self._make_source("1.1.0", body="class B {}\n")
        self.assertEqual(self._compose(), (True, "extracted"))
        with open(os.path.join(self.target, "lib", "auth.dart")) as f:
            self.assertEqual(f.read(), "class B {}\n")

    def test_same_version_source_change_reextracts(self):
        self._compose()
        self._make_source("1.0.0", body="class Changed {}\n")
        self.assertEqual(self._compose(), (True, "extracted"))
        with open(os.path.join(self.target, "lib", "auth.dart")) as f:
            self.assertEqual(f.read(), "class Changed {}\n")

    def test_hand_edited_cache_does_not_block_reextract(self):
        self._compose()
        _write(os.path.join(self.target, "lib", "auth.dart"), "hand edit\n")
        self._make_source("1.0.0", body="class Changed {}\n")
        self.assertEqual(self._compose(), (True, "extracted"))

    def test_legacy_entry_without_source_hash_reextracts(self):
        self._compose()
        state = self.mod.load_install_state()
        state["sdk_cache"]["auth"] = {"version": "1.0.0", "hash": "abc"}
        self.mod.save_install_state(state)
        self.assertEqual(self._compose(), (True, "extracted"))

    def test_cache_missing_lib_reextracts(self):
        self._compose()
        shutil.rmtree(os.path.join(self.target, "lib"))
        self.assertEqual(self._compose(), (True, "extracted"))

    def test_hash_respects_gitignore_inside_git(self):
        repo = os.path.join(self.tmp, "repo")
        _write(os.path.join(repo, ".gitignore"), "ignored.txt\n")
        _write(os.path.join(repo, "d", "kept.txt"), "k")
        _git(repo, "init", "-q")
        d = os.path.join(repo, "d")
        before = self.mod.cache_dir_hash(d)
        _write(os.path.join(d, "ignored.txt"), "noise")
        self.assertEqual(self.mod.cache_dir_hash(d), before)
        _write(os.path.join(d, "other.txt"), "real")
        self.assertNotEqual(self.mod.cache_dir_hash(d), before)

    def test_hash_counts_everything_outside_git(self):
        d = os.path.join(self.tmp, "plain")
        _write(os.path.join(d, "a.txt"), "a")
        _write(os.path.join(d, ".gitignore"), "b.txt\n")
        before = self.mod.cache_dir_hash(d)
        _write(os.path.join(d, "b.txt"), "b")
        self.assertNotEqual(self.mod.cache_dir_hash(d), before)


if __name__ == "__main__":
    unittest.main()
