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

"""Regression tests for compose_backend.py's token pipeline and scaffold mode.

Pins the literal-token gap fixes and the shell scaffold:

  * doctype/ trees get {app_name}/{module_name} substitution (they used to be
    copytree'd verbatim — the polaris SyntaxError / pay gateway_controller
    escape classes), while tokenless files stay byte-identical.
  * {module_name} is a real token, resolved to the manifest "name" in src/
    and doctype/ passes.
  * src-nested doctype JSONs (src/**/doctype/<dt>/<dt>.json) get the
    "module"-key rewrite the module-root primaries always had, and duplicate
    detection for them WARNS instead of failing the build.
  * scaffold mode lays the tokenized shell skeleton into a fresh repo and
    never overwrites a file an existing shell already has.
  * the post-compose token lint warns on unresolved {app_name}/{module_name}
    literals and escalates to a hard error under ROKCT_COMPOSE_STRICT=1.
  * the embedded SHELL_TEMPLATES stay byte-identical to the canonical files
    in core/utils/frappe/templates/shell/.

Run:  python -m pytest core/utils/frappe/tests -q
  or: python core/utils/frappe/tests/test_compose_backend.py
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

_FRAPPE_UTILS_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_COMPOSER_SRC = os.path.join(_FRAPPE_UTILS_DIR, "compose_backend.py")
_TEMPLATES_DIR = os.path.join(_FRAPPE_UTILS_DIR, "templates", "shell")

_module_counter = 0


class ComposeBackendTestBase(unittest.TestCase):
    """Builds a throwaway shell-repo sandbox per test.

    compose_backend.py derives PROJECT_ROOT from os.getcwd() at import time,
    so each test chdirs into its sandbox and loads a fresh module instance
    (which also resets the COMPILED_DOCTYPES / SRC_NESTED_DOCTYPES /
    COMPOSED_PATHS globals between tests).
    """

    APP = "testshell"
    MODULE = "mymod"

    def setUp(self):
        self._old_cwd = os.getcwd()
        self._old_strict = os.environ.pop("ROKCT_COMPOSE_STRICT", None)
        self._old_argv = sys.argv[:]
        sys.argv = ["compose_backend.py"]
        self.root = tempfile.mkdtemp(prefix="compose_backend_test_")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.addCleanup(self._restore)

    def _restore(self):
        os.chdir(self._old_cwd)
        sys.argv = self._old_argv
        if self._old_strict is not None:
            os.environ["ROKCT_COMPOSE_STRICT"] = self._old_strict
        else:
            os.environ.pop("ROKCT_COMPOSE_STRICT", None)

    # -- sandbox builders ---------------------------------------------------

    def write(self, rel, content):
        path = os.path.join(self.root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8", newline="\n") as fh:
            fh.write(content)
        return path

    def read(self, rel):
        with open(os.path.join(self.root, *rel.split("/")), encoding="utf-8") as fh:
            return fh.read()

    def exists(self, rel):
        return os.path.exists(os.path.join(self.root, *rel.split("/")))

    def make_composer_json(self, modules=None):
        if modules is None:
            modules = [
                {
                    "name": self.MODULE,
                    "enabled": True,
                    "path": f"sdk/{self.MODULE}/frappe",
                }
            ]
        self.write(
            "composer.json",
            json.dumps({"name": f"{self.APP}_app", "modules": modules}),
        )

    def make_shell(self):
        self.write(f"{self.APP}/__init__.py", "__version__ = '0.0.1'\n")
        self.write(f"{self.APP}/hooks.py", f'app_name = "{self.APP}"\n')
        self.write(f"{self.APP}/modules.txt", f"{self.APP}\n")

    def make_sdk(self, module=None, manifest=None):
        module = module or self.MODULE
        manifest = manifest or {"name": module, "description": "test sdk"}
        self.write(f"sdk/{module}/frappe/manifest.json", json.dumps(manifest))

    def load_composer(self):
        global _module_counter
        _module_counter += 1
        os.chdir(self.root)
        spec = importlib.util.spec_from_file_location(
            f"compose_backend_under_test_{_module_counter}", _COMPOSER_SRC
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def run_main(self, composer):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            composer.main()
        return out.getvalue(), err.getvalue()


class DoctypeTreeSubstitutionTest(ComposeBackendTestBase):
    def setUp(self):
        super().setUp()
        self.make_composer_json()
        self.make_shell()
        self.make_sdk()
        self.write(
            f"sdk/{self.MODULE}/frappe/doctype/widget/widget.py",
            "from frappe.model.document import Document\n"
            'GATEWAY = "{app_name}.mymod.doctype.widget.widget.Widget"\n'
            'OWNER_MODULE = "{module_name}"\n'
            "class Widget(Document):\n    pass\n",
        )
        self.write(
            f"sdk/{self.MODULE}/frappe/doctype/widget/widget.json",
            json.dumps({"name": "Widget", "module": "{module_name}"}),
        )
        # Non-substitutable extension: must ship byte-for-byte even with a token
        self.write(
            f"sdk/{self.MODULE}/frappe/doctype/widget/notes.txt",
            "literal {app_name} stays put\n",
        )
        # Tokenless substitutable file: must stay byte-identical too
        self.write(
            f"sdk/{self.MODULE}/frappe/doctype/widget/widget.js",
            "frappe.ui.form.on('Widget', {});\n",
        )

    def test_doctype_tokens_resolve(self):
        composer = self.load_composer()
        self.run_main(composer)
        composed = self.read(f"{self.APP}/{self.MODULE}/doctype/widget/widget.py")
        self.assertIn(f'"{self.APP}.mymod.doctype.widget.widget.Widget"', composed)
        self.assertIn(f'OWNER_MODULE = "{self.MODULE}"', composed)
        self.assertNotIn("{app_name}", composed)
        self.assertNotIn("{module_name}", composed)

    def test_primary_json_module_key_still_rewritten(self):
        composer = self.load_composer()
        self.run_main(composer)
        data = json.loads(
            self.read(f"{self.APP}/{self.MODULE}/doctype/widget/widget.json")
        )
        self.assertEqual(data["module"], self.MODULE)

    def test_tokenless_and_non_substitutable_files_byte_identical(self):
        composer = self.load_composer()
        self.run_main(composer)
        for rel in ("notes.txt", "widget.js"):
            src = os.path.join(
                self.root, "sdk", self.MODULE, "frappe", "doctype", "widget", rel
            )
            dst = os.path.join(
                self.root, self.APP, self.MODULE, "doctype", "widget", rel
            )
            with open(src, "rb") as fh:
                src_bytes = fh.read()
            with open(dst, "rb") as fh:
                dst_bytes = fh.read()
            self.assertEqual(src_bytes, dst_bytes, rel)


class ModuleNameTokenInSrcTest(ComposeBackendTestBase):
    def test_module_name_resolves_to_manifest_name(self):
        self.make_composer_json()
        self.make_shell()
        # Manifest "name" differs from the composer entry name on purpose:
        # {module_name} must resolve to the MANIFEST name (the same value the
        # doctype "module" keys are pinned to).
        self.make_sdk(manifest={"name": "Fancy Module"})
        self.write(
            f"sdk/{self.MODULE}/frappe/src/api.py",
            'APP = "{app_name}"\nMODULE = "{module_name}"\n',
        )
        composer = self.load_composer()
        self.run_main(composer)
        composed = self.read(f"{self.APP}/{self.MODULE}/api.py")
        self.assertEqual(composed, f'APP = "{self.APP}"\nMODULE = "Fancy Module"\n')


class SrcNestedDoctypeTest(ComposeBackendTestBase):
    def setUp(self):
        super().setUp()
        self.make_composer_json()
        self.make_shell()
        self.make_sdk()

    def test_token_module_key_resolves(self):
        self.write(
            f"sdk/{self.MODULE}/frappe/src/feature/doctype/gadget/gadget.json",
            json.dumps({"name": "Gadget", "module": "{module_name}"}),
        )
        composer = self.load_composer()
        self.run_main(composer)
        data = json.loads(
            self.read(f"{self.APP}/{self.MODULE}/feature/doctype/gadget/gadget.json")
        )
        self.assertEqual(data["module"], self.MODULE)

    def test_hardcoded_wrong_module_key_rewritten(self):
        self.write(
            f"sdk/{self.MODULE}/frappe/src/feature/doctype/gizmo/gizmo.json",
            json.dumps({"name": "Gizmo", "module": "Something Else"}),
        )
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        data = json.loads(
            self.read(f"{self.APP}/{self.MODULE}/feature/doctype/gizmo/gizmo.json")
        )
        self.assertEqual(data["module"], self.MODULE)
        self.assertIn("Pinned src-nested DocType module: gizmo", out)

    def test_duplicate_src_nested_doctype_warns_not_fails(self):
        self.make_composer_json(
            modules=[
                {
                    "name": self.MODULE,
                    "enabled": True,
                    "path": f"sdk/{self.MODULE}/frappe",
                },
                {"name": "othermod", "enabled": True, "path": "sdk/othermod/frappe"},
            ]
        )
        self.make_sdk("othermod")
        for mod in (self.MODULE, "othermod"):
            self.write(
                f"sdk/{mod}/frappe/src/feature/doctype/clash/clash.json",
                json.dumps({"name": "Clash", "module": mod}),
            )
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        self.assertIn("WARNING", out)
        self.assertIn("clash", out)
        # Both modules still composed despite the collision
        self.assertTrue(
            self.exists(f"{self.APP}/othermod/feature/doctype/clash/clash.json")
        )


class ScaffoldTest(ComposeBackendTestBase):
    def test_fresh_repo_gets_shell_and_composes(self):
        self.make_composer_json()
        self.make_sdk()
        self.write(f"sdk/{self.MODULE}/frappe/src/api.py", 'APP = "{app_name}"\n')
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        self.assertIn("Scaffolding frappe shell skeleton", out)
        # Shell skeleton laid down with tokens resolved
        self.assertIn(f'app_name = "{self.APP}"', self.read(f"{self.APP}/hooks.py"))
        self.assertIn(f'name = "{self.APP}"', self.read("pyproject.toml"))
        self.assertIn(f"recursive-include {self.APP}", self.read("MANIFEST.in"))
        self.assertEqual(self.read(f"{self.APP}/modules.txt").splitlines()[0], self.APP)
        self.assertTrue(self.exists(f"{self.APP}/{self.APP}/doctype/__init__.py"))
        for rel in (f"{self.APP}/hooks.py", "pyproject.toml", "setup.py"):
            content = self.read(rel)
            self.assertNotIn("{app_name}", content, rel)
            self.assertNotIn("{module_name}", content, rel)
        # And the compose itself proceeded into the scaffolded shell
        self.assertEqual(
            self.read(f"{self.APP}/{self.MODULE}/api.py"), f'APP = "{self.APP}"\n'
        )

    def test_existing_shell_files_never_touched(self):
        self.make_composer_json()
        self.make_shell()
        self.make_sdk()
        sentinel = "# HAND WRITTEN SHELL FILE\napp_name = 'testshell'\n"
        self.write(f"{self.APP}/hooks.py", sentinel)
        composer = self.load_composer()
        out = io.StringIO()
        with redirect_stdout(out):
            composer.scaffold_shell(self.APP, explicit=True)
        self.assertEqual(self.read(f"{self.APP}/hooks.py"), sentinel)
        self.assertIn("kept existing", out.getvalue())
        # Missing skeleton files are still added (per-file additive)
        self.assertTrue(self.exists("pyproject.toml"))

    def test_no_scaffold_when_shell_present_and_flag_absent(self):
        self.make_composer_json()
        self.make_shell()
        self.make_sdk()
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        self.assertNotIn("Scaffolding frappe shell skeleton", out)
        self.assertFalse(self.exists("pyproject.toml"))


class TokenLintTest(ComposeBackendTestBase):
    def test_clean_compose_passes_lint(self):
        self.make_composer_json()
        self.make_shell()
        self.make_sdk()
        self.write(f"sdk/{self.MODULE}/frappe/src/api.py", 'APP = "{app_name}"\n')
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        self.assertIn("Token lint: no unresolved template tokens", out)
        self.assertNotIn("still contain literal template tokens", out)

    def test_dirty_tree_warns_by_default(self):
        dirty = os.path.join(self.root, "dirty")
        os.makedirs(dirty)
        with open(os.path.join(dirty, "bad.py"), "w", encoding="utf-8") as fh:
            fh.write('x = "{app_name}.leftover"\n')
        composer = self.load_composer()
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            offenders = composer.lint_composed_tokens([dirty], self.root)
        self.assertEqual(len(offenders), 1)
        self.assertIn("bad.py", out.getvalue())
        self.assertIn("WARNING", out.getvalue())
        self.assertIn("WARNING", err.getvalue())

    def test_dirty_tree_fails_under_strict(self):
        dirty = os.path.join(self.root, "dirty")
        os.makedirs(dirty)
        with open(os.path.join(dirty, "bad.json"), "w", encoding="utf-8") as fh:
            fh.write('{"module": "{module_name}"}\n')
        composer = self.load_composer()
        os.environ["ROKCT_COMPOSE_STRICT"] = "1"
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            with self.assertRaises(RuntimeError):
                composer.lint_composed_tokens([dirty], self.root)

    def test_generic_braces_not_flagged(self):
        tree = os.path.join(self.root, "tree")
        os.makedirs(tree)
        with open(os.path.join(tree, "fmt.py"), "w", encoding="utf-8") as fh:
            fh.write('msg = "hello {user}".format(user=u)\nj = f"{value}"\n')
        composer = self.load_composer()
        with redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            offenders = composer.lint_composed_tokens([tree], self.root)
        self.assertEqual(offenders, [])


class ShellTemplateSyncTest(ComposeBackendTestBase):
    """The embedded SHELL_TEMPLATES and the canonical on-disk templates in
    core/utils/frappe/templates/shell/ must never drift apart."""

    def test_embedded_templates_match_disk(self):
        composer = self.load_composer()
        disk_files = []
        for base, dirs, files in os.walk(_TEMPLATES_DIR):
            dirs[:] = [d for d in dirs if d != "__pycache__"]
            for name in files:
                if name == "README.md":
                    continue
                rel = os.path.relpath(os.path.join(base, name), _TEMPLATES_DIR)
                disk_files.append(rel.replace(os.sep, "/"))
        self.assertEqual(sorted(disk_files), sorted(composer.SHELL_TEMPLATES))
        for rel, embedded in composer.SHELL_TEMPLATES.items():
            with open(
                os.path.join(_TEMPLATES_DIR, *rel.split("/")), encoding="utf-8"
            ) as fh:
                self.assertEqual(fh.read(), embedded, rel)


if __name__ == "__main__":
    unittest.main()
