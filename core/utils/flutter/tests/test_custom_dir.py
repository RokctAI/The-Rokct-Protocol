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



"""Tests for the app-owned custom/ folder hooks in sdk_installer_base.py.

  * no custom/ and no page_overrides -> router and main.dart output is
    exactly what it was before the feature
  * custom/ is mirrored to lib/custom/ (and the mirror removed with it);
    a lib/custom/ compose did not create is left alone
  * custom/routes.dart -> customRoutes spread into the router
  * custom/theme.dart  -> applyCustomTheme() after the SDK brand hook
  * composer.json page_overrides swaps an SDK route's page

Run:  python -m pytest core/utils/flutter/tests -q
"""

import importlib.util
import json
import os
import shutil
import tempfile
import unittest
from contextlib import redirect_stdout
import io

_INSTALLER_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sdk_installer_base.py",
)

ROUTER = """// @generated-imports-start
// @generated-imports-end
class AppRouter {
  List<AutoRoute> get routes => [
// @generated-routes-start
// @generated-routes-end
      ];
}
"""

MAIN = """// @generated-wiring-imports-start
// @generated-wiring-imports-end
void main() {
  // @generated-brandhook-start
  // @generated-brandhook-end
}
"""

_counter = 0


def _write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def _read(path):
    with open(path, encoding="utf-8") as f:
        return f.read()


class CustomDirTest(unittest.TestCase):
    def setUp(self):
        self.root = tempfile.mkdtemp(prefix="custom_dir_test_")
        self.addCleanup(shutil.rmtree, self.root, ignore_errors=True)
        rokct = os.path.join(self.root, ".rokct")
        os.makedirs(os.path.join(rokct, "cache"))
        _write(os.path.join(self.root, "pubspec.yaml"), "name: testapp\n")
        _write(
            os.path.join(self.root, "composer.json"),
            json.dumps({"package_name": "testapp"}),
        )
        self.router = os.path.join(
            self.root, "lib", "presentation", "routes", "app_router.dart"
        )
        self.main = os.path.join(self.root, "lib", "main.dart")
        _write(self.router, ROUTER)
        _write(self.main, MAIN)
        _write(
            os.path.join(rokct, "cache", "install_state.json"),
            json.dumps(
                {
                    "packages": {
                        "auth_sdk": {
                            "files": {},
                            "routes": [
                                {
                                    "path": "/login",
                                    "page": "LoginRoute.page",
                                    "type": "MaterialRoute",
                                    "import": "package:${package}/auth.dart",
                                }
                            ],
                            "brand_hook": {"body": "applyAppBrandColors();"},
                        }
                    }
                }
            ),
        )
        module_path = os.path.join(rokct, "sdk_installer_base.py")
        shutil.copy2(_INSTALLER_SRC, module_path)
        global _counter
        _counter += 1
        spec = importlib.util.spec_from_file_location(
            f"sdk_installer_custom_test_{_counter}", module_path
        )
        self.mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.mod)
        os.environ.pop("ROKCT_COMPOSE_STRICT", None)

    def compose(self):
        with redirect_stdout(io.StringIO()):
            self.mod.update_router_table()
            self.mod.update_brand_hook()
            self.mod.update_wiring_imports()

    def set_composer(self, **extra):
        cfg = {"package_name": "testapp"}
        cfg.update(extra)
        _write(os.path.join(self.root, "composer.json"), json.dumps(cfg))

    def test_absent_custom_is_unchanged(self):
        self.compose()
        self.assertEqual(
            _read(self.router),
            ROUTER.replace(
                "// @generated-imports-start\n",
                "// @generated-imports-start\nimport 'package:testapp/auth.dart';\n",
            ).replace(
                "// @generated-routes-start\n",
                "// @generated-routes-start\n"
                "    MaterialRoute(path: '/login', page: LoginRoute.page),\n",
            ),
        )
        # An empty wiring-imports block renders as one blank line, as before.
        self.assertEqual(
            _read(self.main),
            MAIN.replace(
                "// @generated-wiring-imports-start\n",
                "// @generated-wiring-imports-start\n\n",
            ).replace(
                "  // @generated-brandhook-start\n",
                "  // @generated-brandhook-start\n  applyAppBrandColors();\n",
            ),
        )
        self.assertFalse(os.path.exists(os.path.join(self.root, "lib", "custom")))

    def test_routes_hook(self):
        _write(os.path.join(self.root, "custom", "routes.dart"), "// routes\n")
        self.compose()
        router = _read(self.router)
        self.assertIn(
            "import 'package:testapp/custom/routes.dart' as custom_routes;", router
        )
        self.assertIn("    ...custom_routes.customRoutes,\n", router)
        self.assertTrue(
            os.path.isfile(os.path.join(self.root, "lib", "custom", "routes.dart"))
        )
        self.assertNotIn("custom_theme", _read(self.main))

    def test_theme_hook_runs_after_sdk_brand_hook(self):
        _write(os.path.join(self.root, "custom", "theme.dart"), "// theme\n")
        self.compose()
        main = _read(self.main)
        self.assertIn(
            "import 'package:testapp/custom/theme.dart' as custom_theme;", main
        )
        self.assertIn(
            "  applyAppBrandColors();\n  custom_theme.applyCustomTheme();\n", main
        )
        self.assertNotIn("custom_routes", _read(self.router))

    def test_page_override(self):
        self.set_composer(page_overrides={"LoginRoute": "CustomLoginRoute.page"})
        self.compose()
        router = _read(self.router)
        self.assertIn(
            "MaterialRoute(path: '/login', page: CustomLoginRoute.page),", router
        )
        self.assertNotIn("page: LoginRoute.page", router)

    def test_unknown_override_is_not_fatal_in_strict_mode(self):
        self.set_composer(page_overrides={"NopeRoute": "CustomRoute"})
        os.environ["ROKCT_COMPOSE_STRICT"] = "1"
        self.addCleanup(os.environ.pop, "ROKCT_COMPOSE_STRICT", None)
        self.compose()
        self.assertIn("page: LoginRoute.page", _read(self.router))

    def test_mirror_removed_with_custom(self):
        _write(os.path.join(self.root, "custom", "routes.dart"), "// routes\n")
        self.compose()
        shutil.rmtree(os.path.join(self.root, "custom"))
        self.compose()
        self.assertFalse(os.path.exists(os.path.join(self.root, "lib", "custom")))
        self.assertNotIn("custom_routes", _read(self.router))

    def test_foreign_lib_custom_is_left_alone(self):
        foreign = os.path.join(self.root, "lib", "custom", "mine.dart")
        _write(foreign, "// mine\n")
        self.compose()
        self.assertTrue(os.path.isfile(foreign))
        _write(os.path.join(self.root, "custom", "theme.dart"), "// theme\n")
        self.compose()
        self.assertTrue(os.path.isfile(foreign))
        self.assertFalse(
            os.path.exists(os.path.join(self.root, "lib", "custom", "theme.dart"))
        )


if __name__ == "__main__":
    unittest.main()
