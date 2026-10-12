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

"""update_session_policy() emits the sign-up role and the offline-accounts
setting ("Becoming a seller or driver"): the manager app's policy asks for
seller at sign-up and lets in accounts signed up offline on the phone.

Run:  python -m pytest core/utils/flutter/tests/test_session_policy_signup.py -q
"""

import io
import json
import os
import sys
import unittest
from contextlib import redirect_stderr, redirect_stdout

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from test_sdk_installer_base import LayoutIntegrationTestBase  # noqa: E402

SHELL = """// shell
void applySessionPolicy() {
  // @generated-session-policy-start
  // @generated-session-policy-end
}
"""


class SessionPolicyTestBase(LayoutIntegrationTestBase):
    def write_policy(self, policy):
        state = {
            "packages": {
                "merchants_sdk": {
                    "version": "1.0.0",
                    "files": {},
                    "routes": [],
                    "session_policy": policy,
                }
            }
        }
        path = os.path.join(self.project_root, ".rokct", "cache", "install_state.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(state, f)
        shell = self.installer.SESSION_POLICY_FILE
        os.makedirs(os.path.dirname(shell), exist_ok=True)
        with open(shell, "w", encoding="utf-8") as f:
            f.write(SHELL)
        return shell

    def run_policy(self):
        out, err = io.StringIO(), io.StringIO()
        with redirect_stdout(out), redirect_stderr(err):
            self.installer.update_session_policy()
        with open(self.installer.SESSION_POLICY_FILE, encoding="utf-8") as f:
            return f.read()


class TestSignupAndOffline(SessionPolicyTestBase):
    BASE = {
        "allowed_roles": [{"role": "seller", "landing_route": "/main"}],
        "rejection_route": "/login",
    }

    def test_manager_policy_emits_role_and_offline(self):
        self.write_policy(
            {**self.BASE, "signup_app_role": "seller", "allow_offline_accounts": True}
        )
        content = self.run_policy()
        self.assertIn("    appRole: 'seller',", content)
        self.assertIn("    allowOfflineAccounts: true,", content)

    def test_absent_keys_emit_nothing_new(self):
        self.write_policy(dict(self.BASE))
        content = self.run_policy()
        self.assertNotIn("appRole", content)
        self.assertNotIn("allowOfflineAccounts", content)
        self.assertIn("rejectionRoute: '/login',", content)

    def test_false_emits_nothing(self):
        self.write_policy({**self.BASE, "allow_offline_accounts": False})
        self.assertNotIn("allowOfflineAccounts", self.run_policy())

    def test_non_bool_offline_is_refused(self):
        self.write_policy({**self.BASE, "allow_offline_accounts": "yes"})
        with self.assertRaises(RuntimeError):
            self.run_policy()

    def test_quoted_role_is_refused(self):
        self.write_policy({**self.BASE, "signup_app_role": "sel'ler"})
        with self.assertRaises(RuntimeError):
            self.run_policy()


if __name__ == "__main__":
    unittest.main()
