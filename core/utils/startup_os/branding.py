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

"""Brand assets and design-brief export for StartupOS instances.

Two jobs, both bridging StartupOS to the RokctAI *designer* engine:

1.  **Read a designer design system.** An instance may carry a
    `brand/` folder next to its `questions.md`:

        instances/business/<Name>/brand/
        ├── system.yaml     # designer's design-system format (or system.json)
        ├── logo.png        # raster logo (logo.svg is noted, not embedded)
        └── images/         # optional slide backgrounds: cover.png,
                            #   slide04.png ... (PNG or JPEG)

    `system.yaml` is the file `designer palette "#1a56db" "#f59e0b"
    --name X -o system.yaml` writes. The engine's contract is stdlib
    only, so this module carries a *minimal* YAML-subset parser that
    handles exactly what designer emits and ships: nested maps by
    indentation, inline flow maps (`{ hex: "#0b0b0b", role: surface }`),
    block and inline lists of scalars, quoted strings, numbers, booleans
    and comments. It is not a YAML implementation; anything outside that
    subset is a named error, never a guess.

2.  **Export machine-readable design briefs.** `main.py briefs` turns
    the marketing-plan answers into brief JSONs mirroring the schema of
    the RokctAI agent repo's expo briefs
    (`lms/team/marketing/expo/briefs/*.json`): `id`, `asset_type`,
    `dimensions_or_aspect`, `orientation`, `copy`, `visual_direction`,
    `brand_refs`, so designer's comply/audit pipeline can consume them.
    Copy is the founder's verbatim answers — an unanswered question
    produces a named coaching line, never an empty brief.
"""

import json
import os
import re
import struct

from . import safe_io
from .errors import BrandingError

BRAND_DIRNAME = "brand"
SYSTEM_BASENAMES = ("system.yaml", "system.yml", "system.json")
IMAGE_EXTENSIONS = (".png", ".jpg", ".jpeg")
BRIEFS_DIRNAME = "briefs"

# The real command, so the coaching line is copy-pasteable.
DESIGNER_PALETTE_COMMAND = (
    'designer palette "#1a56db" "#f59e0b" --name {name} -o {output}'
)

_HEX_RE = re.compile(r"\A#?(?:[0-9a-fA-F]{6}|[0-9a-fA-F]{3})\Z")
_KEY_RE = re.compile(r"\A([^:\s][^:]*?)\s*:(\s+.*|)\Z")


# --------------------------------------------------------------------------
# Minimal YAML-subset parser (designer system files only)
# --------------------------------------------------------------------------


def _strip_comment(line):
    """Drop a trailing `# ...` comment that sits outside quotes."""
    out = []
    quote = None
    for index, char in enumerate(line):
        if quote:
            out.append(char)
            if char == quote:
                quote = None
            continue
        if char in "'\"":
            quote = char
            out.append(char)
            continue
        if char == "#" and (index == 0 or line[index - 1] in " \t"):
            break
        out.append(char)
    return "".join(out)


def _split_flow_items(body, source, lineno):
    """Split `a, b, c` on commas that sit outside quotes/brackets."""
    items, depth, quote, current = [], 0, None, []
    for char in body:
        if quote:
            current.append(char)
            if char == quote:
                quote = None
            continue
        if char in "'\"":
            quote = char
            current.append(char)
        elif char in "{[":
            depth += 1
            current.append(char)
        elif char in "}]":
            depth -= 1
            current.append(char)
        elif char == "," and depth == 0:
            items.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    if quote is not None:
        raise BrandingError(f"{source}:{lineno}: unterminated quote in {body!r}")
    tail = "".join(current).strip()
    if tail:
        items.append(tail)
    return items


def _parse_scalar(token, source, lineno):
    token = token.strip()
    if token.startswith("{"):
        if not token.endswith("}"):
            raise BrandingError(f"{source}:{lineno}: unterminated flow map {token!r}")
        result = {}
        for item in _split_flow_items(token[1:-1], source, lineno):
            match = _KEY_RE.match(item) or re.match(r"\A([^:]+):(.*)\Z", item)
            if not match:
                raise BrandingError(
                    f"{source}:{lineno}: expected `key: value` inside {{...}}, got {item!r}"
                )
            result[match.group(1).strip()] = _parse_scalar(
                match.group(2), source, lineno
            )
        return result
    if token.startswith("["):
        if not token.endswith("]"):
            raise BrandingError(f"{source}:{lineno}: unterminated flow list {token!r}")
        return [
            _parse_scalar(item, source, lineno)
            for item in _split_flow_items(token[1:-1], source, lineno)
        ]
    if len(token) >= 2 and token[0] == token[-1] and token[0] in "'\"":
        return token[1:-1]
    if token in ("true", "True"):
        return True
    if token in ("false", "False"):
        return False
    if token in ("null", "~", "None", ""):
        return None
    if re.match(r"\A-?\d+\Z", token):
        return int(token)
    if re.match(r"\A-?\d+\.\d+\Z", token):
        return float(token)
    return token


def _parse_block(lines, index, indent, source):
    """Parse one block (map or list) whose entries sit at `indent`."""
    if lines[index][1].startswith("- ") or lines[index][1] == "-":
        items = []
        while (
            index < len(lines)
            and lines[index][0] == indent
            and (lines[index][1].startswith("- ") or lines[index][1] == "-")
        ):
            _, content, lineno = lines[index]
            items.append(_parse_scalar(content[1:], source, lineno))
            index += 1
        return items, index

    result = {}
    while index < len(lines):
        line_indent, content, lineno = lines[index]
        if line_indent < indent:
            break
        if line_indent > indent:
            raise BrandingError(
                f"{source}:{lineno}: unexpected indentation ({line_indent} spaces, "
                f"expected {indent})"
            )
        if content.startswith("- ") or content == "-":
            break  # a same-indent list belongs to the previous key
        match = _KEY_RE.match(content)
        if not match:
            raise BrandingError(
                f"{source}:{lineno}: expected `key: value`, got {content!r}"
            )
        key, rest = match.group(1).strip(), match.group(2).strip()
        index += 1
        if rest:
            result[key] = _parse_scalar(rest, source, lineno)
            continue
        # Empty value: a nested block (deeper indent), a PyYAML-style list
        # whose dashes sit at the key's own indent, or genuinely empty.
        if index < len(lines) and lines[index][0] > indent:
            result[key], index = _parse_block(lines, index, lines[index][0], source)
        elif (
            index < len(lines)
            and lines[index][0] == indent
            and (lines[index][1].startswith("- ") or lines[index][1] == "-")
        ):
            result[key], index = _parse_block(lines, index, indent, source)
        else:
            result[key] = None
    return result, index


def parse_minimal_yaml(text, source="<yaml>"):
    """Parse the YAML subset used by designer system files into a dict.

    Supported: nested maps by indentation, block lists of scalars (dashes
    at or under the key's indent), inline `{...}` maps and `[...]` lists,
    single/double-quoted strings, ints, floats, booleans, null, comments.
    Anything else raises `BrandingError` naming the file and line.
    """
    lines = []
    for lineno, raw in enumerate(text.splitlines(), start=1):
        content = _strip_comment(raw.replace("\ufeff", ""))
        if not content.strip():
            continue
        stripped = content.lstrip(" ")
        indent = len(content) - len(stripped)
        if content[:indent].count("\t"):
            raise BrandingError(f"{source}:{lineno}: tabs are not valid indentation")
        lines.append((indent, stripped.rstrip(), lineno))

    if not lines:
        raise BrandingError(f"{source}: file is empty")
    value, index = _parse_block(lines, 0, lines[0][0], source)
    if index != len(lines):
        lineno = lines[index][2]
        raise BrandingError(
            f"{source}:{lineno}: content outside the document's root indentation"
        )
    return value


# --------------------------------------------------------------------------
# Design system model
# --------------------------------------------------------------------------


class BrandToken:
    """One named color token: `name`, `hex` (#rrggbb, lowercase), `role`."""

    def __init__(self, name, hex_value, role):
        self.name = name
        self.hex = hex_value
        self.role = role

    @property
    def rgb(self):
        value = self.hex.lstrip("#")
        return tuple(int(value[i : i + 2], 16) for i in (0, 2, 4))

    def luminance(self):
        """WCAG relative luminance, for light-on-dark decisions."""

        def channel(value):
            value /= 255.0
            return (
                value / 12.92 if value <= 0.03928 else ((value + 0.055) / 1.055) ** 2.4
            )

        r, g, b = (channel(c) for c in self.rgb)
        return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _normalise_hex(value, source, token_name):
    text = str(value).strip()
    if not _HEX_RE.match(text):
        raise BrandingError(
            f"Malformed brand system {source}: token {token_name!r} has "
            f"invalid hex color {value!r} (expected #rrggbb)."
        )
    text = text.lstrip("#").lower()
    if len(text) == 3:
        text = "".join(char * 2 for char in text)
    return "#" + text


class BrandSystem:
    """The subset of a designer design system the deck and briefs consume."""

    def __init__(self, name, tokens, fonts, source):
        self.name = name
        self.tokens = tokens  # list of BrandToken, file order preserved
        self.fonts = fonts  # whitelisted font families, file order
        self.source = source  # absolute path of system.yaml / system.json

    def by_role(self, role):
        return [token for token in self.tokens if token.role == role]

    def token(self, name):
        for token in self.tokens:
            if token.name == name:
                return token
        return None

    def first_hex(self, *roles):
        for role in roles:
            for token in self.by_role(role):
                return token
        return None

    def deck_font(self, default):
        """First concrete family from the whitelist; generics are skipped."""
        generic = {
            "sans-serif",
            "serif",
            "monospace",
            "system-ui",
            "cursive",
            "fantasy",
        }
        for family in self.fonts:
            name = str(family).strip()
            if name and name.lower() not in generic and not name.startswith("-"):
                return name
        return default


def system_from_mapping(mapping, source):
    """Build a `BrandSystem` from a parsed system file, validating hard."""
    if not isinstance(mapping, dict):
        raise BrandingError(
            f"Malformed brand system {source}: expected a mapping at the top "
            f"level, got {type(mapping).__name__}."
        )
    color = mapping.get("color")
    raw_tokens = color.get("tokens") if isinstance(color, dict) else None
    if not isinstance(raw_tokens, dict) or not raw_tokens:
        raise BrandingError(
            f"Malformed brand system {source}: no color.tokens mapping. "
            "This should be the file `designer palette` writes."
        )

    tokens = []
    for name, value in raw_tokens.items():
        if isinstance(value, dict):
            hex_value = value.get("hex")
            role = str(value.get("role") or "other").strip().lower()
        else:
            hex_value = value  # the short `name: "#hex"` form
            role = "other"
        if hex_value is None:
            raise BrandingError(
                f"Malformed brand system {source}: token {name!r} has no hex value."
            )
        tokens.append(
            BrandToken(str(name), _normalise_hex(hex_value, source, name), role)
        )

    typography = mapping.get("typography")
    fonts = []
    if isinstance(typography, dict) and isinstance(typography.get("fonts"), list):
        fonts = [str(family) for family in typography["fonts"]]

    name = str(mapping.get("name") or os.path.basename(os.path.dirname(source)))
    return BrandSystem(name=name, tokens=tokens, fonts=fonts, source=source)


def load_system_file(path):
    """Parse `system.yaml` / `system.json` into a `BrandSystem`."""
    with open(path, "rb") as handle:
        blob = handle.read()
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise BrandingError(
            f"Malformed brand system {path}: not UTF-8 ({exc})."
        ) from exc
    if path.lower().endswith(".json"):
        try:
            mapping = json.loads(text)
        except ValueError as exc:
            raise BrandingError(
                f"Malformed brand system {path}: invalid JSON ({exc})."
            ) from exc
    else:
        mapping = parse_minimal_yaml(text, source=path)
    return system_from_mapping(mapping, path)


# --------------------------------------------------------------------------
# Raster inspection (dimensions only, stdlib)
# --------------------------------------------------------------------------


def image_size(blob, path):
    """`(width, height)` of a PNG or JPEG, or a named BrandingError."""
    if blob[:8] == b"\x89PNG\r\n\x1a\n":
        if len(blob) < 24 or blob[12:16] != b"IHDR":
            raise BrandingError(f"Brand image {path} has a corrupt PNG header.")
        return struct.unpack(">II", blob[16:24])
    if blob[:2] == b"\xff\xd8":
        index = 2
        while index + 9 < len(blob):
            if blob[index] != 0xFF:
                index += 1
                continue
            marker = blob[index + 1]
            if marker in (0xD8, 0x01) or 0xD0 <= marker <= 0xD7:
                index += 2
                continue
            length = struct.unpack(">H", blob[index + 2 : index + 4])[0]
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                height, width = struct.unpack(">HH", blob[index + 5 : index + 9])
                return width, height
            index += 2 + length
        raise BrandingError(f"Brand image {path} has no JPEG size marker.")
    raise BrandingError(
        f"Brand image {path} is neither PNG nor JPEG (embedding it would "
        "produce a deck PowerPoint cannot open)."
    )


class BrandImage:
    """One embeddable raster: bytes, extension, pixel size, source path."""

    def __init__(self, path, blob):
        self.path = path
        self.blob = blob
        self.ext = (
            "jpeg" if os.path.splitext(path)[1].lower() in (".jpg", ".jpeg") else "png"
        )
        self.width, self.height = image_size(blob, path)
        if not self.width or not self.height:
            raise BrandingError(f"Brand image {path} reports a zero dimension.")


# --------------------------------------------------------------------------
# The brand/ folder
# --------------------------------------------------------------------------

_SLIDE_IMAGE_RE = re.compile(r"\Aslide0*(\d+)\Z", re.IGNORECASE)
_COVER_NAMES = ("cover", "title", "background", "hero")


class BrandAssets:
    """Everything a `brand/` folder contributes to rendering."""

    def __init__(self, directory, system, logo, cover_image, slide_images, notes):
        self.directory = directory
        self.system = system  # BrandSystem or None
        self.logo = logo  # BrandImage or None
        self.cover_image = cover_image  # BrandImage or None
        self.slide_images = slide_images  # {slide_number: BrandImage}
        self.notes = notes  # coaching lines for the compile output


def _read_image(path):
    with open(path, "rb") as handle:
        return BrandImage(path, handle.read())


def missing_brand_note(instance_dir, trading_name):
    brand_dir = os.path.join(instance_dir, BRAND_DIRNAME)
    command = DESIGNER_PALETTE_COMMAND.format(
        name=json.dumps(trading_name), output=os.path.join(brand_dir, "system.yaml")
    )
    return (
        f"No brand/ folder at {brand_dir} - the investor deck renders in the "
        f"default StartupOS theme. Derive a design system with the designer "
        f"engine ({command}), then add logo.png and optional images/ "
        "(cover.png, slide04.png ...) beside it."
    )


def load_brand(instance_dir, trading_name, warnings=None):
    """Load `<instance>/brand/`, or return None with a coaching note.

    A missing folder is coaching, never an error. A folder whose system
    file or images are malformed raises `BrandingError` naming the file:
    a half-branded deck would look deliberate, so it is refused outright.
    """
    notes = warnings if warnings is not None else []
    brand_dir = os.path.join(instance_dir, BRAND_DIRNAME)
    if not os.path.isdir(brand_dir):
        notes.append(missing_brand_note(instance_dir, trading_name))
        return None

    system = None
    for basename in SYSTEM_BASENAMES:
        candidate = os.path.join(brand_dir, basename)
        if os.path.isfile(candidate):
            system = load_system_file(candidate)
            break
    if system is None:
        notes.append(
            f"{brand_dir} has no system.yaml or system.json - deck colors and "
            "fonts stay on the default theme. Generate one with: "
            + DESIGNER_PALETTE_COMMAND.format(
                name=json.dumps(trading_name),
                output=os.path.join(brand_dir, "system.yaml"),
            )
        )

    logo = None
    for candidate in ("logo.png", "logo.jpg", "logo.jpeg"):
        path = os.path.join(brand_dir, candidate)
        if os.path.isfile(path):
            logo = _read_image(path)
            break
    if logo is None and os.path.isfile(os.path.join(brand_dir, "logo.svg")):
        notes.append(
            f"{os.path.join(brand_dir, 'logo.svg')} found, but the deck embeds "
            "raster only (broad .pptx compatibility) - export brand/logo.png "
            "to put the logo on the slides."
        )

    cover_image = None
    slide_images = {}
    images_dir = os.path.join(brand_dir, "images")
    if os.path.isdir(images_dir):
        unassigned = []
        for entry in sorted(os.listdir(images_dir)):
            stem, ext = os.path.splitext(entry)
            if ext.lower() not in IMAGE_EXTENSIONS:
                continue
            image = _read_image(os.path.join(images_dir, entry))
            slide_match = _SLIDE_IMAGE_RE.match(stem)
            if stem.lower() in _COVER_NAMES:
                cover_image = cover_image or image
            elif slide_match:
                slide_images.setdefault(int(slide_match.group(1)), image)
            else:
                unassigned.append(image)
        if cover_image is None and unassigned:
            cover_image = unassigned.pop(0)
        if unassigned:
            names = ", ".join(os.path.basename(image.path) for image in unassigned)
            notes.append(
                f"Unused brand images ({names}): name a file cover.* for the "
                "title-slide background or slide<NN>.* (e.g. slide04.png) for "
                "a specific slide's background."
            )

    return BrandAssets(
        directory=brand_dir,
        system=system,
        logo=logo,
        cover_image=cover_image,
        slide_images=slide_images,
        notes=notes,
    )


# --------------------------------------------------------------------------
# Design-brief export (agent expo brief schema)
# --------------------------------------------------------------------------


def _clean(text):
    return str(text).replace("**", "").replace("`", "").strip()


def _clean_lines(text):
    lines = [line.strip().lstrip("*-").strip() for line in str(text).splitlines()]
    return [_clean(line) for line in lines if line.strip()]


# Each brief: (filename, asset code, asset_type, dimensions, required
# question keys -> labels, build function name). Copy comes verbatim from
# the founder's answers; a missing required answer skips the brief with a
# coaching line naming the exact question.
_CTA_NOTE = (
    "cta is null - questions.md collects no call-to-action wording, so the "
    "owner supplies the final CTA before production."
)
_VERBATIM_NOTE = (
    "Copy is verbatim from the founder's questions.md answers - do not "
    "rephrase, improve or abbreviate it."
)


def _brief_layout(emphasis):
    return (
        f"Layout is the designer's call. {emphasis} Apply the design system "
        "tokens in the referenced brand system - one accent element per "
        "surface, headline first, supporting lines as a typed list."
    )


def _imagery(brand, briefs_dir):
    refs = []
    if brand is not None:
        if brand.logo is not None:
            refs.append(_relative_to(brand.logo.path, briefs_dir))
        if brand.cover_image is not None:
            refs.append(_relative_to(brand.cover_image.path, briefs_dir))
        for number in sorted(brand.slide_images):
            refs.append(_relative_to(brand.slide_images[number].path, briefs_dir))
    description = (
        "Brand assets referenced below; use them exactly as shipped."
        if refs
        else "No brand imagery supplied - typography-led layout."
    )
    return {"description": description, "asset_refs": refs}


def _relative_to(path, start):
    return os.path.relpath(path, start).replace(os.sep, "/")


def build_briefs(data):
    """Derive the brief payloads from an `InstanceData`.

    Returns `(briefs, coaching)` where `briefs` is a list of
    `(filename, payload_dict)` and `coaching` names every answer that
    blocked or would improve a brief.
    """
    from . import template_engine

    ctx = template_engine.RenderContext(
        values=data.values,
        jurisdiction=data.jurisdiction,
        features=data.jurisdiction.features,
    )

    def answered(key):
        return _clean(ctx.get(key)) if ctx.is_truthy(key) else None

    coaching = []
    briefs = []
    slug = re.sub(r"[^A-Za-z0-9]", "", data.trading_name or data.instance_name).upper()
    slug = slug or "BRAND"

    brand = getattr(data, "brand", None)
    briefs_dir = os.path.join(data.out_dir, BRIEFS_DIRNAME)
    if brand is not None and brand.system is not None:
        brand_system = _relative_to(brand.system.source, briefs_dir)
    else:
        brand_system = None
        coaching.append(
            "Briefs carry brand_system: null - "
            + missing_brand_note(
                os.path.dirname(data.out_dir), data.trading_name or data.instance_name
            )
        )

    def base(code, asset_type, dimensions, copy, emphasis):
        return {
            "id": f"{slug}-BRIEF-{code}",
            "asset_type": asset_type,
            "dimensions_or_aspect": dimensions,
            "orientation": "portrait",
            "copy": copy,
            "visual_direction": {
                "layout": _brief_layout(emphasis),
                "imagery": _imagery(brand, briefs_dir),
                "notes": f"{_VERBATIM_NOTE} {_CTA_NOTE}",
            },
            "brand_refs": [
                "color.tokens",
                "typography.fonts",
                "print",
                "accessibility",
            ],
            "brand_system": brand_system,
        }

    def require(brief_name, pairs):
        missing = [label for key, label in pairs if not answered(key)]
        if missing:
            coaching.append(
                f"{brief_name} brief skipped - answer "
                + " and ".join(f"'{label}'" for label in missing)
                + " in questions.md."
            )
            return False
        return True

    positioning = answered("brand_positioning")
    value_prop = answered("core_value_proposition")

    # Poster: the brand claim.
    if require(
        "poster",
        [
            ("brand_positioning", "Brand Positioning"),
            ("core_value_proposition", "Core Value Proposition"),
        ],
    ):
        copy = {"headline": positioning, "subcopy": value_prop, "cta": None}
        achievements = answered("achievements_to_date")
        if achievements:
            copy["supporting"] = _clean_lines(achievements)
        briefs.append(
            (
                "poster.json",
                base(
                    "PO01",
                    "poster",
                    "A1 portrait (594x841mm), 3mm bleed",
                    copy,
                    "The brand claim, large; the value proposition supports it.",
                ),
            )
        )

    # Pull-up banner: the offer.
    components = answered("product_components") or answered("primary_products")
    if require(
        "pullup-banner",
        [
            ("core_value_proposition", "Core Value Proposition"),
            (
                "product_components"
                if answered("product_components")
                else "primary_products",
                "Product Components (or Primary Products)",
            ),
        ],
    ):
        copy = {
            "headline": value_prop,
            "cta": None,
            "supporting": _clean_lines(components),
        }
        vision = answered("vision_statement") or answered("mission_statement")
        if vision:
            copy["subcopy"] = vision
        briefs.append(
            (
                "pullup-banner.json",
                base(
                    "PB01",
                    "pullup_banner",
                    "850x2000mm, 3mm bleed",
                    copy,
                    "Readable from three metres: the offer, then what ships.",
                ),
            )
        )

    # Flyer: the take-home detail.
    if require(
        "flyer",
        [
            ("core_value_proposition", "Core Value Proposition"),
            ("pricing_tiers", "Pricing Tiers"),
        ],
    ):
        copy = {
            "headline": positioning or answered("vision_statement") or value_prop,
            "subcopy": value_prop,
            "cta": None,
            "supporting": _clean_lines(answered("pricing_tiers")),
        }
        channels = answered("acquisition_channels")
        if channels:
            copy["fine_print"] = " ".join(_clean_lines(channels))
        briefs.append(
            (
                "flyer.json",
                base(
                    "FL01",
                    "flyer",
                    "A5 (148x210mm), 3mm bleed",
                    copy,
                    "Text-dense is fine - this is the take-home facts side.",
                ),
            )
        )

    if briefs:
        coaching.append(_CTA_NOTE)
    return briefs, coaching


def export_briefs(data):
    """Write the brief JSONs to `<output>/briefs/`.

    Returns `(written_relative_names, coaching)`. Nothing is written when
    no brief has its required answers — coaching says exactly which
    questions unlock each brief.
    """
    briefs, coaching = build_briefs(data)
    written = []
    briefs_dir = os.path.join(data.out_dir, BRIEFS_DIRNAME)
    for filename, payload in briefs:
        destination = os.path.join(briefs_dir, filename)
        text = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
        safe_io.atomic_write(destination, text)
        written.append(f"{BRIEFS_DIRNAME}/{filename}")
    return written, coaching
