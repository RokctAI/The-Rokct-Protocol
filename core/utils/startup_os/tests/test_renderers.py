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

"""Tests for the binary renderers (.pptx pitch deck, .xlsx financial model).

The invariants under test are the ones a hand-rolled OOXML writer can break
silently: a part the [Content_Types].xml does not declare, a malformed XML
fragment Office refuses to open, a cached formula value that drifts from the
compiler's arithmetic, a fake number in a cell whose question was never
answered, and a byte-differing rebuild that makes artifact diffs meaningless.

Run:  python -m pytest core/utils/startup_os/tests -q
  or: python core/utils/startup_os/tests/test_renderers.py
"""

import importlib.util
import io
import os
import shutil
import sys
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET

_ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _load_engine():
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

from core import compiler, render_pptx, render_xlsx, schemas  # noqa: E402


class TempWorkspace:
    def __enter__(self):
        self.dir = tempfile.mkdtemp(prefix="startupos-render-test-")
        return self.dir

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)
        return False


def write(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


FULL_ANSWERS = {
    "trading_name": "Acme Clinics",
    "jurisdiction": "ZA",
    "primary_base": "Cape Town, South Africa",
    "industry": "Healthcare software",
    "vision_statement": "Every clinic on one platform.",
    "core_value_proposition": "One platform replacing three tools.",
    "problem_statement": "Clinics lose 10% of revenue to rejected claims.",
    "revenue_streams": "SaaS subscriptions and per-clinic licences.",
    "achievements_to_date": "120 paying clinics. 94% claim acceptance.",
    "executive_team": "A Person — CEO: capital. B Person — CTO: platform.",
    "funding_requirement": "R 18,000,000 seed round.",
    "market_size_tam": "R 9.6 billion",
    "market_size_sam": "R 1.9 billion",
    "market_size_som": "R 190 million",
    "competitive_positioning": "Acme: strong brand, weak product. Beta: desktop-only.",
    "acquisition_channels": "Bureau partnerships and webinars.",
    "projected_year_1": "R 4,800,000 revenue",
    "projected_year_2": "R 12,500,000 revenue",
    "projected_year_3": "R 26,000,000 revenue",
    "gross_margin_target": "78% blended",
    "average_revenue_per_customer": "R 3,500 per clinic per month",
    "customer_acquisition_cost": "R 14,000 per clinic",
    "customer_churn_rate": "2% monthly",
    "customer_count_year_1": "120 clinics",
    "monthly_operating_costs": "R 650,000 per month",
    "cash_on_hand": "R 5,200,000",
}

MINIMAL_ANSWERS = {
    "trading_name": "Bare",
    "jurisdiction": "ZA",
    "primary_base": "Cape Town, South Africa",
}


def _instance_data(answers, name="Acme"):
    with TempWorkspace() as root:
        write(
            os.path.join(root, "instances", "business", name, "questions.md"),
            schemas.render_questions_md("business", name, answers, include_full=True),
        )
        return compiler.load_instance_data(
            "business", name, workspace_root=root, quiet=True
        )


def _parts(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        return {name: archive.read(name) for name in archive.namelist()}


def _declared_parts(parts):
    """Part names covered by [Content_Types].xml, via Default or Override."""
    ns = "{http://schemas.openxmlformats.org/package/2006/content-types}"
    tree = ET.fromstring(parts["[Content_Types].xml"])
    defaults = {node.get("Extension").lower() for node in tree.findall(f"{ns}Default")}
    overrides = {node.get("PartName") for node in tree.findall(f"{ns}Override")}
    covered = set()
    for name in parts:
        if name == "[Content_Types].xml":
            covered.add(name)
        elif f"/{name}" in overrides:
            covered.add(name)
        elif name.rsplit(".", 1)[-1].lower() in defaults:
            covered.add(name)
    return covered


# --------------------------------------------------------------------------
# Pitch deck (.pptx)
# --------------------------------------------------------------------------


class TestPitchDeckPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = _instance_data(FULL_ANSWERS)
        cls.blob = render_pptx.build_pptx_bytes(cls.data)
        cls.parts = _parts(cls.blob)

    def test_every_part_is_well_formed_xml(self):
        for name, payload in self.parts.items():
            ET.fromstring(payload)  # raises on malformed XML

    def test_required_parts_exist(self):
        required = [
            "[Content_Types].xml",
            "_rels/.rels",
            "ppt/presentation.xml",
            "ppt/_rels/presentation.xml.rels",
            "ppt/slideMasters/slideMaster1.xml",
            "ppt/slideMasters/_rels/slideMaster1.xml.rels",
            "ppt/slideLayouts/slideLayout1.xml",
            "ppt/theme/theme1.xml",
        ] + [f"ppt/slides/slide{n}.xml" for n in range(1, render_pptx.SLIDE_COUNT + 1)]
        for name in required:
            self.assertIn(name, self.parts)

    def test_content_types_declares_every_part(self):
        # An undeclared part is the classic hand-rolled-OOXML failure:
        # the zip is fine, every XML is fine, and PowerPoint still refuses
        # the file. Every member must be covered by a Default or Override.
        self.assertEqual(_declared_parts(self.parts), set(self.parts))

    def test_deck_has_twelve_slides_in_order(self):
        ns = "{http://schemas.openxmlformats.org/presentationml/2006/main}"
        tree = ET.fromstring(self.parts["ppt/presentation.xml"])
        slide_ids = tree.findall(f"{ns}sldIdLst/{ns}sldId")
        self.assertEqual(len(slide_ids), render_pptx.SLIDE_COUNT)

    def test_each_slide_references_the_layout(self):
        for n in range(1, render_pptx.SLIDE_COUNT + 1):
            rels = self.parts[f"ppt/slides/_rels/slide{n}.xml.rels"].decode("utf-8")
            self.assertIn("slideLayout1.xml", rels, f"slide{n}")

    def test_title_slide_carries_the_company_name(self):
        self.assertIn(
            "Acme Clinics", self.parts["ppt/slides/slide1.xml"].decode("utf-8")
        )

    def test_financials_slide_shows_compiler_figures(self):
        slide = self.parts["ppt/slides/slide9.xml"].decode("utf-8")
        self.assertIn("R4.8m", slide)  # projection table
        self.assertIn("+160%", slide)  # YoY growth from the compiler
        self.assertIn("5.1 months", slide)  # CAC payback
        self.assertIn("R136,500", slide)  # LTV

    def test_market_slide_has_the_funnel_table(self):
        slide = self.parts["ppt/slides/slide4.xml"].decode("utf-8")
        self.assertIn("graphicFrame", slide)
        self.assertIn("19.8% of TAM", slide)
        self.assertIn("10.0% of SAM", slide)

    def test_output_is_deterministic(self):
        self.assertEqual(self.blob, render_pptx.build_pptx_bytes(self.data))

    def test_no_timestamp_bearing_parts(self):
        # docProps/core.xml carries dcterms:created/modified; its absence is
        # what keeps rebuilds byte-identical.
        for name in self.parts:
            self.assertFalse(name.startswith("docProps/"), name)


class TestPitchDeckHonesty(unittest.TestCase):
    def test_empty_profile_gets_coaching_not_numbers(self):
        data = _instance_data(MINIMAL_ANSWERS, name="Bare")
        parts = _parts(render_pptx.build_pptx_bytes(data))
        traction = parts["ppt/slides/slide6.xml"].decode("utf-8")
        self.assertIn(render_pptx.COACH_TRACTION, traction)
        competition = parts["ppt/slides/slide7.xml"].decode("utf-8")
        self.assertIn(render_pptx.COACH_COMPETITION, competition)
        financials = parts["ppt/slides/slide9.xml"].decode("utf-8")
        self.assertIn("not derivable yet", financials)
        self.assertNotIn("graphicFrame", financials)  # no invented table


# --------------------------------------------------------------------------
# Financial model (.xlsx)
# --------------------------------------------------------------------------


def _cells(sheet_xml):
    """`ref -> (formula, value, inline_text)` for one worksheet part."""
    ns = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
    result = {}
    for cell in ET.fromstring(sheet_xml).iter(f"{ns}c"):
        formula = cell.find(f"{ns}f")
        value = cell.find(f"{ns}v")
        text = cell.find(f"{ns}is/{ns}t")
        result[cell.get("r")] = (
            formula.text if formula is not None else None,
            value.text if value is not None else None,
            text.text if text is not None else None,
        )
    return result


class TestFinancialModelPackage(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = _instance_data(FULL_ANSWERS)
        cls.blob = render_xlsx.build_xlsx_bytes(cls.data)
        cls.parts = _parts(cls.blob)
        cls.fin = compiler.extract_financial_inputs(cls.data.profile)
        cls.metrics = compiler.derive_financial_metrics(cls.fin)

    def test_every_part_is_well_formed_xml(self):
        for name, payload in self.parts.items():
            ET.fromstring(payload)

    def test_required_parts_and_content_type_coverage(self):
        for name in (
            "[Content_Types].xml",
            "_rels/.rels",
            "xl/workbook.xml",
            "xl/_rels/workbook.xml.rels",
            "xl/styles.xml",
            "xl/worksheets/sheet1.xml",
            "xl/worksheets/sheet2.xml",
            "xl/worksheets/sheet3.xml",
        ):
            self.assertIn(name, self.parts)
        self.assertEqual(_declared_parts(self.parts), set(self.parts))

    def test_workbook_names_the_three_sheets(self):
        workbook = self.parts["xl/workbook.xml"].decode("utf-8")
        for name in render_xlsx.SHEET_NAMES:
            self.assertIn(f'name="{name}"', workbook)

    def test_assumption_cells_hold_the_parsed_inputs(self):
        cells = _cells(self.parts["xl/worksheets/sheet1.xml"])
        expected = {
            "B2": self.fin["arpc_monthly"],
            "B3": self.fin["margin_pct"] / 100.0,
            "B4": self.fin["cac"],
            "B6": self.fin["burn"],
            "B7": self.fin["cash"],
            "B9": self.fin["revenue"][0],
        }
        for ref, value in expected.items():
            self.assertAlmostEqual(float(cells[ref][1]), value, places=6, msg=ref)

    def test_projection_formulas_reference_assumptions(self):
        cells = _cells(self.parts["xl/worksheets/sheet2.xml"])
        self.assertEqual(cells["B2"][0], "Assumptions!B9")
        self.assertEqual(cells["C3"][0], "C2/B2-1")
        self.assertEqual(cells["B4"][0], "B2*Assumptions!B3")
        self.assertEqual(cells["B5"][0], "Assumptions!B6*12")

    def test_unit_economics_formulas_are_exact(self):
        cells = _cells(self.parts["xl/worksheets/sheet3.xml"])
        self.assertEqual(cells["B2"][0], "Assumptions!B2*12")
        self.assertEqual(
            cells["B3"][0], "Assumptions!B4/(Assumptions!B2*Assumptions!B3)"
        )
        self.assertEqual(cells["B4"][0], "Assumptions!B2*Assumptions!B3/Assumptions!B5")
        self.assertEqual(cells["B5"][0], "B4/Assumptions!B4")
        self.assertEqual(cells["B6"][0], "Assumptions!B7/Assumptions!B6")

    def test_cached_values_match_the_compilers_arithmetic(self):
        cells = _cells(self.parts["xl/worksheets/sheet3.xml"])
        expected = {
            "B2": self.metrics["arpc_annual"],
            "B3": self.metrics["cac_payback_months"],
            "B4": self.metrics["ltv"],
            "B5": self.metrics["ltv_cac"],
            "B6": self.metrics["runway_months"],
        }
        for ref, value in expected.items():
            self.assertAlmostEqual(float(cells[ref][1]), value, places=6, msg=ref)

    def test_growth_cached_values_match(self):
        cells = _cells(self.parts["xl/worksheets/sheet2.xml"])
        self.assertAlmostEqual(
            float(cells["C3"][1]), self.metrics["growth"][1], places=6
        )
        self.assertAlmostEqual(
            float(cells["D3"][1]), self.metrics["growth"][2], places=6
        )

    def test_output_is_deterministic(self):
        self.assertEqual(self.blob, render_xlsx.build_xlsx_bytes(self.data))


class TestFinancialModelHonesty(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.data = _instance_data(MINIMAL_ANSWERS, name="Bare")
        cls.parts = _parts(render_xlsx.build_xlsx_bytes(cls.data))

    def test_missing_inputs_are_coaching_text_never_numbers(self):
        cells = _cells(self.parts["xl/worksheets/sheet1.xml"])
        for ref in render_xlsx.ASSUMPTION_CELLS.values():
            formula, value, text = cells[ref]
            self.assertIsNone(formula, ref)
            self.assertIsNone(value, ref)
            self.assertIn("Pending — answer", text, ref)

    def test_dependent_cells_degrade_without_formulas(self):
        cells = _cells(self.parts["xl/worksheets/sheet3.xml"])
        for ref in ("B2", "B3", "B4", "B5", "B6"):
            formula, value, text = cells[ref]
            self.assertIsNone(formula, ref)
            self.assertIsNone(value, ref)
            self.assertTrue(text, ref)

    def test_arpc_without_period_stays_locked(self):
        answers = dict(MINIMAL_ANSWERS, average_revenue_per_customer="R 3,500")
        data = _instance_data(answers, name="Bare2")
        cells = _cells(
            _parts(render_xlsx.build_xlsx_bytes(data))["xl/worksheets/sheet1.xml"]
        )
        formula, value, text = cells["B2"]
        self.assertIsNone(value)
        self.assertIn("no period", text)


# --------------------------------------------------------------------------
# Compile integration — rendered artifacts survive pruning, and only when
# rendered this run: a stale binary that no longer matches the markdown is
# exactly what the prune step exists to remove.
# --------------------------------------------------------------------------


class TestCompileRenderIntegration(unittest.TestCase):
    def _workspace(self, root):
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
        shutil.copytree(template_src, os.path.join(root, "templates"))
        write(
            os.path.join(root, "instances", "business", "Acme", "questions.md"),
            schemas.render_questions_md(
                "business", "Acme", FULL_ANSWERS, include_full=True
            ),
        )

    def test_compile_with_render_writes_and_keeps_both_artifacts(self):
        with TempWorkspace() as root:
            self._workspace(root)
            result = compiler.compile_instance(
                "business", "Acme", workspace_root=root, quiet=True, render=True
            )
            self.assertIn(render_pptx.PITCH_DECK_FILENAME, result.written)
            self.assertIn(render_xlsx.FINANCIAL_MODEL_FILENAME, result.written)
            out = os.path.join(root, "instances", "business", "Acme", "output")
            for filename in (
                render_pptx.PITCH_DECK_FILENAME,
                render_xlsx.FINANCIAL_MODEL_FILENAME,
            ):
                self.assertTrue(os.path.exists(os.path.join(out, filename)))

            # A recompile without --render prunes the now-unrefreshed binaries.
            result = compiler.compile_instance(
                "business", "Acme", workspace_root=root, quiet=True
            )
            self.assertIn(render_pptx.PITCH_DECK_FILENAME, result.removed)
            self.assertIn(render_xlsx.FINANCIAL_MODEL_FILENAME, result.removed)


if __name__ == "__main__":
    unittest.main(verbosity=2)
