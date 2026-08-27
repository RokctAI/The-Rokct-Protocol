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

"""Financial model renderer: `output/financial_model.xlsx` with live formulas.

The markdown financial documents print computed figures; this workbook makes
the same model *workable*. Three sheets:

*   **Assumptions** — the parsed inputs from `questions.md`, one named cell
    each. This is the only sheet an investor should need to touch.
*   **Projections** — the three-year table, where growth, gross profit and
    costs are formulas over the Assumptions cells (`=Assumptions!B9`,
    `=B2*Assumptions!B3`, `=Assumptions!B6*12`), not pasted numbers.
*   **Unit Economics** — CAC payback, LTV, LTV:CAC and runway as formulas
    over the same cells.

Two hard rules, inherited from the compiler:

1.  **Nothing invented.** A missing input renders as a coaching string in the
    cell ("Pending — answer 'Cash On Hand' in questions.md"), and every cell
    whose formula would need it degrades to the same honesty. No fake zeros.
2.  **Formulas carry cached values.** Each formula cell also stores the value
    the compiler computed (`derive_financial_metrics` — the same arithmetic
    that fills the markdown), so the workbook shows real numbers in any
    viewer before its first recalculation, and a recalculation reproduces
    them.

Deterministic like the .pptx: stdlib `zipfile` with pinned metadata, inline
strings instead of a shared-strings table (one fewer part, no ordering
freedom), and no docProps — the parts that would carry timestamps.
"""

import io
import zipfile
from xml.sax.saxutils import escape

from . import safe_io
from .compiler import derive_financial_metrics, extract_financial_inputs

FINANCIAL_MODEL_FILENAME = "financial_model.xlsx"

SHEET_NAMES = ("Assumptions", "Projections", "Unit Economics")

# Where each parsed input lives on the Assumptions sheet. Everything else in
# the workbook references these addresses, and the tests pin them: moving a
# row silently breaks every dependent formula, so treat this map as an API.
ASSUMPTION_CELLS = {
    "arpc_monthly": "B2",
    "margin_fraction": "B3",
    "cac": "B4",
    "churn_monthly_rate": "B5",
    "burn": "B6",
    "cash": "B7",
    "customers_y1": "B8",
    "revenue_y1": "B9",
    "revenue_y2": "B10",
    "revenue_y3": "B11",
}

_XML_DECL = '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
_ZIP_DATE = (1980, 1, 1, 0, 0, 0)

# Style indexes into cellXfs, defined once in _styles_xml().
S_DEFAULT = 0
S_HEADER = 1
S_CURRENCY = 2
S_PERCENT = 3
S_DECIMAL = 4
S_RATIO = 5
S_NOTE = 6


def _coach(label):
    """The compiler's coaching line, without markdown — cells have no bold."""
    return f"Pending — answer '{label}' in questions.md"


def _num(value):
    """Deterministic numeric literal for `<v>`: no float repr noise."""
    if value == int(value):
        return str(int(value))
    return f"{value:.10g}"


class _Cell:
    def __init__(self, ref, style=S_DEFAULT, text=None, number=None, formula=None):
        self.ref = ref
        self.style = style
        self.text = text
        self.number = number
        self.formula = formula

    def to_xml(self):
        if self.formula is not None:
            cached = f"<v>{_num(self.number)}</v>" if self.number is not None else ""
            return (
                f'<c r="{self.ref}" s="{self.style}">'
                f"<f>{escape(self.formula)}</f>{cached}</c>"
            )
        if self.number is not None:
            return f'<c r="{self.ref}" s="{self.style}"><v>{_num(self.number)}</v></c>'
        if self.text is not None:
            return (
                f'<c r="{self.ref}" s="{self.style}" t="inlineStr">'
                f'<is><t xml:space="preserve">{escape(str(self.text))}</t></is></c>'
            )
        return f'<c r="{self.ref}" s="{self.style}"/>'


def _row(number, cells):
    return f'<row r="{number}">' + "".join(cell.to_xml() for cell in cells) + "</row>"


def _sheet_xml(col_widths, rows):
    cols = "".join(
        f'<col min="{index}" max="{index}" width="{width}" customWidth="1"/>'
        for index, width in enumerate(col_widths, start=1)
    )
    return (
        _XML_DECL
        + '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        + f"<cols>{cols}</cols><sheetData>"
        + "".join(rows)
        + "</sheetData></worksheet>"
    )


# --------------------------------------------------------------------------
# Sheet builders
# --------------------------------------------------------------------------


def _assumptions_sheet(fin):
    """Sheet 1: every parsed input, or the coaching line that unlocks it."""
    arpc_value = fin["arpc_monthly"]
    arpc_note = "Parsed from 'Average Revenue Per Customer'"
    arpc_coach = _coach("Average Revenue Per Customer")
    if fin["arpc"] is not None and fin["arpc_monthly"] is None:
        arpc_coach = (
            "A figure was found but no period — say per month or per year in "
            "'Average Revenue Per Customer'"
        )
    if fin["arpc_period"] == "annual" and arpc_value is not None:
        arpc_note += " (annual figure ÷ 12)"

    churn_note = "Parsed from 'Customer Churn Rate'"
    if fin["churn_period"] == "annual" and fin["churn_monthly_rate"] is not None:
        churn_note += " (annual rate ÷ 12)"

    spec = [
        # (label, value, style, coaching text when absent, source note)
        (
            "Average revenue per customer (per month)",
            arpc_value,
            S_CURRENCY,
            arpc_coach,
            arpc_note,
        ),
        (
            "Gross margin target",
            fin["margin_pct"] / 100.0 if fin["margin_pct"] is not None else None,
            S_PERCENT,
            _coach("Gross Margin Target"),
            "Parsed from 'Gross Margin Target'",
        ),
        (
            "Customer acquisition cost",
            fin["cac"],
            S_CURRENCY,
            _coach("Customer Acquisition Cost"),
            "Parsed from 'Customer Acquisition Cost'",
        ),
        (
            "Customer churn rate (per month)",
            fin["churn_monthly_rate"],
            S_PERCENT,
            _coach("Customer Churn Rate"),
            churn_note,
        ),
        (
            "Monthly operating costs",
            fin["burn"],
            S_CURRENCY,
            _coach("Monthly Operating Costs"),
            "Parsed from 'Monthly Operating Costs'",
        ),
        (
            "Cash on hand",
            fin["cash"],
            S_CURRENCY,
            _coach("Cash On Hand"),
            "Parsed from 'Cash On Hand'",
        ),
        (
            "Customer count — Year 1",
            fin["customers_y1"],
            S_DEFAULT,
            _coach("Customer Count Year 1"),
            "Parsed from 'Customer Count Year 1'",
        ),
        (
            "Projected revenue — Year 1",
            fin["revenue"][0],
            S_CURRENCY,
            _coach("Projected Year 1"),
            "Parsed from 'Projected Year 1'",
        ),
        (
            "Projected revenue — Year 2",
            fin["revenue"][1],
            S_CURRENCY,
            _coach("Projected Year 2"),
            "Parsed from 'Projected Year 2'",
        ),
        (
            "Projected revenue — Year 3",
            fin["revenue"][2],
            S_CURRENCY,
            _coach("Projected Year 3"),
            "Parsed from 'Projected Year 3'",
        ),
    ]

    rows = [
        _row(
            1,
            [
                _Cell("A1", S_HEADER, text="Assumption"),
                _Cell("B1", S_HEADER, text="Value"),
                _Cell("C1", S_HEADER, text="Source"),
            ],
        )
    ]
    for offset, (label, value, style, coach_text, note) in enumerate(spec):
        number = 2 + offset
        if value is not None:
            value_cell = _Cell(f"B{number}", style, number=value)
            note_cell = _Cell(f"C{number}", S_NOTE, text=note)
        else:
            value_cell = _Cell(f"B{number}", S_NOTE, text=coach_text)
            note_cell = _Cell(f"C{number}", S_NOTE, text="—")
        rows.append(
            _row(number, [_Cell(f"A{number}", text=label), value_cell, note_cell])
        )

    rows.append(
        _row(
            13,
            [
                _Cell(
                    "A13",
                    S_NOTE,
                    text=(
                        "Edit values here and the Projections and Unit Economics "
                        "sheets recalculate. The canonical source stays "
                        "questions.md — recompile to refresh this workbook."
                    ),
                )
            ],
        )
    )
    return _sheet_xml([44, 18, 62], rows)


def _projections_sheet(fin, metrics):
    """Sheet 2: three-year table where every figure is a formula."""
    a = ASSUMPTION_CELLS
    revenue_refs = (a["revenue_y1"], a["revenue_y2"], a["revenue_y3"])
    columns = ("B", "C", "D")

    rows = [
        _row(
            1,
            [
                _Cell("A1", S_HEADER, text="Metric"),
                _Cell("B1", S_HEADER, text="Year 1"),
                _Cell("C1", S_HEADER, text="Year 2"),
                _Cell("D1", S_HEADER, text="Year 3"),
            ],
        )
    ]

    revenue_cells = [_Cell("A2", text="Revenue")]
    for column, ref, amount, year in zip(
        columns, revenue_refs, fin["revenue"], (1, 2, 3)
    ):
        if amount is not None:
            revenue_cells.append(
                _Cell(
                    f"{column}2",
                    S_CURRENCY,
                    formula=f"Assumptions!{ref}",
                    number=amount,
                )
            )
        else:
            revenue_cells.append(
                _Cell(f"{column}2", S_NOTE, text=_coach(f"Projected Year {year}"))
            )
    rows.append(_row(2, revenue_cells))

    growth_cells = [
        _Cell("A3", text="Revenue growth (YoY)"),
        _Cell("B3", S_NOTE, text="—"),
    ]
    for index, column, previous in ((1, "C", "B"), (2, "D", "C")):
        value = metrics["growth"][index]
        if value is not None:
            growth_cells.append(
                _Cell(
                    f"{column}3",
                    S_PERCENT,
                    formula=f"{column}2/{previous}2-1",
                    number=value,
                )
            )
        else:
            growth_cells.append(_Cell(f"{column}3", S_NOTE, text="—"))
    rows.append(_row(3, growth_cells))

    profit_cells = [_Cell("A4", text="Gross profit (at target margin)")]
    for index, column in enumerate(columns):
        value = metrics["gross_profit"][index]
        if value is not None:
            profit_cells.append(
                _Cell(
                    f"{column}4",
                    S_CURRENCY,
                    formula=f"{column}2*Assumptions!{a['margin_fraction']}",
                    number=value,
                )
            )
        elif fin["margin_pct"] is None:
            profit_cells.append(
                _Cell(f"{column}4", S_NOTE, text=_coach("Gross Margin Target"))
            )
        else:
            profit_cells.append(_Cell(f"{column}4", S_NOTE, text="—"))
    rows.append(_row(4, profit_cells))

    cost_cells = [_Cell("A5", text="Operating costs (annualised)")]
    for column in columns:
        if metrics["annual_operating_costs"] is not None:
            cost_cells.append(
                _Cell(
                    f"{column}5",
                    S_CURRENCY,
                    formula=f"Assumptions!{a['burn']}*12",
                    number=metrics["annual_operating_costs"],
                )
            )
        else:
            cost_cells.append(
                _Cell(f"{column}5", S_NOTE, text=_coach("Monthly Operating Costs"))
            )
    rows.append(_row(5, cost_cells))

    rows.append(
        _row(
            7,
            [
                _Cell(
                    "A7",
                    S_NOTE,
                    text=(
                        "Live formulas over the Assumptions sheet. Costs are held "
                        "flat at the current monthly burn — no per-year cost "
                        "projections were supplied in questions.md."
                    ),
                )
            ],
        )
    )
    return _sheet_xml([34, 18, 18, 18], rows)


def _unit_economics_sheet(fin, metrics):
    """Sheet 3: the compiler's unit-economics metrics as live formulas."""
    a = ASSUMPTION_CELLS
    rows = [
        _row(
            1,
            [
                _Cell("A1", S_HEADER, text="Metric"),
                _Cell("B1", S_HEADER, text="Value"),
                _Cell("C1", S_HEADER, text="Basis"),
            ],
        )
    ]

    def metric_row(number, label, formula, cached, style, basis, coach_text):
        cells = [_Cell(f"A{number}", text=label)]
        if cached is not None:
            cells.append(_Cell(f"B{number}", style, formula=formula, number=cached))
            cells.append(_Cell(f"C{number}", S_NOTE, text=basis))
        else:
            cells.append(_Cell(f"B{number}", S_NOTE, text=coach_text))
            cells.append(_Cell(f"C{number}", S_NOTE, text="—"))
        rows.append(_row(number, cells))

    metric_row(
        2,
        "Revenue per customer (per year)",
        f"Assumptions!{a['arpc_monthly']}*12",
        metrics["arpc_annual"],
        S_CURRENCY,
        "Monthly revenue per customer × 12",
        _coach("Average Revenue Per Customer"),
    )

    if metrics["cac_payback_basis"] == "revenue":
        payback_formula = f"Assumptions!{a['cac']}/Assumptions!{a['arpc_monthly']}"
        payback_basis = (
            "CAC ÷ monthly revenue per customer (revenue basis — no margin supplied)"
        )
    else:
        payback_formula = (
            f"Assumptions!{a['cac']}/"
            f"(Assumptions!{a['arpc_monthly']}*Assumptions!{a['margin_fraction']})"
        )
        payback_basis = "CAC ÷ (monthly revenue per customer × gross margin)"
    metric_row(
        3,
        "CAC payback (months)",
        payback_formula,
        metrics["cac_payback_months"],
        S_DECIMAL,
        payback_basis,
        "Not derivable yet — needs 'Customer Acquisition Cost' and a per-period "
        "'Average Revenue Per Customer'",
    )

    metric_row(
        4,
        "Customer lifetime value",
        f"Assumptions!{a['arpc_monthly']}*Assumptions!{a['margin_fraction']}"
        f"/Assumptions!{a['churn_monthly_rate']}",
        metrics["ltv"],
        S_CURRENCY,
        "Monthly revenue per customer × gross margin ÷ monthly churn",
        "Not derivable yet — needs 'Average Revenue Per Customer', "
        "'Gross Margin Target' and 'Customer Churn Rate'",
    )

    metric_row(
        5,
        "LTV : CAC",
        f"B4/Assumptions!{a['cac']}",
        metrics["ltv_cac"],
        S_RATIO,
        "Lifetime value ÷ acquisition cost",
        "Not derivable yet — needs the lifetime value above and "
        "'Customer Acquisition Cost'",
    )

    metric_row(
        6,
        "Runway (months)",
        f"Assumptions!{a['cash']}/Assumptions!{a['burn']}",
        metrics["runway_months"],
        S_DECIMAL,
        "Cash on hand ÷ monthly operating costs",
        "Not derivable yet — needs 'Cash On Hand' and 'Monthly Operating Costs'",
    )

    rows.append(
        _row(
            8,
            [
                _Cell(
                    "A8",
                    S_NOTE,
                    text=(
                        "Cached values match the compiled markdown; press "
                        "recalculate (F9) and the formulas reproduce them."
                    ),
                )
            ],
        )
    )
    return _sheet_xml([34, 18, 66], rows)


# --------------------------------------------------------------------------
# Static package parts
# --------------------------------------------------------------------------


def _content_types():
    sheet_overrides = "".join(
        f'<Override PartName="/xl/worksheets/sheet{n}.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>'
        for n in range(1, len(SHEET_NAMES) + 1)
    )
    return (
        _XML_DECL
        + '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
        '<Default Extension="xml" ContentType="application/xml"/>'
        '<Override PartName="/xl/workbook.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>'
        + sheet_overrides
        + '<Override PartName="/xl/styles.xml" '
        'ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
        "</Types>"
    )


def _root_rels():
    return (
        _XML_DECL
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        '<Relationship Id="rId1" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" '
        'Target="xl/workbook.xml"/>'
        "</Relationships>"
    )


def _workbook_xml():
    sheets = "".join(
        f'<sheet name="{escape(name)}" sheetId="{index}" r:id="rId{index}"/>'
        for index, name in enumerate(SHEET_NAMES, start=1)
    )
    return (
        _XML_DECL
        + '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        f"<sheets>{sheets}</sheets></workbook>"
    )


def _workbook_rels():
    sheet_rels = "".join(
        f'<Relationship Id="rId{index}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" '
        f'Target="worksheets/sheet{index}.xml"/>'
        for index in range(1, len(SHEET_NAMES) + 1)
    )
    styles_rid = len(SHEET_NAMES) + 1
    return (
        _XML_DECL
        + '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
        + sheet_rels
        + f'<Relationship Id="rId{styles_rid}" '
        'Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" '
        'Target="styles.xml"/>'
        "</Relationships>"
    )


def _styles_xml(currency_symbol):
    """Number formats, fonts and the cellXfs the S_* constants index into."""
    symbol = escape(currency_symbol or "")
    currency_code = f"&quot;{symbol}&quot;#,##0" if symbol else "#,##0"
    return (
        _XML_DECL
        + '<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        '<numFmts count="4">'
        f'<numFmt numFmtId="164" formatCode="{currency_code}"/>'
        '<numFmt numFmtId="165" formatCode="0.0%"/>'
        '<numFmt numFmtId="166" formatCode="0.0"/>'
        '<numFmt numFmtId="167" formatCode="0.0&quot;x&quot;"/>'
        "</numFmts>"
        '<fonts count="3">'
        '<font><sz val="11"/><name val="Calibri"/></font>'
        '<font><b/><sz val="11"/><color rgb="FF10243E"/><name val="Calibri"/></font>'
        '<font><i/><sz val="10"/><color rgb="FF6E7B8A"/><name val="Calibri"/></font>'
        "</fonts>"
        '<fills count="3">'
        '<fill><patternFill patternType="none"/></fill>'
        '<fill><patternFill patternType="gray125"/></fill>'
        '<fill><patternFill patternType="solid"><fgColor rgb="FFEDF2F8"/>'
        '<bgColor indexed="64"/></patternFill></fill>'
        "</fills>"
        '<borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders>'
        '<cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs>'
        '<cellXfs count="7">'
        '<xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>'
        '<xf numFmtId="0" fontId="1" fillId="2" borderId="0" applyFont="1" applyFill="1"/>'
        '<xf numFmtId="164" fontId="0" fillId="0" borderId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="165" fontId="0" fillId="0" borderId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="166" fontId="0" fillId="0" borderId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="167" fontId="0" fillId="0" borderId="0" applyNumberFormat="1"/>'
        '<xf numFmtId="0" fontId="2" fillId="0" borderId="0" applyFont="1"/>'
        "</cellXfs>"
        '<cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles>'
        "</styleSheet>"
    )


# --------------------------------------------------------------------------
# Package assembly
# --------------------------------------------------------------------------


def _write_part(archive, name, text):
    info = zipfile.ZipInfo(name, date_time=_ZIP_DATE)
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, text.encode("utf-8"))


def build_xlsx_bytes(data):
    """Assemble the full .xlsx package in memory, deterministically."""
    fin = extract_financial_inputs(data.profile)
    metrics = derive_financial_metrics(fin)
    symbol = data.jurisdiction.currency_symbol or ""

    sheets = (
        _assumptions_sheet(fin),
        _projections_sheet(fin, metrics),
        _unit_economics_sheet(fin, metrics),
    )

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        _write_part(archive, "[Content_Types].xml", _content_types())
        _write_part(archive, "_rels/.rels", _root_rels())
        _write_part(archive, "xl/workbook.xml", _workbook_xml())
        _write_part(archive, "xl/_rels/workbook.xml.rels", _workbook_rels())
        _write_part(archive, "xl/styles.xml", _styles_xml(symbol))
        for index, sheet in enumerate(sheets, start=1):
            _write_part(archive, f"xl/worksheets/sheet{index}.xml", sheet)

    return buffer.getvalue()


def render(data, destination):
    """Render the financial model workbook for an instance to `destination`."""
    safe_io.atomic_write_bytes(destination, build_xlsx_bytes(data))
    return destination
