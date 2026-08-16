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

# Licensed under the MIT License.
# Copyright 2026 RokctAI
"""Regression tests for repo-aware workflows/.rok distribution.

workflows/.rok/distribution.json drives which variant of each Protocol-only
workflow initiate.py installs into a consumer repo's .github/workflows/:

  * the repos whose scheduled/push/PR-closed jobs the shared suite hard-gates
    to (factory, opportunities, the-rokct-protocol) get the canonical full
    agent.yml;
  * every other repo — unknown/new repos included — gets agent.trimmed.yml
    (dispatch/call-only triggers) installed AS agent.yml, so it never carries
    triggers that can only produce no-op runs;
  * unlisted files and workflows without a trimmed_variant distribute
    verbatim, and a missing manifest falls back to verbatim for everything.

The trimmed variant must stay byte-identical to the canonical file except for
the `on:` triggers — same pinned shared-workflows SHA, same explicit secrets.

Run:  python -m pytest tests/test_workflow_distribution.py -q
  or: python tests/test_workflow_distribution.py
"""

import importlib.util
import json
import os
import shutil
import sys
import tempfile
import unittest

import yaml

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_ROK_DIR = os.path.join(_REPO_ROOT, "workflows", ".rok")

_FULL_TRIGGER_REPOS = ("factory", "opportunities", "the-rokct-protocol")
_TRIMMED_REPOS = ("agent", "The-Rokct-Protocol-Docs", "some-brand-new-repo")


def _load_module(rel_path, name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_REPO_ROOT, rel_path)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_WEB = _load_module(os.path.join("profiles", "web", "initiate.py"), "initiate_web")
_LOCAL = _load_module(
    os.path.join("profiles", "local", "initiate.py"), "initiate_local"
)
_MODULES = (("web", _WEB), ("local", _LOCAL))


def _workflow_on_block(path):
    with open(path, "r", encoding="utf-8") as f:
        doc = yaml.safe_load(f)
    # YAML 1.1 parses the bare `on` key as boolean True.
    return doc, doc.get(True, doc.get("on"))


class TestVariantSelection(unittest.TestCase):
    def _selected(self, module, repo_name):
        return dict(
            (dst, src) for src, dst in module.select_rok_workflows(_ROK_DIR, repo_name)
        )

    def test_gated_repos_get_full_agent_workflow(self):
        for profile, module in _MODULES:
            for repo in _FULL_TRIGGER_REPOS:
                with self.subTest(profile=profile, repo=repo):
                    self.assertEqual(
                        self._selected(module, repo)["agent.yml"], "agent.yml"
                    )

    def test_gated_repo_match_is_case_insensitive(self):
        for profile, module in _MODULES:
            with self.subTest(profile=profile):
                selected = self._selected(module, "The-Rokct-Protocol")
                self.assertEqual(selected["agent.yml"], "agent.yml")

    def test_other_and_unknown_repos_get_trimmed_agent_workflow(self):
        for profile, module in _MODULES:
            for repo in _TRIMMED_REPOS:
                with self.subTest(profile=profile, repo=repo):
                    selected = self._selected(module, repo)
                    self.assertEqual(selected["agent.yml"], "agent.trimmed.yml")

    def test_workflows_without_variants_distribute_verbatim(self):
        for profile, module in _MODULES:
            for repo in _FULL_TRIGGER_REPOS + _TRIMMED_REPOS:
                with self.subTest(profile=profile, repo=repo):
                    selected = self._selected(module, repo)
                    self.assertEqual(
                        selected["branch-cleanup.yml"], "branch-cleanup.yml"
                    )
                    self.assertEqual(selected["play-deploy.yml"], "play-deploy.yml")

    def test_manifest_and_variant_files_are_never_installed(self):
        for profile, module in _MODULES:
            for repo in ("factory", "agent"):
                with self.subTest(profile=profile, repo=repo):
                    installed = set(self._selected(module, repo))
                    self.assertNotIn("distribution.json", installed)
                    self.assertNotIn("agent.trimmed.yml", installed)

    def test_missing_manifest_falls_back_to_verbatim_distribution(self):
        tmp = tempfile.mkdtemp()
        try:
            for name in ("agent.yml", "branch-cleanup.yml"):
                shutil.copy2(os.path.join(_ROK_DIR, name), os.path.join(tmp, name))
            for profile, module in _MODULES:
                with self.subTest(profile=profile):
                    self.assertEqual(
                        module.select_rok_workflows(tmp, "agent"),
                        [
                            ("agent.yml", "agent.yml"),
                            ("branch-cleanup.yml", "branch-cleanup.yml"),
                        ],
                    )
        finally:
            shutil.rmtree(tmp)

    def test_selection_pairs_reference_real_files(self):
        for profile, module in _MODULES:
            for repo in ("factory", "agent", None):
                with self.subTest(profile=profile, repo=repo):
                    for src, _ in module.select_rok_workflows(_ROK_DIR, repo):
                        self.assertTrue(os.path.isfile(os.path.join(_ROK_DIR, src)))

    def test_web_and_local_selection_are_identical(self):
        for repo in _FULL_TRIGGER_REPOS + _TRIMMED_REPOS + (None,):
            with self.subTest(repo=repo):
                self.assertEqual(
                    _WEB.select_rok_workflows(_ROK_DIR, repo),
                    _LOCAL.select_rok_workflows(_ROK_DIR, repo),
                )


class TestDistributionManifest(unittest.TestCase):
    def setUp(self):
        with open(os.path.join(_ROK_DIR, "distribution.json"), encoding="utf-8") as f:
            self.manifest = json.load(f)

    def test_every_rok_workflow_is_listed_or_a_variant(self):
        variants = {
            cfg["trimmed_variant"]
            for cfg in self.manifest.values()
            if cfg.get("trimmed_variant")
        }
        for name in sorted(os.listdir(_ROK_DIR)):
            if name == "distribution.json":
                continue
            self.assertTrue(
                name in self.manifest or name in variants,
                f"workflows/.rok/{name} is neither listed in distribution.json "
                "nor referenced as a variant",
            )

    def test_manifest_entries_reference_existing_files(self):
        for name, cfg in self.manifest.items():
            self.assertTrue(os.path.isfile(os.path.join(_ROK_DIR, name)), name)
            if cfg.get("trimmed_variant"):
                self.assertTrue(
                    os.path.isfile(os.path.join(_ROK_DIR, cfg["trimmed_variant"])),
                    cfg["trimmed_variant"],
                )

    def test_agent_full_trigger_repos_match_shared_suite_gates(self):
        self.assertEqual(
            self.manifest["agent.yml"]["full_trigger_repos"],
            list(_FULL_TRIGGER_REPOS),
        )


class TestTrimmedAgentVariant(unittest.TestCase):
    def setUp(self):
        self.full, self.full_on = _workflow_on_block(
            os.path.join(_ROK_DIR, "agent.yml")
        )
        self.trimmed, self.trimmed_on = _workflow_on_block(
            os.path.join(_ROK_DIR, "agent.trimmed.yml")
        )

    def test_body_is_identical_except_triggers(self):
        for key in ("name", "concurrency", "jobs"):
            with self.subTest(key=key):
                self.assertEqual(self.full[key], self.trimmed[key])
        self.assertEqual(
            {k for k in self.full if k not in (True, "on")},
            {k for k in self.trimmed if k not in (True, "on")},
        )

    def test_trimmed_triggers_are_dispatch_and_call_only(self):
        self.assertEqual(set(self.trimmed_on), {"workflow_dispatch", "workflow_call"})

    def test_kept_triggers_match_canonical_definitions(self):
        for trigger in ("workflow_dispatch", "workflow_call"):
            with self.subTest(trigger=trigger):
                self.assertEqual(self.full_on[trigger], self.trimmed_on[trigger])

    def test_canonical_still_carries_the_gated_triggers(self):
        for trigger in ("push", "pull_request", "schedule"):
            with self.subTest(trigger=trigger):
                self.assertIn(trigger, self.full_on)


class TestDeployment(unittest.TestCase):
    def test_trimmed_variant_is_installed_under_canonical_name(self):
        tmp = tempfile.mkdtemp()
        try:
            for profile, module in _MODULES:
                dst = os.path.join(tmp, profile)
                os.makedirs(dst)
                for src_name, dst_name in module.select_rok_workflows(
                    _ROK_DIR, "agent"
                ):
                    shutil.copy2(
                        os.path.join(_ROK_DIR, src_name), os.path.join(dst, dst_name)
                    )
                with self.subTest(profile=profile):
                    self.assertEqual(
                        sorted(os.listdir(dst)),
                        ["agent.yml", "branch-cleanup.yml", "play-deploy.yml"],
                    )
                    with open(os.path.join(_ROK_DIR, "agent.trimmed.yml"), "rb") as f:
                        trimmed = f.read()
                    with open(os.path.join(dst, "agent.yml"), "rb") as f:
                        self.assertEqual(f.read(), trimmed)
        finally:
            shutil.rmtree(tmp)


if __name__ == "__main__":
    sys.exit(unittest.main())
