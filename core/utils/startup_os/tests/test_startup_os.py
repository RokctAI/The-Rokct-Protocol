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

"""Regression tests for StartupOS.

Every test here corresponds to a defect that was confirmed by execution against
the previous engine, not to a hypothetical. The names say which.

Run:  python -m pytest core/utils/startup_os/tests -q
  or: python core/utils/startup_os/tests/test_startup_os.py
"""

import importlib.util
import os
import sys
import unittest
from datetime import date

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

from core import compliance, documents, jurisdictions, safe_io, schemas  # noqa: E402
from core import paths as path_utils  # noqa: E402
from core import template_engine  # noqa: E402
from core.errors import UnsafeNameError  # noqa: E402
from core.parser import parse_questions_md  # noqa: E402

import tempfile  # noqa: E402


class TempWorkspace:
    """Throwaway workspace directory."""

    def __enter__(self):
        self.dir = tempfile.mkdtemp(prefix="startupos-test-")
        return self.dir

    def __exit__(self, *exc):
        import shutil

        shutil.rmtree(self.dir, ignore_errors=True)
        return False


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


# --------------------------------------------------------------------------
# Path safety — CONFIRMED: `../../../ESCAPED` wrote outside the workspace.
# --------------------------------------------------------------------------


class TestPathSafety(unittest.TestCase):
    def test_traversal_in_instance_name_is_rejected(self):
        for name in ("../../../ESCAPED", "..", "a/b", "a\\b", "/etc/passwd", "C:\\x"):
            with self.assertRaises(UnsafeNameError, msg=name):
                path_utils.sanitize_instance_name(name)

    def test_traversal_in_instance_type_is_rejected(self):
        with self.assertRaises(UnsafeNameError):
            path_utils.validate_instance_type("../../evil")

    def test_windows_reserved_names_rejected(self):
        for name in ("CON", "nul", "COM1", "LPT9", "con.md"):
            with self.assertRaises(UnsafeNameError, msg=name):
                path_utils.sanitize_instance_name(name)

    def test_trailing_dot_rejected(self):
        # Windows silently strips a trailing dot, so "profile." and "profile"
        # would name the same file.
        with self.assertRaises(UnsafeNameError):
            path_utils.sanitize_instance_name("profile.")

    def test_surrounding_whitespace_is_trimmed_not_rejected(self):
        # A name arriving from a chat message often carries stray whitespace.
        # Trimming is safe; the trimmed name still has to pass every other check.
        self.assertEqual(path_utils.sanitize_instance_name("  Acme  "), "Acme")

    def test_ordinary_names_accepted(self):
        for name in ("ROKCT", "South-River", "acme_clinic", "Profile.v2", "a1"):
            self.assertEqual(path_utils.sanitize_instance_name(name), name)

    def test_instance_dir_stays_inside_root(self):
        with TempWorkspace() as root:
            resolved = path_utils.instance_dir(root, "business", "Acme")
            self.assertTrue(
                os.path.realpath(resolved).startswith(os.path.realpath(root))
            )


# --------------------------------------------------------------------------
# Parser — CONFIRMED losses: multi-line answers, `-` bullets, key collisions.
# --------------------------------------------------------------------------


class TestParser(unittest.TestCase):
    def _parse(self, body):
        with TempWorkspace() as root:
            path = write(os.path.join(root, "questions.md"), body)
            return parse_questions_md(path)

    def test_multiline_answer_is_preserved(self):
        profile = self._parse(
            "*   **Vision Statement**: q\n"
            "    *   **Answer**: First line of the vision\n"
            "        second line that used to be discarded\n"
        )
        self.assertIn(
            "second line that used to be discarded", profile.get("vision_statement")
        )

    def test_paragraph_answer_survives_blank_line(self):
        profile = self._parse(
            "*   **Vision Statement**: q\n"
            "    *   **Answer**: Paragraph one.\n"
            "\n"
            "        Paragraph two.\n"
            "\n"
            "*   **Industry**: q\n"
            "    *   **Answer**: Health\n"
        )
        self.assertIn("Paragraph two.", profile.get("vision_statement"))
        self.assertEqual(profile.get("industry"), "Health")

    def test_bulleted_multiline_answer_is_not_truncated(self):
        # An answer that is itself a list — an executive team, revenue streams —
        # must survive intact. Indent, not bullet syntax, decides where it ends.
        profile = self._parse(
            "*   **Executive Team**: q\n"
            "    *   **Answer**: *   **CEO**: capital and partnerships.\n"
            "        *   **CTO**: infrastructure and architecture.\n"
            "        *   **Ops Lead**: field onboarding.\n"
            "*   **Industry**: q\n"
            "    *   **Answer**: Fintech\n"
        )
        team = profile.get("executive_team")
        self.assertIn("CTO", team)
        self.assertIn("Ops Lead", team)
        self.assertEqual(profile.get("industry"), "Fintech")

    def test_round_trip_preserves_a_bulleted_answer(self):
        from core.agent_bridge import update_profile_answer

        value = "*   **CEO**: capital.\n*   **CTO**: architecture."
        with TempWorkspace() as root:
            path = write(
                os.path.join(root, "instances", "business", "Acme", "questions.md"),
                "*   **Executive Team**: q\n    *   **Answer**: Pending\n",
            )
            update_profile_answer(path, "Executive Team", value, recompile=False)
            reparsed = parse_questions_md(path).get("executive_team")
            self.assertIn("CEO", reparsed)
            self.assertIn("CTO", reparsed)

    def test_dash_bullets_are_parsed(self):
        profile = self._parse("-   **Industry**: q\n    -   **Answer**: Logistics\n")
        self.assertEqual(profile.get("industry"), "Logistics")

    def test_required_marker_does_not_hide_the_question(self):
        profile = self._parse(
            "*   **Trading Name** *(required)*: q\n    *   **Answer**: Acme\n"
        )
        self.assertEqual(profile.get("trading_name"), "Acme")

    def test_duplicate_keys_produce_a_warning(self):
        profile = self._parse(
            "*   **Key Suppliers**: q\n"
            "    *   **Answer**: First\n"
            "*   **Key-Suppliers**: q\n"
            "    *   **Answer**: Second\n"
        )
        self.assertTrue(any("collides" in w for w in profile.warnings))

    def test_answer_line_is_not_captured_as_a_question(self):
        profile = self._parse("*   **Industry**: q\n    *   **Answer**: Health\n")
        self.assertNotIn("answer", profile.answers)

    def test_pending_answers_count_as_unanswered(self):
        profile = self._parse(
            "*   **Industry**: q\n    *   **Answer**: Pending — tell me later\n"
        )
        self.assertNotIn("industry", profile.answers)
        self.assertIn("industry", profile.pending)

    def test_milestones_are_collected(self):
        profile = self._parse(
            "## Conversational Milestone Log\n"
            "*   **[2026-01-05] (Technical Mastery)**: Shipped the compiler.\n"
        )
        self.assertEqual(len(profile.milestones), 1)
        self.assertEqual(profile.milestones[0].category, "Technical Mastery")


# --------------------------------------------------------------------------
# Jurisdiction — CONFIRMED: a Berlin clinic with a compliance folder became
# South African; "Sa Pa, Vietnam" produced a (Pty) Ltd with B-BBEE Level 1.
# --------------------------------------------------------------------------


class TestJurisdiction(unittest.TestCase):
    def test_sa_pa_vietnam_is_not_south_africa(self):
        warnings = []
        resolved = jurisdictions.resolve({"primary_base": "Sa Pa, Vietnam"}, warnings)
        self.assertNotEqual(resolved.code, "ZA")

    def test_explicit_code_wins(self):
        resolved = jurisdictions.resolve(
            {"jurisdiction": "DE", "primary_base": "South Africa"}, []
        )
        self.assertEqual(resolved.code, "DE")

    def test_full_country_name_in_base_is_inferred(self):
        resolved = jurisdictions.resolve(
            {"primary_base": "Cape Town, South Africa"}, []
        )
        self.assertEqual(resolved.code, "ZA")

    def test_unknown_when_nothing_declared(self):
        resolved = jurisdictions.resolve({}, [])
        self.assertEqual(resolved.code, "UNKNOWN")
        self.assertEqual(resolved.features, frozenset())

    def test_only_south_africa_has_bbee(self):
        with_bbee = [
            code
            for code in jurisdictions.all_codes()
            if jurisdictions.get(code).supports(jurisdictions.FEATURE_BBEE)
        ]
        self.assertEqual(with_bbee, ["ZA"])


# --------------------------------------------------------------------------
# Compliance — the headline defect: fabricated B-BBEE and tax standing.
# --------------------------------------------------------------------------


class TestCompliance(unittest.TestCase):
    def test_south_african_venture_without_certificate_is_pending_not_level_1(self):
        with TempWorkspace() as root:
            record = compliance.load_compliance(
                os.path.join(root, "missing"), "Acme", jurisdictions.get("ZA")
            )
            rendered = record.render("bee_level")
            self.assertTrue(rendered.startswith("Pending"), rendered)
            self.assertNotIn("Level 1", rendered)

    def test_no_fabricated_ownership_or_tax_standing(self):
        with TempWorkspace() as root:
            record = compliance.load_compliance(
                os.path.join(root, "missing"), "Acme", jurisdictions.get("ZA")
            )
            self.assertNotIn("100%", record.render("bee_black_ownership"))
            self.assertNotIn("Good Standing", record.render("tax_compliance_status"))

    def test_non_south_african_venture_has_no_bbee_fields(self):
        with TempWorkspace() as root:
            compliance_dir = os.path.join(root, "compliance")
            os.makedirs(compliance_dir)
            record = compliance.load_compliance(
                compliance_dir, "Acme Clinic", jurisdictions.get("DE")
            )
            self.assertFalse(record.get("bee_level").is_applicable)
            self.assertEqual(record.render("bee_level"), compliance.NOT_APPLICABLE_TEXT)

    def test_bbee_cannot_be_set_outside_south_africa(self):
        record = compliance.ComplianceRecord(jurisdictions.get("US"), "Acme")
        accepted = record.set(
            "bee_level", "Level 1 Contributor", compliance.STATUS_OVERRIDE, "override"
        )
        self.assertFalse(accepted)
        self.assertEqual(record.render("bee_level"), compliance.NOT_APPLICABLE_TEXT)
        self.assertTrue(any("Ignored" in w for w in record.warnings))

    def test_company_name_is_never_derived_from_the_folder(self):
        with TempWorkspace() as root:
            record = compliance.load_compliance(
                os.path.join(root, "missing"),
                "TableMountainTech",
                jurisdictions.get("ZA"),
            )
            self.assertFalse(record.is_verified("company_name"))
            self.assertNotIn("(Pty) Ltd", record.render("company_name"))

    def test_unknown_jurisdiction_suppresses_everything(self):
        with TempWorkspace() as root:
            record = compliance.load_compliance(
                os.path.join(root, "any"), "Acme", jurisdictions.UNKNOWN
            )
            self.assertTrue(all(not f.is_applicable for f in record.fields.values()))


class TestComplianceDates(unittest.TestCase):
    """The date format that let an expired certificate pass as valid."""

    def test_full_month_name_parses(self):
        self.assertEqual(compliance.parse_date("25-October-2024"), date(2024, 10, 25))

    def test_common_formats_parse(self):
        cases = {
            "25-Oct-2024": date(2024, 10, 25),
            "2024-10-25": date(2024, 10, 25),
            "25/10/2024": date(2024, 10, 25),
            "25 October 2024": date(2024, 10, 25),
        }
        for text, expected in cases.items():
            self.assertEqual(compliance.parse_date(text), expected, text)

    def test_pending_is_not_a_date(self):
        self.assertIsNone(compliance.parse_date("Pending — add BEE.pdf"))

    def test_expired_certificate_is_flagged(self):
        record = compliance.ComplianceRecord(jurisdictions.get("ZA"), "Acme")
        record.set(
            "bee_level", "Level 1 Contributor", compliance.STATUS_VERIFIED, "BEE.pdf"
        )
        record.set(
            "bee_expiry_date", "25-October-2024", compliance.STATUS_VERIFIED, "BEE.pdf"
        )
        log = compliance.build_compliance_log(record, "Acme", date(2026, 7, 29))
        self.assertIn("EXPIRED", log)

        status, _ = compliance.compliance_exit_status(record, date(2026, 7, 29))
        self.assertEqual(status, 2)

    def test_valid_certificate_is_not_flagged(self):
        record = compliance.ComplianceRecord(jurisdictions.get("ZA"), "Acme")
        record.set(
            "bee_level", "Level 2 Contributor", compliance.STATUS_VERIFIED, "BEE.pdf"
        )
        record.set(
            "bee_expiry_date", "2027-01-01", compliance.STATUS_VERIFIED, "BEE.pdf"
        )
        log = compliance.build_compliance_log(record, "Acme", date(2026, 7, 29))
        self.assertIn("is valid", log)


# --------------------------------------------------------------------------
# Template engine — CONFIRMED: `{{x}}` inside an answer was re-expanded, and
# a `|` in a value silently added table columns.
# --------------------------------------------------------------------------


class TestTemplateEngine(unittest.TestCase):
    def _ctx(self, values, code="ZA"):
        entry = jurisdictions.get(code)
        return template_engine.RenderContext(values, entry, entry.features)

    def test_values_are_not_re_expanded(self):
        context = self._ctx({"a": "see {{b}}", "b": "SECRET"})
        text, _ = template_engine.render("{{a}}", context)
        self.assertNotIn("SECRET", text)

    def test_pipe_in_a_table_cell_is_escaped(self):
        context = self._ctx({"a": "one | two"})
        text, _ = template_engine.render("| {{a}} |", context)
        self.assertIn("one \\| two", text)

    def test_bbee_block_is_dropped_outside_south_africa(self):
        template = "Start{{#if_feature bbee}}B-BBEE Level 1{{/if_feature}}End"
        text, _ = template_engine.render(template, self._ctx({}, "DE"))
        self.assertNotIn("B-BBEE", text)
        text, _ = template_engine.render(template, self._ctx({}, "ZA"))
        self.assertIn("B-BBEE", text)

    def test_jurisdiction_block(self):
        template = "{{#if_jurisdiction ZA,NA}}SADC{{/if_jurisdiction}}"
        self.assertIn("SADC", template_engine.render(template, self._ctx({}, "NA"))[0])
        self.assertNotIn(
            "SADC", template_engine.render(template, self._ctx({}, "US"))[0]
        )

    def test_pending_value_is_falsy(self):
        template = "{{#if x}}YES{{else}}NO{{/if}}"
        for value in (
            "Pending — add BEE.pdf",
            "Not yet provided",
            "Not applicable",
            "",
        ):
            text, _ = template_engine.render(template, self._ctx({"x": value}))
            self.assertEqual(text.strip(), "NO", value)

    def test_real_value_is_truthy(self):
        text, _ = template_engine.render(
            "{{#if x}}YES{{else}}NO{{/if}}", self._ctx({"x": "Level 2 Contributor"})
        )
        self.assertEqual(text.strip(), "YES")

    def test_nested_blocks(self):
        template = "{{#if_feature bbee}}A{{#if x}}B{{/if}}C{{/if_feature}}"
        text, _ = template_engine.render(template, self._ctx({"x": "yes"}, "ZA"))
        self.assertEqual(text.strip(), "ABC")

    def test_mismatched_block_tag_is_reported(self):
        # `{{#if_feature}}` closed with `{{/if}}` — a typo that renders the
        # whole block literally into the finished document.
        errors = template_engine.check_blocks("{{#if_feature bbee}}text{{/if}}")
        self.assertTrue(errors)
        self.assertIn("if_feature", errors[0])

    def test_unclosed_block_is_reported(self):
        errors = template_engine.check_blocks("{{#if x}}text")
        self.assertTrue(any("never closed" in e for e in errors))

    def test_balanced_blocks_report_nothing(self):
        self.assertEqual(
            template_engine.check_blocks(
                "{{#if_feature bbee}}{{#if x}}a{{else}}b{{/if}}{{/if_feature}}"
            ),
            [],
        )

    def test_shipped_templates_are_structurally_sound(self):
        root = os.path.join(
            os.path.dirname(_ENGINE_DIR),
            os.pardir,
            "skills",
            ".rok",
            "startup_os",
            "templates",
        )
        if not os.path.isdir(root):
            self.skipTest("templates not present")
        problems = []
        for current, _subdirs, filenames in os.walk(root):
            for entry in sorted(filenames):
                if not entry.endswith(".md"):
                    continue
                with open(os.path.join(current, entry), encoding="utf-8") as handle:
                    for error in template_engine.check_blocks(handle.read()):
                        problems.append(f"{entry}: {error}")
        self.assertEqual(problems, [])

    def test_unknown_placeholder_warns(self):
        _text, warnings = template_engine.render("{{nope}}", self._ctx({}))
        self.assertTrue(any("undefined" in w for w in warnings))


# --------------------------------------------------------------------------
# Document assembly — CONFIRMED: the version block was injected by replacing
# the first `---`, which shredded YAML front matter.
# --------------------------------------------------------------------------


class TestDocuments(unittest.TestCase):
    def test_front_matter_survives(self):
        source = (
            "---\ntitle: Investor Memo\nconfidential: true\n---\n\n# Acme\n\nBody.\n"
        )
        result = documents.insert_version_block(source, "> [!IMPORTANT]\n> Control\n")
        self.assertTrue(
            result.startswith("---\ntitle: Investor Memo\nconfidential: true\n---")
        )
        self.assertIn("Control", result)
        self.assertLess(result.index("confidential: true"), result.index("Control"))

    def test_block_lands_after_the_title(self):
        result = documents.insert_version_block("# Acme\n\nBody.\n", "CONTROL\n")
        lines = [line for line in result.split("\n") if line.strip()]
        self.assertEqual(lines[0], "# Acme")
        self.assertEqual(lines[1], "CONTROL")

    def test_version_block_is_computed_not_hardcoded(self):
        block = documents.build_version_block(
            "Acme", "business", "2.0.0", "abc12345", date(2026, 7, 29)
        )
        self.assertIn("2026-07-29", block)
        self.assertIn("abc12345", block)
        self.assertNotIn("sinyage.1aedb8", block)
        self.assertNotIn("2026-05-22", block)

    def test_fingerprint_changes_with_content(self):
        self.assertNotEqual(
            documents.content_fingerprint("a"), documents.content_fingerprint("b")
        )


# --------------------------------------------------------------------------
# Safe IO — CONFIRMED absent: no locking, no atomicity, no history.
# --------------------------------------------------------------------------


class TestSafeIO(unittest.TestCase):
    def test_atomic_write_and_snapshot(self):
        with TempWorkspace() as root:
            path = os.path.join(root, "questions.md")
            safe_io.atomic_write(path, "one")
            safe_io.snapshot(path)
            safe_io.atomic_write(path, "two")
            with open(path, encoding="utf-8") as handle:
                self.assertEqual(handle.read(), "two")
            history = os.listdir(os.path.join(root, safe_io.HISTORY_DIRNAME))
            self.assertEqual(len(history), 1)

    def test_lock_is_exclusive(self):
        with TempWorkspace() as root:
            path = os.path.join(root, "questions.md")
            safe_io.atomic_write(path, "x")
            with safe_io.FileLock(path):
                with self.assertRaises(TimeoutError):
                    safe_io.FileLock(path, timeout=0.2).acquire()

    def test_prune_removes_only_stale_files(self):
        with TempWorkspace() as root:
            for name in ("keep.md", "stale.md"):
                safe_io.atomic_write(os.path.join(root, name), "x")
            removed = safe_io.prune_directory(root, {"keep.md"})
            self.assertEqual(removed, ["stale.md"])
            self.assertTrue(os.path.exists(os.path.join(root, "keep.md")))


# --------------------------------------------------------------------------
# Schema/template agreement — CONFIRMED: provisioning asked for fields no
# template used, and templates needed fields provisioning never asked for.
# --------------------------------------------------------------------------


class TestSchemas(unittest.TestCase):
    TEMPLATE_ROOT = os.path.join(
        os.path.dirname(_ENGINE_DIR),
        os.pardir,
        "skills",
        ".rok",
        "startup_os",
        "templates",
    )

    ENGINE_SUPPLIED = {
        "trading_name",
        "instance_name",
        "company_name",
        "company_name_status",
        "entity_type_hint",
        "jurisdiction_code",
        "jurisdiction_name",
        "currency",
        "currency_symbol",
        "currency_note",
        "privacy_law",
        "standards_body",
        "registry_name",
        "tax_authority",
        "trademarks_details",
        "fin_summary",
        "fin_grid_rev",
        "fin_projection_table",
        "fin_unit_economics",
        "fin_consistency",
        "market_funnel_table",
        "market_sizing_flags",
        "competitor_table",
        "competitor_pricing_table",
        "fin_cac_by_channel_table",
        "fin_cohort_analysis",
        "living_ledger_cv",
        "living_ledger_obituary",
        "milestone_count",
        "he_she",
        "he_she_lower",
        "his_her",
        "his_her_capital",
        "him_her",
        "himself_herself",
        "reg_number",
        "reg_date",
        "registered_office",
        "postal_address",
        "tax_number",
        "tax_pin",
        "tax_pin_issue_date",
        "tax_pin_expiry_date",
        "tax_compliance_status",
        "bee_level",
        "bee_procurement_recognition",
        "bee_black_ownership",
        "bee_youth_owned",
        "bee_disabled_owned",
        "bee_rural_owned",
        "bee_cert_number",
        "bee_issue_date",
        "bee_expiry_date",
    }

    def _placeholders(self, instance_type):
        """Every placeholder across the suite, annexures included."""
        directory = os.path.join(self.TEMPLATE_ROOT, instance_type)
        if not os.path.isdir(directory):
            self.skipTest(f"templates not present at {directory}")
        found = set()
        for current, _subdirs, filenames in os.walk(directory):
            for entry in sorted(filenames):
                if not entry.endswith(".md"):
                    continue
                with open(os.path.join(current, entry), encoding="utf-8") as handle:
                    found |= template_engine.find_placeholders(handle.read())
        return found

    def test_annexures_are_covered_by_the_scan(self):
        directory = os.path.join(self.TEMPLATE_ROOT, "business", "annexures")
        if not os.path.isdir(directory):
            self.skipTest("no annexures directory")
        annexures = [n for n in os.listdir(directory) if n.endswith(".md")]
        self.assertGreater(len(annexures), 0)

    def test_every_business_placeholder_is_collected(self):
        uncollected, _unused = schemas.validate_schema_against_templates(
            "business", self._placeholders("business"), self.ENGINE_SUPPLIED
        )
        self.assertEqual(
            uncollected, [], f"templates need fields nobody asks for: {uncollected}"
        )

    def test_every_life_placeholder_is_collected(self):
        uncollected, _unused = schemas.validate_schema_against_templates(
            "life", self._placeholders("life"), self.ENGINE_SUPPLIED
        )
        self.assertEqual(
            uncollected, [], f"templates need fields nobody asks for: {uncollected}"
        )

    def test_full_provisioned_file_round_trips_through_the_parser(self):
        with TempWorkspace() as root:
            for instance_type in ("business", "life"):
                content = schemas.render_questions_md(
                    instance_type,
                    "Acme",
                    {"trading_name": "Acme", "jurisdiction": "ZA"},
                    include_full=True,
                )
                path = write(os.path.join(root, instance_type, "questions.md"), content)
                profile = parse_questions_md(path)
                parsed = set(profile.answers) | set(profile.pending)
                missing = schemas.schema_keys(instance_type) - parsed
                self.assertEqual(
                    missing, set(), f"{instance_type}: parser missed {missing}"
                )

    def test_default_provisioning_writes_only_core_questions(self):
        # A new user should not meet fifty prompts; `expand` adds the rest.
        with TempWorkspace() as root:
            content = schemas.render_questions_md("business", "Acme")
            path = write(os.path.join(root, "questions.md"), content)
            profile = parse_questions_md(path)
            parsed = set(profile.answers) | set(profile.pending)
            self.assertEqual(parsed, schemas.schema_keys("business", schemas.TIER_CORE))

    def test_expand_adds_every_missing_question(self):
        from core.agent_bridge import expand_profile

        with TempWorkspace() as root:
            path = write(
                os.path.join(root, "instances", "business", "Acme", "questions.md"),
                schemas.render_questions_md("business", "Acme"),
            )
            expand_profile(path, "business")
            profile = parse_questions_md(path)
            parsed = set(profile.answers) | set(profile.pending)
            self.assertEqual(schemas.schema_keys("business") - parsed, set())


# --------------------------------------------------------------------------
# Depth ladder — documents compile at the deepest level the answers support;
# the coaching names the exact missing fields, and Level 3 analysis blocks
# never render from guessed data.
# --------------------------------------------------------------------------


class TestDepthLadder(unittest.TestCase):
    L1 = {
        "trading_name": "x",
        "jurisdiction": "x",
        "primary_base": "x",
        "industry": "x",
        "vision_statement": "x",
        "core_value_proposition": "x",
        "primary_products": "x",
        "customer_segments": "x",
        "growth_strategy": "x",
    }
    L2 = {
        "problem_statement": "x",
        "market_size_tam": "x",
        "market_size_sam": "x",
        "market_size_som": "x",
        "competitive_positioning": "x",
        "revenue_streams": "x",
        "pricing_tiers": "x",
        "executive_team": "x",
        "funding_requirement": "x",
        "gross_margin_target": "x",
        "average_revenue_per_customer": "x",
        "customer_acquisition_cost": "x",
        "monthly_operating_costs": "x",
        "cash_on_hand": "x",
    }
    L3 = {
        "customer_churn_rate": "x",
        "funding_history": "x",
        "hiring_plan": "x",
        "competitor_pricing": "x",
        "cac_by_channel": "x",
        "sales_cycle_length": "x",
        "retention_cohorts": "x",
        "cap_table": "x",
    }

    def test_every_depth_key_is_a_real_schema_key(self):
        collected = schemas.schema_keys("business")
        for level in schemas.depth_levels("business"):
            for key in level.keys:
                self.assertIn(key, collected, key)

    def test_empty_profile_is_level_zero_and_coaches_level_one(self):
        report = schemas.compute_depth("business", set())
        self.assertEqual(report.level, 0)
        self.assertEqual(report.next_level, 1)
        described = schemas.describe_depth(report)
        self.assertIn("Level 0 of 3", described)
        self.assertIn("to reach Level 1 (foundation) answer:", described)
        self.assertIn("Trading Name", described)

    def test_core_answers_reach_level_one_and_coach_level_two(self):
        report = schemas.compute_depth("business", set(self.L1))
        self.assertEqual(report.level, 1)
        described = schemas.describe_depth(report)
        self.assertIn("Level 1 of 3 — foundation", described)
        self.assertIn("to reach Level 2 (investor-ready) answer:", described)
        self.assertIn("Market Size TAM", described)

    def test_investor_answers_reach_level_two_and_name_the_l3_gaps(self):
        report = schemas.compute_depth("business", set(self.L1) | set(self.L2))
        self.assertEqual(report.level, 2)
        described = schemas.describe_depth(report)
        self.assertIn("Level 2 of 3 — investor-ready", described)
        self.assertIn("to reach Level 3 (diligence-grade) answer:", described)
        for label in ("CAC By Channel", "Retention Cohorts", "Cap Table"):
            self.assertIn(label, described)

    def test_all_answers_reach_level_three(self):
        report = schemas.compute_depth(
            "business", set(self.L1) | set(self.L2) | set(self.L3)
        )
        self.assertEqual(report.level, 3)
        self.assertIsNone(report.next_level)
        self.assertIn(
            "Level 3 of 3 — diligence-grade", schemas.describe_depth(report)
        )

    def test_life_profiles_have_no_depth_ladder(self):
        self.assertIsNone(schemas.compute_depth("life", {"full_name"}))
        self.assertIsNone(schemas.describe_depth(None))

    def test_partial_l3_answers_do_not_unlock_the_analysis_blocks(self):
        # One diligence answer without the rest stays locked: no level renders
        # from guessed data, and the depth coaching names what is missing.
        from core import compiler as compiler_mod

        answers = dict(self.L1, **self.L2)
        answers["cac_by_channel"] = "Bureau partnerships: R 9,000"
        values = {}
        compiler_mod._add_diligence_analysis(
            values,
            FakeProfile(answers),
            jurisdictions.get("ZA"),
        )
        self.assertEqual(values["fin_cac_by_channel_table"], "")
        self.assertEqual(values["fin_cohort_analysis"], "")
        self.assertEqual(values["competitor_pricing_table"], "")

    def test_full_l3_answers_unlock_the_analysis_blocks(self):
        from core import compiler as compiler_mod

        answers = dict(self.L1, **self.L2, **self.L3)
        answers.update(
            {
                "competitor_pricing": "GoodX: R 4,100/month\nHealthbridge: R 2,900/month",
                "cac_by_channel": "Bureau partnerships: R 9,000\nWebinars: R 21,000",
                "customer_acquisition_cost": "R 14,000 per clinic",
                "customer_churn_rate": "2% monthly",
                "retention_cohorts": "82% of a signup cohort active at month 12",
            }
        )
        values = {}
        compiler_mod._add_diligence_analysis(
            values, FakeProfile(answers), jurisdictions.get("ZA")
        )
        self.assertIn("| GoodX | R 4,100/month |", values["competitor_pricing_table"])
        self.assertIn("| Bureau partnerships | R9,000 |", values["fin_cac_by_channel_table"])
        self.assertIn("Blended (all channels)", values["fin_cac_by_channel_table"])
        self.assertIn("78%", values["fin_cohort_analysis"])  # (1-0.02)^12
        self.assertIn("50 months", values["fin_cohort_analysis"])  # 1/0.02


class TestDepthLadderEndToEnd(unittest.TestCase):
    TEMPLATE_SRC = os.path.join(
        os.path.dirname(_ENGINE_DIR),
        os.pardir,
        "skills",
        ".rok",
        "startup_os",
        "templates",
    )

    def _compile(self, seed):
        import shutil

        from core import compiler as compiler_mod

        if not os.path.isdir(self.TEMPLATE_SRC):
            self.skipTest("templates not present")
        self.workspace = TempWorkspace()
        root = self.workspace.__enter__()
        self.addCleanup(self.workspace.__exit__, None, None, None)
        shutil.copytree(self.TEMPLATE_SRC, os.path.join(root, "templates"))
        write(
            os.path.join(root, "instances", "business", "Acme", "questions.md"),
            schemas.render_questions_md("business", "Acme", seed, include_full=True),
        )
        result = compiler_mod.compile_instance(
            "business", "Acme", workspace_root=root, quiet=True
        )
        self.assertTrue(result.ok)
        out = os.path.join(root, "instances", "business", "Acme", "output")
        return {
            name: open(os.path.join(out, name), encoding="utf-8").read()
            for name in ("01_executive_summary.md", "03_market_analysis.md", "07_financial_model.md")
        }

    SEED_L1 = {
        "trading_name": "Acme",
        "jurisdiction": "ZA",
        "primary_base": "Cape Town, South Africa",
        "industry": "Retail",
        "vision_statement": "A store on every corner.",
        "core_value_proposition": "Fast delivery.",
        "primary_products": "Groceries",
        "customer_segments": "Households",
        "growth_strategy": "Word of mouth",
    }

    def test_depth_line_renders_with_the_actual_missing_fields(self):
        docs = self._compile(self.SEED_L1)
        control = docs["01_executive_summary.md"]
        self.assertIn("> *   **Depth**: Level 1 of 3 — foundation", control)
        self.assertIn("to reach Level 2 (investor-ready) answer:", control)
        self.assertIn("Problem Statement", control)
        # Level 3 blocks stay locked, with the unlock coaching in place.
        self.assertNotIn("### CAC by Channel", docs["07_financial_model.md"])
        self.assertIn(
            "unlock at Level 3", docs["07_financial_model.md"]
        )
        self.assertNotIn(
            "### Named-Competitor Pricing", docs["03_market_analysis.md"]
        )

    def test_level_three_profile_unlocks_the_deeper_blocks(self):
        seed = dict(
            self.SEED_L1,
            problem_statement="Households waste hours shopping.",
            market_size_tam="R 9.6 billion — category report",
            market_size_sam="R 1.9 billion — reachable slice",
            market_size_som="R 190 million — 36-month capture",
            competitive_positioning="BigCo: broad but slow. SmallCo: fast but narrow.",
            revenue_streams="Delivery fees and subscriptions",
            pricing_tiers="R 99/month standard",
            executive_team="Jane Doe — CEO: everything.",
            funding_requirement="R 5,000,000 seed",
            gross_margin_target="60%",
            average_revenue_per_customer="R 250 per month",
            customer_acquisition_cost="R 900",
            monthly_operating_costs="R 400,000 per month",
            cash_on_hand="R 3,000,000",
            customer_churn_rate="3% monthly",
            funding_history="R 1,000,000 angel round",
            hiring_plan="2 drivers in Q1",
            competitor_pricing="BigCo: R 149/month. SmallCo: R 79/month.",
            cac_by_channel="Referrals: R 400\nSocial ads: R 1,600",
            sales_cycle_length="7 days median",
            retention_cohorts="70% of a cohort active at month 12",
            cap_table="Ordinary shares only; 10% option pool; no notes outstanding",
        )
        docs = self._compile(seed)
        self.assertIn(
            "**Depth**: Level 3 of 3 — diligence-grade",
            docs["01_executive_summary.md"],
        )
        financial = docs["07_financial_model.md"]
        self.assertIn("### CAC by Channel", financial)
        self.assertIn("| Referrals | R400 |", financial)
        self.assertIn("### Cohort & Retention Analysis", financial)
        self.assertNotIn("unlock at Level 3", financial)
        market = docs["03_market_analysis.md"]
        self.assertIn("### Named-Competitor Pricing", market)
        self.assertIn("BigCo", market)


# --------------------------------------------------------------------------
# Financial computation — CONFIRMED: the financial model echoed free-text
# answers and shipped literal "_to be supplied_" unit-economics cells even
# when ARPC, CAC, burn and cash were all present in questions.md.
# --------------------------------------------------------------------------

from core import compiler  # noqa: E402


class FakeProfile:
    """Minimal stand-in for ParsedProfile: just `.get`."""

    def __init__(self, answers):
        self.answers = dict(answers)

    def get(self, key, default=None):
        return self.answers.get(key, default)


class TestMoneyParsing(unittest.TestCase):
    def test_common_money_formats(self):
        cases = {
            "R 1,200,000": 1_200_000,
            "$1.2m": 1_200_000,
            "ZAR 500k": 500_000,
            "R 9.6 billion — CMS 2025 report": 9_600_000_000,
            "1 200 000": 1_200_000,
            "R4.8m revenue": 4_800_000,
            "5,200,000": 5_200_000,
        }
        for text, expected in cases.items():
            self.assertEqual(compiler.parse_money(text), expected, text)

    def test_currency_marked_figure_beats_a_bare_count(self):
        # "120 clinics" must not be mistaken for the revenue figure.
        self.assertEqual(
            compiler.parse_money("120 paying clinics and R 5m revenue"), 5_000_000
        )

    def test_lone_bare_number_is_accepted(self):
        self.assertEqual(compiler.parse_money("120 clinics"), 120)

    def test_two_bare_numbers_are_ambiguous_narrative(self):
        self.assertIsNone(compiler.parse_money("120 clinics in 3 provinces"))

    def test_percent_is_not_money(self):
        self.assertIsNone(compiler.parse_money("12%"))

    def test_prose_is_not_money(self):
        self.assertIsNone(compiler.parse_money("strong growth expected"))
        self.assertIsNone(compiler.parse_money(""))
        self.assertIsNone(compiler.parse_money(None))

    def test_percent_parsing(self):
        self.assertEqual(compiler.parse_percent("12%"), 12)
        self.assertEqual(compiler.parse_percent("78% blended (subs 85%)"), 78)
        self.assertEqual(compiler.parse_percent("2.5 percent"), 2.5)
        self.assertIsNone(compiler.parse_percent("high"))
        self.assertIsNone(compiler.parse_percent(None))

    def test_period_detection(self):
        self.assertEqual(compiler.detect_period("R 3,500 per month"), "monthly")
        self.assertEqual(compiler.detect_period("2% monthly churn"), "monthly")
        self.assertEqual(compiler.detect_period("R 42,000 per annum"), "annual")
        self.assertEqual(compiler.detect_period("R 42,000 / yr"), "annual")
        self.assertIsNone(compiler.detect_period("R 42,000"))

    def test_money_formatting(self):
        self.assertEqual(compiler.format_money(4_800_000, "R"), "R4.8m")
        self.assertEqual(compiler.format_money(9_600_000_000, "R"), "R9.6bn")
        self.assertEqual(compiler.format_money(650_000, "R"), "R650,000")


class TestComputedFinancials(unittest.TestCase):
    FULL = {
        "projected_year_1": "R 4,800,000 revenue | 120 paying clinics",
        "projected_year_2": "R 12,500,000 revenue | 300 clinics",
        "projected_year_3": "R 26,000,000 revenue | 600 clinics",
        "gross_margin_target": "78% blended",
        "average_revenue_per_customer": "R 3,500 per clinic per month",
        "customer_acquisition_cost": "R 14,000 per clinic",
        "customer_churn_rate": "2% monthly",
        "customer_count_year_1": "120 clinics",
        "monthly_operating_costs": "R 650,000 per month",
        "cash_on_hand": "R 5,200,000",
    }

    def _values(self, answers):
        values = {"currency_symbol": "R"}
        compiler._add_computed_financials(
            values, FakeProfile(answers), jurisdictions.get("ZA")
        )
        return values

    def test_projection_table_computes_growth_and_gross_profit(self):
        table = self._values(self.FULL)["fin_projection_table"]
        self.assertIn("| Year 1 | R4.8m | — |", table)
        self.assertIn("+160%", table)  # 4.8m -> 12.5m
        self.assertIn("+108%", table)  # 12.5m -> 26m
        self.assertIn("78% target margin", table)
        self.assertIn("Projected Year 1", table)  # traceability

    def test_unit_economics_are_derived_not_to_be_supplied(self):
        table = self._values(self.FULL)["fin_unit_economics"]
        self.assertNotIn("_to be supplied_", table)
        self.assertIn("8 months", table)  # runway: 5.2m / 650k
        self.assertIn("5.1 months", table)  # payback: 14000 / (3500*0.78)
        self.assertIn("R136,500", table)  # LTV: 3500*0.78/0.02
        self.assertIn("9.8x", table)  # LTV:CAC
        self.assertIn("computed from cash on hand", table)

    def test_consistent_year1_revenue_is_reported_consistent(self):
        checks = self._values(self.FULL)["fin_consistency"]
        # 120 × R3,500 × 12 = R5.04m vs R4.8m stated — within tolerance.
        self.assertIn("Consistent", checks)

    def test_inconsistent_year1_revenue_is_flagged(self):
        answers = dict(self.FULL, projected_year_1="R 40,000,000 revenue")
        checks = self._values(answers)["fin_consistency"]
        self.assertIn("Check", checks)

    def test_implausible_growth_is_a_note_not_an_error(self):
        answers = dict(self.FULL, projected_year_2="R 96,000,000")
        checks = self._values(answers)["fin_consistency"]
        self.assertIn("above 10×", checks)

    def test_missing_inputs_fall_back_to_coaching_never_invented(self):
        values = self._values({})
        self.assertEqual(values["fin_projection_table"], "")
        table = values["fin_unit_economics"]
        self.assertNotIn("_to be supplied_", table)
        self.assertIn("Pending — answer **Average Revenue Per Customer**", table)
        self.assertIn("Not derivable yet", table)
        # No digits invented for any metric value.
        self.assertNotIn("months |", table.replace("Not derivable", ""))

    def test_arpc_without_a_period_does_not_unlock_payback(self):
        answers = dict(self.FULL, average_revenue_per_customer="R 3,500")
        table = self._values(answers)["fin_unit_economics"]
        self.assertIn("period not stated", table)
        self.assertIn("Not derivable yet", table)

    def test_narrative_projections_yield_no_table(self):
        answers = {"projected_year_1": "Strong growth across two provinces"}
        # "two provinces" carries no figure — nothing must be invented.
        self.assertEqual(self._values(answers)["fin_projection_table"], "")


class TestMarketAnalysisComputation(unittest.TestCase):
    SIZING = {
        "market_size_tam": "R 9.6 billion — CMS 2025 report",
        "market_size_sam": "R 1.9 billion — 8,000 small practices",
        "market_size_som": "R 190 million — 10% of SAM in 36 months",
    }

    def _values(self, answers):
        values = {"currency_symbol": "R"}
        compiler._add_market_analysis(values, FakeProfile(answers))
        return values

    def test_funnel_shows_layer_shares(self):
        table = self._values(self.SIZING)["market_funnel_table"]
        self.assertIn("19.8% of TAM", table)
        self.assertIn("10.0% of SAM", table)
        self.assertIn("R9.6bn", table)

    def test_som_larger_than_sam_is_flagged(self):
        answers = dict(self.SIZING, market_size_som="R 2.5 billion")
        flags = self._values(answers)["market_sizing_flags"]
        self.assertIn("SOM exceeds SAM", flags)

    def test_sam_larger_than_tam_is_flagged(self):
        answers = dict(self.SIZING, market_size_sam="R 12 billion")
        flags = self._values(answers)["market_sizing_flags"]
        self.assertIn("SAM exceeds TAM", flags)

    def test_coherent_funnel_has_no_flags(self):
        self.assertEqual(self._values(self.SIZING)["market_sizing_flags"], "")

    def test_narrative_sizing_yields_no_funnel(self):
        values = self._values({"market_size_tam": "Large and growing"})
        self.assertEqual(values["market_funnel_table"], "")
        self.assertEqual(values["market_sizing_flags"], "")

    def test_competitor_table_from_one_line_per_competitor(self):
        answers = {
            "competitive_positioning": "Acme: strong brand, weak product. "
            "Beta: cheap but desktop-only."
        }
        table = self._values(answers)["competitor_table"]
        self.assertIn("| Acme | strong brand, weak product. |", table)
        self.assertIn("| Beta | cheap but desktop-only. |", table)

    def test_competitor_table_falls_back_to_named_competitors(self):
        answers = {"key_competitors": "Acme, Beta and paper records"}
        table = self._values(answers)["competitor_table"]
        self.assertIn("| Acme |", table)
        self.assertIn("Pending — answer **Competitive Positioning**", table)


# --------------------------------------------------------------------------
# Canvas fallbacks — CONFIRMED: the Business Model Canvas reused
# `growth_strategy` for both Channels and Customer Relationships, and the
# Lean Canvas filled "Problem" from `key_operational_risks`.
# --------------------------------------------------------------------------


class TestCanvasFallbacks(unittest.TestCase):
    TEMPLATES = os.path.join(
        os.path.dirname(_ENGINE_DIR),
        os.pardir,
        "skills",
        ".rok",
        "startup_os",
        "templates",
        "business",
    )

    def _render(self, template_name, values):
        path = os.path.join(self.TEMPLATES, template_name)
        if not os.path.isfile(path):
            self.skipTest(f"template not present: {template_name}")
        with open(path, encoding="utf-8") as handle:
            body = handle.read()
        entry = jurisdictions.get("ZA")
        context = template_engine.RenderContext(values, entry, entry.features)
        text, _warnings = template_engine.render(body, context)
        return text

    BASE = {
        "company_name": "Acme",
        "key_suppliers": "SupplierCo",
        "primary_products": "The Product",
        "core_value_proposition": "Value",
        "customer_segments": "Clinics",
        "growth_strategy": "REFERRAL-LOOP",
        "personnel_count": "5",
        "unfair_advantage": "Moat",
    }

    def test_bmc_dedicated_answers_fill_their_own_boxes(self):
        values = dict(
            self.BASE,
            sales_channels="BUREAU-CHANNEL",
            customer_relationships="QUARTERLY-REVIEWS",
            revenue_streams="SUBSCRIPTIONS",
        )
        text = self._render("09_business_model_canvas.md", values)
        self.assertIn("BUREAU-CHANNEL", text)
        self.assertIn("QUARTERLY-REVIEWS", text)
        self.assertIn("SUBSCRIPTIONS", text)

    def test_bmc_old_profile_falls_back_to_growth_strategy(self):
        # A questions.md written before these questions existed must still
        # compile with sensible content in every box.
        text = self._render("09_business_model_canvas.md", dict(self.BASE))
        self.assertIn("REFERRAL-LOOP", text)
        self.assertNotIn("«", text.split("## 2. Block Breakdown")[0])

    def test_lean_canvas_problem_uses_problem_statement(self):
        values = dict(
            self.BASE,
            problem_statement="CUSTOMER-PAIN",
            key_operational_risks="SERVER-OUTAGES",
        )
        text = self._render("10_lean_canvas.md", values)
        problem_section = text.split("### B. The Solution")[0]
        self.assertIn("CUSTOMER-PAIN", problem_section)
        self.assertNotIn("SERVER-OUTAGES", problem_section)

    def test_lean_canvas_without_problem_coaches_instead_of_risks(self):
        values = dict(self.BASE, key_operational_risks="SERVER-OUTAGES")
        text = self._render("10_lean_canvas.md", values)
        problem_section = text.split("### B. The Solution")[0]
        self.assertNotIn("SERVER-OUTAGES", problem_section)
        self.assertIn("Problem Statement", problem_section)


# --------------------------------------------------------------------------
# End-to-end backwards compatibility — an old questions.md with none of the
# new answers must compile cleanly, with coaching instead of blanks.
# --------------------------------------------------------------------------


class TestOldProfileStillCompiles(unittest.TestCase):
    def test_core_tier_profile_compiles_without_to_be_supplied(self):
        template_src = os.path.join(
            os.path.dirname(_ENGINE_DIR),
            os.pardir,
            "skills",
            ".rok",
            "startup_os",
            "templates",
        )
        if not os.path.isdir(template_src):
            self.skipTest("templates not present")
        import shutil

        with TempWorkspace() as root:
            shutil.copytree(template_src, os.path.join(root, "templates"))
            write(
                os.path.join(root, "instances", "business", "Acme", "questions.md"),
                schemas.render_questions_md(
                    "business",
                    "Acme",
                    {
                        "trading_name": "Acme",
                        "jurisdiction": "ZA",
                        "primary_base": "Cape Town, South Africa",
                        "industry": "Retail",
                        "vision_statement": "A store on every corner.",
                        "core_value_proposition": "Fast delivery.",
                        "primary_products": "Groceries",
                        "customer_segments": "Households",
                        "growth_strategy": "Word of mouth",
                    },
                ),
            )
            result = compiler.compile_instance(
                "business", "Acme", workspace_root=root, quiet=True
            )
            self.assertTrue(result.ok)
            out = os.path.join(root, "instances", "business", "Acme", "output")
            with open(
                os.path.join(out, "07_financial_model.md"), encoding="utf-8"
            ) as handle:
                financial = handle.read()
            self.assertNotIn("_to be supplied_", financial)
            self.assertNotIn("«", financial)
            self.assertIn("Pending — answer", financial)
            for name in ("09_business_model_canvas.md", "10_lean_canvas.md"):
                with open(os.path.join(out, name), encoding="utf-8") as handle:
                    self.assertNotIn("«", handle.read(), name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
