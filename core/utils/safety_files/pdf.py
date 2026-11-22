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

"""A small stdlib-only PDF writer for the binder.

The engine ships with no runtime dependencies (same rule as StartupOS), so
this writes PDF 1.4 by hand: A4 pages, the built-in Helvetica fonts,
WinAnsi text, wrapped lines, a running header and page numbers. It is
enough for an indexed, printable binder; it is not a layout engine.
"""

import textwrap

PAGE_W, PAGE_H = 595, 842  # A4 in points
MARGIN_X, TOP, BOTTOM = 50, 790, 60

STYLES = {
    # name: (font resource, size, leading, wrap width in characters)
    "title": ("F2", 18, 26, 55),
    "h1": ("F2", 14, 20, 70),
    "h2": ("F2", 11, 16, 88),
    "body": ("F1", 10, 14, 98),
    "mono": ("F3", 8, 11, 103),
    "small": ("F1", 7, 9, 135),
}


def _escape(text):
    raw = text.encode("cp1252", errors="replace").decode("latin-1")
    return raw.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


class Document:
    """Collects styled lines into pages. `pages` is a list of line lists."""

    def __init__(self, header="", footer=""):
        self.header = header
        self.footer = footer
        self.pages = [[]]
        self._y = TOP

    @property
    def page_number(self):
        return len(self.pages)

    def new_page(self):
        if self.pages[-1]:
            self.pages.append([])
        self._y = TOP

    def space(self, points=8):
        self._y -= points

    def text(self, value, style="body"):
        font, size, leading, width = STYLES[style]
        lines = []
        for para in str(value).split("\n"):
            lines.extend(textwrap.wrap(para, width) or [""])
        for line in lines:
            if self._y - leading < BOTTOM:
                self.new_page()
            self._y -= leading
            self.pages[-1].append((font, size, MARGIN_X, self._y, line))

    def render(self):
        """Return the PDF as bytes."""
        objects = []

        def add(body):
            objects.append(body)
            return len(objects)

        catalog = add(None)
        pages_obj = add(None)
        fonts = {
            "F1": add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>"),
            "F2": add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica-Bold /Encoding /WinAnsiEncoding >>"),
            "F3": add(b"<< /Type /Font /Subtype /Type1 /BaseFont /Courier /Encoding /WinAnsiEncoding >>"),
        }
        resources = "<< /Font << %s >> >>" % " ".join("/%s %d 0 R" % (k, v) for k, v in fonts.items())
        total = len(self.pages)
        kids = []
        for index, lines in enumerate(self.pages, start=1):
            ops = ["BT"]
            items = list(lines)
            if self.header:
                items.append(("F1", 7, MARGIN_X, PAGE_H - 30, self.header))
            foot = "%s   Page %d of %d" % (self.footer, index, total) if self.footer else "Page %d of %d" % (index, total)
            items.append(("F1", 7, MARGIN_X, 30, foot))
            for font, size, x, y, line in items:
                ops.append("/%s %d Tf 1 0 0 1 %d %d Tm (%s) Tj" % (font, size, x, y, _escape(line)))
            ops.append("ET")
            stream = "\n".join(ops).encode("latin-1")
            content = add(b"<< /Length %d >>\nstream\n" % len(stream) + stream + b"\nendstream")
            page = add(
                (
                    "<< /Type /Page /Parent %d 0 R /MediaBox [0 0 %d %d] /Resources %s /Contents %d 0 R >>"
                    % (pages_obj, PAGE_W, PAGE_H, resources, content)
                ).encode("latin-1")
            )
            kids.append(page)
        objects[catalog - 1] = b"<< /Type /Catalog /Pages %d 0 R >>" % pages_obj
        objects[pages_obj - 1] = (
            "<< /Type /Pages /Kids [%s] /Count %d >>" % (" ".join("%d 0 R" % k for k in kids), len(kids))
        ).encode("latin-1")

        out = bytearray(b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n")
        offsets = []
        for number, body in enumerate(objects, start=1):
            offsets.append(len(out))
            out += b"%d 0 obj\n" % number + body + b"\nendobj\n"
        xref = len(out)
        out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
        for offset in offsets:
            out += b"%010d 00000 n \n" % offset
        out += b"trailer\n<< /Size %d /Root %d 0 R >>\nstartxref\n%d\n%%EOF\n" % (len(objects) + 1, catalog, xref)
        return bytes(out)
