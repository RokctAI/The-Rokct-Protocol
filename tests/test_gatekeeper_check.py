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

"""Tests for core/skills/.rok/pr-gatekeeper-check/gatekeeper_check.py.

Run:  python -m pytest tests/test_gatekeeper_check.py -q
  or: python tests/test_gatekeeper_check.py
"""

import contextlib
import importlib.util
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from unittest import mock

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))
SKILL = os.path.join(ROOT, "core", "skills", ".rok", "pr-gatekeeper-check")
spec = importlib.util.spec_from_file_location(
    "gatekeeper_check", os.path.join(SKILL, "gatekeeper_check.py")
)
gk = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gk)


def git(repo, *args):
    subprocess.run(
        ["git", "-C", repo] + list(args), check=True, capture_output=True, text=True
    )


def write(repo, path, text):
    full = os.path.join(repo, path)
    os.makedirs(os.path.dirname(full), exist_ok=True)
    with open(full, "w") as f:
        f.write(text)


class Repo(unittest.TestCase):
    def setUp(self):
        self.repo = tempfile.mkdtemp(prefix="gk-test-")
        self.addCleanup(shutil.rmtree, self.repo, True)
        git(self.repo, "init", "-q", "-b", "main")
        git(self.repo, "config", "user.email", "t@example.com")
        git(self.repo, "config", "user.name", "t")
        write(self.repo, "pkg/manifest.json", json.dumps({"version": "1.0.0"}))
        write(self.repo, "pkg/CHANGELOG.md", "# Changelog\n\n## 1.0.0\n- first\n")
        write(self.repo, "pkg/code.py", "x = 1\n")
        write(self.repo, "shared.txt", "a\nb\nc\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "base")
        git(self.repo, "branch", "-q", "origin-main")  # stand-in for origin/main

    def branch(self, name="pr"):
        git(self.repo, "checkout", "-q", "-b", name, "main")

    def commit(self, msg="pr"):
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", msg)

    def ctx(self, body="", name="control", run_commands=True, head="pr"):
        return gk.Ctx(self.repo, head, "main", body, name, run_commands)

    def one(self, rule, **kw):
        res = [r for r in gk.run(self.ctx(**kw), [rule]) if r[0] != "tests"]
        self.assertEqual(len(res), 1)
        return res[0][1], res[0][2]


class TestMerge(Repo):
    def test_clean(self):
        self.branch()
        write(self.repo, "pkg/code.py", "x = 2\n")
        self.commit()
        status, detail = self.one({"id": "merge", "check": "merge"})
        self.assertEqual(status, gk.PASS, detail)

    def test_conflict_names_files_and_fails(self):
        self.branch()
        write(self.repo, "shared.txt", "a\nPR\nc\n")
        write(self.repo, "pkg/CHANGELOG.md", "# Changelog\n\n## 1.1.0\n- pr\n")
        self.commit()
        git(self.repo, "checkout", "-q", "main")
        write(self.repo, "shared.txt", "a\nMAIN\nc\n")
        write(self.repo, "pkg/CHANGELOG.md", "# Changelog\n\n## 1.1.0\n- main\n")
        self.commit("main moved")
        status, detail = self.one({"id": "merge", "check": "merge"})
        self.assertEqual(status, gk.FAIL)
        self.assertIn("shared.txt", detail)
        self.assertIn("CHANGELOG.md", detail)
        self.assertIn("2 conflict", detail)


class TestBulletFiles(Repo):
    def test_missing_named_file_needs_reading(self):
        self.branch()
        write(self.repo, "pkg/code.py", "x = 2\n")
        self.commit()
        body = "Files: `pkg/code.py`, `pkg/other.py`, `tests/test_other.py`"
        status, detail = self.one({"id": "b", "check": "bullet_files"}, body=body)
        self.assertEqual(status, gk.READ)
        self.assertIn("pkg/other.py", detail)
        self.assertNotIn("pkg/code.py,", detail)

    def test_trailing_path_match_is_reported(self):
        self.branch()
        write(self.repo, "other/tests/test_x.py", "pass\n")
        self.commit()
        status, detail = self.one(
            {"id": "b", "check": "bullet_files"}, body="Adds `tests/test_x.py`"
        )
        self.assertEqual(status, gk.PASS)
        self.assertIn("matched only by trailing path", detail)
        self.assertIn("other/tests/test_x.py", detail)

    def test_all_present(self):
        self.branch()
        write(self.repo, "pkg/code.py", "x = 2\n")
        self.commit()
        status, _ = self.one(
            {"id": "b", "check": "bullet_files"}, body="Changed `code.py` and `pkg/`"
        )
        self.assertEqual(status, gk.PASS)

    def test_no_body_is_not_run(self):
        self.branch()
        write(self.repo, "pkg/code.py", "x = 2\n")
        self.commit()
        status, detail = self.one({"id": "b", "check": "bullet_files"})
        self.assertEqual(status, gk.NOTRUN)
        self.assertTrue(detail.startswith("NOT RUN:"))


class TestVersions(Repo):
    rule = {"id": "v", "check": "versions", "require_bump": True}

    def test_consistent_bump(self):
        self.branch()
        write(self.repo, "pkg/code.py", "x = 2\n")
        write(self.repo, "pkg/manifest.json", json.dumps({"version": "1.1.0"}))
        write(
            self.repo,
            "pkg/CHANGELOG.md",
            "# Changelog\n\n## 1.1.0\n- new\n\n## 1.0.0\n- first\n",
        )
        self.commit()
        status, detail = self.one(self.rule)
        self.assertEqual(status, gk.PASS, detail)

    def test_changelog_and_manifest_disagree(self):
        self.branch()
        write(self.repo, "pkg/manifest.json", json.dumps({"version": "1.1.0"}))
        write(
            self.repo,
            "pkg/CHANGELOG.md",
            "# Changelog\n\n## 1.2.0\n- new\n\n## 1.0.0\n- first\n",
        )
        self.commit()
        status, detail = self.one(self.rule)
        self.assertEqual(status, gk.FAIL)
        self.assertIn("1.2.0", detail)
        self.assertIn("1.1.0", detail)

    def test_code_without_bump_fails(self):
        self.branch()
        write(self.repo, "pkg/code.py", "x = 3\n")
        self.commit()
        status, detail = self.one(self.rule)
        self.assertEqual(status, gk.FAIL)
        self.assertIn("no bump in its own package: pkg", detail)

    def test_version_going_down_fails(self):
        self.branch()
        write(self.repo, "pkg/manifest.json", json.dumps({"version": "0.9.0"}))
        self.commit()
        status, detail = self.one({"id": "v", "check": "versions"})
        self.assertEqual(status, gk.FAIL)
        self.assertIn("goes down", detail)


class TestVersionsPerPackage(Repo):
    """A bump in an unrelated package must not satisfy a change in this one."""

    rule = {"id": "v", "check": "versions", "require_bump": True}

    def test_bump_in_other_package_fails(self):
        write(self.repo, "a/manifest.json", json.dumps({"version": "1.0.0"}))
        write(self.repo, "b/manifest.json", json.dumps({"version": "1.0.0"}))
        write(self.repo, "a/c.py", "x = 1\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "two packages")
        self.branch()
        write(self.repo, "a/c.py", "x = 2\n")
        write(self.repo, "b/manifest.json", json.dumps({"version": "1.0.1"}))
        self.commit()
        status, detail = self.one(self.rule)
        self.assertEqual(status, gk.FAIL, detail)
        self.assertIn("a (1 file(s), e.g. a/c.py)", detail)

    def test_bump_in_own_package_passes(self):
        write(self.repo, "a/manifest.json", json.dumps({"version": "1.0.0"}))
        write(self.repo, "a/deep/er/c.py", "x = 1\n")
        git(self.repo, "add", "-A")
        git(self.repo, "commit", "-qm", "pkg a")
        self.branch()
        write(self.repo, "a/deep/er/c.py", "x = 2\n")
        write(self.repo, "a/manifest.json", json.dumps({"version": "1.0.1"}))
        self.commit()
        status, detail = self.one(self.rule)
        self.assertEqual(status, gk.PASS, detail)

    def test_without_require_bump_it_needs_reading(self):
        self.branch()
        write(self.repo, "pkg/code.py", "x = 9\n")
        self.commit()
        self.assertEqual(self.one({"id": "v", "check": "versions"})[0], gk.READ)


class TestOtherChecks(Repo):
    def test_secret_fails(self):
        self.branch()
        write(
            self.repo, "pkg/conf.py", 'API_KEY = "abcdefghijklmnopqrstuvwxyz123456"\n'
        )
        self.commit()
        status, detail = self.one({"id": "s", "check": "secrets"})
        self.assertEqual(status, gk.FAIL)
        self.assertIn("pkg/conf.py", detail)

    def test_unquoted_env_secret_and_bearer_fail(self):
        self.branch()
        write(self.repo, "pkg/.env.sample", "DB_PASSWORD=abcdefghijklmnopqrstuvwx\n")
        write(
            self.repo,
            "pkg/call.sh",
            "curl -H 'Authorization: Bearer abcdefghijklmnopqrstuvwxyz0123'\n",
        )
        self.commit()
        status, detail = self.one({"id": "s", "check": "secrets"})
        self.assertEqual(status, gk.FAIL)
        self.assertIn("unquoted secret assignment in pkg/.env.sample", detail)
        self.assertIn("bearer token in pkg/call.sh", detail)

    def test_env_lookup_is_not_a_secret(self):
        self.branch()
        write(
            self.repo,
            "pkg/conf.py",
            'token = os.environ.get("TOKEN_FROM_ENV_VARIABLE_NAME")\nSECRET_KEY = config_value_lookup\n',
        )
        self.commit()
        self.assertEqual(self.one({"id": "s", "check": "secrets"})[0], gk.PASS)

    def test_no_secret_passes(self):
        self.branch()
        write(self.repo, "pkg/conf.py", 'name = "plain"\n')
        self.commit()
        self.assertEqual(self.one({"id": "s", "check": "secrets"})[0], gk.PASS)

    def test_note_for_next_time_needs_reading(self):
        self.branch()
        write(self.repo, "pkg/code.py", "x = 2\n")
        self.commit()
        status, detail = self.one(
            {"id": "n", "check": "notes"}, body="Fine. Ray can wire this next time."
        )
        self.assertEqual(status, gk.READ)
        self.assertIn("next time", detail)

    def test_clean_body_passes(self):
        self.branch()
        write(self.repo, "pkg/code.py", "x = 2\n")
        self.commit()
        self.assertEqual(
            self.one(
                {"id": "n", "check": "notes"}, body="Not run: Flutter is not installed."
            )[0],
            gk.PASS,
        )

    def test_art_needs_ray(self):
        self.branch()
        write(self.repo, "assets/feature.png", "not really a png")
        self.commit()
        status, detail = self.one({"id": "a", "check": "art"})
        self.assertEqual(status, gk.RAY)
        self.assertIn("assets/feature.png", detail)

    def test_merge_order_info(self):
        self.branch()
        write(self.repo, "pkg/code.py", "x = 2\n")
        self.commit()
        status, detail = self.one(
            {"id": "o", "check": "merge_order"},
            body="Stacks on #191. Merge #190 first.",
        )
        self.assertEqual(status, gk.INFO)
        self.assertIn("#190", detail)
        self.assertIn("#191", detail)

    def test_pair_rule(self):
        self.branch()
        write(self.repo, "lib/home.dart", "void main() {}\n")
        self.commit()
        rule = {
            "id": "t",
            "check": "requires_pair",
            "if_touches": ["lib/*.dart"],
            "then_touches": [".rokct/tours/*"],
            "what": "tour for a UI change",
        }
        status, detail = self.one(rule)
        self.assertEqual(status, gk.READ)
        self.assertIn("tour for a UI change", detail)
        write(self.repo, ".rokct/tours/home.yaml", "steps: []\n")
        self.commit("tour")
        self.assertEqual(self.one(rule)[0], gk.PASS)

    def test_repo_scoping_and_when_touches(self):
        self.branch()
        write(self.repo, "pkg/code.py", "x = 2\n")
        self.commit()
        res = gk.run(
            self.ctx(name="other"),
            [
                {"id": "x", "check": "secrets", "repos": ["control"]},
                {"id": "y", "check": "secrets", "when_touches": ["nope/*"]},
                {"id": "z", "check": "secrets", "when_touches": ["pkg/*"]},
            ],
        )
        self.assertEqual([r[0] for r in res if r[0] != "tests"], ["z"])

    def test_unknown_check_never_passes(self):
        self.branch()
        self.commit_empty = None
        write(self.repo, "pkg/code.py", "x = 2\n")
        self.commit()
        self.assertEqual(self.one({"id": "q", "check": "does_not_exist"})[0], gk.READ)


class TestCommand(Repo):
    def setUp(self):
        super().setUp()
        self.branch()
        write(self.repo, "pkg/code.py", "x = 2\n")
        self.commit()

    def test_pass_and_claim_match(self):
        rule = {
            "id": "t",
            "check": "command",
            "cmd": "python3 -c \"print('3 passed in 0.1s')\"",
        }
        self.assertEqual(self.one(rule, body="3 passed")[0], gk.PASS)

    def test_claim_mismatch_needs_reading(self):
        rule = {
            "id": "t",
            "check": "command",
            "cmd": "python3 -c \"print('3 passed in 0.1s')\"",
        }
        status, detail = self.one(rule, body="I ran it: 70 passed")
        self.assertEqual(status, gk.READ)
        self.assertIn("70", detail)

    def test_failed_tests_fail(self):
        rule = {
            "id": "t",
            "check": "command",
            "cmd": "python3 -c \"print('2 passed, 1 failed')\"",
        }
        self.assertEqual(self.one(rule)[0], gk.FAIL)

    def test_errors_over_allowance_fail(self):
        cmd = "python3 -c \"print('5 passed, 14 errors')\""
        self.assertEqual(
            self.one({"id": "t", "check": "command", "cmd": cmd, "allow_errors": 13})[
                0
            ],
            gk.FAIL,
        )
        self.assertEqual(
            self.one(
                {
                    "id": "t",
                    "check": "command",
                    "cmd": cmd.replace("14", "13"),
                    "allow_errors": 13,
                }
            )[0],
            gk.PASS,
        )

    def test_missing_tool_says_so_in_plain_words(self):
        rule = {
            "id": "dart",
            "check": "command",
            "cmd": "flutter test",
            "requires": ["flutter-not-here-xyz"],
            "not_run_text": "NOT RUN: Dart not tested because Flutter is not installed",
        }
        status, detail = self.one(rule)
        self.assertEqual(status, gk.NOTRUN)
        self.assertEqual(
            detail, "NOT RUN: Dart not tested because Flutter is not installed"
        )

    def test_no_run_flag(self):
        rule = {
            "id": "t",
            "check": "command",
            "cmd": "python3 -c \"print('3 passed')\"",
        }
        self.assertEqual(self.one(rule, run_commands=False)[0], gk.NOTRUN)

    def test_nonzero_exit_with_pass_count_is_not_a_pass(self):
        rule = {
            "id": "t",
            "check": "command",
            "cmd": "python3 -c \"import sys;print('5 passed');sys.exit(1)\"",
        }
        status, detail = self.one(rule)
        self.assertEqual(status, gk.FAIL)
        self.assertIn("exit 1", detail)

    def test_nonzero_exit_explained_by_allowed_errors_passes(self):
        cmd = "python3 -c \"import sys;print('5 passed, 13 errors');sys.exit(2)\""
        self.assertEqual(
            self.one({"id": "t", "check": "command", "cmd": cmd, "allow_errors": 13})[
                0
            ],
            gk.PASS,
        )
        self.assertEqual(
            self.one({"id": "t", "check": "command", "cmd": cmd})[0], gk.FAIL
        )

    def test_skipped_tests_are_reported_not_passed(self):
        rule = {
            "id": "t",
            "check": "command",
            "cmd": "python3 -c \"print('591 passed, 65 skipped')\"",
        }
        status, detail = self.one(rule, body="656 passed")
        self.assertEqual(status, gk.READ)
        self.assertIn("65 tests skipped", detail)

    def test_optional_env_checkout_only_set_when_present(self):
        rule = {
            "id": "t",
            "check": "command",
            "env": {"GK_X": "{PARENT}/no-such-checkout-xyz"},
            "cmd": "python3 -c \"import os;print('1 passed' if 'GK_X' not in os.environ else '0 passed')\"",
        }
        self.assertEqual(self.one(rule)[0], gk.PASS)

    def test_no_test_rule_matched_says_so(self):
        res = gk.run(self.ctx(name="other"), [{"id": "x", "check": "secrets"}])
        row = [r for r in res if r[0] == "tests"]
        self.assertEqual(len(row), 1)
        self.assertEqual(row[0][1], gk.NOTRUN)
        self.assertIn("no test rule", row[0][2])

    def test_worktree_is_cleaned_up(self):
        rule = {
            "id": "t",
            "check": "command",
            "cmd": "python3 -c \"print('1 passed')\"",
        }
        self.one(rule)
        out = subprocess.run(
            ["git", "-C", self.repo, "worktree", "list"], capture_output=True, text=True
        ).stdout
        self.assertEqual(len(out.strip().splitlines()), 1)


class TestMain(Repo):
    def run_main(self, *extra):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            code = gk.main(
                [
                    "--repo",
                    self.repo,
                    "--head",
                    "pr",
                    "--base",
                    "main",
                    "--name",
                    "control",
                ]
                + list(extra)
            )
        return code, buf.getvalue()

    def checklist(self, rules):
        path = os.path.join(self.repo, "..", os.path.basename(self.repo) + "-cl.json")
        with open(path, "w") as f:
            json.dump({"rules": rules}, f)
        self.addCleanup(os.remove, path)
        return path

    def test_exit_codes_table_and_log(self):
        self.branch()
        write(
            self.repo, "pkg/conf.py", 'API_KEY = "abcdefghijklmnopqrstuvwxyz123456"\n'
        )
        self.commit()
        logdir = tempfile.mkdtemp(prefix="gk-log-")
        self.addCleanup(shutil.rmtree, logdir, True)
        log = os.path.join(logdir, "runs.jsonl")
        cl = self.checklist(
            [{"id": "secrets", "check": "secrets"}, {"id": "merge", "check": "merge"}]
        )
        code, out = self.run_main("--checklist", cl, "--log", log, "--pr", "control#1")
        self.assertEqual(code, 1)
        self.assertIn("secrets", out)
        self.assertIn("FAIL", out)
        self.assertIn("RESULT: FAIL (1)", out)
        row = json.loads(open(log).read().splitlines()[-1])
        self.assertEqual(row["pr"], "control#1")
        self.assertEqual(
            row["results"], {"secrets": "FAIL", "merge": "PASS", "tests": "NOT RUN"}
        )

    def test_all_good_exit_zero(self):
        self.branch()
        write(self.repo, "pkg/code.py", "x = 2\n")
        self.commit()
        cl = self.checklist([{"id": "merge", "check": "merge"}])
        code, out = self.run_main(
            "--checklist", cl, "--log", "/nonexistent-dir/runs.jsonl"
        )
        self.assertEqual(code, 0)
        self.assertIn("no FAIL", out)

    def test_bad_ref_is_usage_error(self):
        code = gk.main(["--repo", self.repo, "--head", "no-such-ref", "--base", "main"])
        self.assertEqual(code, 2)

    def test_shipped_checklist_is_valid(self):
        with open(os.path.join(SKILL, "checklist.json")) as f:
            rules = json.load(f)["rules"]
        ids = [r["id"] for r in rules]
        self.assertEqual(len(ids), len(set(ids)))
        for r in rules:
            self.assertIn(r["check"], gk.CHECKS, r)

    def test_shipped_checklist_runs_clean_on_a_small_pr(self):
        self.branch()
        write(self.repo, "pkg/code.py", "x = 2\n")
        write(self.repo, "pkg/manifest.json", json.dumps({"version": "1.0.1"}))
        write(
            self.repo,
            "pkg/CHANGELOG.md",
            "# Changelog\n\n## 1.0.1\n- fix\n\n## 1.0.0\n- first\n",
        )
        self.commit()
        code, out = self.run_main("--no-run", "--log", "/nonexistent-dir/runs.jsonl")
        self.assertEqual(code, 0, out)
        self.assertIn("NOT RUN", out)


if __name__ == "__main__":
    unittest.main()
