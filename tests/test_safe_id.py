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


# Copyright 2026 ROKCT INTELLIGENCE (PTY) LTD
"""Regression tests for Safe ID registration in initiate.py.

A container whose git email was noreply@anthropic.com used to append a bogus
second `## Safe ID` (noreply.26c12d) to memory.md. register_safe_id() must:
prefer ROKCT_SAFE_ID, keep an existing Safe ID section, skip bot/noreply
emails, and never write a second section. All three initiate.py copies are
checked so they cannot drift apart.

Run:  python -m pytest tests/test_safe_id.py -q
  or: python tests/test_safe_id.py
"""

import contextlib
import importlib.util
import io
import os
import sys
import tempfile
import unittest
from unittest import mock

_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_COPIES = (
    "profiles/local/initiate.py",
    "profiles/web/initiate.py",
    ".rokct/initiate.py",
)


def _load_module(rel_path, name):
    spec = importlib.util.spec_from_file_location(
        name, os.path.join(_REPO_ROOT, rel_path)
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class TestRegisterSafeId(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.mem = os.path.join(tmp.name, "memory.md")
        env = mock.patch.dict(os.environ)
        env.start()
        self.addCleanup(env.stop)
        os.environ.pop("ROKCT_SAFE_ID", None)

    def _run(self, rel_path, email, existing=None):
        if existing is not None:
            with open(self.mem, "w", encoding="utf-8") as f:
                f.write(existing)
        elif os.path.exists(self.mem):
            os.remove(self.mem)
        module = _load_module(rel_path, "initiate_" + rel_path.replace("/", "_"))
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            result = module.register_safe_id(self.mem, email)
        content = ""
        if os.path.exists(self.mem):
            with open(self.mem, encoding="utf-8") as f:
                content = f.read()
        return result, content, out.getvalue()

    def test_human_email_registers_once(self):
        for rel in _COPIES:
            with self.subTest(copy=rel):
                result, content, _ = self._run(rel, "Ray.Dev@example.com")
                self.assertEqual(result, "raydev.5ababd")
                self.assertEqual(content.count("## Safe ID"), 1)

    def test_existing_section_is_kept_and_never_duplicated(self):
        existing = "# Memory\n\n## Safe ID\nsinyage.f74d39\n"
        for rel in _COPIES:
            for email in ("noreply@anthropic.com", "someone.else@example.com"):
                with self.subTest(copy=rel, email=email):
                    result, content, _ = self._run(rel, email, existing)
                    self.assertIsNone(result)
                    self.assertEqual(content, existing)

    def test_bot_emails_are_skipped_with_hint(self):
        bots = (
            "noreply@anthropic.com",
            "claude@anthropic.com",
            "no-reply-noreply@example.com",
            "12345+ray@users.noreply.github.com",
            "github-actions[bot]@users.noreply.github.com",
        )
        for rel in _COPIES:
            for email in bots:
                with self.subTest(copy=rel, email=email):
                    result, content, out = self._run(rel, email)
                    self.assertIsNone(result)
                    self.assertNotIn("## Safe ID", content)
                    self.assertIn("ROKCT_SAFE_ID", out)

    def test_env_var_wins_even_for_bot_email(self):
        os.environ["ROKCT_SAFE_ID"] = "ray.custom"
        for rel in _COPIES:
            for email in ("noreply@anthropic.com", ""):
                with self.subTest(copy=rel, email=email):
                    result, content, _ = self._run(rel, email)
                    self.assertEqual(result, "ray.custom")
                    self.assertEqual(content, "\n## Safe ID\n\nray.custom\n")

    def test_env_var_does_not_add_second_section(self):
        os.environ["ROKCT_SAFE_ID"] = "ray.custom"
        existing = "## Safe ID\n\nsinyage.f74d39\n"
        for rel in _COPIES:
            with self.subTest(copy=rel):
                result, content, _ = self._run(rel, "x@example.com", existing)
                self.assertIsNone(result)
                self.assertEqual(content, existing)

    def test_no_email_and_no_env_writes_nothing(self):
        for rel in _COPIES:
            with self.subTest(copy=rel):
                result, content, _ = self._run(rel, "")
                self.assertIsNone(result)
                self.assertEqual(content, "")


if __name__ == "__main__":
    sys.exit(unittest.main())
