# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD
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
  * src-nested doctype JSONs (src/**/doctype/<dt>/<dt>.json) under
    NON-persona src/ dirs get the "module"-key rewrite the module-root
    primaries always had, and duplicate detection for them WARNS instead of
    failing the build.
  * persona-scoped doctypes (src/<persona>/doctype/<dt>/, persona declared in
    the manifest's app_type) RELOCATE to the module-root doctype/ destination
    with module-root semantics: hard-error duplicates and the "module"-key
    injection from the manifest name. Excluded personas' doctypes never
    compose; a role-less compose relocates every persona's doctypes.
  * a top-level src/templates/ tree (templates/pages/ portal pages included)
    redirects to the APP-level templates/ dir — where Frappe's website router
    resolves portal pages — with the www/-style collision policy: directories
    union across modules, duplicate destination files hard-error. The
    carve-out is persona-neutral: it composes for every role, like src/www/.
  * manifest hooks.on_login entries (top-level or persona-scoped) merge into
    the composed hooks.py as a deduped LIST — frappe's LoginManager runs
    every registered handler — coercing a bare-string shell on_login first,
    like after_install. They used to be silently dropped at compose time.
  * manifest doctype_js / doctype_list_js entries (declared relative to the
    module's src/ tree) register in the composed hooks.py rewritten to the
    composed module folder, accumulate as a deduped list per DocType across
    modules, and are existence-checked against the composed output.
  * an SDK's top-level frappe/fixtures/ tree redirects to the APP-level
    fixtures/ dir — the only place frappe's import_fixtures() looks — with
    the www/-style collision policy: duplicate destination files hard-error.
    It used to not be copied at all, so seven SDKs' fixture records shipped
    to the built app and never applied.
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
    """Doctypes nested under NON-persona src/ dirs (src/feature/doctype/...,
    where "feature" is not declared in the manifest's app_type) keep their
    established composed path and warn-only duplicate handling. Only doctypes
    under declared PERSONA folders relocate to the module root — see
    PersonaDoctypeRelocationTest; a blanket src/**/doctype/ relocation would
    move the existing src-nested doctypes of non-persona modules and break
    imports referencing their composed paths."""

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


class PersonaDoctypeRelocationTest(ComposeBackendTestBase):
    """Persona-scoped doctypes: src/<persona>/doctype/<dt>/ (persona declared
    in the manifest's app_type) relocates to the module-root doctype/
    destination — the only path Frappe's model sync walks and get_controller
    imports — with module-root semantics: hard-error duplicates via
    COMPILED_DOCTYPES and the primary-JSON "module" key injected from the
    manifest name. The persona strip still governs inclusion: an excluded
    persona's folder (doctypes included) never composes, and a role-less
    shell (no .rokct/config/app_type marker = serve all roles) composes and
    relocates EVERY declared persona's doctypes."""

    def make_persona_sdk(self, module=None):
        module = module or self.MODULE
        self.make_sdk(
            module,
            manifest={
                "name": module,
                "description": "test sdk",
                "app_type": {"tenant": {}, "control": {}},
            },
        )

    def set_role(self, value):
        # A plain role marker: matches no registry template (verified miss
        # against the local registry dir), so resolve_composer_config stays a
        # no-op and no network is touched.
        self.write(".rokct/config/app_type", f"{value}\n")

    def write_persona_doctype(self, persona, dt, module=None):
        module = module or self.MODULE
        self.write(
            f"sdk/{module}/frappe/src/{persona}/doctype/{dt}/{dt}.json",
            json.dumps({"name": dt.title(), "module": "{module_name}"}),
        )
        self.write(
            f"sdk/{module}/frappe/src/{persona}/doctype/{dt}/{dt}.py",
            "from frappe.model.document import Document\n"
            f'PATH = "{{app_name}}.{self.MODULE}.doctype.{dt}.{dt}"\n'
            f"class {dt.title()}(Document):\n    pass\n",
        )

    def test_included_persona_doctype_relocates_to_module_root(self):
        self.make_composer_json()
        self.make_shell()
        self.make_persona_sdk()
        self.set_role("tenant")
        self.write_persona_doctype("tenant", "widget")
        self.write(
            f"sdk/{self.MODULE}/frappe/src/tenant/api.py", 'APP = "{app_name}"\n'
        )
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        # Relocated to the module-root doctype/ destination, module key
        # injected from the manifest name, tokens resolved.
        data = json.loads(
            self.read(f"{self.APP}/{self.MODULE}/doctype/widget/widget.json")
        )
        self.assertEqual(data["module"], self.MODULE)
        controller = self.read(f"{self.APP}/{self.MODULE}/doctype/widget/widget.py")
        self.assertIn(f'"{self.APP}.{self.MODULE}.doctype.widget.widget"', controller)
        self.assertNotIn("{app_name}", controller)
        self.assertIn("Relocated persona DocType: tenant/widget", out)
        # No duplicate copy left under the composed persona subtree
        self.assertFalse(self.exists(f"{self.APP}/{self.MODULE}/tenant/doctype"))
        # The rest of the persona folder still composes as a subpackage
        self.assertEqual(
            self.read(f"{self.APP}/{self.MODULE}/tenant/api.py"),
            f'APP = "{self.APP}"\n',
        )

    def test_excluded_persona_doctype_stripped(self):
        self.make_composer_json()
        self.make_shell()
        self.make_persona_sdk()
        self.set_role("tenant")
        self.write_persona_doctype("control", "secret")
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        self.assertIn("Skipped unused role folder src/control/", out)
        self.assertFalse(self.exists(f"{self.APP}/{self.MODULE}/doctype/secret"))
        self.assertFalse(self.exists(f"{self.APP}/{self.MODULE}/control"))

    def test_roleless_compose_relocates_all_personas(self):
        self.make_composer_json()
        self.make_shell()
        self.make_persona_sdk()
        # No .rokct/config/app_type marker: absence = serve all roles.
        self.write_persona_doctype("tenant", "alpha")
        self.write_persona_doctype("control", "beta")
        composer = self.load_composer()
        self.run_main(composer)
        for dt in ("alpha", "beta"):
            data = json.loads(
                self.read(f"{self.APP}/{self.MODULE}/doctype/{dt}/{dt}.json")
            )
            self.assertEqual(data["module"], self.MODULE, dt)
        self.assertFalse(self.exists(f"{self.APP}/{self.MODULE}/tenant/doctype"))
        self.assertFalse(self.exists(f"{self.APP}/{self.MODULE}/control/doctype"))

    def test_duplicate_doctype_across_persona_dirs_hard_errors(self):
        self.make_composer_json()
        self.make_shell()
        self.make_persona_sdk()
        # Role-less compose pulls BOTH persona folders — the same doctype in
        # two persona dirs would land twice in module-root doctype/, so this
        # is a hard error, not the src-nested warn.
        self.write_persona_doctype("tenant", "clash")
        self.write_persona_doctype("control", "clash")
        composer = self.load_composer()
        with self.assertRaises(ValueError) as ctx:
            self.run_main(composer)
        self.assertIn("Duplicate DocType 'clash'", str(ctx.exception))


class GlobalTemplatesRedirectTest(ComposeBackendTestBase):
    """A module's top-level src/templates/ tree (portal pages under
    templates/pages/ included) must land at the APP-level templates/ dir —
    the only place Frappe's website router resolves portal pages — not under
    the composed module package. Same collision policy as the www/ merge:
    directories union, duplicate destination files hard-error."""

    def setUp(self):
        super().setUp()
        self.make_composer_json()
        self.make_shell()
        self.make_sdk()

    def test_templates_pages_redirect_to_app_level(self):
        self.write(
            f"sdk/{self.MODULE}/frappe/src/templates/pages/portal.html",
            "<h1>{app_name} portal ({module_name})</h1>\n",
        )
        self.write(
            f"sdk/{self.MODULE}/frappe/src/templates/pages/portal.py",
            'import frappe\nAPP = "{app_name}"\n\n\ndef get_context(context):\n    pass\n',
        )
        self.write(
            f"sdk/{self.MODULE}/frappe/src/templates/includes/nav.html",
            "<nav>{app_name}</nav>\n",
        )
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        self.assertIn(f"Merged global templates files from: {self.MODULE}", out)
        # App-level destination, tokens resolved.
        html = self.read(f"{self.APP}/templates/pages/portal.html")
        self.assertEqual(html, f"<h1>{self.APP} portal ({self.MODULE})</h1>\n")
        controller = self.read(f"{self.APP}/templates/pages/portal.py")
        self.assertIn(f'APP = "{self.APP}"', controller)
        self.assertNotIn("{app_name}", controller)
        self.assertEqual(
            self.read(f"{self.APP}/templates/includes/nav.html"),
            f"<nav>{self.APP}</nav>\n",
        )
        # NOT composed into the module package.
        self.assertFalse(self.exists(f"{self.APP}/{self.MODULE}/templates"))

    def test_distinct_files_union_across_modules(self):
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
        self.write(
            f"sdk/{self.MODULE}/frappe/src/templates/pages/alpha.html", "<p>a</p>\n"
        )
        self.write("sdk/othermod/frappe/src/templates/pages/beta.html", "<p>b</p>\n")
        composer = self.load_composer()
        self.run_main(composer)
        self.assertTrue(self.exists(f"{self.APP}/templates/pages/alpha.html"))
        self.assertTrue(self.exists(f"{self.APP}/templates/pages/beta.html"))

    def test_duplicate_template_file_hard_errors(self):
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
                f"sdk/{mod}/frappe/src/templates/pages/clash.html", f"<p>{mod}</p>\n"
            )
        composer = self.load_composer()
        with self.assertRaises(ValueError) as ctx:
            self.run_main(composer)
        self.assertIn(
            "Duplicate global templates file 'pages/clash.html'", str(ctx.exception)
        )

    def test_templates_carveout_is_persona_neutral(self):
        # src/templates/ is a top-level carve-out like src/www/: it composes
        # regardless of the shell's role marker and is never persona-stripped.
        self.make_sdk(
            manifest={
                "name": self.MODULE,
                "description": "test sdk",
                "app_type": {"tenant": {}, "control": {}},
            }
        )
        self.write(".rokct/config/app_type", "tenant\n")
        self.write(
            f"sdk/{self.MODULE}/frappe/src/templates/pages/portal.html",
            "<h1>{app_name}</h1>\n",
        )
        self.write(f"sdk/{self.MODULE}/frappe/src/control/api.py", "X = 1\n")
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        self.assertIn("Skipped unused role folder src/control/", out)
        self.assertEqual(
            self.read(f"{self.APP}/templates/pages/portal.html"),
            f"<h1>{self.APP}</h1>\n",
        )


class FixturesCompositionTest(ComposeBackendTestBase):
    """An SDK's frappe/fixtures/ must land at the APP root, not the module.

    frappe/utils/fixtures.py::import_fixtures walks <app>/fixtures/*.json
    (flat, app-level) on every migrate; a fixtures/ dir left inside the
    composed module folder is never read, so SDK fixture records used to
    ship to the built app and silently never apply.
    """

    def setUp(self):
        super().setUp()
        self.make_composer_json()
        self.make_shell()
        self.make_sdk()

    def test_sdk_fixtures_land_at_app_root(self):
        self.write(
            f"sdk/{self.MODULE}/frappe/fixtures/custom_field_widget.json",
            json.dumps(
                {"doctype": "Custom Field", "dt": "Widget", "fieldname": "colour"}
            ),
        )
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        self.assertTrue(
            self.exists(f"{self.APP}/fixtures/custom_field_widget.json"),
            "SDK fixture did not reach <app>/fixtures/",
        )
        # and NOT inside the composed module folder, where nothing reads it
        self.assertFalse(
            self.exists(f"{self.APP}/{self.MODULE}/fixtures/custom_field_widget.json")
        )
        self.assertIn("Merged fixtures from", out)
        data = json.loads(self.read(f"{self.APP}/fixtures/custom_field_widget.json"))
        self.assertEqual(data["fieldname"], "colour")

    def test_fixture_tokens_resolve(self):
        self.write(
            f"sdk/{self.MODULE}/frappe/fixtures/tokened.json",
            json.dumps(
                {
                    "doctype": "Server Script",
                    "script": "import {app_name}.{module_name}",
                }
            ),
        )
        composer = self.load_composer()
        self.run_main(composer)
        data = json.loads(self.read(f"{self.APP}/fixtures/tokened.json"))
        self.assertEqual(data["script"], f"import {self.APP}.{self.MODULE}")

    def test_tokenless_fixture_stays_byte_identical(self):
        raw = '{\n  "doctype": "Role",\n  "role_name": "Seller"\n}\n'
        self.write(f"sdk/{self.MODULE}/frappe/fixtures/role.json", raw)
        composer = self.load_composer()
        self.run_main(composer)
        self.assertEqual(self.read(f"{self.APP}/fixtures/role.json"), raw)

    def test_fixture_subdirectories_are_copied(self):
        self.write(
            f"sdk/{self.MODULE}/frappe/fixtures/Subscription_Plan/Free.json",
            json.dumps({"doctype": "Subscription Plan", "name": "Free"}),
        )
        composer = self.load_composer()
        self.run_main(composer)
        self.assertTrue(self.exists(f"{self.APP}/fixtures/Subscription_Plan/Free.json"))

    def test_duplicate_fixture_filename_across_modules_hard_errors(self):
        self.make_composer_json(
            modules=[
                {"name": "moda", "enabled": True, "path": "sdk/moda/frappe"},
                {"name": "modb", "enabled": True, "path": "sdk/modb/frappe"},
            ]
        )
        for m in ("moda", "modb"):
            self.make_sdk(module=m)
            self.write(
                f"sdk/{m}/frappe/fixtures/shared.json",
                json.dumps({"doctype": "Role", "role_name": m}),
            )
        composer = self.load_composer()
        with self.assertRaises(ValueError) as ctx:
            self.run_main(composer)
        self.assertIn("Duplicate fixture", str(ctx.exception))

    def test_sdk_without_fixtures_dir_is_a_noop(self):
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        self.assertFalse(self.exists(f"{self.APP}/fixtures"))
        self.assertNotIn("Merged fixtures from", out)


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


class WhitelistedMethodsKeyValidationTest(ComposeBackendTestBase):
    """whitelisted_methods KEYS may carry a single gateway prefix
    ("control:claim_tender") so SDK modules can register gateway-scoped
    cmds; VALUES stay strictly dotted and a second prefix is rejected."""

    def _manifest(self, whitelisted):
        return {
            "name": self.MODULE,
            "description": "test sdk",
            "hooks": {"whitelisted_methods": whitelisted},
        }

    def setUp(self):
        super().setUp()
        self.make_composer_json()
        self.make_shell()

    def test_gateway_prefixed_key_composes(self):
        self.make_sdk(
            manifest=self._manifest(
                {
                    "control:claim_tender": "{app_name}.tender.control.claim_tender",
                    "{app_name}.tender.claim": "{app_name}.tender.control.claim_tender",
                }
            )
        )
        composer = self.load_composer()
        self.run_main(composer)
        hooks = self.read(f"{self.APP}/hooks.py")
        val = f"{self.APP}.tender.control.claim_tender"
        self.assertIn(
            f"whitelisted_methods[{'control:claim_tender'!r}] = {val!r}", hooks
        )
        self.assertIn(
            f"override_whitelisted_methods[{'control:claim_tender'!r}] = {val!r}",
            hooks,
        )
        self.assertIn(
            f"whitelisted_methods[{f'{self.APP}.tender.claim'!r}] = {val!r}", hooks
        )

    def test_colon_in_value_still_aborts(self):
        self.make_sdk(
            manifest=self._manifest(
                {
                    "control:claim_tender": (
                        "control:{app_name}.tender.control.claim_tender"
                    ),
                }
            )
        )
        composer = self.load_composer()
        with self.assertRaises(SystemExit):
            self.run_main(composer)

    def test_double_prefixed_key_aborts(self):
        self.make_sdk(
            manifest=self._manifest(
                {"control:extra:claim": "{app_name}.tender.control.claim_tender"}
            )
        )
        composer = self.load_composer()
        with self.assertRaises(SystemExit):
            self.run_main(composer)


class AfterInstallShellCoercionTest(ComposeBackendTestBase):
    """A shell hooks.py may declare after_install as a bare string (standard
    Frappe style, and what the scaffold template emits). The emitted merge
    block must coerce that string to a list before appending module hooks,
    or importing the composed hooks module raises AttributeError."""

    SHELL_HOOK = "testshell.install.after_install"

    def _compose_with_shell_hooks(self, shell_hooks_content):
        self.make_composer_json()
        self.write(f"{self.APP}/__init__.py", "__version__ = '0.0.1'\n")
        self.write(f"{self.APP}/hooks.py", shell_hooks_content)
        self.write(f"{self.APP}/modules.txt", f"{self.APP}\n")
        self.make_sdk(
            manifest={
                "name": self.MODULE,
                "description": "test sdk",
                "hooks": {"after_install": "{app_name}.mymod.install.after_install"},
            }
        )
        composer = self.load_composer()
        self.run_main(composer)
        return self.read(f"{self.APP}/hooks.py")

    def _exec_hooks(self, content):
        """Execute the composed hooks.py the way an import would; any
        AttributeError from the merge block surfaces here."""
        namespace = {}
        exec(compile(content, "hooks.py", "exec"), namespace)
        return namespace

    def test_string_shell_after_install_coerced_to_list(self):
        content = self._compose_with_shell_hooks(
            f'app_name = "{self.APP}"\nafter_install = "{self.SHELL_HOOK}"\n'
        )
        ns = self._exec_hooks(content)
        self.assertEqual(
            ns["after_install"],
            [self.SHELL_HOOK, f"{self.APP}.mymod.install.after_install"],
        )

    def test_list_shell_after_install_preserved(self):
        content = self._compose_with_shell_hooks(
            f'app_name = "{self.APP}"\nafter_install = ["{self.SHELL_HOOK}"]\n'
        )
        ns = self._exec_hooks(content)
        self.assertEqual(
            ns["after_install"],
            [self.SHELL_HOOK, f"{self.APP}.mymod.install.after_install"],
        )

    def test_absent_shell_after_install_starts_fresh_list(self):
        content = self._compose_with_shell_hooks(f'app_name = "{self.APP}"\n')
        ns = self._exec_hooks(content)
        self.assertEqual(
            ns["after_install"], [f"{self.APP}.mymod.install.after_install"]
        )


class OnLoginMergeTest(ComposeBackendTestBase):
    """on_login is a list hook: frappe's LoginManager.run_trigger calls every
    handler get_hooks("on_login") returns, and get_hooks coerces a bare
    string. Module handlers must accumulate as a deduped list, coercing a
    shell hooks.py bare-string on_login (standard Frappe style) to a list
    first — the after_install treatment. Before this lane existed, manifest
    hooks.on_login entries were silently dropped at compose time."""

    SHELL_HOOK = "testshell.auth.on_login"

    def _make_shell_with_hooks(self, shell_hooks_content):
        self.write(f"{self.APP}/__init__.py", "__version__ = '0.0.1'\n")
        self.write(f"{self.APP}/hooks.py", shell_hooks_content)
        self.write(f"{self.APP}/modules.txt", f"{self.APP}\n")

    def _exec_hooks(self):
        namespace = {}
        exec(compile(self.read(f"{self.APP}/hooks.py"), "hooks.py", "exec"), namespace)
        return namespace

    def test_string_shell_on_login_coerced_and_extended(self):
        self.make_composer_json()
        self._make_shell_with_hooks(
            f'app_name = "{self.APP}"\non_login = "{self.SHELL_HOOK}"\n'
        )
        self.make_sdk(
            manifest={
                "name": self.MODULE,
                "description": "test sdk",
                "hooks": {"on_login": "{app_name}.mymod.auth.sync_roles"},
            }
        )
        composer = self.load_composer()
        self.run_main(composer)
        ns = self._exec_hooks()
        self.assertEqual(
            ns["on_login"], [self.SHELL_HOOK, f"{self.APP}.mymod.auth.sync_roles"]
        )

    def test_multi_module_on_login_accumulates_deduped(self):
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
        self._make_shell_with_hooks(f'app_name = "{self.APP}"\n')
        shared = "{app_name}.shared.auth.sync_roles"
        self.make_sdk(
            manifest={
                "name": self.MODULE,
                "description": "test sdk",
                "hooks": {"on_login": shared},
            }
        )
        self.make_sdk(
            "othermod",
            manifest={
                "name": "othermod",
                "description": "test sdk",
                # A list form, carrying a duplicate of the first module's
                # handler plus its own: the duplicate must land only once.
                "hooks": {"on_login": [shared, "{app_name}.othermod.auth.extra"]},
            },
        )
        composer = self.load_composer()
        self.run_main(composer)
        ns = self._exec_hooks()
        self.assertEqual(
            ns["on_login"],
            [
                f"{self.APP}.shared.auth.sync_roles",
                f"{self.APP}.othermod.auth.extra",
            ],
        )

    def test_tenant_persona_on_login_merges_only_for_matching_role(self):
        # The agent#162 shape: on_login declared under app_type.tenant.hooks.
        self.make_composer_json()
        self._make_shell_with_hooks(f'app_name = "{self.APP}"\n')
        self.make_sdk(
            manifest={
                "name": self.MODULE,
                "description": "test sdk",
                "app_type": {
                    "tenant": {
                        "hooks": {
                            "on_login": "{app_name}.mymod.tenant.permissions.sync_user_roles_on_login"
                        }
                    },
                    "control": {},
                },
            }
        )
        self.write(".rokct/config/app_type", "tenant\n")
        composer = self.load_composer()
        self.run_main(composer)
        ns = self._exec_hooks()
        self.assertEqual(
            ns["on_login"],
            [f"{self.APP}.mymod.tenant.permissions.sync_user_roles_on_login"],
        )

    def test_tenant_persona_on_login_stripped_for_other_role(self):
        # Role marker "hub" (a plain role: matches no registry template, so
        # resolve_composer_config stays a no-op) excludes the tenant block.
        self.make_composer_json()
        self._make_shell_with_hooks(f'app_name = "{self.APP}"\n')
        self.make_sdk(
            manifest={
                "name": self.MODULE,
                "description": "test sdk",
                "app_type": {
                    "tenant": {
                        "hooks": {"on_login": "{app_name}.mymod.tenant.sync_roles"}
                    },
                    "hub": {},
                },
            }
        )
        self.write(".rokct/config/app_type", "hub\n")
        composer = self.load_composer()
        self.run_main(composer)
        self.assertNotIn("on_login", self.read(f"{self.APP}/hooks.py"))

    def test_malformed_on_login_aborts(self):
        self.make_composer_json()
        self._make_shell_with_hooks(f'app_name = "{self.APP}"\n')
        self.make_sdk(
            manifest={
                "name": self.MODULE,
                "description": "test sdk",
                "hooks": {"on_login": "x'; import os #"},
            }
        )
        composer = self.load_composer()
        with self.assertRaises(SystemExit):
            self.run_main(composer)


class DoctypeJsLaneTest(ComposeBackendTestBase):
    """doctype_js / doctype_list_js manifest entries: declared relative to
    the module's own src/ tree, rewritten to the composed module folder
    (frappe resolves these hooks with get_app_path, i.e. app-package
    relative), accumulated as a deduped list per DocType across modules, and
    existence-checked against the composed output. Before this lane existed,
    desk list/form JS shipped under a module's public/js/ composed as dead
    files — nothing registered them in hooks.py."""

    # Persona name "hub" stands in for the agent SDK's "control" persona:
    # a test role marker of "control" would match the registry template
    # control.json and materialize a real composer.json.
    LIST_JS_REL = "hub/public/js/company_subscription_list.js"

    def _exec_hooks(self):
        namespace = {}
        exec(compile(self.read(f"{self.APP}/hooks.py"), "hooks.py", "exec"), namespace)
        return namespace

    def test_persona_list_js_registers_for_matching_role(self):
        # The agent#162 shape: src/<persona>/public/js/... declared under
        # that persona's hooks.doctype_list_js.
        self.make_composer_json()
        self.make_shell()
        self.make_sdk(
            manifest={
                "name": self.MODULE,
                "description": "test sdk",
                "app_type": {
                    "tenant": {},
                    "hub": {
                        "hooks": {
                            "doctype_list_js": {
                                "Company Subscription": self.LIST_JS_REL
                            }
                        }
                    },
                },
            }
        )
        self.write(
            f"sdk/{self.MODULE}/frappe/src/{self.LIST_JS_REL}",
            "frappe.listview_settings['Company Subscription'] = {};\n",
        )
        self.write(".rokct/config/app_type", "hub\n")
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        # The file composed into the module tree...
        self.assertTrue(self.exists(f"{self.APP}/{self.MODULE}/{self.LIST_JS_REL}"))
        # ...and hooks.py registers it app-package-relative, as a list.
        ns = self._exec_hooks()
        self.assertEqual(
            ns["doctype_list_js"],
            {"Company Subscription": [f"{self.MODULE}/{self.LIST_JS_REL}"]},
        )
        self.assertNotIn("WARNING", out)

    def test_form_js_accumulates_across_modules_onto_shell_string(self):
        # A shell that already registers form JS in bare-string frappe style
        # keeps its entry, coerced to a list, and both modules' entries for
        # the SAME DocType accumulate after it (deduped).
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
        self.write(f"{self.APP}/__init__.py", "__version__ = '0.0.1'\n")
        self.write(
            f"{self.APP}/hooks.py",
            f'app_name = "{self.APP}"\n'
            'doctype_js = {"Widget": "public/js/widget.js"}\n',
        )
        self.write(f"{self.APP}/modules.txt", f"{self.APP}\n")
        for mod in (self.MODULE, "othermod"):
            self.make_sdk(
                mod,
                manifest={
                    "name": mod,
                    "description": "test sdk",
                    "hooks": {"doctype_js": {"Widget": "public/js/widget.js"}},
                },
            )
            self.write(
                f"sdk/{mod}/frappe/src/public/js/widget.js",
                "frappe.ui.form.on('Widget', {});\n",
            )
        composer = self.load_composer()
        self.run_main(composer)
        ns = self._exec_hooks()
        self.assertEqual(
            ns["doctype_js"],
            {
                "Widget": [
                    "public/js/widget.js",
                    f"{self.MODULE}/public/js/widget.js",
                    "othermod/public/js/widget.js",
                ]
            },
        )

    def test_missing_registered_js_warns(self):
        self.make_composer_json()
        self.make_shell()
        self.make_sdk(
            manifest={
                "name": self.MODULE,
                "description": "test sdk",
                "hooks": {"doctype_list_js": {"Widget": "public/js/nope_list.js"}},
            }
        )
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        self.assertIn("WARNING", out)
        self.assertIn("not composed into the app", out)
        # The registration is still emitted (warn-and-continue by default).
        ns = self._exec_hooks()
        self.assertEqual(
            ns["doctype_list_js"],
            {"Widget": [f"{self.MODULE}/public/js/nope_list.js"]},
        )

    def test_traversal_js_path_aborts(self):
        self.make_composer_json()
        self.make_shell()
        self.make_sdk(
            manifest={
                "name": self.MODULE,
                "description": "test sdk",
                "hooks": {"doctype_list_js": {"Widget": "../../evil.js"}},
            }
        )
        composer = self.load_composer()
        with self.assertRaises(SystemExit):
            self.run_main(composer)


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
