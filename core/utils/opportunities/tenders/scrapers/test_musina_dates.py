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

# Licensed under the MIT License.
# Copyright 2026 ROKCT INTELLIGENCE (PTY) LTD
# Table-driven tests for musina.py closing-date extraction.
#
# Run directly (no pytest needed):  python test_musina_dates.py
# Also collectable by pytest.
#
# Each CASES row: (case_id, provenance, input_text, expected YYYY-MM-DD or None).
# provenance is 'real' for phrasing found verbatim/near-verbatim in the wild
# (source noted per row) or 'constructed' for variants built from Ray's
# first-hand description of Musina notices, pending his manual PDF fetch —
# extend this table with rows from the fetched PDFs.

import sys
import types
import unittest
from pathlib import Path

# musina.py imports network/parsing libs at module level; only the
# date-extraction helpers are under test, so stub what's missing rather
# than requiring the full scraper toolchain.
for _mod in (
    "requests",
    "bs4",
    "pdfplumber",
    "urllib3",
    "urllib3.util",
    "urllib3.util.retry",
    "requests.adapters",
):
    if _mod not in sys.modules:
        stub = types.ModuleType(_mod)
        sys.modules[_mod] = stub
if not hasattr(sys.modules["bs4"], "BeautifulSoup"):
    sys.modules["bs4"].BeautifulSoup = object
if not hasattr(sys.modules["requests.adapters"], "HTTPAdapter"):
    sys.modules["requests.adapters"].HTTPAdapter = object
if not hasattr(sys.modules["urllib3.util.retry"], "Retry"):
    sys.modules["urllib3.util.retry"].Retry = object

sys.path.insert(0, str(Path(__file__).resolve().parent))
from musina import find_closing_date, normalize_date, pub_date_from_url  # noqa: E402

CASES = [
    # --- real phrasings (web-search evidence; musina.gov.za egress-blocked) ---
    (
        "musina_rfq23_closing",
        "real: Musina RFQ23/2025-2026 listing",
        "Closing date: 27 November 2025 at 11:00",
        "2025-11-27",
    ),
    (
        "musina_rfq51_closing_at_symbol",
        "real: Musina RFQ51 page",
        "Closing date: 07 April 2026 @ 11h00",
        "2026-04-07",
    ),
    (
        "musina_rfq08_closing_of",
        "real: tenderbulletins.co.za Musina RFQ08",
        "closing date of 03 August 2026 at 11h00",
        "2026-08-03",
    ),
    (
        "musina_rfq61_before",
        "real: Musina RFQ61 page",
        "quotations before 8 May 2026 @ 11h00",
        "2026-05-08",
    ),
    (
        "musina_on_or_before_room17",
        "real: Musina RFQ listing",
        "written formal quotations to be submitted on or before 23 January 2026 @ 11h00 to room no: 17 Civic Centre, Irwin Street, Musina",
        "2026-01-23",
    ),
    (
        "ethekwini_tenderbox_numeric",
        "real: eThekwini RFQ1003 AW PDF",
        "are to be placed in the Tender Box located in the Reception, uShaka Marine World, (and not any other department), no later than: 26/05/2022 at 11:00am",
        "2022-05-26",
    ),
    (
        "musina_standard_notice_dateless",
        "real: Musina standard tender notice",
        "The bid document must be deposited in the designated Tender box located at the reception area of Musina Local Municipality Civic Centre, 21 Irwin Street, not later than the closing date and time.",
        None,
    ),  # no date in the sentence — must NOT hallucinate one
    # --- constructed from Ray's description (pending his PDF fetch) ---
    (
        "ray_tenderbox_not_later",
        "constructed: Ray's tender-box phrasing",
        "Documents must be deposited in the tender box at the municipal offices not later than 21 May 2026",
        "2026-05-21",
    ),
    (
        "ray_tenderbox_by",
        "constructed: Ray's tender-box phrasing",
        "The document is needed in the tender box by 21 May 2026 at 11h00",
        "2026-05-21",
    ),
    (
        "ray_no_later_numeric",
        "constructed: Ray's phrasing + numeric date",
        "must be submitted by no later than 21/05/2026 at 11h00",
        "2026-05-21",
    ),
    (
        "caps_closing_date",
        "constructed: all-caps municipal style",
        "CLOSING DATE: 21 MAY 2026 AT 11H00",
        "2026-05-21",
    ),
    (
        "closing_time_iso",
        "constructed: closing time + ISO date",
        "Closing time: 2026-05-21 11h00",
        "2026-05-21",
    ),
    (
        "closing_date_and_time",
        "constructed: combined label",
        "Closing date and time: 21 May 2026 at 11h00",
        "2026-05-21",
    ),
    (
        "deadline_hyphen_numeric",
        "constructed: Deadline + dd-mm-yyyy",
        "Deadline: 21-05-2026",
        "2026-05-21",
    ),
    (
        "not_later_month_first",
        "constructed: Month-first US-ish variant",
        "submissions not later than May 21, 2026",
        "2026-05-21",
    ),
    # --- precision guards: dates in non-closing context must NOT match ---
    (
        "advert_date_ignored",
        "guard",
        "This RFQ was advertised on 01 May 2026 in the local press.",
        None,
    ),
    ("create_date_ignored", "guard", "Create Date May 1, 2026 | Musina Web", None),
    ("bare_date_ignored", "guard", "21 May 2026", None),
]


class TestFindClosingDate(unittest.TestCase):
    def test_table(self):
        for case_id, provenance, text, expected in CASES:
            with self.subTest(case=case_id, provenance=provenance):
                self.assertEqual(find_closing_date(text), expected)


class TestHelpers(unittest.TestCase):
    def test_normalize_numeric_formats(self):
        for raw, expected in [
            ("26/05/2022", "2022-05-26"),
            ("21-05-2026", "2026-05-21"),
            ("21.05.2026", "2026-05-21"),
            ("8 May 2026", "2026-05-08"),
            ("21 MAY 2026", "2026-05-21"),
            ("2026-05-21", "2026-05-21"),
        ]:
            self.assertEqual(normalize_date(raw), expected)

    def test_pub_date_from_url(self):
        self.assertEqual(
            pub_date_from_url(
                "https://musina.gov.za/wp-content/uploads/2025/10/RFQ23-Supply-and-delivery-of-stationary.pdf"
            ),
            "2025-10-01",
        )
        self.assertIsNone(
            pub_date_from_url(
                "https://www.musina.gov.za/download/rfq-4-supply-and-delivery-of-cold-mix-asphalt/"
            )
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
