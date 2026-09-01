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

"""Jurisdiction registry — what compliance regime applies, and where.

The previous engine inferred "is this South African?" from, among other things,
the existence of a directory named `compliance/`. A clinic in Berlin with a
compliance folder compiled to `(Pty) Ltd`, `B-BBEE Level 1 Contributor`,
`100% black ownership` and `Tax: Good Standing`. None of that was true.

Jurisdiction is now declared, never guessed. When it cannot be established the
answer is `UNKNOWN`, which enables no regulated feature at all — every
jurisdiction-specific claim is suppressed rather than defaulted.

Adding a country means adding a `Jurisdiction` entry. Templates gate their
regional prose on `{{#if_feature bbee}}` / `{{#if_jurisdiction ZA}}`, so no
template edit is needed for the general case.
"""

import re

# Compliance features a jurisdiction may support. Templates gate on these.
FEATURE_COMPANY_REGISTRY = "company_registry"
FEATURE_TAX_CLEARANCE = "tax_clearance"
FEATURE_BBEE = "bbee"
FEATURE_TRADEMARKS = "trademarks"
FEATURE_VAT = "vat"


class Jurisdiction:
    """A country's business-compliance profile."""

    def __init__(
        self,
        code,
        name,
        currency,
        currency_symbol,
        features=(),
        registry_name=None,
        registry_document=None,
        tax_authority=None,
        privacy_law=None,
        standards_body=None,
        default_entity_suffix=None,
        entity_suffix_by_code=None,
        aliases=(),
    ):
        self.code = code
        self.name = name
        self.currency = currency
        self.currency_symbol = currency_symbol
        self.features = frozenset(features)
        self.registry_name = registry_name
        self.registry_document = (
            registry_document or "Business Registration Certificate"
        )
        self.tax_authority = tax_authority
        self.privacy_law = privacy_law
        self.standards_body = standards_body
        self.default_entity_suffix = default_entity_suffix
        self.entity_suffix_by_code = entity_suffix_by_code or {}
        self.aliases = tuple(aliases)

    def supports(self, feature):
        return feature in self.features

    @property
    def is_known(self):
        return self.code != "UNKNOWN"

    def __repr__(self):
        return f"Jurisdiction({self.code!r}, {self.name!r})"


UNKNOWN = Jurisdiction(
    code="UNKNOWN",
    name="Unspecified jurisdiction",
    currency="",
    currency_symbol="",
    features=(),
)

_REGISTRY = {
    "ZA": Jurisdiction(
        code="ZA",
        name="South Africa",
        currency="ZAR",
        currency_symbol="R",
        features=(
            FEATURE_COMPANY_REGISTRY,
            FEATURE_TAX_CLEARANCE,
            FEATURE_BBEE,
            FEATURE_TRADEMARKS,
            FEATURE_VAT,
        ),
        registry_name="CIPC",
        registry_document="Business Registration Certificate",
        tax_authority="SARS",
        privacy_law="POPIA",
        standards_body="SANS",
        default_entity_suffix=None,
        # CIPC enterprise-type codes — the trailing pair of a YYYY/NNNNNN/EE number.
        entity_suffix_by_code={
            "06": "NPC",
            "07": "(Pty) Ltd",
            "08": "Ltd",
            "21": "Inc",
            "23": "(Pty) Ltd",
            "24": "(Pty) Ltd",
            "28": "CC",
            "30": "CC",
        },
        aliases=("south africa", "rsa", "republic of south africa"),
    ),
    "NA": Jurisdiction(
        code="NA",
        name="Namibia",
        currency="NAD",
        currency_symbol="N$",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TAX_CLEARANCE, FEATURE_VAT),
        registry_name="BIPA",
        tax_authority="NamRA",
        aliases=("namibia",),
    ),
    "BW": Jurisdiction(
        code="BW",
        name="Botswana",
        currency="BWP",
        currency_symbol="P",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TAX_CLEARANCE, FEATURE_VAT),
        registry_name="CIPA",
        tax_authority="BURS",
        aliases=("botswana",),
    ),
    "ZW": Jurisdiction(
        code="ZW",
        name="Zimbabwe",
        currency="USD",
        currency_symbol="US$",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TAX_CLEARANCE, FEATURE_VAT),
        registry_name="Companies Registry",
        tax_authority="ZIMRA",
        aliases=("zimbabwe",),
    ),
    "KE": Jurisdiction(
        code="KE",
        name="Kenya",
        currency="KES",
        currency_symbol="KSh",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TAX_CLEARANCE, FEATURE_VAT),
        registry_name="Business Registration Service",
        tax_authority="KRA",
        privacy_law="Data Protection Act 2019",
        aliases=("kenya",),
    ),
    "NG": Jurisdiction(
        code="NG",
        name="Nigeria",
        currency="NGN",
        currency_symbol="₦",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TAX_CLEARANCE, FEATURE_VAT),
        registry_name="CAC",
        tax_authority="FIRS",
        privacy_law="NDPA",
        aliases=("nigeria",),
    ),
    "GH": Jurisdiction(
        code="GH",
        name="Ghana",
        currency="GHS",
        currency_symbol="GH₵",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TAX_CLEARANCE, FEATURE_VAT),
        registry_name="Registrar General's Department",
        tax_authority="GRA",
        aliases=("ghana",),
    ),
    "US": Jurisdiction(
        code="US",
        name="United States",
        currency="USD",
        currency_symbol="$",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TRADEMARKS),
        registry_name="Secretary of State",
        registry_document="Certificate of Incorporation",
        tax_authority="IRS",
        privacy_law="CCPA/CPRA",
        standards_body="ANSI",
        default_entity_suffix="LLC",
        aliases=(
            "united states",
            "united states of america",
            "usa",
            "u.s.a.",
            "america",
        ),
    ),
    "CA": Jurisdiction(
        code="CA",
        name="Canada",
        currency="CAD",
        currency_symbol="C$",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TRADEMARKS, FEATURE_VAT),
        registry_name="Corporations Canada",
        tax_authority="CRA",
        privacy_law="PIPEDA",
        standards_body="CSA",
        aliases=("canada",),
    ),
    "GB": Jurisdiction(
        code="GB",
        name="United Kingdom",
        currency="GBP",
        currency_symbol="£",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TRADEMARKS, FEATURE_VAT),
        registry_name="Companies House",
        registry_document="Certificate of Incorporation",
        tax_authority="HMRC",
        privacy_law="UK GDPR",
        standards_body="BSI",
        default_entity_suffix="Ltd",
        aliases=(
            "united kingdom",
            "uk",
            "great britain",
            "england",
            "scotland",
            "wales",
        ),
    ),
    "IE": Jurisdiction(
        code="IE",
        name="Ireland",
        currency="EUR",
        currency_symbol="€",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TRADEMARKS, FEATURE_VAT),
        registry_name="CRO",
        tax_authority="Revenue",
        privacy_law="GDPR",
        default_entity_suffix="Ltd",
        aliases=("ireland", "republic of ireland"),
    ),
    "DE": Jurisdiction(
        code="DE",
        name="Germany",
        currency="EUR",
        currency_symbol="€",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TRADEMARKS, FEATURE_VAT),
        registry_name="Handelsregister",
        registry_document="Handelsregisterauszug",
        tax_authority="Finanzamt",
        privacy_law="GDPR",
        standards_body="DIN",
        default_entity_suffix="GmbH",
        aliases=("germany", "deutschland"),
    ),
    "FR": Jurisdiction(
        code="FR",
        name="France",
        currency="EUR",
        currency_symbol="€",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TRADEMARKS, FEATURE_VAT),
        registry_name="RCS",
        registry_document="Extrait Kbis",
        tax_authority="DGFiP",
        privacy_law="GDPR",
        standards_body="AFNOR",
        default_entity_suffix="SAS",
        aliases=("france",),
    ),
    "NL": Jurisdiction(
        code="NL",
        name="Netherlands",
        currency="EUR",
        currency_symbol="€",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TRADEMARKS, FEATURE_VAT),
        registry_name="KvK",
        tax_authority="Belastingdienst",
        privacy_law="GDPR",
        standards_body="NEN",
        default_entity_suffix="B.V.",
        aliases=("netherlands", "holland", "the netherlands"),
    ),
    "AE": Jurisdiction(
        code="AE",
        name="United Arab Emirates",
        currency="AED",
        currency_symbol="AED",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_VAT),
        registry_name="DED",
        tax_authority="FTA",
        default_entity_suffix="LLC",
        aliases=("united arab emirates", "uae", "dubai", "abu dhabi"),
    ),
    "IN": Jurisdiction(
        code="IN",
        name="India",
        currency="INR",
        currency_symbol="₹",
        features=(
            FEATURE_COMPANY_REGISTRY,
            FEATURE_TAX_CLEARANCE,
            FEATURE_TRADEMARKS,
            FEATURE_VAT,
        ),
        registry_name="MCA",
        registry_document="Certificate of Incorporation",
        tax_authority="Income Tax Department",
        privacy_law="DPDP Act",
        standards_body="BIS",
        default_entity_suffix="Pvt Ltd",
        aliases=("india",),
    ),
    "AU": Jurisdiction(
        code="AU",
        name="Australia",
        currency="AUD",
        currency_symbol="A$",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TRADEMARKS, FEATURE_VAT),
        registry_name="ASIC",
        tax_authority="ATO",
        privacy_law="Privacy Act",
        standards_body="Standards Australia",
        default_entity_suffix="Pty Ltd",
        aliases=("australia",),
    ),
    "NZ": Jurisdiction(
        code="NZ",
        name="New Zealand",
        currency="NZD",
        currency_symbol="NZ$",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TRADEMARKS, FEATURE_VAT),
        registry_name="NZ Companies Office",
        tax_authority="IRD",
        default_entity_suffix="Limited",
        aliases=("new zealand",),
    ),
    "SG": Jurisdiction(
        code="SG",
        name="Singapore",
        currency="SGD",
        currency_symbol="S$",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TRADEMARKS, FEATURE_VAT),
        registry_name="ACRA",
        tax_authority="IRAS",
        privacy_law="PDPA",
        default_entity_suffix="Pte Ltd",
        aliases=("singapore",),
    ),
    "BR": Jurisdiction(
        code="BR",
        name="Brazil",
        currency="BRL",
        currency_symbol="R$",
        features=(FEATURE_COMPANY_REGISTRY, FEATURE_TAX_CLEARANCE, FEATURE_VAT),
        registry_name="Junta Comercial",
        tax_authority="Receita Federal",
        privacy_law="LGPD",
        default_entity_suffix="Ltda",
        aliases=("brazil", "brasil"),
    ),
}


def all_codes():
    return sorted(_REGISTRY)


def get(code):
    """Look up a jurisdiction by ISO 3166-1 alpha-2 code. Unknown codes -> UNKNOWN."""
    if not code:
        return UNKNOWN
    return _REGISTRY.get(str(code).strip().upper(), UNKNOWN)


def resolve(answers, warnings=None):
    """Determine the jurisdiction for a profile.

    Order:
    1.  An explicit `Jurisdiction` answer (ISO code or country name) — preferred.
    2.  A full country name found in `Primary Base`, matched on word
        boundaries against known names and aliases.
    3.  UNKNOWN.

    Note what is *not* here: no inference from directory layout, and no
    two-letter token matching. The old resolver treated any `primary_base`
    containing the standalone word "sa" as South Africa, so "Sa Pa, Vietnam"
    produced a `(Pty) Ltd` with B-BBEE Level 1.
    """
    warnings = warnings if warnings is not None else []

    declared = answers.get("jurisdiction") if hasattr(answers, "get") else None
    if declared:
        candidate = str(declared).strip()
        direct = _REGISTRY.get(candidate.upper())
        if direct:
            return direct
        by_name = _match_country_name(candidate)
        if by_name:
            return by_name
        warnings.append(
            f"Jurisdiction {declared!r} is not in the registry. Falling back to "
            "UNKNOWN — all jurisdiction-specific compliance is suppressed. "
            f"Known codes: {', '.join(all_codes())}."
        )
        return UNKNOWN

    primary_base = answers.get("primary_base") if hasattr(answers, "get") else None
    if primary_base:
        inferred = _match_country_name(str(primary_base))
        if inferred:
            warnings.append(
                f"Jurisdiction inferred as {inferred.code} ({inferred.name}) from "
                f"Primary Base {primary_base!r}. Add an explicit "
                "'**Jurisdiction**' question to questions.md to make this "
                "deterministic."
            )
            return inferred

    warnings.append(
        "No jurisdiction declared and none could be inferred from Primary Base. "
        "Compiling as UNKNOWN: company-registry, tax-clearance and B-BBEE "
        "sections are suppressed. Add a '**Jurisdiction**' question with an ISO "
        "country code (e.g. ZA, US, GB) to enable them."
    )
    return UNKNOWN


def _match_country_name(text):
    """Match a country name or alias on word boundaries. Never matches bare codes."""
    lowered = str(text).lower()
    best = None
    best_length = 0
    for jurisdiction in _REGISTRY.values():
        candidates = [jurisdiction.name.lower(), *jurisdiction.aliases]
        for candidate in candidates:
            # Aliases shorter than 3 characters are too collision-prone to match
            # inside free text ("uk" is fine, "sa" is not — hence the length gate
            # plus explicit word boundaries).
            if len(candidate) < 2:
                continue
            pattern = r"(?<![a-z])" + re.escape(candidate) + r"(?![a-z])"
            if re.search(pattern, lowered):
                # Prefer the longest match: "south africa" beats "africa".
                if len(candidate) > best_length:
                    best = jurisdiction
                    best_length = len(candidate)
    return best


def entity_suffix_for(jurisdiction, registration_number):
    """Derive the legal entity suffix from a registration number, if the
    jurisdiction encodes one. Returns None when it does not.

    This is used for *display hints only*. The compiler never rewrites a legal
    name that came from a registry document — see compliance.py.
    """
    if not registration_number or not jurisdiction.entity_suffix_by_code:
        return None
    match = re.search(
        r"(\d{4})\s*/\s*(\d{6,7})\s*/\s*(\d{2})", str(registration_number)
    )
    if not match:
        return None
    return jurisdiction.entity_suffix_by_code.get(match.group(3))
