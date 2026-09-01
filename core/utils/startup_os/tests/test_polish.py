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
    return json.dumps({"choices": [{"message": {"content": content}}]}).encode("utf-8")


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

    def test_financial_compliance_and_will_files_are_never_eligible(self):
        # The will, the living will and the power of attorney are enforceable
        # (or medically directive) language and the financial-legacy plan is
        # numbers: all sit in the same never-sent class as the financial
        # model and the compliance log.
        for name in (
            "07_financial_model.md",
            "financial_plan_on_a_page.md",
            "financial_legacy_plan_on_a_page.md",
            "compliance_log.md",
            "last_will_and_testament.md",
            "living_will_and_healthcare_directive.md",
            "power_of_attorney.md",
        ):
            self.assertFalse(polish.file_is_eligible(name), name)
        self.assertTrue(polish.file_is_eligible("01_executive_summary.md"))
        self.assertTrue(polish.file_is_eligible("annexures/marketing_plan.md"))
        self.assertTrue(polish.file_is_eligible("life_plan_on_a_page.md"))


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
        outcome = polish.polish_text(PROSE, RecordingCallModel(lambda m: m + " ⟦NZZ⟧"))
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
        note_index = next(i for i, line in enumerate(lines) if "**Language**" in line)
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


# --------------------------------------------------------------------------
# Word-capped drafting — the model writes narrative slots from masked founder
# answers, under a hard word budget. Over budget is a rejection and a
# fallback, never a truncation; drafted output is always labeled.
# --------------------------------------------------------------------------


ANSWERS = {
    "vision_statement": "Every clinic in the region running on one platform.",
    "core_value_proposition": (
        "KarooFlow replaces paper diaries and three tools with one platform "
        "priced at R 2,400/month for a two-doctor practice."
    ),
    "problem_statement": (
        "A practice loses 8-12% of billable revenue to rejected claims."
    ),
    "industry": "Healthcare software",
    "primary_base": "Cape Town",
    "customer_segments": "Small private practices with 1-5 practitioners.",
}

LABELS = {
    "vision_statement": "Vision Statement",
    "core_value_proposition": "Core Value Proposition",
    "problem_statement": "Problem Statement",
    "industry": "Industry",
    "primary_base": "Primary Base",
    "customer_segments": "Customer Segments",
}


def _slot(name):
    return polish.draft_slots_by_name()[name]


class TestDraftRequest(unittest.TestCase):
    def test_slot_request_is_digit_free_and_budget_is_spelled_out(self):
        slot = _slot("executive_summary_opening")
        user_text, masked, mapping = polish.prepare_slot_request(slot, ANSWERS, LABELS)
        self.assertFalse(any(ch.isdigit() for ch in user_text), user_text)
        self.assertIn("one hundred and fifty words", user_text)
        self.assertIn("Vision Statement:", user_text)
        # The founder's numbers exist only in the local mapping.
        originals = [token for _p, token in mapping]
        self.assertIn("R 2,400", originals)

    def test_unanswered_slot_is_a_clean_skip(self):
        slot = _slot("competitive_narrative")
        with self.assertRaises(polish.PolishSkipped):
            polish.prepare_slot_request(slot, {}, LABELS)

    def test_draft_system_prompt_is_digit_free(self):
        self.assertFalse(any(ch.isdigit() for ch in polish.DRAFT_SYSTEM_PROMPT))

    def test_life_slots_exist_with_hard_word_budgets(self):
        slots = polish.draft_slots_by_name()
        self.assertEqual(slots["life_plan_opening"].budget, 120)
        self.assertEqual(slots["life_plan_opening"].document, "life_plan_on_a_page.md")
        self.assertEqual(slots["legacy_plan_opening"].budget, 60)
        for slot in polish.DRAFT_SLOTS:
            # Every budget must have a spelled-out, digit-free form.
            self.assertIn(slot.budget, polish._BUDGET_WORDS, slot.name)
            # No slot may ever target the will — enforceable language is
            # never AI-drafted.
            self.assertNotIn("last_will", slot.document, slot.name)

    def test_transport_payload_carries_the_draft_prompt_and_no_digits(self):
        seen = {}

        def fake_transport(url, data, headers, timeout):
            request = json.loads(data.decode("utf-8"))
            seen["system"] = request["messages"][0]["content"]
            seen["user"] = request["messages"][-1]["content"]
            return 200, _groq_body("A fine paragraph.")

        call_model = polish.build_call_model(
            "test-key",
            transport=fake_transport,
            system_prompt=polish.DRAFT_SYSTEM_PROMPT,
        )
        slot = _slot("pitch_problem")
        user_text, _masked, _mapping = polish.prepare_slot_request(
            slot, ANSWERS, LABELS
        )
        call_model(user_text)
        self.assertEqual(seen["system"], polish.DRAFT_SYSTEM_PROMPT)
        self.assertFalse(any(ch.isdigit() for ch in seen["user"]))
        self.assertFalse(any(ch.isdigit() for ch in seen["system"]))


class TestDraftVerification(unittest.TestCase):
    def _request(self, slot_name="pitch_problem"):
        return polish.prepare_slot_request(_slot(slot_name), ANSWERS, LABELS)

    def test_within_budget_draft_is_accepted_with_numbers_restored(self):
        _user, masked, mapping = self._request()
        placeholder = mapping[0][0]
        response = f"Practices lose {placeholder} of revenue to rejected claims."
        text = polish.verify_draft(response, masked, mapping, 60)
        self.assertIn("8-12%", text)
        self.assertNotIn(polish._PLACEHOLDER_OPEN, text)

    def test_over_budget_draft_is_rejected_not_truncated(self):
        _user, masked, mapping = self._request()
        response = "word " * 61
        with self.assertRaises(polish.DraftRejected) as caught:
            polish.verify_draft(response, masked, mapping, 60)
        self.assertIn("over budget", str(caught.exception))
        self.assertIn("rejected rather than truncated", str(caught.exception))

    def test_invented_placeholder_is_rejected(self):
        _user, masked, mapping = self._request()
        with self.assertRaises(polish.DraftRejected):
            polish.verify_draft("Revenue is ⟦NZZ⟧ now.", masked, mapping, 60)

    def test_duplicated_placeholder_is_rejected(self):
        _user, masked, mapping = self._request()
        placeholder = mapping[0][0]
        with self.assertRaises(polish.DraftRejected):
            polish.verify_draft(
                f"Lose {placeholder} then {placeholder} again.",
                masked,
                mapping,
                60,
            )

    def test_stray_digit_is_rejected(self):
        _user, masked, mapping = self._request()
        with self.assertRaises(polish.DraftRejected):
            polish.verify_draft("Growth of 42x is certain.", masked, mapping, 60)

    def test_multi_paragraph_and_structural_markdown_are_rejected(self):
        _user, masked, mapping = self._request()
        for response in (
            "Paragraph one.\n\nParagraph two.",
            "# A heading",
            "*   a list item",
        ):
            with self.assertRaises(polish.DraftRejected, msg=response):
                polish.verify_draft(response, masked, mapping, 60)


DRAFT_DOCUMENT = "\n".join(
    [
        "# Acme — Executive Summary",
        "",
        "> [!IMPORTANT]",
        "> **Document Control**",
        "> *   **Profile**: `business/Acme`",
        "",
        "## 1. The Venture",
        "Founder text stays here.",
        "",
        "## 2. The Problem",
        "More founder text.",
    ]
)


class TestDraftApplication(unittest.TestCase):
    def test_draft_lands_under_its_anchor_with_a_visible_label(self):
        slot = _slot("executive_summary_opening")
        updated = polish.apply_draft(DRAFT_DOCUMENT, slot, "Drafted paragraph.")
        self.assertIn("<!-- ai-draft:executive_summary_opening -->", updated)
        self.assertIn(polish.DRAFT_PROVENANCE_LABEL, updated)
        self.assertLess(
            updated.index("## 1. The Venture"), updated.index("Drafted paragraph.")
        )
        self.assertLess(
            updated.index("Drafted paragraph."), updated.index("## 2. The Problem")
        )
        self.assertIn("Founder text stays here.", updated)

    def test_redraft_replaces_the_block_not_stacks_it(self):
        slot = _slot("executive_summary_opening")
        once = polish.apply_draft(DRAFT_DOCUMENT, slot, "First draft.")
        twice = polish.apply_draft(once, slot, "Second draft.")
        self.assertEqual(twice.count("<!-- ai-draft:"), 1)
        self.assertIn("Second draft.", twice)
        self.assertNotIn("First draft.", twice)

    def test_missing_anchor_is_a_skip_not_a_guess(self):
        slot = _slot("pitch_problem")
        with self.assertRaises(polish.PolishSkipped):
            polish.apply_draft("# Something Else\n\nBody.", slot, "text")

    def test_draft_note_lands_in_document_control_idempotently(self):
        noted = polish.add_draft_note(polish.add_draft_note(DRAFT_DOCUMENT, 1, 0), 2, 1)
        self.assertEqual(noted.count("**Drafting**"), 1)
        self.assertIn("2 section(s) AI-drafted from founder answers", noted)
        self.assertIn("1 draft(s) rejected", noted)

    def test_no_api_key_is_a_clean_noop(self):
        self.assertIsNone(polish.build_draft_call_model_from_env(environ={}))


class TestDraftInstanceEndToEnd(unittest.TestCase):
    """Full pipeline against a compiled workspace with a fake model."""

    def _workspace(self):
        import shutil
        import tempfile

        engine_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        template_src = os.path.join(
            os.path.dirname(engine_dir),
            os.pardir,
            "skills",
            ".rok",
            "startup_os",
            "templates",
        )
        if not os.path.isdir(template_src):
            self.skipTest("templates not present")
        root = tempfile.mkdtemp(prefix="startupos-draft-")
        self.addCleanup(shutil.rmtree, root, True)
        shutil.copytree(template_src, os.path.join(root, "templates"))

        from core import compiler as compiler_mod
        from core import schemas as schemas_mod

        os.makedirs(os.path.join(root, "instances", "business", "Acme"))
        with open(
            os.path.join(root, "instances", "business", "Acme", "questions.md"),
            "w",
            encoding="utf-8",
        ) as handle:
            handle.write(
                schemas_mod.render_questions_md(
                    "business",
                    "Acme",
                    {
                        "trading_name": "Acme",
                        "jurisdiction": "ZA",
                        "primary_base": "Cape Town, South Africa",
                        "industry": "Retail",
                        "vision_statement": "A store on every corner.",
                        "core_value_proposition": "Delivery in 30 minutes for R 99.",
                        "primary_products": "Groceries",
                        "customer_segments": "Households",
                        "growth_strategy": "Word of mouth",
                    },
                )
            )
        compiler_mod.compile_instance(
            "business", "Acme", workspace_root=root, quiet=True
        )
        return root

    def test_accepted_draft_is_labeled_and_rejected_draft_falls_back(self):
        root = self._workspace()

        def respond(user_text):
            if "executive summary" in user_text:
                return "A concise drafted opening that fits its budget."
            return "endless " * 100  # over any budget

        report = polish.draft_instance(
            "business",
            "Acme",
            RecordingCallModel(respond),
            slots=["executive_summary_opening", "pitch_solution"],
            workspace_root=root,
            quiet=True,
        )

        drafted_slots = [name for name, _doc, _words in report.drafted]
        self.assertEqual(drafted_slots, ["executive_summary_opening"])
        self.assertEqual(
            [name for name, _reason in report.rejected], ["pitch_solution"]
        )
        self.assertIn("over budget", report.rejected[0][1])

        out = os.path.join(root, "instances", "business", "Acme", "output")
        with open(
            os.path.join(out, "01_executive_summary.md"), encoding="utf-8"
        ) as handle:
            summary = handle.read()
        self.assertIn("<!-- ai-draft:executive_summary_opening -->", summary)
        self.assertIn(polish.DRAFT_PROVENANCE_LABEL, summary)
        self.assertIn("**Drafting**: 1 section(s) AI-drafted", summary)

        # The rejected slot's document is untouched — founder coaching stands.
        with open(
            os.path.join(out, "annexures", "investor_pitch_deck.md"),
            encoding="utf-8",
        ) as handle:
            deck = handle.read()
        self.assertNotIn("<!-- ai-draft:", deck)
        self.assertNotIn("**Drafting**", deck)

    def test_everything_transmitted_for_drafting_is_digit_free(self):
        root = self._workspace()
        recorder = RecordingCallModel(lambda _text: "Fine.")
        polish.draft_instance(
            "business",
            "Acme",
            recorder,
            workspace_root=root,
            quiet=True,
        )
        self.assertTrue(recorder.sent)
        for payload in recorder.sent:
            self.assertFalse(any(ch.isdigit() for ch in payload), payload)


if __name__ == "__main__":
    unittest.main()
