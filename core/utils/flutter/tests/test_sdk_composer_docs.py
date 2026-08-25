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

"""Regression tests for sdk_composer.py's compliance-docs compose.

Background: the composer used to stage EVERY stack's docs (dart, frappe,
nextjs) from each SDK repo and write them to <shell_root>/<stack>/docs/api/,
so a flutter shell ended up carrying frappe and nextjs compliance docs in
top-level dart/, frappe/ and nextjs/ directories. These tests pin the fix:

  * stage_repo_docs stages ONLY the host flavor's (dart) docs, from all
    three recognized source layouts
  * ensure_docs writes the staged docs to the shell root's docs/api/ (no
    per-stack nesting) and records them in the ownership manifest as
    docs/api/<file>.md
  * a shell composed by the interim per-stack composer is migrated: its
    manifest-owned <stack>/docs/api/*.md files are removed and the emptied
    stack directories pruned
  * frappe/nextjs leftovers in previously staged cache trees are ignored
  * files the manifest does not own are never touched

Run:  python -m pytest core/utils/flutter/tests -q
  or: python core/utils/flutter/tests/test_sdk_composer_docs.py
"""

import importlib.util
import io
import json
import os
import shutil
import sys
import tempfile
import unittest
from contextlib import redirect_stderr, redirect_stdout

_COMPOSER_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sdk_composer.py",
)

_module_counter = 0


class ComposerDocsTestBase(unittest.TestCase):
    """Builds a throwaway host-project sandbox per test.

    sdk_composer.py derives PROJECT_ROOT from os.getcwd() at import time
    (compose always runs from the shell root), so each test imports a fresh
    copy under a unique module name and points its PROJECT_ROOT at the
    sandbox.
    """

    def setUp(self):
        self.project_root = tempfile.mkdtemp(prefix="sdk_composer_docs_test_")
        self.addCleanup(shutil.rmtree, self.project_root, ignore_errors=True)
        self.cache_base = os.path.join(self.project_root, ".rokct", "cache")
        os.makedirs(self.cache_base)
        self.mod = self._import_composer()

    def _import_composer(self):
        global _module_counter
        _module_counter += 1
        name = f"sdk_composer_under_test_{_module_counter}"
        spec = importlib.util.spec_from_file_location(name, _COMPOSER_SRC)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        self.addCleanup(sys.modules.pop, name, None)
        spec.loader.exec_module(module)
        module.PROJECT_ROOT = self.project_root
        return module

    # -- helpers -----------------------------------------------------------

    def write(self, *rel_parts, content="doc body\n"):
        path = os.path.join(self.project_root, *rel_parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def write_at(self, base, *rel_parts, content="doc body\n"):
        path = os.path.join(base, *rel_parts)
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def run_quiet(self, fn, *args, **kwargs):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            fn(*args, **kwargs)
        return out.getvalue() + err.getvalue()

    def stage_dir(self, repo_name):
        return os.path.join(self.cache_base, self.mod.DOCS_STAGE_DIRNAME, repo_name)

    def manifest(self):
        path = os.path.join(self.cache_base, self.mod.DOCS_MANIFEST_NAME)
        if not os.path.exists(path):
            return None
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)

    def listdir_tree(self, base):
        found = []
        for dirpath, _dirnames, filenames in os.walk(base):
            for name in filenames:
                found.append(
                    os.path.relpath(os.path.join(dirpath, name), base).replace(
                        os.sep, "/"
                    )
                )
        return sorted(found)


class StageRepoDocsTests(ComposerDocsTestBase):
    def test_current_layout_stages_only_dart(self):
        repo = tempfile.mkdtemp(prefix="sdk_repo_")
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        self.write_at(repo, "fav", "dart", "docs", "api", "fav_dart_lib_a.md")
        self.write_at(repo, "fav", "frappe", "docs", "api", "fav_frappe_x.md")
        self.write_at(repo, "fav", "nextjs", "docs", "api", "fav_nextjs_y.md")

        self.run_quiet(self.mod.stage_repo_docs, repo, "productivity", self.cache_base)

        self.assertEqual(
            self.listdir_tree(self.stage_dir("productivity")),
            ["dart/fav_dart_lib_a.md"],
        )

    def test_previous_and_legacy_layouts_stage_only_dart(self):
        repo = tempfile.mkdtemp(prefix="sdk_repo_")
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        # Previous layout: repo-root docs/api/<stack>/
        self.write_at(repo, "docs", "api", "dart", "auth_dart_lib_b.md")
        self.write_at(repo, "docs", "api", "frappe", "auth_frappe_c.md")
        # Legacy FLAT layout, mapped by filename token.
        self.write_at(repo, "docs", "api", "auth_dart.md")
        self.write_at(repo, "docs", "api", "auth_py.md")  # frappe token
        self.write_at(repo, "docs", "api", "auth_ts.md")  # nextjs token
        self.write_at(repo, "docs", "api", "mystery.md")  # no token

        output = self.run_quiet(
            self.mod.stage_repo_docs, repo, "authrepo", self.cache_base
        )

        self.assertEqual(
            self.listdir_tree(self.stage_dir("authrepo")),
            ["dart/auth_dart.md", "dart/auth_dart_lib_b.md"],
        )
        # Unmappable file is reported; other-stack files are skipped quietly.
        self.assertIn("mystery.md", output)
        self.assertNotIn("auth_py.md", output)
        self.assertNotIn("auth_ts.md", output)

    def test_repo_with_only_other_stack_docs_stages_nothing(self):
        repo = tempfile.mkdtemp(prefix="sdk_repo_")
        self.addCleanup(shutil.rmtree, repo, ignore_errors=True)
        self.write_at(repo, "tender", "frappe", "docs", "api", "tender_frappe_z.md")

        self.run_quiet(self.mod.stage_repo_docs, repo, "opportunities", self.cache_base)

        self.assertFalse(os.path.isdir(self.stage_dir("opportunities")))


class EnsureDocsTests(ComposerDocsTestBase):
    def test_writes_docs_into_shell_root_docs_api(self):
        self.write(
            ".rokct", "cache", "_docs", "productivity", "dart", "fav_dart_lib_a.md"
        )
        self.write(".rokct", "cache", "_docs", "corerepo", "dart", "core_dart_b.md")

        self.run_quiet(self.mod.ensure_docs)

        docs_root = os.path.join(self.project_root, "docs", "api")
        self.assertEqual(
            self.listdir_tree(docs_root), ["core_dart_b.md", "fav_dart_lib_a.md"]
        )
        # No per-stack directories at the shell root.
        for stack in self.mod.DOC_STACKS:
            self.assertFalse(
                os.path.exists(os.path.join(self.project_root, stack)),
                f"unexpected top-level {stack}/ directory",
            )
        self.assertEqual(
            self.manifest()["files"],
            ["docs/api/core_dart_b.md", "docs/api/fav_dart_lib_a.md"],
        )

    def test_ignores_other_stack_stage_leftovers(self):
        # Stage tree written by the earlier composer version: all stacks.
        self.write(".rokct", "cache", "_docs", "repo1", "dart", "a_dart.md")
        self.write(".rokct", "cache", "_docs", "repo1", "frappe", "a_frappe.md")
        self.write(".rokct", "cache", "_docs", "repo1", "nextjs", "a_nextjs.md")
        # Stale FLAT stage tree: only the dart-token file may pass.
        self.write(".rokct", "cache", "_docs", "repo2", "b_dart.md")
        self.write(".rokct", "cache", "_docs", "repo2", "b_py.md")

        self.run_quiet(self.mod.ensure_docs)

        docs_root = os.path.join(self.project_root, "docs", "api")
        self.assertEqual(self.listdir_tree(docs_root), ["a_dart.md", "b_dart.md"])
        self.assertEqual(
            self.manifest()["files"], ["docs/api/a_dart.md", "docs/api/b_dart.md"]
        )

    def test_migrates_interim_per_stack_layout(self):
        # A shell composed by the interim composer: manifest-owned docs under
        # top-level <stack>/docs/api/ directories.
        self.write("dart", "docs", "api", "fav_dart_lib_a.md", content="old copy\n")
        self.write("frappe", "docs", "api", "tender_frappe_x.md")
        self.write("nextjs", "docs", "api", "tender_nextjs_y.md")
        self.write(
            ".rokct",
            "cache",
            self.mod.DOCS_MANIFEST_NAME,
            content=json.dumps(
                {
                    "files": [
                        "dart/docs/api/fav_dart_lib_a.md",
                        "frappe/docs/api/tender_frappe_x.md",
                        "nextjs/docs/api/tender_nextjs_y.md",
                    ]
                }
            ),
        )
        self.write(
            ".rokct",
            "cache",
            "_docs",
            "productivity",
            "dart",
            "fav_dart_lib_a.md",
            content="new copy\n",
        )

        self.run_quiet(self.mod.ensure_docs)

        # The dart doc now lives at the shell root's docs/api; every
        # misplaced per-stack copy is gone and the emptied dirs are pruned.
        dest = os.path.join(self.project_root, "docs", "api", "fav_dart_lib_a.md")
        with open(dest, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "new copy\n")
        for stack in self.mod.DOC_STACKS:
            self.assertFalse(
                os.path.exists(os.path.join(self.project_root, stack)),
                f"misplaced top-level {stack}/ directory survived migration",
            )
        self.assertEqual(self.manifest()["files"], ["docs/api/fav_dart_lib_a.md"])

    def test_never_touches_unowned_host_files(self):
        host_doc = self.write("docs", "api", "host_notes.md", content="host's own\n")
        self.write("dart", "docs", "api", "unowned.md", content="unowned\n")
        self.write(".rokct", "cache", "_docs", "repo1", "dart", "a_dart.md")

        self.run_quiet(self.mod.ensure_docs)

        with open(host_doc, "r", encoding="utf-8") as f:
            self.assertEqual(f.read(), "host's own\n")
        # An unowned file under a stack dir is NOT deleted (no manifest entry).
        self.assertTrue(
            os.path.exists(
                os.path.join(self.project_root, "dart", "docs", "api", "unowned.md")
            )
        )
        self.assertEqual(self.manifest()["files"], ["docs/api/a_dart.md"])

    def test_stale_owned_docs_removed_when_nothing_staged(self):
        self.write("docs", "api", "gone_dart.md")
        self.write(
            ".rokct",
            "cache",
            self.mod.DOCS_MANIFEST_NAME,
            content=json.dumps({"files": ["docs/api/gone_dart.md"]}),
        )

        self.run_quiet(self.mod.ensure_docs)

        self.assertFalse(os.path.exists(os.path.join(self.project_root, "docs", "api")))
        self.assertIsNone(self.manifest())


if __name__ == "__main__":
    unittest.main()
