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

"""Shared parts come with Pulsar: on a "runtime": "pulsar" template they are never poured or pip-installed,
and a module that requires one is satisfied. Run:  python -m pytest core/utils/frappe/tests -q
"""

import importlib.util
import os
import shutil
import sys
import tempfile
import unittest

_SRC = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "compose_backend.py")


class PulsarProvidedTest(unittest.TestCase):
    def setUp(self):
        self._old_cwd = os.getcwd()
        self.root = tempfile.mkdtemp()
        os.chdir(self.root)
        name = "compose_backend_under_pulsar_test"
        spec = importlib.util.spec_from_file_location(name, _SRC)
        self.mod = importlib.util.module_from_spec(spec)
        sys.modules[name] = self.mod
        spec.loader.exec_module(self.mod)

    def tearDown(self):
        os.chdir(self._old_cwd)
        shutil.rmtree(self.root, ignore_errors=True)

    def test_only_pulsar_templates_get_provided(self):
        self.assertEqual(self.mod.pulsar_provided({"runtime": "pulsar"}), self.mod.PULSAR_PROVIDED)
        self.assertEqual(self.mod.pulsar_provided({}), ())

    def test_requirement_on_provided_part_is_satisfied(self):
        modules = [{"name": "forex", "enabled": True}]
        reqs = {"forex": ["auth", "users", "base"]}
        provided = self.mod.pulsar_provided({"runtime": "pulsar"})
        self.assertEqual(self.mod.find_missing_sdk_requires(modules, reqs, provided), [("forex", "base")])
        self.assertEqual(len(self.mod.find_missing_sdk_requires(modules, reqs)), 3)

    def test_provided_names_never_reach_requirements_txt(self):
        manifests = {"forex": {"dependencies": ["auth", "users", "requests==2.0"]},
                     "erp": {"dependencies": ["auth", "rapidfuzz~=3.14.3"]}}
        self.mod.merge_dependencies(self.root, manifests, self.mod.PULSAR_PROVIDED)
        with open(os.path.join(self.root, "requirements.txt")) as f:
            lines = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
        self.assertEqual(sorted(lines), ["rapidfuzz~=3.14.3", "requests==2.0"])


if __name__ == "__main__":
    unittest.main()
