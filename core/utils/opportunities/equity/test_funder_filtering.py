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
# Table-driven tests for the equity sync non-funder heading filter and the
# consumer-repo denylist (.rokct/agent/equity_denylist.json).
#
# Run directly (no pytest needed):  python test_funder_filtering.py
# Also collectable by pytest.
#
# REJECT rows are real headings the sync turned into junk cards (deleted in
# RokctAI/opportunities PR #69); ACCEPT rows are real firm names, including
# ones that brush against the heuristics ("Canaan Partners" starts with
# "Can...", "500 Global" starts with digits).

import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from funder_manager import FunderManager, is_junk_heading, load_denylist

# Headings that must be rejected (all seen in the wild on synced sources).
REJECT = (
    "Contents",
    "See also",
    "References",
    "Related posts",
    "Frequently Asked Questions",
    "FAQ",
    "Methodology — How we keep this list current",
    "Quick facts about US startup investment",
    "Useful resources for American startup founders",
    "60% off",
    "What is a venture capital firm?",
    "What is OpenVC ?",
    "Why do founders raise with OpenVC?",
    "How can I find investors for my startup?",
    "How do VC firms in India hire?",
    "Who are Tier 1 VCs?",
    "Who is behind OpenVC?",
    "Where are most of the top VC firms located?",
    "When should you raise?",
    "Can I raise pre-seed or seed funding on OpenVC",
    "Is OpenVC free to use",
    "Do accelerators take equity?",
    "OpenVC startups have raised $1+ billion from",
    "Get Fin free for 1 year with OpenVC?",
    "",
)

# Plausible firm names that must be ACCEPTED by the heuristics.
ACCEPT = (
    "Sequoia Capital",
    "Andreessen Horowitz",
    "Y Combinator",
    "Khosla Ventures",
    "Founders Factory Africa",
    "Canaan Partners",  # first word is "canaan", not the interrogative "can"
    "500 Global",  # leading digits without a percent sign
    "Isomer Capital",  # starts with "Iso...", not the word "is"
    "Dodla Ventures",  # starts with "Do..." as part of a longer word
    "Larsson Ventures",  # junk in practice — handled by the denylist, not heuristics
)


class TestIsJunkHeading(unittest.TestCase):
    def test_rejects_non_funder_headings(self):
        for name in REJECT:
            with self.subTest(name=name):
                self.assertTrue(is_junk_heading(name), f"should reject {name!r}")

    def test_accepts_plausible_firm_names(self):
        for name in ACCEPT:
            with self.subTest(name=name):
                self.assertFalse(is_junk_heading(name), f"should accept {name!r}")


def _card_data(name):
    """Full card payload as equity_sync.run() builds it."""
    return {
        "Organization": name,
        "Funder Type": "VC / Accelerator",
        "Funding Type": "Seed / Series A",
        "Industry": "Tech",
        "Territory": "Global",
        "Country": "Unspecified",
        "Website": "Unspecified",
        "Contact Person": "Unspecified",
        "LinkedIn": "Unspecified",
        "Phone": "",
        "Source": "https://example.com/list",
        "Verification Status": "UNVERIFIED",
        "Notes": "test card",
    }


class TestDenylist(unittest.TestCase):
    def _make_repo(self, denylist_payload):
        root = Path(tempfile.mkdtemp(prefix="equity_denylist_test_"))
        (root / "01_equity").mkdir()
        if denylist_payload is not None:
            agent_dir = root / ".rokct" / "agent"
            agent_dir.mkdir(parents=True)
            (agent_dir / "equity_denylist.json").write_text(
                denylist_payload, encoding="utf-8"
            )
        return root

    def test_missing_denylist_is_empty(self):
        root = self._make_repo(None)
        self.assertEqual(load_denylist(root), set())

    def test_malformed_denylist_is_empty(self):
        root = self._make_repo("{not json")
        self.assertEqual(load_denylist(root), set())

    def test_loads_list_and_normalizes(self):
        root = self._make_repo(json.dumps(["Larsson_Ventures.md", " contents ", ""]))
        self.assertEqual(load_denylist(root), {"larsson_ventures", "contents"})

    def test_create_funder_file_refuses_denylisted_slug(self):
        root = self._make_repo(json.dumps(["larsson_ventures"]))
        manager = FunderManager(registry_path=str(root / "01_equity"))
        self.assertTrue(manager.is_denylisted("Larsson Ventures"))
        with self.assertRaises(ValueError):
            manager.create_funder_file(_card_data("Larsson Ventures"))
        self.assertFalse((root / "01_equity" / "larsson_ventures.md").exists())

    def test_create_funder_file_allows_non_denylisted(self):
        root = self._make_repo(json.dumps(["larsson_ventures"]))
        manager = FunderManager(registry_path=str(root / "01_equity"))
        self.assertFalse(manager.is_denylisted("Sequoia Capital"))
        path = manager.create_funder_file(_card_data("Sequoia Capital"))
        self.assertTrue(Path(path).exists())


class TestSlugGeneration(unittest.TestCase):
    def test_slugs_match_deleted_junk_filenames(self):
        # The denylist keys are card filenames without .md; the generator
        # must keep producing the same slugs the junk cards were saved under.
        manager = FunderManager(registry_path="01_equity/")
        self.assertEqual(manager.slug_for("60% off"), "60%_off")
        self.assertEqual(manager.slug_for("See also"), "see_also")
        self.assertEqual(
            manager.slug_for("Frequently Asked Questions"),
            "frequently_asked_questions",
        )


if __name__ == "__main__":
    unittest.main()
