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

"""Regression tests for the composer template registry.

Pins the thin-shell contract shared by the frappe and Next.js composers:

  * a shell whose one-line .rokct/config/app_type names a registry template
    (core/utils/frappe/composer/<name>.json) gets composer.json materialized
    from that template before composing — the template WINS over a committed
    composer.json (the flutter CI's clobber semantics);
  * a shell with NO app_type file composes from its committed composer.json
    byte-identically to the legacy behavior;
  * an app_type value that names NO registry template is a plain ROLE marker
    (the pre-existing persona semantics): the committed composer.json is used
    unchanged, with no warning and no failure under ROKCT_COMPOSE_STRICT=1;
  * the sibling-checkout workspace layout (../The-Rokct-Protocol/) is a valid
    registry location, matching resolve_module_sources()' sibling lookup;
  * the Next.js composer (core/utils/nextjs/sdk_composer.py) routes template
    resolution through the shared frappe composer core rather than its own
    implementation, and reads the template's "sdks" key while the frappe
    engine reads "modules" — one product template drives both stacks;
  * every real template in core/utils/frappe/composer/ stays valid JSON and
    declares at least one of "modules"/"sdks".

Run:  python -m pytest core/utils/frappe/tests -q
  or: python core/utils/frappe/tests/test_template_resolution.py
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
_NEXTJS_COMPOSER_SRC = os.path.join(
    os.path.dirname(_FRAPPE_UTILS_DIR), "nextjs", "sdk_composer.py"
)
_REGISTRY_DIR = os.path.join(_FRAPPE_UTILS_DIR, "composer")

_module_counter = 0

_ENV_KEYS = (
    "ROKCT_COMPOSE_STRICT",
    "ROKCT_COMPOSER_TEMPLATES_DIR",
    "ROKCT_PROTOCOL_DIR",
)


class TemplateResolutionTestBase(unittest.TestCase):
    """Throwaway shell-repo sandbox per test, in the style of
    test_compose_backend.py. Both composers derive PROJECT_ROOT from
    os.getcwd() at import time, so each test chdirs into its sandbox and
    loads a fresh module instance."""

    APP = "testshell"
    MODULE = "mymod"
    TEMPLATE = "testproduct"  # must not collide with a real registry template

    def setUp(self):
        self._old_cwd = os.getcwd()
        self._old_env = {k: os.environ.pop(k, None) for k in _ENV_KEYS}
        self._old_argv = sys.argv[:]
        sys.argv = ["compose_backend.py"]
        self.root = tempfile.mkdtemp(prefix="template_resolution_test_")
        self.addCleanup(shutil.rmtree, self.root, True)
        self.addCleanup(self._restore)

    def _restore(self):
        os.chdir(self._old_cwd)
        sys.argv = self._old_argv
        for k, v in self._old_env.items():
            if v is not None:
                os.environ[k] = v
            else:
                os.environ.pop(k, None)

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

    def make_shell(self):
        self.write(f"{self.APP}/__init__.py", "__version__ = '0.0.1'\n")
        self.write(f"{self.APP}/hooks.py", f'app_name = "{self.APP}"\n')
        self.write(f"{self.APP}/modules.txt", f"{self.APP}\n")

    def make_sdk(self, module=None, manifest=None):
        module = module or self.MODULE
        manifest = manifest or {"name": module, "description": "test sdk"}
        self.write(f"sdk/{module}/frappe/manifest.json", json.dumps(manifest))
        self.write(
            f"sdk/{module}/frappe/src/api.py",
            'APP = "{app_name}"\n',
        )

    def make_registry(self, name=None, config=None):
        """A registry directory OUTSIDE the sandbox shell, injected via the
        ROKCT_COMPOSER_TEMPLATES_DIR override — the same template dict the
        real core/utils/frappe/composer/ files use."""
        name = name or self.TEMPLATE
        if config is None:
            config = {
                "name": f"{self.APP}_app",
                "modules": [
                    {
                        "name": self.MODULE,
                        "enabled": True,
                        "path": f"sdk/{self.MODULE}/frappe",
                    }
                ],
            }
        registry = os.path.join(self.root, "_registry")
        os.makedirs(registry, exist_ok=True)
        with open(
            os.path.join(registry, f"{name}.json"), "w", encoding="utf-8", newline="\n"
        ) as fh:
            json.dump(config, fh)
        os.environ["ROKCT_COMPOSER_TEMPLATES_DIR"] = registry
        return registry

    def set_app_type(self, value):
        self.write(".rokct/config/app_type", f"{value}\n")

    def load_composer(self, src=_COMPOSER_SRC):
        global _module_counter
        _module_counter += 1
        os.chdir(self.root)
        spec = importlib.util.spec_from_file_location(
            f"template_resolution_under_test_{_module_counter}", src
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module

    def run_main(self, composer):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            composer.main()
        return out.getvalue(), err.getvalue()


class FrappeTemplateResolutionTest(TemplateResolutionTestBase):
    def test_app_type_template_materializes_composer_json(self):
        self.make_registry()
        self.make_shell()
        self.make_sdk()
        self.set_app_type(self.TEMPLATE)
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        self.assertIn(f"registry template '{self.TEMPLATE}'", out)
        config = json.loads(self.read("composer.json"))
        self.assertEqual(config["name"], f"{self.APP}_app")
        # The compose itself ran from the materialized template
        self.assertEqual(
            self.read(f"{self.APP}/{self.MODULE}/api.py"), f'APP = "{self.APP}"\n'
        )

    def test_template_wins_over_committed_composer_json(self):
        self.make_registry()
        self.make_shell()
        self.make_sdk()
        self.set_app_type(self.TEMPLATE)
        # Committed copy names a module that does not exist; the registry
        # template must clobber it (flutter CI semantics).
        self.write(
            "composer.json",
            json.dumps(
                {
                    "name": f"{self.APP}_app",
                    "modules": [
                        {"name": "ghost", "enabled": True, "path": "sdk/ghost/frappe"}
                    ],
                }
            ),
        )
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        self.assertIn("overwritten from registry template", out)
        self.assertTrue(self.exists(f"{self.APP}/{self.MODULE}/api.py"))
        self.assertFalse(self.exists(f"{self.APP}/ghost"))

    def test_no_app_type_file_is_pure_legacy(self):
        self.make_shell()
        self.make_sdk()
        committed = json.dumps(
            {
                "name": f"{self.APP}_app",
                "modules": [
                    {
                        "name": self.MODULE,
                        "enabled": True,
                        "path": f"sdk/{self.MODULE}/frappe",
                    }
                ],
            }
        )
        self.write("composer.json", committed)
        composer = self.load_composer()
        out, _ = self.run_main(composer)
        self.assertNotIn("registry template", out)
        # Committed composer.json byte-identical and used
        self.assertEqual(self.read("composer.json"), committed)
        self.assertTrue(self.exists(f"{self.APP}/{self.MODULE}/api.py"))

    def test_role_marker_falls_back_quietly_even_under_strict(self):
        """An app_type value that names no template is a ROLE marker — the
        pre-existing persona semantics. It must not warn (and must not fail
        under ROKCT_COMPOSE_STRICT=1), and the committed composer.json must
        be used unchanged."""
        self.make_registry()  # registry exists, but has no 'manager.json'
        self.make_shell()
        self.make_sdk()
        committed = json.dumps(
            {
                "name": f"{self.APP}_app",
                "modules": [
                    {
                        "name": self.MODULE,
                        "enabled": True,
                        "path": f"sdk/{self.MODULE}/frappe",
                    }
                ],
            }
        )
        self.write("composer.json", committed)
        self.set_app_type("manager")
        os.environ["ROKCT_COMPOSE_STRICT"] = "1"
        composer = self.load_composer()
        out, _ = self.run_main(composer)  # must not raise
        self.assertNotIn("registry template", out)
        self.assertEqual(self.read("composer.json"), committed)
        self.assertTrue(self.exists(f"{self.APP}/{self.MODULE}/api.py"))

    def test_role_marker_still_selects_persona_blocks(self):
        """The role semantics of the SAME one-line value are untouched: a
        manifest app_type persona block matching the marker still merges."""
        self.make_registry()  # no 'manager.json' in it
        self.make_shell()
        self.make_sdk(
            manifest={
                "name": self.MODULE,
                "app_type": {
                    "manager": {
                        "hooks": {
                            "fixtures": ["Manager Fixture"],
                        }
                    }
                },
            }
        )
        self.write(
            "composer.json",
            json.dumps(
                {
                    "name": f"{self.APP}_app",
                    "modules": [
                        {
                            "name": self.MODULE,
                            "enabled": True,
                            "path": f"sdk/{self.MODULE}/frappe",
                        }
                    ],
                }
            ),
        )
        self.set_app_type("manager")
        composer = self.load_composer()
        self.run_main(composer)
        self.assertIn("Manager Fixture", self.read(f"{self.APP}/hooks.py"))

    def test_sibling_protocol_checkout_is_a_registry_location(self):
        """<workspace>/<shell> next to <workspace>/The-Rokct-Protocol/ — the
        standard sibling layout — resolves templates with no env override."""
        shell = os.path.join(self.root, "shellrepo")
        sibling_registry = os.path.join(
            self.root, "The-Rokct-Protocol", "core", "utils", "frappe", "composer"
        )
        os.makedirs(shell)
        os.makedirs(sibling_registry)
        template = {
            "name": f"{self.APP}_app",
            "modules": [
                {
                    "name": self.MODULE,
                    "enabled": True,
                    "path": f"sdk/{self.MODULE}/frappe",
                }
            ],
        }
        with open(
            os.path.join(sibling_registry, "siblingproduct.json"),
            "w",
            encoding="utf-8",
            newline="\n",
        ) as fh:
            json.dump(template, fh)
        os.makedirs(os.path.join(shell, ".rokct", "config"))
        with open(
            os.path.join(shell, ".rokct", "config", "app_type"),
            "w",
            encoding="utf-8",
            newline="\n",
        ) as fh:
            fh.write("siblingproduct\n")

        global _module_counter
        _module_counter += 1
        os.chdir(shell)
        spec = importlib.util.spec_from_file_location(
            f"template_resolution_under_test_{_module_counter}", _COMPOSER_SRC
        )
        composer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(composer)
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertTrue(composer.resolve_composer_config(shell))
        with open(os.path.join(shell, "composer.json"), encoding="utf-8") as fh:
            self.assertEqual(json.load(fh)["name"], f"{self.APP}_app")

    def test_invalid_template_json_warns_and_falls_back(self):
        registry = self.make_registry()
        with open(
            os.path.join(registry, "brokenproduct.json"), "w", encoding="utf-8"
        ) as fh:
            fh.write("{not json")
        committed = json.dumps({"name": f"{self.APP}_app", "modules": []})
        self.write("composer.json", committed)
        self.set_app_type("brokenproduct")
        composer = self.load_composer()
        out = io.StringIO()
        with redirect_stdout(out), redirect_stderr(io.StringIO()):
            self.assertFalse(composer.resolve_composer_config())
        self.assertIn("WARNING", out.getvalue())
        self.assertEqual(self.read("composer.json"), committed)


class NextjsSharedCoreTest(TemplateResolutionTestBase):
    """The Next.js composer must route template resolution through the
    shared frappe composer core, not a parallel implementation."""

    def test_loads_frappe_core_from_own_checkout(self):
        composer = self.load_composer(src=_NEXTJS_COMPOSER_SRC)
        core = composer.load_composer_core()
        self.assertIsNotNone(core)
        # It really is the frappe composer core (registry + engine surface)
        self.assertTrue(hasattr(core, "resolve_composer_config"))
        self.assertTrue(hasattr(core, "fetch_composer_template"))
        self.assertTrue(hasattr(core, "compose_module"))

    def test_template_sdks_key_resolved_via_shared_core(self):
        self.make_registry(
            config={
                "name": f"{self.APP}_app",
                "modules": [
                    {"name": "backendmod", "enabled": True, "path": "sdk/x/frappe"}
                ],
                "sdks": [
                    {
                        "name": "example_sdk",
                        "enabled": True,
                        "source": "local",
                        "path": "sdk/example/nextjs",
                    }
                ],
            }
        )
        self.set_app_type(self.TEMPLATE)
        composer = self.load_composer(src=_NEXTJS_COMPOSER_SRC)
        out = io.StringIO()
        with redirect_stdout(out):
            self.assertTrue(composer.resolve_composer_config())
        self.assertIn(f"registry template '{self.TEMPLATE}'", out.getvalue())
        config = json.loads(self.read("composer.json"))
        # The nextjs side of the SAME product template
        self.assertEqual(config["sdks"][0]["name"], "example_sdk")
        # And the frappe side is present for the backend shell to consume
        self.assertEqual(config["modules"][0]["name"], "backendmod")

    def test_no_app_type_is_noop(self):
        composer = self.load_composer(src=_NEXTJS_COMPOSER_SRC)
        self.assertFalse(composer.resolve_composer_config())
        self.assertFalse(self.exists("composer.json"))

    def test_role_marker_is_noop(self):
        self.make_registry()  # registry exists, but has no 'manager.json'
        self.set_app_type("manager")
        composer = self.load_composer(src=_NEXTJS_COMPOSER_SRC)
        with redirect_stdout(io.StringIO()):
            self.assertFalse(composer.resolve_composer_config())
        self.assertFalse(self.exists("composer.json"))


class RealRegistryTest(unittest.TestCase):
    """The real templates in core/utils/frappe/composer/ stay well-formed."""

    def test_all_templates_parse_and_declare_a_stack(self):
        names = [n for n in os.listdir(_REGISTRY_DIR) if n.endswith(".json")]
        self.assertTrue(names)
        for n in names:
            with open(os.path.join(_REGISTRY_DIR, n), encoding="utf-8") as fh:
                data = json.load(fh)
            self.assertTrue(
                isinstance(data.get("modules"), list)
                or isinstance(data.get("sdks"), list),
                f"{n} declares neither 'modules' nor 'sdks'",
            )

    def test_rokctapp_template_carries_nextjs_sdks(self):
        with open(os.path.join(_REGISTRY_DIR, "rokctapp.json"), encoding="utf-8") as fh:
            data = json.load(fh)
        sdk_names = [s["name"] for s in data["sdks"]]
        self.assertIn("erp_sdk", sdk_names)
        erp = data["sdks"][sdk_names.index("erp_sdk")]
        self.assertEqual(erp["path"], "../pay/erp/nextjs")
        self.assertIn("crm_sdk", sdk_names)
        crm = data["sdks"][sdk_names.index("crm_sdk")]
        self.assertEqual(crm["path"], "../productivity/crm/nextjs")
        # crm_sdk's manifest "requires" names accounting files erp_sdk
        # installs; keep erp_sdk ahead of crm_sdk in the compose order.
        self.assertLess(sdk_names.index("erp_sdk"), sdk_names.index("crm_sdk"))


if __name__ == "__main__":
    unittest.main()
