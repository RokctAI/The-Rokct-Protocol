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

"""Tests for the brand layer (`core.branding`) and the branded deck.

The fixtures under `fixtures/` are *verbatim* copies of real designer
system files: `designer_supacharge.yaml` is the hand-written
`designer/systems/supacharge.yaml` (comments, inline flow maps, quoted
hex), `designer_palette_output.yaml` is the file the `designer palette`
CLI actually wrote (PyYAML block style, dashes at the key's own indent,
floats). The minimal parser must read both — the invariant is "handles
what designer really emits", not "handles YAML".

Run:  python -m pytest core/utils/startup_os/tests -q
"""

import importlib.util
import io
import json
import os
import shutil
import struct
import sys
import tempfile
import unittest
import zipfile
import zlib
import xml.etree.ElementTree as ET

_ENGINE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_FIXTURES = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fixtures")


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

from core import branding, compiler, render_pptx, schemas  # noqa: E402
from core.errors import BrandingError  # noqa: E402


def _fixture(name):
    with open(os.path.join(_FIXTURES, name), "r", encoding="utf-8") as handle:
        return handle.read()


def make_png(width, height, rgb=(31, 111, 84)):
    """A real, minimal PNG built with stdlib only — no invented branding."""

    def chunk(tag, payload):
        body = tag + payload
        return (
            struct.pack(">I", len(payload)) + body + struct.pack(">I", zlib.crc32(body))
        )

    header = struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    raw = b"".join(b"\x00" + bytes(rgb) * width for _ in range(height))
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


class TempWorkspace:
    def __enter__(self):
        self.dir = tempfile.mkdtemp(prefix="startupos-brand-test-")
        return self.dir

    def __exit__(self, *exc):
        shutil.rmtree(self.dir, ignore_errors=True)
        return False


def write_text(path, content):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write(content)
    return path


def write_bytes(path, blob):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as handle:
        handle.write(blob)
    return path


ANSWERS = {
    "trading_name": "Acme Clinics",
    "jurisdiction": "ZA",
    "primary_base": "Cape Town, South Africa",
    "industry": "Healthcare software",
    "vision_statement": "Every clinic on one platform.",
    "core_value_proposition": "One platform replacing three tools.",
    "problem_statement": "Clinics lose 10% of revenue to rejected claims.",
    "brand_positioning": "The claims platform clinics trust.",
    "product_components": "Claims engine.\nBilling console.",
    "pricing_tiers": "Starter at R 900 per month. Pro at R 2,400 per month.",
    "acquisition_channels": "Bureau partnerships and webinars.",
    "achievements_to_date": "120 paying clinics. 94% claim acceptance.",
}


def _make_instance(root, name="Acme", answers=ANSWERS):
    write_text(
        os.path.join(root, "instances", "business", name, "questions.md"),
        schemas.render_questions_md("business", name, answers, include_full=True),
    )
    return os.path.join(root, "instances", "business", name)


def _write_brand(instance_dir, system_text=None, logo=True, cover=True, slide4=False):
    brand_dir = os.path.join(instance_dir, "brand")
    if system_text is not None:
        write_text(os.path.join(brand_dir, "system.yaml"), system_text)
    if logo:
        write_bytes(os.path.join(brand_dir, "logo.png"), make_png(8, 4))
    if cover:
        write_bytes(
            os.path.join(brand_dir, "images", "cover.png"),
            make_png(16, 9, (233, 243, 238)),
        )
    if slide4:
        write_bytes(
            os.path.join(brand_dir, "images", "slide04.png"),
            make_png(16, 9, (224, 166, 60)),
        )
    return brand_dir


def _load(root, name="Acme"):
    return compiler.load_instance_data(
        "business", name, workspace_root=root, quiet=True
    )


def _parts(blob):
    with zipfile.ZipFile(io.BytesIO(blob)) as archive:
        return {part: archive.read(part) for part in archive.namelist()}


def _declared_parts(parts):
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
# Minimal YAML parser against designer's real files
# --------------------------------------------------------------------------


class TestMinimalYamlParser(unittest.TestCase):
    def test_hand_written_designer_file(self):
        # supacharge.yaml: comments everywhere, inline flow maps, quoted hex.
        data = branding.parse_minimal_yaml(_fixture("designer_supacharge.yaml"))
        self.assertEqual(data["name"], "Supacharge (Option A — dark)")
        tokens = data["color"]["tokens"]
        self.assertEqual(tokens["bg"], {"hex": "#0b0b0b", "role": "surface"})
        self.assertEqual(tokens["accent"], {"hex": "#e0793c", "role": "accent"})
        self.assertEqual(tokens["accent-ink"], {"hex": "#2a1204", "role": "ink"})
        self.assertEqual(data["color"]["max_colors"], 6)
        self.assertIs(data["gradient"]["allowed"], False)
        self.assertEqual(
            data["typography"]["fonts"],
            ["Inter", "-apple-system", "Segoe UI", "Roboto", "sans-serif"],
        )
        self.assertEqual(data["print"]["bleed"], 35)
        self.assertEqual(data["accessibility"]["min_contrast_text"], 4.5)

    def test_palette_cli_output(self):
        # The file `designer palette` wrote: PyYAML block style, dashes at
        # the key's own indent, single-quoted hex, floats and booleans.
        data = branding.parse_minimal_yaml(_fixture("designer_palette_output.yaml"))
        self.assertEqual(data["name"], "KarooFlow (fictional demo)")
        tokens = data["color"]["tokens"]
        self.assertEqual(tokens["primary"], {"hex": "#1f6f54", "role": "primary"})
        self.assertEqual(tokens["neutral-100"], {"hex": "#d5ebe1", "role": "other"})
        self.assertEqual(data["typography"]["fonts"], ["Inter", "sans-serif"])
        self.assertEqual(data["typography"]["scale"], [12, 14, 16, 20, 24, 32, 48, 64])
        self.assertEqual(data["layout"]["grid"], 8.0)
        self.assertIs(data["layout"]["role_aware_snapping"], True)
        self.assertEqual(data["print"]["bleed"], 35.4)

    def test_system_from_real_files_orders_tokens(self):
        system = branding.system_from_mapping(
            branding.parse_minimal_yaml(_fixture("designer_supacharge.yaml")), "x.yaml"
        )
        self.assertEqual(system.by_role("surface")[0].hex, "#0b0b0b")  # file order
        self.assertEqual(system.first_hex("accent", "primary").hex, "#e0793c")
        self.assertEqual(system.deck_font("Calibri"), "Inter")

    def test_json_system_accepted(self):
        with TempWorkspace() as root:
            path = write_text(
                os.path.join(root, "system.json"),
                json.dumps({"name": "J", "color": {"tokens": {"ink": "#111827"}}}),
            )
            system = branding.load_system_file(path)
        self.assertEqual(system.token("ink").hex, "#111827")

    def test_unsupported_yaml_is_a_named_error(self):
        with self.assertRaises(BrandingError) as caught:
            branding.parse_minimal_yaml("color:\n  - {broken\n", "bad.yaml")
        self.assertIn("bad.yaml", str(caught.exception))

    def test_malformed_hex_names_the_file(self):
        mapping = {"color": {"tokens": {"accent": "#notahex"}}}
        with self.assertRaises(BrandingError) as caught:
            branding.system_from_mapping(mapping, "brand/system.yaml")
        self.assertIn("brand/system.yaml", str(caught.exception))
        self.assertIn("accent", str(caught.exception))

    def test_missing_tokens_names_the_file(self):
        with self.assertRaises(BrandingError) as caught:
            branding.system_from_mapping({"name": "empty"}, "brand/system.yaml")
        self.assertIn("color.tokens", str(caught.exception))


# --------------------------------------------------------------------------
# brand/ folder loading
# --------------------------------------------------------------------------


class TestBrandLoading(unittest.TestCase):
    def test_missing_brand_folder_is_coaching_not_error(self):
        with TempWorkspace() as root:
            _make_instance(root)
            data = _load(root)
        self.assertIsNone(data.brand)
        self.assertTrue(
            any("designer palette" in warning for warning in data.warnings),
            data.warnings,
        )

    def test_full_brand_folder_loads(self):
        with TempWorkspace() as root:
            instance = _make_instance(root)
            _write_brand(
                instance, _fixture("designer_palette_output.yaml"), slide4=True
            )
            data = _load(root)
        self.assertIsNotNone(data.brand)
        self.assertEqual(data.brand.system.name, "KarooFlow (fictional demo)")
        self.assertIsNotNone(data.brand.logo)
        self.assertEqual((data.brand.logo.width, data.brand.logo.height), (8, 4))
        self.assertIsNotNone(data.brand.cover_image)
        self.assertIn(4, data.brand.slide_images)
        self.assertFalse(any("designer palette" in w for w in data.warnings))

    def test_malformed_system_file_is_a_clear_error(self):
        with TempWorkspace() as root:
            instance = _make_instance(root)
            _write_brand(instance, "color: [unclosed\n", logo=False, cover=False)
            with self.assertRaises(BrandingError) as caught:
                _load(root)
        self.assertIn("system.yaml", str(caught.exception))

    def test_svg_only_logo_is_coached_not_embedded(self):
        with TempWorkspace() as root:
            instance = _make_instance(root)
            _write_brand(
                instance,
                _fixture("designer_palette_output.yaml"),
                logo=False,
                cover=False,
            )
            write_text(os.path.join(instance, "brand", "logo.svg"), "<svg></svg>")
            data = _load(root)
        self.assertIsNone(data.brand.logo)
        self.assertTrue(any("logo.svg" in w for w in data.warnings))
        parts = _parts(render_pptx.build_pptx_bytes(data))
        self.assertFalse(any(name.startswith("ppt/media/") for name in parts))

    def test_non_image_logo_bytes_are_refused(self):
        with TempWorkspace() as root:
            instance = _make_instance(root)
            _write_brand(
                instance,
                _fixture("designer_palette_output.yaml"),
                logo=False,
                cover=False,
            )
            write_bytes(os.path.join(instance, "brand", "logo.png"), b"not a png")
            with self.assertRaises(BrandingError) as caught:
                _load(root)
        self.assertIn("logo.png", str(caught.exception))


# --------------------------------------------------------------------------
# Branded vs unbranded deck
# --------------------------------------------------------------------------


class TestBrandedDeck(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workspace = tempfile.mkdtemp(prefix="startupos-brand-deck-")
        instance = _make_instance(cls.workspace)
        _write_brand(instance, _fixture("designer_palette_output.yaml"), slide4=True)
        cls.data = _load(cls.workspace)
        cls.blob = render_pptx.build_pptx_bytes(cls.data)
        cls.parts = _parts(cls.blob)

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def test_every_part_is_well_formed_xml(self):
        for name, payload in self.parts.items():
            if name.endswith(".xml") or name.endswith(".rels"):
                ET.fromstring(payload)

    def test_content_types_declares_every_part_including_media(self):
        self.assertEqual(_declared_parts(self.parts), set(self.parts))

    def test_brand_colors_reach_the_slide_xml(self):
        slide = self.parts["ppt/slides/slide2.xml"].decode("utf-8")
        self.assertIn("E0A63C", slide)  # accent -> bar + bullets
        self.assertIn("10241C", slide)  # ink -> titles
        master = self.parts["ppt/slideMasters/slideMaster1.xml"].decode("utf-8")
        self.assertIn("E9F3EE", master)  # first surface -> background
        self.assertNotIn("1F4E79", slide)  # the default accent is gone

    def test_brand_font_reaches_runs_and_theme(self):
        self.assertIn(
            'typeface="Inter"', self.parts["ppt/slides/slide1.xml"].decode("utf-8")
        )
        self.assertIn(
            'typeface="Inter"', self.parts["ppt/theme/theme1.xml"].decode("utf-8")
        )

    def test_logo_part_embedded_and_referenced_on_every_slide(self):
        self.assertIn("ppt/media/image1.png", self.parts)
        self.assertEqual(self.parts["ppt/media/image1.png"][:8], b"\x89PNG\r\n\x1a\n")
        for number in range(1, render_pptx.SLIDE_COUNT + 1):
            rels = self.parts[f"ppt/slides/_rels/slide{number}.xml.rels"].decode(
                "utf-8"
            )
            self.assertIn("../media/image1.png", rels, f"slide{number}")
            slide = self.parts[f"ppt/slides/slide{number}.xml"].decode("utf-8")
            self.assertIn("<p:pic>", slide, f"slide{number}")

    def test_cover_and_named_slide_get_background_images(self):
        cover = self.parts["ppt/slides/slide1.xml"].decode("utf-8")
        self.assertIn("<p:bg>", cover)
        self.assertIn("blipFill", cover)
        self.assertIn('name="Scrim"', cover)  # text stays legible
        slide4 = self.parts["ppt/slides/slide4.xml"].decode("utf-8")
        self.assertIn("<p:bg>", slide4)
        # A slide with no named image gets no background override.
        self.assertNotIn("<p:bg>", self.parts["ppt/slides/slide3.xml"].decode("utf-8"))

    def test_branded_output_is_deterministic(self):
        self.assertEqual(self.blob, render_pptx.build_pptx_bytes(self.data))

    def test_unbranded_deck_is_untouched(self):
        with TempWorkspace() as root:
            _make_instance(root)
            parts = _parts(render_pptx.build_pptx_bytes(_load(root)))
        self.assertFalse(any(name.startswith("ppt/media/") for name in parts))
        slide = parts["ppt/slides/slide2.xml"].decode("utf-8")
        self.assertIn("1F4E79", slide)  # default accent
        self.assertIn('typeface="Calibri"', slide)


# --------------------------------------------------------------------------
# Briefs exporter
# --------------------------------------------------------------------------


class TestBriefsExporter(unittest.TestCase):
    def test_briefs_round_trip_with_brand(self):
        with TempWorkspace() as root:
            instance = _make_instance(root)
            _write_brand(instance, _fixture("designer_palette_output.yaml"))
            data = _load(root)
            written, coaching = branding.export_briefs(data)
            self.assertEqual(
                written,
                [
                    "briefs/poster.json",
                    "briefs/pullup-banner.json",
                    "briefs/flyer.json",
                ],
            )
            for name in written:
                with open(
                    os.path.join(data.out_dir, *name.split("/")), encoding="utf-8"
                ) as handle:
                    payload = json.loads(handle.read())
                for key in (
                    "id",
                    "asset_type",
                    "dimensions_or_aspect",
                    "orientation",
                    "copy",
                    "visual_direction",
                    "brand_refs",
                    "brand_system",
                ):
                    self.assertIn(key, payload, name)
                self.assertIn("headline", payload["copy"], name)
                self.assertTrue(
                    payload["brand_system"].endswith("brand/system.yaml"), name
                )
                self.assertIn("color.tokens", payload["brand_refs"], name)
                # imagery references resolve from output/briefs/ back to brand/
                briefs_dir = os.path.join(data.out_dir, "briefs")
                for ref in payload["visual_direction"]["imagery"]["asset_refs"]:
                    self.assertTrue(
                        os.path.exists(os.path.join(briefs_dir, *ref.split("/"))), ref
                    )

            with open(
                os.path.join(data.out_dir, "briefs", "poster.json"), encoding="utf-8"
            ) as handle:
                poster = json.loads(handle.read())
        self.assertEqual(poster["id"], "ACMECLINICS-BRIEF-PO01")
        self.assertEqual(poster["asset_type"], "poster")
        # Copy is verbatim from the founder's answers.
        self.assertEqual(poster["copy"]["headline"], ANSWERS["brand_positioning"])
        self.assertEqual(poster["copy"]["subcopy"], ANSWERS["core_value_proposition"])
        self.assertIsNone(poster["copy"]["cta"])  # owner supplies the CTA

    def test_missing_marketing_answers_coach_instead_of_empty_briefs(self):
        minimal = {
            "trading_name": "Bare",
            "jurisdiction": "ZA",
            "primary_base": "Cape Town, South Africa",
        }
        with TempWorkspace() as root:
            _make_instance(root, name="Bare", answers=minimal)
            data = _load(root, name="Bare")
            written, coaching = branding.export_briefs(data)
            self.assertEqual(written, [])
            self.assertFalse(os.path.isdir(os.path.join(data.out_dir, "briefs")))
        joined = "\n".join(coaching)
        self.assertIn("Brand Positioning", joined)
        self.assertIn("Core Value Proposition", joined)
        self.assertIn("Pricing Tiers", joined)

    def test_missing_brand_yields_null_brand_system_and_coaching(self):
        with TempWorkspace() as root:
            _make_instance(root)
            data = _load(root)
            written, coaching = branding.export_briefs(data)
            with open(
                os.path.join(data.out_dir, "briefs", "poster.json"), encoding="utf-8"
            ) as handle:
                poster = json.loads(handle.read())
        self.assertIsNone(poster["brand_system"])
        self.assertTrue(any("designer palette" in note for note in coaching))


if __name__ == "__main__":
    unittest.main()
