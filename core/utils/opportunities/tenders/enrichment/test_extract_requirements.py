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

# Copyright 2024 ROKCT INTELLIGENCE (PTY) LTD
# Table-driven tests for extract_requirements.py deterministic text
# extraction (CIDB grading, compulsory briefing, functionality threshold,
# gate-1 registration keywords).
#
# Run directly (no pytest needed):  python test_extract_requirements.py
# Also collectable by pytest.
#
# Every 'real' input below is a verbatim fragment from an extracted tender
# PDF in the RokctAI/opportunities card corpus (tender id noted per row) —
# line breaks included, because pdfplumber output is hard-wrapped and the
# patterns must tolerate that.

import sys
import types
import unittest
from pathlib import Path

# extract_requirements.py imports network/PDF libs at module level; only the
# pure text-extraction helpers are under test, so stub what's missing rather
# than requiring the full toolchain.
for _mod in ("requests", "pdfplumber"):
    if _mod not in sys.modules:
        stub = types.ModuleType(_mod)
        sys.modules[_mod] = stub
if not hasattr(sys.modules["requests"], "RequestException"):
    sys.modules["requests"].RequestException = Exception

sys.path.insert(0, str(Path(__file__).resolve().parent))
import extract_requirements  # noqa: E402
from extract_requirements import (  # noqa: E402
    extract_requirements_from_text,
    generate_actionable_tasks,
)

# The fallback path logs an extraction failure; keep the test run from
# writing .rokct/agent/logs into whatever directory it happens to run in.
extract_requirements.log_failure = lambda *args, **kwargs: None

CIDB_CASES = [
    (
        "ezemvelo_1eb",
        "real: ocds-9t57fa-164683",
        "IT IS ESTIMATED THAT TENDERERS SHOULD HAVE A CIDB CONTRACTOR\n"
        "REQUIRED CIDB GRADING\nGRADING OF 1EB OR HIGHER",
        "1EB OR HIGHER",
    ),
    (
        "grade_1ce_bullet",
        "real: ocds-9t57fa-164649",
        "• Only bidders who are CIDB grade 1CE or higher may respond to this bid.",
        "1CE OR HIGHER",
    ),
    (
        "atns_2ep_dash",
        "real: ocds-9t57fa-164465",
        "CIDB Grading – 2EP or Higher Bidder to submit proof of registration",
        "2EP OR HIGHER",
    ),
    (
        "linewrap_1eb",
        "real: ocds-9t57fa-164683 (hard-wrapped)",
        "1. It is estimated that tenderers should have a CIDB contractor grading of\n"
        "1EB or higher.",
        "1EB OR HIGHER",
    ),
    (
        "spaced_5gb",
        "real: KZN ULM 08/26/27 pack",
        "REQUIRED GRADING 5 GB or higher CIDB Grading",
        "5 GB OR HIGHER",
    ),
    (
        "nrf_1sl",
        "real: NRF-SAASTA pack",
        "Bidder is to supply proof of a valid CIDB grade 1 SL or higher "
        "registration certificate",
        "1 SL OR HIGHER",
    ),
    (
        "school_grade_12_no_match",
        "constructed: matric qualification must NOT read as a CIDB grade",
        "Minimum qualification: Grade 12 and Computer Literacy",
        None,
    ),
]

BRIEFING_CASES = [
    (
        "there_will_be",
        "real: ocds-9t57fa-164547",
        "KINDLY TAKE NOTE THAT THERE WILL BE COMPULSORY BRIEFING SESSION\nFOR THIS BID",
        True,
    ),
    (
        "parenthetical",
        "real: ocds-9t57fa-164704",
        "Briefing Session (briefing is compulsory)\nThe briefing session will be "
        "held as follows:\nDate: 26 August 2026",
        True,
    ),
    (
        "mandatory_bullet",
        "real: ocds-9t57fa-164423",
        "• Attendance of the compulsory briefing and site inspection sessions.",
        True,
    ),
    (
        "will_be_held",
        "real: New Hanover pack phrasing",
        "A compulsory Briefing and Site Inspection sessions will be held at New "
        "Hanover offices",
        True,
    ),
    (
        "boilerplate_conditional_no_match",
        "real: SBD boilerplate present in packs WITHOUT a briefing",
        "Where the clarification meeting / briefing session is indicated as "
        "compulsory, bidders will only be considered by entities who have "
        "attended the meeting",
        False,
    ),
    (
        "boilerplate_if_applicable_no_match",
        "real: generic bid-conditions boilerplate",
        "1. Failure to attend the compulsory briefing session (if applicable to "
        "the bid) will result in disqualification of the bid.",
        False,
    ),
]

THRESHOLD_CASES = [
    (
        "threshold_of_80_points",
        "real: ocds-9t57fa-164502",
        "Only bidders achieving the minimum functionality threshold of 80 points "
        "will proceed to the next\nstage of evaluation",
        80,
    ),
    (
        "threshold_for_functionality_70pct",
        "real: ocds-9t57fa-164537",
        "Total 100\nMinimum threshold for functionality: 70%.",
        70,
    ),
    (
        "acceptable_minimum_60",
        "real: ocds-9t57fa-164598",
        "TOTAL SCORE 100 POINTS\nACCEPTABLE MINIMUM SCORE 60 POINTS (60% OF TOTAL "
        "POINTS FOR\nFUNCTIONALITY)",
        60,
    ),
    (
        "minimum_qualifying_score_70",
        "real: corpus phrasing",
        "TOTAL 100\nMINIMUM QUALIFYING SCORE 70 REQUIRED",
        70,
    ),
    (
        "no_threshold",
        "constructed: plain goods RFQ with no functionality stage",
        "Supply and delivery of stationery to the district office.",
        None,
    ),
]


class TestCidbGrading(unittest.TestCase):
    def test_cases(self):
        for case_id, provenance, text, expected in CIDB_CASES:
            with self.subTest(case=case_id, provenance=provenance):
                grades = extract_requirements_from_text(text)["cidb_grading"]
                if expected is None:
                    self.assertEqual(grades, [])
                else:
                    self.assertIn(expected, grades)


class TestBriefingCompulsory(unittest.TestCase):
    def test_cases(self):
        for case_id, provenance, text, expected in BRIEFING_CASES:
            with self.subTest(case=case_id, provenance=provenance):
                found = bool(
                    extract_requirements_from_text(text)["briefing_compulsory"]
                )
                self.assertEqual(found, expected)


class TestFunctionalityThreshold(unittest.TestCase):
    def test_cases(self):
        for case_id, provenance, text, expected in THRESHOLD_CASES:
            with self.subTest(case=case_id, provenance=provenance):
                threshold = extract_requirements_from_text(text)[
                    "functionality_threshold"
                ]
                if expected is None:
                    self.assertIsNone(threshold)
                else:
                    self.assertIsNotNone(threshold)
                    self.assertEqual(threshold["score"], expected)
                    # Grounding: the quote must literally occur in the source
                    # (modulo the whitespace normalization applied to it).
                    import re as _re

                    normalized_src = _re.sub(r"\s+", " ", text)
                    self.assertIn(threshold["quote"], normalized_src)


class TestGateOneRegistrations(unittest.TestCase):
    def test_restricted_suppliers_register(self):
        # real: ocds-9t57fa-164704
        text = (
            "Where a person/s are listed in the Register for Tender Defaulters "
            "and / or the List of Restricted Suppliers, that\nperson will "
            "automatically be disqualified from the bid process."
        )
        gate_1 = extract_requirements_from_text(text)["gate_1_mandatory"]
        upper = [g.upper() for g in gate_1]
        self.assertIn("REGISTER FOR TENDER DEFAULTERS", upper)
        self.assertIn("LIST OF RESTRICTED SUPPLIERS", upper)

    def test_psira(self):
        text = "certified unexpired PSIRA registration certificates"
        gate_1 = extract_requirements_from_text(text)["gate_1_mandatory"]
        self.assertIn("PSIRA", [g.upper() for g in gate_1])


class TestTaskGeneration(unittest.TestCase):
    def test_hard_gates_lead_the_checklist(self):
        text = (
            "• Only bidders who are CIDB grade 1CE or higher may respond to "
            "this bid.\n"
            "KINDLY TAKE NOTE THAT THERE WILL BE COMPULSORY BRIEFING SESSION\n"
            "Complete SBD 4 and attach your CSD report and Tax Clearance."
        )
        reqs = extract_requirements_from_text(text)
        tasks = generate_actionable_tasks(reqs, "test-tender")
        self.assertLessEqual(len(tasks), 7)
        self.assertIn("1CE OR HIGHER", tasks[0])
        self.assertIn("compulsory briefing", tasks[1])

    def test_fallback_unchanged_when_nothing_extracted(self):
        reqs = extract_requirements_from_text("")
        tasks = generate_actionable_tasks(reqs, "test-tender")
        self.assertEqual(
            tasks,
            [
                "Analyze Tender Documents for specific requirements | 1",
                "Identify Mandatory Compliance items | 2",
                "Prepare Initial Response Proposal | 3",
            ],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
