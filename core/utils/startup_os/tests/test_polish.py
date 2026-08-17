# Copyright (c) 2026 RokctAI
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

"""Regression tests for the AI polish step's number firewall.

Each test pins one way the "no digit ever leaves the machine, no digit can be
changed by the model" guarantee could fail: an unmasked token shape, a
placeholder the model drops or invents, a digit the model adds, a runaway
response, or a file that must never be sent at all. The fake transports here
stand in for the network — no test opens a socket.

Run:  python -m pytest core/utils/startup_os/tests -q
"""

import importlib.util
import json
import os
import sys
import unittest

_ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_engine():
    """Register the engine directory as the `core` package."""
    if "core" in sys.modules and hasattr(sys.modules["core"], "__path__"):
        return
    spec = importlib.util.spec_from_file_location(
        "core",
        os.path.join(_ENGINE_DIR, "__init__.py"),
        submodule_search_locations=[_ENGINE_DIR],
    )
    module = importlib.util.module_from_spec(spec)
    sys.modules["core"] = module
    spec.loader.exec_module(module)


_load_engine()

from core import polish  # noqa: E402


def _groq_body(content):
    return json.dumps({"choices": [{"message": {"content": content}}]}).encode(
        "utf-8"
    )


class RecordingCallModel:
    """Fake model capturing exactly what would have been transmitted."""

    def __init__(self, respond=None):
        self.sent = []
        self.respond = respond or (lambda masked: masked)

    def __call__(self, masked_text):
        self.sent.append(masked_text)
        return self.respond(masked_text)


PROSE = (
    "The venture projects revenue of R 4,800,000 in the first year, growing "
    "past $1.2m equivalent, with ZAR 500k of that contracted. Churn is 12% "
    "against a market entered on 2026-08-17. Call +27 82 123 4567 or quote "
    "registration 2019/123456/07 for verification, noting the 8-12% claims "
    "rejection band."
)


# --------------------------------------------------------------------------
# Masking — every numeric shape in the shipped templates must be caught, and
# whatever the regex misses must still never be transmitted.
# --------------------------------------------------------------------------


class TestMasking(unittest.TestCase):
    def test_every_numeric_token_shape_is_masked(self):
        masked, mapping = polish.mask_numbers(PROSE)
        self.assertFalse(
            any(ch.isdigit() for ch in masked),
            f"digits survived masking: {masked!r}",
        )
        originals = [token for _p, token in mapping]
        self.assertIn("R 4,800,000", originals)
        self.assertIn("$1.2m", originals)
        self.assertIn("ZAR 500k", originals)
        self.assertIn("12%", originals)

    def test_masking_round_trips_exactly(self):
        masked, mapping = polish.mask_numbers(PROSE)
        self.assertEqual(polish.restore_numbers(masked, mapping), PROSE)

    def test_placeholders_themselves_contain_no_digits(self):
        # ⟦N1⟧-style placeholders would make the zero-digit outbound check
        # impossible to state literally; the letter indexing keeps it honest.
        for index in (0, 1, 25, 26, 700):
            self.assertFalse(any(ch.isdigit() for ch in polish._letters(index)))

    def test_unicode_digit_the_regex_misses_blocks_transmission(self):
        # '²' is a digit to isdigit() but not to \d — the paragraph must be
        # kept local rather than sent with a digit in it.
        sneaky = (
            "The engine covers a full twenty-five m² of rack space and stays "
            "well within the cooling envelope agreed with the facility."
        )
        recorder = RecordingCallModel()
        outcome = polish.polish_text(sneaky, recorder)
        self.assertEqual(recorder.sent, [])
        self.assertEqual(outcome.text, sneaky)
        self.assertEqual(outcome.skipped, 1)

    def test_system_prompt_is_digit_free(self):
        self.assertFalse(any(ch.isdigit() for ch in polish.SYSTEM_PROMPT))


# --------------------------------------------------------------------------
# Segmentation — structure, evidence and financials are never eligible.
# --------------------------------------------------------------------------


DOCUMENT = "\n".join(
    [
        "# KarooFlow — Executive Summary",
        "",
        "> [!IMPORTANT]",
        "> **Document Control**",
        "> *   **Profile**: `business/KarooFlow`",
        "> *   **Generated**: `2026-08-17`",
        "",
        "This paragraph is plain prose describing the venture at length, "
        "which makes it the only block eligible for rephrasing here.",
        "",
        "| Year | Revenue |",
        "| :--- | :--- |",
        "| One | R 310,000 |",
        "",
        "```python",
        "print('code stays put')",
        "```",
        "",
        "*   A bullet with R 1,650,000 inside it stays local.",
        "",
        "## Evidence & Provenance",
        "",
        "Everything in this section stays local even though it is prose, "
        "because provenance is evidence and evidence is never rephrased.",
        "",
        "## Completion Gaps",
        "",
        "Gap prose also stays local for exactly the same reason as above, "
        "no matter how paragraph-like it looks to the segmenter.",
    ]
)


class TestSegmentation(unittest.TestCase):
    def test_only_the_prose_paragraph_is_sent(self):
        recorder = RecordingCallModel()
        polish.polish_text(DOCUMENT, recorder)
        self.assertEqual(len(recorder.sent), 1)
        self.assertIn("plain prose describing the venture", recorder.sent[0])

    def test_nothing_sent_ever_contains_a_digit(self):
        recorder = RecordingCallModel()
        polish.polish_text(DOCUMENT, recorder)
        polish.polish_text(PROSE, recorder)
        for payload in recorder.sent:
            self.assertFalse(any(ch.isdigit() for ch in payload), payload)

    def test_segmentation_is_lossless(self):
        rebuilt = "\n".join(seg.text for seg in polish.segment(DOCUMENT))
        self.assertEqual(rebuilt, DOCUMENT)

    def test_financial_and_compliance_files_are_never_eligible(self):
        for name in (
            "07_financial_model.md",
            "financial_plan_on_a_page.md",
            "financial_legacy_plan_on_a_page.md",
            "compliance_log.md",
        ):
            self.assertFalse(polish.file_is_eligible(name), name)
        self.assertTrue(polish.file_is_eligible("01_executive_summary.md"))
        self.assertTrue(polish.file_is_eligible("annexures/marketing_plan.md"))


# --------------------------------------------------------------------------
# Post-pass verification — a misbehaving model reverts, never corrupts.
# --------------------------------------------------------------------------


class TestVerification(unittest.TestCase):
    def test_dropped_placeholder_reverts_the_paragraph(self):
        def drop_first(masked):
            return polish.PLACEHOLDER_RE.sub("", masked, count=1)

        outcome = polish.polish_text(PROSE, RecordingCallModel(drop_first))
        self.assertEqual(outcome.text, PROSE)
        self.assertEqual(outcome.reverted, 1)
        self.assertEqual(outcome.polished, 0)

    def test_invented_placeholder_reverts_the_paragraph(self):
        outcome = polish.polish_text(
            PROSE, RecordingCallModel(lambda m: m + " ⟦NZZ⟧")
        )
        self.assertEqual(outcome.text, PROSE)
        self.assertEqual(outcome.reverted, 1)

    def test_stray_digit_in_response_reverts_the_paragraph(self):
        outcome = polish.polish_text(
            PROSE, RecordingCallModel(lambda m: m + " Revenue grew 42x.")
        )
        self.assertEqual(outcome.text, PROSE)
        self.assertEqual(outcome.reverted, 1)

    def test_runaway_length_reverts_the_paragraph(self):
        outcome = polish.polish_text(
            PROSE, RecordingCallModel(lambda m: m + " Truly." * 200)
        )
        self.assertEqual(outcome.text, PROSE)
        self.assertEqual(outcome.reverted, 1)

    def test_identical_response_is_not_counted_as_a_change(self):
        outcome = polish.polish_text(PROSE, RecordingCallModel())
        self.assertEqual(outcome.text, PROSE)
        self.assertEqual(outcome.polished, 0)
        self.assertEqual(outcome.reverted, 0)

    def test_wellbehaved_rephrasing_restores_exact_numbers(self):
        def rephrase(masked):
            return "In plainer terms: " + masked

        outcome = polish.polish_text(PROSE, RecordingCallModel(rephrase))
        self.assertEqual(outcome.polished, 1)
        for token in ("R 4,800,000", "$1.2m", "ZAR 500k", "12%", "2026-08-17"):
            self.assertIn(token, outcome.text)
        self.assertNotIn(polish._PLACEHOLDER_OPEN, outcome.text)


# --------------------------------------------------------------------------
# Transport — injectable, stdlib-shaped, and fail-safe on every error path.
# --------------------------------------------------------------------------


class TestTransport(unittest.TestCase):
    def test_full_pipeline_through_a_fake_transport(self):
        def fake_transport(url, data, headers, timeout):
            request = json.loads(data.decode("utf-8"))
            user_text = request["messages"][-1]["content"]
            self.assertFalse(any(ch.isdigit() for ch in user_text))
            return 200, _groq_body("Rephrased: " + user_text)

        call_model = polish.build_call_model("test-key", transport=fake_transport)
        outcome = polish.polish_text(PROSE, call_model)
        self.assertEqual(outcome.polished, 1)
        self.assertIn("R 4,800,000", outcome.text)
        self.assertTrue(outcome.text.startswith("Rephrased: "))

    def test_transport_exception_keeps_the_original(self):
        def broken_transport(url, data, headers, timeout):
            raise OSError("connection refused")

        call_model = polish.build_call_model("test-key", transport=broken_transport)
        outcome = polish.polish_text(PROSE, call_model)
        self.assertEqual(outcome.text, PROSE)
        self.assertEqual(outcome.skipped, 1)
        self.assertEqual(outcome.polished, 0)

    def test_non_200_keeps_the_original(self):
        call_model = polish.build_call_model(
            "test-key", transport=lambda *a: (500, b"boom")
        )
        outcome = polish.polish_text(PROSE, call_model)
        self.assertEqual(outcome.text, PROSE)
        self.assertEqual(outcome.skipped, 1)

    def test_malformed_json_keeps_the_original(self):
        call_model = polish.build_call_model(
            "test-key", transport=lambda *a: (200, b"not json")
        )
        outcome = polish.polish_text(PROSE, call_model)
        self.assertEqual(outcome.text, PROSE)
        self.assertEqual(outcome.skipped, 1)

    def test_no_api_key_is_a_clean_noop(self):
        self.assertIsNone(polish.build_call_model_from_env(environ={}))


# --------------------------------------------------------------------------
# Provenance — polished documents say so, idempotently.
# --------------------------------------------------------------------------


class TestProvenanceNote(unittest.TestCase):
    def test_note_lands_inside_the_document_control_block(self):
        noted = polish.add_polish_note(DOCUMENT, 3, 1)
        lines = noted.split("\n")
        note_index = next(
            i for i, line in enumerate(lines) if "**Language**" in line
        )
        self.assertTrue(lines[note_index].startswith("> *   "))
        self.assertTrue(lines[note_index - 1].startswith(">"))
        self.assertIn("3 paragraph(s) rephrased, 1 reverted", noted)

    def test_note_is_replaced_not_stacked_on_rerun(self):
        noted_twice = polish.add_polish_note(
            polish.add_polish_note(DOCUMENT, 3, 1), 5, 0
        )
        self.assertEqual(noted_twice.count("**Language**"), 1)
        self.assertIn("5 paragraph(s) rephrased, 0 reverted", noted_twice)

    def test_document_without_control_block_gets_a_standalone_note(self):
        noted = polish.add_polish_note("Plain text only.", 1, 0)
        self.assertTrue(noted.startswith("> [!NOTE]"))
        self.assertIn("Plain text only.", noted)


if __name__ == "__main__":
    unittest.main()
