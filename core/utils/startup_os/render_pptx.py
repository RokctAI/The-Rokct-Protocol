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

"""Investor pitch deck renderer: `output/investor_pitch_deck.pptx`.

The markdown pitch deck (`annexures/investor_pitch_deck.md`) stays canonical.
This module renders the *same* parsed answers and compiler-computed figures
into a 12-slide 16:9 PresentationML package, so the deck a founder mails an
investor and the deck in the document suite can never disagree.

Design constraints, in order:

1.  **Stdlib only.** The engine's contract is zero third-party dependencies,
    so the package is hand-rolled Office Open XML — a deliberately minimal,
    known-good skeleton (one master, one blank layout, one theme, plain
    textboxes and DrawingML tables) rather than anything clever. PowerPoint,
    Keynote and LibreOffice all open it; fancy layout mechanics are exactly
    where hand-rolled OOXML goes wrong.
2.  **Nothing invented.** A slide whose question is unanswered shows the same
    coaching line the markdown shows ("No traction recorded…"), styled as
    coaching. The deck is honest about its gaps.
3.  **Deterministic.** Same `questions.md` in, byte-identical .pptx out: no
    timestamps anywhere (the optional docProps parts, which carry creation
    times, are deliberately omitted) and fixed zip metadata. A recompile with
    unchanged answers produces an unchanged file, so diffs mean something.

Branding: when the instance carries a `brand/` folder (see `core.branding`),
the deck adopts the designer design system — background, title, body and
accent colors mapped from the token roles, the first concrete family from
the font whitelist, `logo.png` on the cover plus a small mark on content
slides, and `images/` files as cover/per-slide backgrounds (behind a
translucent scrim so text stays legible). Without a brand the deck renders
exactly as before, byte for byte.
"""

import io
import zipfile
from xml.sax.saxutils import escape

from . import safe_io
from . import template_engine
from .compiler import (
    derive_financial_metrics,
    extract_competitor_rows,
    extract_financial_inputs,
    format_money,
)

PITCH_DECK_FILENAME = "investor_pitch_deck.pptx"
SLIDE_COUNT = 12

# --- One place for every visual constant ----------------------------------
# 16:9 slide in EMU (914400 per inch).
SLIDE_W = 12192000
SLIDE_H = 6858000
MARGIN = 685800  # 0.75"

FONT = "Calibri"
COLOR_TITLE = "10243E"  # deep navy
COLOR_ACCENT = "1F4E79"  # header bars, table headers
COLOR_BODY = "333F4D"  # body text
COLOR_MUTED = "6E7B8A"  # coaching and footers
COLOR_TABLE_BAND = "EDF2F8"  # alternating table rows
COLOR_WHITE = "FFFFFF"

SZ_COVER_TITLE = 4000
SZ_COVER_SUB = 1800
SZ_TITLE = 2800
SZ_BODY = 1500
SZ_TABLE = 1200
SZ_FOOTER = 1000

# Body content area shared by every content slide.
TITLE_Y = 396240
TITLE_H = 822960
BAR_Y = 1258570
BAR_H = 45720
BAR_W = 1097280
BODY_Y = 1481328
BODY_H = 4684392
FOOTER_Y = 6396990
ROW_H = 335280  # table row height

# Coaching lines, mirroring the markdown template exactly where it has one.
COACH_TRACTION = (
    "No traction recorded. This is the slide investors read most carefully."
)
COACH_COMPETITION = "No competitive analysis recorded."

# Logo and background-image geometry.
LOGO_COVER_H = 731520  # 0.8"
LOGO_COVER_MAX_W = 2743200  # 3"
LOGO_MARK_H = 274320  # 0.3"
LOGO_MARK_MAX_W = 1828800  # 2"
SCRIM_ALPHA = 60000  # 60% opaque wash over background images


class DeckTheme:
    """Resolved visual constants for one build — engine defaults or brand."""

    def __init__(
        self,
        font=FONT,
        title=COLOR_TITLE,
        accent=COLOR_ACCENT,
        body=COLOR_BODY,
        muted=COLOR_MUTED,
        band=COLOR_TABLE_BAND,
        background=COLOR_WHITE,
        on_accent=COLOR_WHITE,
    ):
        self.font = font
        self.title = title
        self.accent = accent
        self.body = body
        self.muted = muted
        self.band = band
        self.background = background
        self.on_accent = on_accent


DEFAULT_THEME = DeckTheme()


def _contrast(luminance_a, luminance_b):
    lighter, darker = max(luminance_a, luminance_b), min(luminance_a, luminance_b)
    return (lighter + 0.05) / (darker + 0.05)


def theme_from_brand(brand):
    """Map designer token roles onto the deck's slots.

    surface -> background (first token) and table band (second), ink ->
    titles, text -> body (first) and muted (second), accent (else primary)
    -> bars, bullets and table headers. Text on accent fills honours an
    explicit `accent-ink` token, else picks whichever of ink/background
    contrasts better. A slot whose role no token carries keeps the engine
    default — nothing is guessed from unlabeled colors.
    """
    if brand is None or brand.system is None:
        return DEFAULT_THEME

    system = brand.system

    def hex_of(token, fallback):
        return token.hex.lstrip("#").upper() if token is not None else fallback

    surfaces = system.by_role("surface")
    texts = system.by_role("text")
    ink = system.first_hex("ink")
    accent = system.first_hex("accent", "primary")

    background = surfaces[0] if surfaces else None
    band = surfaces[1] if len(surfaces) > 1 else background
    title = ink
    body = texts[0] if texts else ink
    muted = texts[1] if len(texts) > 1 else body

    on_accent = system.token("accent-ink") or system.token("on-accent")
    if on_accent is None and accent is not None:
        candidates = [token for token in (ink, background) if token is not None]
        if candidates:
            on_accent = max(
                candidates,
                key=lambda token: _contrast(token.luminance(), accent.luminance()),
            )

    return DeckTheme(
        font=system.deck_font(FONT),
        title=hex_of(title, COLOR_TITLE),
        accent=hex_of(accent, COLOR_ACCENT),
        body=hex_of(body, COLOR_BODY),
        muted=hex_of(muted, COLOR_MUTED),
        band=hex_of(band, COLOR_TABLE_BAND),
        background=hex_of(background, COLOR_WHITE),
        on_accent=hex_of(on_accent, COLOR_WHITE),
    )


# --------------------------------------------------------------------------
# Data helpers
# --------------------------------------------------------------------------


def _plain(text):
    """Strip the markdown the compiler writes for markdown documents."""
    return str(text).replace("**", "").replace("`", "").strip()


def _blocks(text):
    """Split a free-text answer into displayable lines.

    Multi-line answers become one bullet per line (leading `*`/`-` markers
    stripped); a single-line answer stays a single paragraph.
    """
    lines = [line.strip().lstrip("*-").strip() for line in str(text).splitlines()]
    lines = [_plain(line) for line in lines if line.strip()]
    if len(lines) <= 1:
        return [("para", lines[0])] if lines else []
    return [("bullet", line) for line in lines]


def _sentences(text):
    """One bullet per sentence — for answers that pack one item per sentence."""
    from .compiler import _split_positioning_lines

    return [("bullet", _plain(part)) for part in _split_positioning_lines(text)]


class _Slide:
    """One slide's content, independent of the XML that carries it."""

    def __init__(self, title, items=None, table=None, cover=False):
        self.title = title
        self.items = items or []  # (kind, text): para | bullet | label | coach
        self.table = table  # (headers, rows) or None
        self.cover = cover


def build_slides(data):
    """Derive the 12 slides from an `InstanceData`, mirroring the markdown."""
    values = data.values
    ctx = template_engine.RenderContext(
        values=values,
        jurisdiction=data.jurisdiction,
        features=data.jurisdiction.features,
    )

    def answered(key):
        return _plain(ctx.get(key)) if ctx.is_truthy(key) else None

    fin = extract_financial_inputs(data.profile)
    metrics = derive_financial_metrics(fin)
    symbol = data.jurisdiction.currency_symbol or ""
    company = _plain(values.get("company_name") or data.trading_name)

    slides = []

    # 1 — Title
    items = []
    tagline = answered("brand_positioning") or answered("vision_statement")
    if tagline:
        items.append(("para", tagline))
    meta = " · ".join(
        part
        for part in (
            answered("industry"),
            answered("primary_base"),
            f"founded {answered('establishment_date')}"
            if answered("establishment_date")
            else None,
        )
        if part
    )
    if meta:
        items.append(("coach", meta))
    slides.append(_Slide(company, items, cover=True))

    # 2 — The Problem
    problem = answered("problem_statement")
    slides.append(
        _Slide(
            "The Problem",
            _blocks(problem)
            if problem
            else [
                (
                    "coach",
                    "Required for this deck. Answer Problem Statement in questions.md.",
                )
            ],
        )
    )

    # 3 — The Solution
    items = []
    if answered("core_value_proposition"):
        items.extend(_blocks(answered("core_value_proposition")))
    if answered("product_components"):
        items.append(("label", "What ships"))
        items.extend(_blocks(answered("product_components")))
    if not items:
        items = [
            (
                "coach",
                "Required for this deck. Answer Core Value Proposition in questions.md.",
            )
        ]
    slides.append(_Slide("The Solution", items))

    # 4 — Market (TAM/SAM/SOM funnel)
    items, table = [], None
    if fin["tam"] and fin["sam"] and fin["som"]:
        table = (
            ["Layer", "Size", "Share of the layer above"],
            [
                ["TAM — the whole category", format_money(fin["tam"], symbol), "—"],
                [
                    "SAM — reachable with the current model",
                    format_money(fin["sam"], symbol),
                    f"{fin['sam'] / fin['tam']:.1%} of TAM",
                ],
                [
                    "SOM — realistic capture over 36 months",
                    format_money(fin["som"], symbol),
                    f"{fin['som'] / fin['sam']:.1%} of SAM",
                ],
            ],
        )
        for line in str(values.get("market_sizing_flags") or "").splitlines():
            if line.strip():
                items.append(("coach", _plain(line.lstrip(" *-"))))
    elif answered("market_size_tam"):
        for label, key in (
            ("TAM", "market_size_tam"),
            ("SAM", "market_size_sam"),
            ("SOM (36 months)", "market_size_som"),
        ):
            if answered(key):
                items.append(("bullet", f"{label}: {answered(key)}"))
    else:
        items.append(
            (
                "coach",
                "Required for this deck. Answer Market Size TAM / SAM / SOM — with sources.",
            )
        )
    if answered("market_trends"):
        items.append(("label", "Why now"))
        items.extend(_blocks(answered("market_trends")))
    slides.append(_Slide("Market", items, table=table))

    # 5 — Business Model
    items = []
    if answered("revenue_streams"):
        items.extend(_blocks(answered("revenue_streams")))
    else:
        items.append(("coach", "Required for this deck. Answer Revenue Streams."))
    if answered("pricing_tiers"):
        items.append(("label", "Pricing"))
        items.extend(_sentences(answered("pricing_tiers")))
    slides.append(_Slide("Business Model", items))

    # 6 — Traction
    items = (
        _sentences(answered("achievements_to_date"))
        if answered("achievements_to_date")
        else [("coach", COACH_TRACTION)]
    )
    if answered("funding_history"):
        items.append(("label", "Raised to date"))
        items.extend(_blocks(answered("funding_history")))
    slides.append(_Slide("Traction", items))

    # 7 — Competition
    items, table = [], None
    rows = extract_competitor_rows(data.profile)
    if rows:
        table = (
            ["Competitor", "Positioning against them"],
            [[_plain(name), _plain(stance)] for name, stance in rows],
        )
    else:
        items.append(("coach", COACH_COMPETITION))
    if answered("unfair_advantage"):
        items.append(("label", "Our advantage"))
        items.extend(_blocks(answered("unfair_advantage")))
    slides.append(_Slide("Competition", items, table=table))

    # 8 — Go To Market
    gtm = answered("acquisition_channels") or answered("growth_strategy")
    slides.append(
        _Slide(
            "Go To Market",
            _blocks(gtm)
            if gtm
            else [
                (
                    "coach",
                    "No go-to-market recorded. Answer Acquisition Channels in questions.md.",
                )
            ],
        )
    )

    # 9 — Financials
    items, table = [], None
    if any(amount is not None for amount in fin["revenue"]):
        margin = fin["margin_pct"]
        headers = ["Year", "Revenue", "YoY growth"]
        if margin is not None:
            headers.append(f"Gross profit (at {margin:.0f}% target margin)")
        body_rows = []
        for index, amount in enumerate(fin["revenue"]):
            if amount is None:
                row = [
                    f"Year {index + 1}",
                    f"Pending — answer Projected Year {index + 1}",
                    "—",
                ]
            else:
                growth = metrics["growth"][index]
                row = [
                    f"Year {index + 1}",
                    format_money(amount, symbol),
                    f"{growth:+.0%}" if growth is not None else "—",
                ]
            if margin is not None:
                profit = metrics["gross_profit"][index]
                row.append(format_money(profit, symbol) if profit is not None else "—")
            body_rows.append(row)
        table = (headers, body_rows)
    else:
        items.append(
            (
                "coach",
                "No revenue projections recorded. Answer Projected Year 1–3 in questions.md.",
            )
        )

    if metrics["cac_payback_months"] is not None:
        basis = (
            ""
            if metrics["cac_payback_basis"] == "margin"
            else " (revenue basis — no margin supplied)"
        )
        items.append(
            (
                "bullet",
                f"CAC payback: {metrics['cac_payback_months']:.1f} months{basis}",
            )
        )
    else:
        items.append(
            (
                "coach",
                "CAC payback not derivable yet — needs Customer Acquisition Cost and a per-period Average Revenue Per Customer.",
            )
        )
    if metrics["ltv"] is not None:
        line = f"Customer lifetime value: {format_money(metrics['ltv'], symbol)}"
        if metrics["ltv_cac"] is not None:
            line += f" · LTV:CAC {metrics['ltv_cac']:.1f}x"
        items.append(("bullet", line))
    else:
        items.append(
            (
                "coach",
                "LTV not derivable yet — needs Average Revenue Per Customer, Gross Margin Target and Customer Churn Rate.",
            )
        )
    if metrics["runway_months"] is not None:
        items.append(
            (
                "bullet",
                f"Runway: {metrics['runway_months']:.0f} months "
                f"({format_money(fin['cash'], symbol)} cash ÷ "
                f"{format_money(fin['burn'], symbol)}/month burn)",
            )
        )
    else:
        items.append(
            (
                "coach",
                "Runway not derivable yet — needs Cash On Hand and Monthly Operating Costs.",
            )
        )
    if answered("break_even_point"):
        items.append(("bullet", f"Break-even: {answered('break_even_point')}"))
    items.append(("coach", _plain(values.get("currency_note") or "")))
    slides.append(_Slide("Financials", items, table=table))

    # 10 — Team
    items = []
    team = answered("executive_team") or answered("board_directors")
    if team:
        items.extend(_sentences(team))
    else:
        items.append(
            ("coach", "No team recorded. Answer Executive Team in questions.md.")
        )
    if answered("personnel_count"):
        items.append(("bullet", f"Headcount: {answered('personnel_count')}"))
    if answered("hiring_plan"):
        items.append(("label", "Hiring next"))
        items.extend(_sentences(answered("hiring_plan")))
    slides.append(_Slide("Team", items))

    # 11 — The Ask
    items = []
    if answered("funding_requirement"):
        items.extend(_blocks(answered("funding_requirement")))
    else:
        items.append(
            ("coach", "No capital requirement recorded. Answer Funding Requirement.")
        )
    if answered("capital_allocation"):
        items.append(("label", "Use of funds"))
        items.extend(_sentences(answered("capital_allocation")))
    slides.append(_Slide("The Ask", items))

    # 12 — Corporate Standing
    items = []
    features = data.jurisdiction.features
    if "company_registry" in features:
        status = _plain(values.get("company_name_status") or "Registered name")
        items.append(("bullet", f"{status}: {company}"))
        registry = _plain(values.get("registry_name") or "Registry")
        items.append(
            (
                "bullet",
                f"{registry} number: {_plain(values.get('reg_number') or 'Pending')}",
            )
        )
        if "tax_clearance" in features:
            items.append(
                (
                    "bullet",
                    f"Tax compliance: {_plain(values.get('tax_compliance_status') or 'Pending')}",
                )
            )
    if "bbee" in features:
        if ctx.is_truthy("bee_level"):
            items.append(
                (
                    "bullet",
                    f"B-BBEE: {_plain(values.get('bee_level'))}, "
                    f"{_plain(values.get('bee_procurement_recognition'))} procurement recognition, "
                    f"valid to {_plain(values.get('bee_expiry_date'))}",
                )
            )
        else:
            items.append(
                ("bullet", "B-BBEE: no certificate on file; no level is claimed.")
            )
    if answered("intellectual_property"):
        items.append(("label", "Intellectual property"))
        items.extend(_blocks(answered("intellectual_property")))
    if not items:
        items.append(
            (
                "coach",
                "No corporate records on file. Add compliance evidence to make this slide.",
            )
        )
    items.append(
        (
            "coach",
            "Figures are management projections from questions.md — unaudited, and unverified where marked Pending.",
        )
    )
    slides.append(_Slide("Corporate Standing", items))

    assert len(slides) == SLIDE_COUNT
    return slides


# --------------------------------------------------------------------------
# DrawingML emitters
# --------------------------------------------------------------------------

_XMLNS = (
    'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
    'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships" '
    'xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"'
)

_XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'


def _run(theme, text, size, bold=False, italic=False, color=None):
    color = color or theme.body
    return (
        f'<a:r><a:rPr lang="en-US" sz="{size}" b="{1 if bold else 0}" '
        f'i="{1 if italic else 0}" dirty="0">'
        f'<a:solidFill><a:srgbClr val="{color}"/></a:solidFill>'
        f'<a:latin typeface="{theme.font}"/><a:cs typeface="{theme.font}"/></a:rPr>'
        f"<a:t>{escape(text)}</a:t></a:r>"
    )


def _para(runs, align="l", space_after=600):
    return (
        f'<a:p><a:pPr algn="{align}"><a:spcAft><a:spcPts val="{space_after}"/></a:spcAft>'
        f"<a:buNone/></a:pPr>{runs}</a:p>"
    )


def _textbox(shape_id, name, x, y, cx, cy, paragraphs, autofit=True):
    fit = "<a:normAutofit/>" if autofit else ""
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="{escape(name)}"/>'
        f'<p:cNvSpPr txBox="1"/><p:nvPr/></p:nvSpPr>'
        f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom><a:noFill/></p:spPr>'
        f'<p:txBody><a:bodyPr wrap="square" lIns="0" tIns="0" rIns="0" bIns="0">{fit}</a:bodyPr>'
        f"<a:lstStyle/>{paragraphs}</p:txBody></p:sp>"
    )


def _accent_bar(theme, shape_id, x, y, cx, cy):
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Accent"/>'
        f"<p:cNvSpPr/><p:nvPr/></p:nvSpPr>"
        f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'<a:solidFill><a:srgbClr val="{theme.accent}"/></a:solidFill>'
        f"<a:ln><a:noFill/></a:ln></p:spPr>"
        f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="en-US"/></a:p></p:txBody></p:sp>'
    )


def _scrim(theme, shape_id):
    """Translucent wash between a background image and the slide's text."""
    return (
        f'<p:sp><p:nvSpPr><p:cNvPr id="{shape_id}" name="Scrim"/>'
        f"<p:cNvSpPr/><p:nvPr/></p:nvSpPr>"
        f'<p:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{SLIDE_W}" cy="{SLIDE_H}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom>'
        f'<a:solidFill><a:srgbClr val="{theme.background}">'
        f'<a:alpha val="{SCRIM_ALPHA}"/></a:srgbClr></a:solidFill>'
        f"<a:ln><a:noFill/></a:ln></p:spPr>"
        f'<p:txBody><a:bodyPr/><a:lstStyle/><a:p><a:endParaRPr lang="en-US"/></a:p></p:txBody></p:sp>'
    )


def _picture(shape_id, name, rid, x, y, cx, cy):
    return (
        f'<p:pic><p:nvPicPr><p:cNvPr id="{shape_id}" name="{escape(name)}"/>'
        f"<p:cNvPicPr/><p:nvPr/></p:nvPicPr>"
        f'<p:blipFill><a:blip r:embed="{rid}"/><a:stretch><a:fillRect/></a:stretch></p:blipFill>'
        f'<p:spPr><a:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm>'
        f'<a:prstGeom prst="rect"><a:avLst/></a:prstGeom></p:spPr></p:pic>'
    )


def _fit(image, height, max_width):
    """EMU box for `image` at `height`, aspect preserved, width capped."""
    width = int(round(height * image.width / image.height))
    if width > max_width:
        height = int(round(height * max_width / width))
        width = max_width
    return width, height


def _table_cell(theme, text, bold=False, fill=None, color=None):
    fill_xml = f'<a:solidFill><a:srgbClr val="{fill}"/></a:solidFill>' if fill else ""
    return (
        "<a:tc><a:txBody><a:bodyPr/><a:lstStyle/>"
        + _para(_run(theme, text, SZ_TABLE, bold=bold, color=color), space_after=0)
        + "</a:txBody>"
        f'<a:tcPr marL="91440" marR="91440" marT="45720" marB="45720">{fill_xml}</a:tcPr></a:tc>'
    )


def _table_frame(theme, shape_id, x, y, cx, headers, rows):
    columns = len(headers)
    width = cx // columns
    grid = "".join(f'<a:gridCol w="{width}"/>' for _ in range(columns))

    header_cells = "".join(
        _table_cell(theme, text, bold=True, fill=theme.accent, color=theme.on_accent)
        for text in headers
    )
    body = ""
    for index, row in enumerate(rows):
        fill = theme.band if index % 2 else None
        cells = "".join(_table_cell(theme, str(cell), fill=fill) for cell in row)
        body += f'<a:tr h="{ROW_H}">{cells}</a:tr>'

    return (
        f'<p:graphicFrame><p:nvGraphicFramePr><p:cNvPr id="{shape_id}" name="Table"/>'
        f"<p:cNvGraphicFramePr/><p:nvPr/></p:nvGraphicFramePr>"
        f'<p:xfrm><a:off x="{x}" y="{y}"/><a:ext cx="{cx}" cy="{ROW_H * (len(rows) + 1)}"/></p:xfrm>'
        f'<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/table">'
        f'<a:tbl><a:tblPr firstRow="1" bandRow="1"/><a:tblGrid>{grid}</a:tblGrid>'
        f'<a:tr h="{ROW_H}">{header_cells}</a:tr>{body}</a:tbl>'
        f"</a:graphicData></a:graphic></p:graphicFrame>"
    )


def _item_para(theme, kind, text):
    if kind == "label":
        return _para(
            _run(theme, text, SZ_BODY, bold=True, color=theme.title), space_after=200
        )
    if kind == "coach":
        return _para(_run(theme, text, SZ_BODY, italic=True, color=theme.muted))
    if kind == "bullet":
        return _para(
            _run(theme, "•  ", SZ_BODY, color=theme.accent) + _run(theme, text, SZ_BODY)
        )
    return _para(_run(theme, text, SZ_BODY))


def _slide_xml(theme, slide, number, company, background_rid=None, logo=None):
    """One slide part. Shape ids restart per slide; ids only need part-local uniqueness.

    `background_rid` is the relationship id of a brand background image for
    this slide; `logo` is `(rid, BrandImage)` for the brand logo. Both None
    without a brand, and the emitted XML is then exactly the pre-brand XML.
    """
    shapes = []
    shape_id = 2
    content_w = SLIDE_W - 2 * MARGIN

    if background_rid is not None:
        shapes.append(_scrim(theme, shape_id))
        shape_id += 1

    if slide.cover:
        if logo is not None:
            rid, image = logo
            width, height = _fit(image, LOGO_COVER_H, LOGO_COVER_MAX_W)
            shapes.append(
                _picture(shape_id, "Logo", rid, MARGIN, 1005840, width, height)
            )
            shape_id += 1
        shapes.append(_accent_bar(theme, shape_id, MARGIN, 2065020, BAR_W, BAR_H))
        shape_id += 1
        shapes.append(
            _textbox(
                shape_id,
                "Title",
                MARGIN,
                2286000,
                content_w,
                1143000,
                _para(
                    _run(
                        theme, slide.title, SZ_COVER_TITLE, bold=True, color=theme.title
                    )
                ),
                autofit=False,
            )
        )
        shape_id += 1
        paragraphs = ""
        for kind, text in slide.items:
            size = SZ_COVER_SUB if kind == "para" else SZ_BODY
            color = theme.muted if kind == "coach" else theme.body
            paragraphs += _para(_run(theme, text, size, color=color))
        if paragraphs:
            shapes.append(
                _textbox(
                    shape_id,
                    "Subtitle",
                    MARGIN,
                    3581400,
                    content_w,
                    1600200,
                    paragraphs,
                )
            )
            shape_id += 1
    else:
        if logo is not None:
            rid, image = logo
            width, height = _fit(image, LOGO_MARK_H, LOGO_MARK_MAX_W)
            shapes.append(
                _picture(
                    shape_id,
                    "Logo",
                    rid,
                    SLIDE_W - MARGIN - width,
                    457200,
                    width,
                    height,
                )
            )
            shape_id += 1
        shapes.append(
            _textbox(
                shape_id,
                "Title",
                MARGIN,
                TITLE_Y,
                content_w,
                TITLE_H,
                _para(_run(theme, slide.title, SZ_TITLE, bold=True, color=theme.title)),
                autofit=False,
            )
        )
        shape_id += 1
        shapes.append(_accent_bar(theme, shape_id, MARGIN, BAR_Y, BAR_W, BAR_H))
        shape_id += 1

        body_y = BODY_Y
        body_h = BODY_H
        if slide.table:
            headers, rows = slide.table
            shapes.append(
                _table_frame(theme, shape_id, MARGIN, body_y, content_w, headers, rows)
            )
            shape_id += 1
            used = ROW_H * (len(rows) + 1) + 182880
            body_y += used
            body_h -= used

        paragraphs = "".join(
            _item_para(theme, kind, text) for kind, text in slide.items
        )
        if paragraphs:
            shapes.append(
                _textbox(
                    shape_id, "Body", MARGIN, body_y, content_w, body_h, paragraphs
                )
            )
            shape_id += 1

    shapes.append(
        _textbox(
            shape_id,
            "Footer",
            MARGIN,
            FOOTER_Y,
            content_w,
            274320,
            _para(
                _run(
                    theme,
                    f"{company}  ·  {number} / {SLIDE_COUNT}",
                    SZ_FOOTER,
                    color=theme.muted,
                ),
                align="r",
                space_after=0,
            ),
        )
    )

    background = ""
    if background_rid is not None:
        background = (
            "<p:bg><p:bgPr><a:blipFill>"
            f'<a:blip r:embed="{background_rid}"/>'
            "<a:stretch><a:fillRect/></a:stretch></a:blipFill>"
            "<a:effectLst/></p:bgPr></p:bg>"
        )

    return (
        _XML_DECL
        + f"<p:sld {_XMLNS}><p:cSld>{background}<p:spTree>"
        + '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
        + '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
        + '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
        + "".join(shapes)
        + "</p:spTree></p:cSld><p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr></p:sld>"
    )


# --------------------------------------------------------------------------
# Static package parts
# --------------------------------------------------------------------------


def _content_types(media_extensions=()):
    overrides = "".join(
        f'<Override PartName="/ppt/slides/slide{n}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slide+xml"/>'
        for n in range(1, SLIDE_COUNT + 1)
    )
    media_defaults = "".join(
        f'<Default Extension="{ext}" ContentType="image/{ext}"/>'
        for ext in sorted(media_extensions)
    )
    return (
        _XML_DECL
        + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        + media_defaults
        + '<Override PartName="/ppt/presentation.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.presentation.main+xml"/>'
        '<Override PartName="/ppt/slideMasters/slideMaster1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideMaster+xml"/>'
        '<Override PartName="/ppt/slideLayouts/slideLayout1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.presentationml.slideLayout+xml"/>'
        '<Override PartName="/ppt/theme/theme1.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.theme+xml"/>'
        + overrides
        + "</Types>"
    )


def _rels(pairs):
    """`pairs` is (rId, type-suffix, target)."""
    body = "".join(
        f'<Relationship Id="{rid}" '
        f'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/{rtype}" '
        f'Target="{target}"/>'
        for rid, rtype, target in pairs
    )
    return (
        _XML_DECL
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + body
        + "</Relationships>"
    )


def _presentation_xml():
    slide_ids = "".join(
        f'<p:sldId id="{255 + n}" r:id="rId{1 + n}"/>'
        for n in range(1, SLIDE_COUNT + 1)
    )
    return (
        _XML_DECL + f"<p:presentation {_XMLNS}>"
        '<p:sldMasterIdLst><p:sldMasterId id="2147483648" r:id="rId1"/></p:sldMasterIdLst>'
        f"<p:sldIdLst>{slide_ids}</p:sldIdLst>"
        f'<p:sldSz cx="{SLIDE_W}" cy="{SLIDE_H}"/>'
        '<p:notesSz cx="6858000" cy="9144000"/>'
        "</p:presentation>"
    )


_EMPTY_SPTREE = (
    "<p:spTree>"
    '<p:nvGrpSpPr><p:cNvPr id="1" name=""/><p:cNvGrpSpPr/><p:nvPr/></p:nvGrpSpPr>'
    '<p:grpSpPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="0" cy="0"/>'
    '<a:chOff x="0" y="0"/><a:chExt cx="0" cy="0"/></a:xfrm></p:grpSpPr>'
    "</p:spTree>"
)


def _slide_master_xml(theme):
    return (
        _XML_DECL + f"<p:sldMaster {_XMLNS}>"
        "<p:cSld>"
        f'<p:bg><p:bgPr><a:solidFill><a:srgbClr val="{theme.background}"/></a:solidFill><a:effectLst/></p:bgPr></p:bg>'
        + _EMPTY_SPTREE
        + "</p:cSld>"
        '<p:clrMap bg1="lt1" tx1="dk1" bg2="lt2" tx2="dk2" accent1="accent1" '
        'accent2="accent2" accent3="accent3" accent4="accent4" accent5="accent5" '
        'accent6="accent6" hlink="hlink" folHlink="folHlink"/>'
        '<p:sldLayoutIdLst><p:sldLayoutId id="2147483649" r:id="rId1"/></p:sldLayoutIdLst>'
        "</p:sldMaster>"
    )


def _slide_layout_xml():
    return (
        _XML_DECL + f'<p:sldLayout {_XMLNS} type="blank" preserve="1">'
        '<p:cSld name="Blank">' + _EMPTY_SPTREE + "</p:cSld>"
        "<p:clrMapOvr><a:masterClrMapping/></p:clrMapOvr>"
        "</p:sldLayout>"
    )


def _theme_xml(theme):
    """Minimal but complete theme: PowerPoint requires clr/font/fmt schemes."""
    fills = (
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill>'
    )
    lines = "".join(
        f'<a:ln w="{w}" cap="flat" cmpd="sng" algn="ctr">'
        '<a:solidFill><a:schemeClr val="phClr"/></a:solidFill><a:prstDash val="solid"/></a:ln>'
        for w in (6350, 12700, 19050)
    )
    effects = "<a:effectStyle><a:effectLst/></a:effectStyle>" * 3
    return (
        _XML_DECL
        + '<a:theme xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" name="StartupOS">'
        "<a:themeElements>"
        '<a:clrScheme name="StartupOS">'
        f'<a:dk1><a:srgbClr val="{theme.title}"/></a:dk1><a:lt1><a:srgbClr val="{theme.background}"/></a:lt1>'
        f'<a:dk2><a:srgbClr val="{theme.body}"/></a:dk2><a:lt2><a:srgbClr val="{theme.band}"/></a:lt2>'
        f'<a:accent1><a:srgbClr val="{theme.accent}"/></a:accent1><a:accent2><a:srgbClr val="2E86AB"/></a:accent2>'
        '<a:accent3><a:srgbClr val="6E7B8A"/></a:accent3><a:accent4><a:srgbClr val="B0C4DE"/></a:accent4>'
        '<a:accent5><a:srgbClr val="4472C4"/></a:accent5><a:accent6><a:srgbClr val="264478"/></a:accent6>'
        f'<a:hlink><a:srgbClr val="{theme.accent}"/></a:hlink><a:folHlink><a:srgbClr val="{theme.muted}"/></a:folHlink>'
        "</a:clrScheme>"
        f'<a:fontScheme name="StartupOS">'
        f'<a:majorFont><a:latin typeface="{theme.font}"/><a:ea typeface=""/><a:cs typeface=""/></a:majorFont>'
        f'<a:minorFont><a:latin typeface="{theme.font}"/><a:ea typeface=""/><a:cs typeface=""/></a:minorFont>'
        "</a:fontScheme>"
        '<a:fmtScheme name="StartupOS">'
        f"<a:fillStyleLst>{fills}</a:fillStyleLst>"
        f"<a:lnStyleLst>{lines}</a:lnStyleLst>"
        f"<a:effectStyleLst>{effects}</a:effectStyleLst>"
        f"<a:bgFillStyleLst>{fills}</a:bgFillStyleLst>"
        "</a:fmtScheme>"
        "</a:themeElements><a:objectDefaults/><a:extraClrSchemeLst/>"
        "</a:theme>"
    )


# --------------------------------------------------------------------------
# Package assembly
# --------------------------------------------------------------------------

# Fixed timestamp inside the zip: the epoch of the zip format itself. Real
# times would make every build differ; the content hash in the markdown's
# Document Control block is the real provenance record.
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)


def _write_part(archive, name, text):
    info = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, text.encode("utf-8"))


def _write_media(archive, name, blob):
    info = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, blob)


def _collect_media(brand):
    """Deduplicated media parts plus per-slide usage, all deterministic.

    Returns `(parts, backgrounds, logo_name)`: `parts` is an ordered list of
    `(basename, bytes)` for `ppt/media/`, `backgrounds` maps slide number to
    a basename, `logo_name` is the logo's basename or None. Order is fixed
    (logo, cover, then slide numbers ascending) so rebuilds stay identical.
    """
    parts = []
    seen = {}

    def register(image):
        if image.path not in seen:
            basename = f"image{len(parts) + 1}.{image.ext}"
            parts.append((basename, image.blob))
            seen[image.path] = basename
        return seen[image.path]

    logo_name = None
    backgrounds = {}
    if brand is not None:
        if brand.logo is not None:
            logo_name = register(brand.logo)
        if brand.cover_image is not None:
            backgrounds[1] = register(brand.cover_image)
        for number in sorted(brand.slide_images):
            if 1 <= number <= SLIDE_COUNT:
                backgrounds.setdefault(number, register(brand.slide_images[number]))
    return parts, backgrounds, logo_name


def build_pptx_bytes(data):
    """Assemble the full .pptx package in memory, deterministically."""
    brand = getattr(data, "brand", None)
    theme = theme_from_brand(brand)
    slides = build_slides(data)
    company = _plain(data.values.get("company_name") or data.trading_name)

    media_parts, backgrounds, logo_name = _collect_media(brand)
    media_extensions = {basename.rsplit(".", 1)[-1] for basename, _blob in media_parts}

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        _write_part(archive, "[Content_Types].xml", _content_types(media_extensions))
        _write_part(
            archive,
            "_rels/.rels",
            _rels([("rId1", "officeDocument", "ppt/presentation.xml")]),
        )
        _write_part(archive, "ppt/presentation.xml", _presentation_xml())
        _write_part(
            archive,
            "ppt/_rels/presentation.xml.rels",
            _rels(
                [("rId1", "slideMaster", "slideMasters/slideMaster1.xml")]
                + [
                    (f"rId{1 + n}", "slide", f"slides/slide{n}.xml")
                    for n in range(1, SLIDE_COUNT + 1)
                ]
            ),
        )
        _write_part(
            archive, "ppt/slideMasters/slideMaster1.xml", _slide_master_xml(theme)
        )
        _write_part(
            archive,
            "ppt/slideMasters/_rels/slideMaster1.xml.rels",
            _rels(
                [
                    ("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml"),
                    ("rId2", "theme", "../theme/theme1.xml"),
                ]
            ),
        )
        _write_part(archive, "ppt/slideLayouts/slideLayout1.xml", _slide_layout_xml())
        _write_part(
            archive,
            "ppt/slideLayouts/_rels/slideLayout1.xml.rels",
            _rels([("rId1", "slideMaster", "../slideMasters/slideMaster1.xml")]),
        )
        _write_part(archive, "ppt/theme/theme1.xml", _theme_xml(theme))
        for basename, blob in media_parts:
            _write_media(archive, f"ppt/media/{basename}", blob)
        for number, slide in enumerate(slides, start=1):
            rels = [("rId1", "slideLayout", "../slideLayouts/slideLayout1.xml")]
            background_rid = None
            logo = None
            if number in backgrounds:
                background_rid = f"rId{len(rels) + 1}"
                rels.append(
                    (background_rid, "image", f"../media/{backgrounds[number]}")
                )
            if logo_name is not None:
                logo_rid = f"rId{len(rels) + 1}"
                rels.append((logo_rid, "image", f"../media/{logo_name}"))
                logo = (logo_rid, brand.logo)
            _write_part(
                archive,
                f"ppt/slides/slide{number}.xml",
                _slide_xml(
                    theme,
                    slide,
                    number,
                    company,
                    background_rid=background_rid,
                    logo=logo,
                ),
            )
            _write_part(
                archive,
                f"ppt/slides/_rels/slide{number}.xml.rels",
                _rels(rels),
            )

    return buffer.getvalue()


def render(data, destination):
    """Render the investor pitch deck for an instance to `destination`."""
    safe_io.atomic_write_bytes(destination, build_pptx_bytes(data))
    return destination
