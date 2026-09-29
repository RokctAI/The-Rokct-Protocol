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

"""parse_tender_card: an empty `- **Field**:` stays empty (it must not take
the next `## Heading` line as its value), and every bullet is kept.

Run: python core/utils/opportunities/registry_orchestrator/test_parse_card.py
"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from updaters import parse_tender_card  # noqa: E402

CARD = """---
# Equity Opportunity: Episode 1

## Quick Stats
- **Organization**: Episode 1
- **Country**: UK
- **Flag**: GB

## Contact
- **Phone**:

## Source
- **Source / Verification**: https://episode1.com/team
- **Notes**:

## Audit & Status
- **Status**: ACTIVE
- **Verification Status**: VERIFIED
- **Last Verified**: 2026-04-14
---
"""


class ParseCardTest(unittest.TestCase):
    def test_empty_fields_stay_empty(self):
        data = parse_tender_card(CARD)
        self.assertEqual(data["phone"], "")
        self.assertEqual(data["notes"], "")

    def test_fields_after_an_empty_one_are_kept(self):
        data = parse_tender_card(CARD)
        self.assertEqual(data["flag"], "GB")
        self.assertEqual(data["verification_status"], "VERIFIED")
        self.assertEqual(data["source_/_verification"], "https://episode1.com/team")
        self.assertEqual(data["title"], "Equity Opportunity: Episode 1")

    def test_crlf_card(self):
        data = parse_tender_card(CARD.replace("\n", "\r\n"))
        self.assertEqual(data["phone"], "")
        self.assertEqual(data["flag"], "GB")


if __name__ == "__main__":
    unittest.main()
