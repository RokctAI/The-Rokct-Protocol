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

"""The [GENERATED TEMPLATE FILE] banner leaves exactly one blank line before
the code it sits on, so an installed file is already prettier-clean.

Before, a template with a blank line after "use client" got the banner's own
blank line plus the template's, and the fleet linter's prettier pass removed
one on every app that tracks the file - which the next compose put back
(supacharge-web a0e95f6, #82).

Run:  python -m pytest core/utils/nextjs/tests -q
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from test_nextjs_home_sdk import HOME_REL, HomeSdkTestBase  # noqa: E402

BANNER_END = "// ==========================================\n"


class BannerSpacingTest(HomeSdkTestBase):
    def write_page(self, body):
        path = os.path.join(self.cache_dir, "alpha", "templates", "page.tsx")
        with open(path, "w", encoding="utf-8") as f:
            f.write(body)

    def installed(self):
        self.write_composer(["alpha_sdk"], home="alpha_sdk")
        self.install("alpha_sdk")
        return self.read(HOME_REL)

    def test_blank_line_after_directive_is_not_doubled(self):
        self.write_page('"use client";\n\nimport * as React from "react";\n')
        out = self.installed()
        self.assertNotIn("\n\n\n", out)
        self.assertIn(BANNER_END + '\nimport * as React from "react";\n', out)

    def test_banner_adds_the_blank_line_when_the_template_has_none(self):
        self.write_page('"use client";\nimport * as React from "react";\n')
        out = self.installed()
        self.assertNotIn("\n\n\n", out)
        self.assertIn(BANNER_END + '\nimport * as React from "react";\n', out)

    def test_licence_header_then_import(self):
        self.write_page('/* licence */\n\nimport * as React from "react";\n')
        out = self.installed()
        self.assertNotIn("\n\n\n", out)
        self.assertTrue(out.startswith("/* licence */\n\n// ====="))


if __name__ == "__main__":
    unittest.main()
