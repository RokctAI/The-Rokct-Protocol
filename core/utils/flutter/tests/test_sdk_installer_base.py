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

"""Regression tests for sdk_installer_base.py's compose/wiring loudness.

Background: update_layout_integrations() used to skip silently when an
integration's target file was missing and to no-op silently when the
@marker placeholder was absent from the target — composes reported success
while wiring was silently missing. These tests pin the fix:

  * missing target file  -> loud warning naming SDK/file/placeholder
  * absent placeholder   -> loud warning naming SDK/file/marker
  * ROKCT_COMPOSE_STRICT=1 escalates either warning to a hard RuntimeError
  * the happy path (placeholder present) still wires and stays warning-free,
    with or without the strict flag

Run:  python -m pytest core/utils/flutter/tests -q
  or: python core/utils/flutter/tests/test_sdk_installer_base.py
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

_INSTALLER_SRC = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    "sdk_installer_base.py",
)

_module_counter = 0


class LayoutIntegrationTestBase(unittest.TestCase):
    """Builds a throwaway host-project sandbox per test.

    sdk_installer_base.py derives PROJECT_ROOT from its own file location
    (parent of the .rokct/ directory it is fetched into at compose time), so
    each test copies the module into <sandbox>/.rokct/ and imports that copy
    under a unique module name.
    """

    SDK_NAME = "demo_sdk"
    TARGET_REL = "lib/presentation/layout/home_layout.dart"
    PLACEHOLDER = "// @sdk-widget-slot"
    REPLACEMENT = "const DemoSdkCard(),"

    def setUp(self):
        self.project_root = tempfile.mkdtemp(prefix="sdk_installer_test_")
        self.addCleanup(shutil.rmtree, self.project_root, ignore_errors=True)
        rokct_dir = os.path.join(self.project_root, ".rokct")
        os.makedirs(os.path.join(rokct_dir, "cache"))
        # A pubspec.yaml must exist or load_state() would try `flutter create`.
        with open(
            os.path.join(self.project_root, "pubspec.yaml"), "w", encoding="utf-8"
        ) as f:
            f.write("name: testapp\nflutter:\n  assets:\n")
        module_path = os.path.join(rokct_dir, "sdk_installer_base.py")
        shutil.copy2(_INSTALLER_SRC, module_path)

        global _module_counter
        _module_counter += 1
        spec = importlib.util.spec_from_file_location(
            f"sdk_installer_base_under_test_{_module_counter}", module_path
        )
        self.installer = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(self.installer)

        self._saved_strict = os.environ.pop("ROKCT_COMPOSE_STRICT", None)
        self.addCleanup(self._restore_strict)

    def _restore_strict(self):
        os.environ.pop("ROKCT_COMPOSE_STRICT", None)
        if self._saved_strict is not None:
            os.environ["ROKCT_COMPOSE_STRICT"] = self._saved_strict

    def write_state(self, integrations):
        state = {
            "packages": {
                self.SDK_NAME: {
                    "version": "1.0.0",
                    "files": {},
                    "routes": [],
                    "integrations": integrations,
                }
            }
        }
        state_file = os.path.join(
            self.project_root, ".rokct", "cache", "install_state.json"
        )
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f)

    def default_integration(self):
        return {
            "target": self.TARGET_REL,
            "placeholder": self.PLACEHOLDER,
            "replacement": self.REPLACEMENT,
        }

    def write_target(self, content):
        target_abs = os.path.join(self.project_root, self.TARGET_REL)
        os.makedirs(os.path.dirname(target_abs), exist_ok=True)
        with open(target_abs, "w", encoding="utf-8") as f:
            f.write(content)
        return target_abs

    def read_target(self):
        target_abs = os.path.join(self.project_root, self.TARGET_REL)
        with open(target_abs, "r", encoding="utf-8") as f:
            return f.read()

    def run_update(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.installer.update_layout_integrations()
        return out.getvalue(), err.getvalue()


class TestMissingTargetFile(LayoutIntegrationTestBase):
    def test_warning_names_sdk_file_and_placeholder(self):
        """Missing target used to `continue` silently; now it must warn."""
        self.write_state([self.default_integration()])
        out, err = self.run_update()
        combined = out + err
        self.assertIn("WARNING", combined)
        self.assertIn("compose skipped", combined)
        self.assertIn(self.TARGET_REL, combined)
        self.assertIn(self.SDK_NAME, combined)
        self.assertIn(self.PLACEHOLDER, combined)
        self.assertIn("wiring NOT applied", combined)
        # The warning must reach stderr too, not only the stdout transcript.
        self.assertIn("WARNING", err)

    def test_strict_flag_escalates_to_error(self):
        self.write_state([self.default_integration()])
        os.environ["ROKCT_COMPOSE_STRICT"] = "1"
        with self.assertRaises(RuntimeError) as ctx:
            self.run_update()
        self.assertIn("ROKCT_COMPOSE_STRICT", str(ctx.exception))
        self.assertIn(self.TARGET_REL, str(ctx.exception))


class TestAbsentPlaceholder(LayoutIntegrationTestBase):
    def test_warning_names_sdk_file_and_marker(self):
        """Absent placeholder used to make str.replace a silent no-op."""
        self.write_state([self.default_integration()])
        original = "class HomeLayout {}\n// some other content\n"
        self.write_target(original)
        out, err = self.run_update()
        combined = out + err
        self.assertIn("WARNING", combined)
        self.assertIn(f"marker {self.PLACEHOLDER} not found", combined)
        self.assertIn(self.TARGET_REL, combined)
        self.assertIn(self.SDK_NAME, combined)
        self.assertIn("wiring NOT applied", combined)
        self.assertEqual(self.read_target(), original)

    def test_strict_flag_escalates_to_error(self):
        self.write_state([self.default_integration()])
        self.write_target("class HomeLayout {}\n")
        os.environ["ROKCT_COMPOSE_STRICT"] = "true"
        with self.assertRaises(RuntimeError) as ctx:
            self.run_update()
        self.assertIn(self.PLACEHOLDER, str(ctx.exception))


class TestMalformedIntegrationEntry(LayoutIntegrationTestBase):
    def test_entry_without_replacement_warns(self):
        entry = self.default_integration()
        del entry["replacement"]
        self.write_state([entry])
        out, err = self.run_update()
        combined = out + err
        self.assertIn("WARNING", combined)
        self.assertIn("malformed integrations entry", combined)
        self.assertIn(self.SDK_NAME, combined)

    def test_entry_without_replacement_strict_raises(self):
        entry = self.default_integration()
        del entry["replacement"]
        self.write_state([entry])
        os.environ["ROKCT_COMPOSE_STRICT"] = "yes"
        with self.assertRaises(RuntimeError):
            self.run_update()


class TestHappyPathUnchanged(LayoutIntegrationTestBase):
    def test_injection_applies_and_emits_no_warning(self):
        self.write_state([self.default_integration()])
        self.write_target(f"class HomeLayout {{}}\n{self.PLACEHOLDER}\n")
        out, err = self.run_update()
        combined = out + err
        self.assertNotIn("WARNING", combined)
        content = self.read_target()
        # Placeholder preserved for future recomposes, replacement injected.
        self.assertIn(f"{self.PLACEHOLDER}\n{self.REPLACEMENT}", content)

    def test_happy_path_unaffected_by_strict_flag(self):
        self.write_state([self.default_integration()])
        self.write_target(f"class HomeLayout {{}}\n{self.PLACEHOLDER}\n")
        os.environ["ROKCT_COMPOSE_STRICT"] = "1"
        out, err = self.run_update()
        self.assertNotIn("WARNING", out + err)
        self.assertIn(self.REPLACEMENT, self.read_target())

    def test_already_injected_is_still_silent_noop(self):
        self.write_state([self.default_integration()])
        already = f"class HomeLayout {{}}\n{self.PLACEHOLDER}\n{self.REPLACEMENT}\n"
        self.write_target(already)
        os.environ["ROKCT_COMPOSE_STRICT"] = "1"
        out, err = self.run_update()
        self.assertNotIn("WARNING", out + err)
        self.assertEqual(self.read_target(), already)

    def test_strict_flag_off_by_default(self):
        """Unset/other values must keep the warn-and-continue default."""
        self.write_state([self.default_integration()])
        # No target file at all -> warning path, but never an exception.
        out, err = self.run_update()
        self.assertIn("WARNING", out + err)
        os.environ["ROKCT_COMPOSE_STRICT"] = "0"
        out, err = self.run_update()
        self.assertIn("WARNING", out + err)


MANIFEST_WITH_MARKERS = """<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <!-- @sdk-android-permissions-start -->
    <!-- @sdk-android-permissions-end -->
    <uses-permission android:name="android.permission.INTERNET"/>
    <application android:label="app"/>
</manifest>
"""

MANIFEST_WITHOUT_MARKERS = """<manifest xmlns:android="http://schemas.android.com/apk/res/android">
    <uses-permission android:name="android.permission.INTERNET"/>
    <application android:label="app"/>
</manifest>
"""

PLIST_WITHOUT_MARKERS = """<?xml version="1.0" encoding="UTF-8"?>
<plist version="1.0">
<dict>
\t<key>CFBundleName</key>
\t<string>app</string>
</dict>
</plist>
"""


class PlatformPermissionsTestBase(LayoutIntegrationTestBase):
    """Reuses the sandbox; state carries platform_permissions instead."""

    ANDROID_REL = "android/app/src/main/AndroidManifest.xml"
    IOS_REL = "ios/Runner/Info.plist"

    def write_permission_state(self, packages):
        state = {"packages": packages}
        state_file = os.path.join(
            self.project_root, ".rokct", "cache", "install_state.json"
        )
        with open(state_file, "w", encoding="utf-8") as f:
            json.dump(state, f)

    def write_file(self, rel, content):
        path = os.path.join(self.project_root, *rel.split("/"))
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        return path

    def read_file(self, rel):
        path = os.path.join(self.project_root, *rel.split("/"))
        with open(path, "r", encoding="utf-8") as f:
            return f.read()

    def run_permissions_update(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.installer.update_platform_permissions()
        return out.getvalue(), err.getvalue()

    def demo_state(self, android=None, ios=None):
        return {
            "demo_sdk": {
                "version": "1.0.0",
                "files": {},
                "routes": [],
                "platform_permissions": {
                    "android": android or [],
                    "ios": ios or {},
                },
            }
        }


class TestAndroidPermissionInjection(PlatformPermissionsTestBase):
    def test_injects_into_marker_block(self):
        self.write_permission_state(
            self.demo_state(android=["android.permission.POST_NOTIFICATIONS"])
        )
        self.write_file(self.ANDROID_REL, MANIFEST_WITH_MARKERS)
        out, err = self.run_permissions_update()
        self.assertNotIn("WARNING", out + err)
        content = self.read_file(self.ANDROID_REL)
        self.assertIn(
            '<uses-permission android:name="android.permission.POST_NOTIFICATIONS"/>',
            content,
        )

    def test_seeds_markers_when_absent(self):
        self.write_permission_state(
            self.demo_state(android=["android.permission.POST_NOTIFICATIONS"])
        )
        self.write_file(self.ANDROID_REL, MANIFEST_WITHOUT_MARKERS)
        self.run_permissions_update()
        content = self.read_file(self.ANDROID_REL)
        self.assertIn("@sdk-android-permissions-start", content)
        self.assertIn("android.permission.POST_NOTIFICATIONS", content)
        # Seeded block lands after the opening tag, before existing elements.
        self.assertLess(
            content.index("@sdk-android-permissions-start"),
            content.index("android.permission.INTERNET"),
        )

    def test_host_declared_permission_is_never_duplicated(self):
        self.write_permission_state(
            self.demo_state(android=["android.permission.INTERNET"])
        )
        self.write_file(self.ANDROID_REL, MANIFEST_WITH_MARKERS)
        self.run_permissions_update()
        content = self.read_file(self.ANDROID_REL)
        self.assertEqual(content.count("android.permission.INTERNET"), 1)

    def test_removed_sdk_entries_vanish_and_reruns_are_idempotent(self):
        self.write_permission_state(
            self.demo_state(android=["android.permission.POST_NOTIFICATIONS"])
        )
        self.write_file(self.ANDROID_REL, MANIFEST_WITH_MARKERS)
        self.run_permissions_update()
        first = self.read_file(self.ANDROID_REL)
        self.run_permissions_update()
        self.assertEqual(self.read_file(self.ANDROID_REL), first)
        self.write_permission_state({})
        self.run_permissions_update()
        self.assertNotIn(
            "android.permission.POST_NOTIFICATIONS", self.read_file(self.ANDROID_REL)
        )

    def test_missing_manifest_with_entries_warns(self):
        self.write_permission_state(
            self.demo_state(android=["android.permission.POST_NOTIFICATIONS"])
        )
        out, err = self.run_permissions_update()
        self.assertIn("WARNING", out + err)
        self.assertIn("NOT applied", out + err)


class TestIosUsageKeyInjection(PlatformPermissionsTestBase):
    def test_seeds_markers_and_injects_before_closing_dict(self):
        self.write_permission_state(
            self.demo_state(
                ios={"NSCalendarsUsageDescription": "Sync your class schedule."}
            )
        )
        self.write_file(self.IOS_REL, PLIST_WITHOUT_MARKERS)
        out, err = self.run_permissions_update()
        self.assertNotIn("WARNING", out + err)
        content = self.read_file(self.IOS_REL)
        self.assertIn("<key>NSCalendarsUsageDescription</key>", content)
        self.assertIn("<string>Sync your class schedule.</string>", content)
        self.assertLess(
            content.index("NSCalendarsUsageDescription"), content.index("</dict>")
        )

    def test_host_declared_key_wins(self):
        self.write_permission_state(
            self.demo_state(ios={"CFBundleName": "should never appear"})
        )
        self.write_file(self.IOS_REL, PLIST_WITHOUT_MARKERS)
        self.run_permissions_update()
        content = self.read_file(self.IOS_REL)
        self.assertEqual(content.count("CFBundleName"), 1)
        self.assertNotIn("should never appear", content)

    def test_reruns_are_idempotent(self):
        self.write_permission_state(
            self.demo_state(ios={"NSCalendarsUsageDescription": "Sync."})
        )
        self.write_file(self.IOS_REL, PLIST_WITHOUT_MARKERS)
        self.run_permissions_update()
        first = self.read_file(self.IOS_REL)
        self.run_permissions_update()
        self.assertEqual(self.read_file(self.IOS_REL), first)


if __name__ == "__main__":
    unittest.main()
