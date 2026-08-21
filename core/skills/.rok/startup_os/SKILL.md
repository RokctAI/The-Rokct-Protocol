---
name: StartupOS Compiler & Conversational Bridge
description: Compiles business and life strategy documents from a questions.md single source of truth, with jurisdiction-aware compliance sourcing, provenance tracking, and a conversational bridge for WhatsApp/web agents.
---

# StartupOS Compiler & Conversational Bridge

Turns a `questions.md` file into a suite of strategy documents. Compliance
evidence is read from certificates on disk; the conversational bridge lets an
agent provision profiles, update answers and log milestones mid-conversation.

## Core contract

**Nothing is asserted that a document or an answer does not support.**

| Situation | What the document says |
| :--- | :--- |
| Regulated field, certificate on file | The verified value, labelled *Document-backed* |
| Regulated field, no certificate | `Pending — <which document to add>` |
| Regime does not exist in this jurisdiction | The section is omitted entirely |
| Jurisdiction not declared | Every regulated section is suppressed |
| Question unanswered | `Not yet provided`, and it is listed under **Completion Gaps** |

B-BBEE is the clearest case. It exists only in South Africa, so it is gated on
`{{#if_feature bbee}}`. A venture outside South Africa gets no B-BBEE section at
all. A South African venture with no `BEE.pdf` gets an explicit "no certificate
is on file, so no contribution level is claimed" — never a level.

## Layout

```text
core/skills/.rok/startup_os/          # this skill — deployed to <repo>/.rokct/skills/
├── SKILL.md
├── scripts/
│   ├── _bootstrap.py                 # engine fetch + template install
│   ├── compile.py                    # compile a document suite
│   ├── provision.py                  # create a profile
│   ├── log_milestone.py              # append to the living ledger
│   └── seed_cv_ledger.py             # extract milestones from a CV PDF
├── templates/business/               # 31 templates (20 documents + 11 annexures)
└── templates/life/                   # 14 templates (incl. the legal drafts)

core/utils/startup_os/                # the engine — stays in the protocol repo
├── main.py                           # standalone CLI
├── compiler.py, parser.py, agent_bridge.py
├── jurisdictions.py, compliance.py, schemas.py
├── template_engine.py, documents.py
├── paths.py, safe_io.py, errors.py
└── tests/test_startup_os.py
```

The skill ships the templates; the engine is fetched from GitHub at run time so
callers always execute current code. Templates are **not** fetched — they are
copied from this directory, which the protocol installer refreshes on init.

## Workspace

```text
<project>/StartupOS/
├── templates/{business,life}/
└── instances/{business,life}/<Name>/
    ├── questions.md          # the SSOT
    ├── compliance/           # optional: certificates for this instance
    ├── brand/                # optional: designer design system + assets
    │   ├── system.yaml       # from `designer palette` (system.json also accepted)
    │   ├── logo.png          # raster logo (an svg-only logo is coached, not embedded)
    │   └── images/           # cover.png / slide04.png ... deck backgrounds
    ├── .history/             # automatic snapshots before every write
    └── output/               # generated documents (regenerated, never edited)
```

Resolution order for the workspace root, first match wins:
`--root` → `$STARTUPOS_ROOT` → `.startupos.json` → Frappe site path →
a discovered `StartupOS/` directory → `<cwd>/StartupOS`. The rule that fired is
printed on every run.

## Commands

```bash
python scripts/provision.py --type business --name AcmeClinic --base "Berlin, Germany" --jurisdiction DE
```

```bash
python scripts/compile.py --type business --name AcmeClinic
```

```bash
python scripts/log_milestone.py --type life --name Amara --category "Technical Mastery" --entry "Shipped the payments migration."
```

```bash
python scripts/seed_cv_ledger.py --type life --name Amara --pdf ./cv.pdf
```

`seed_cv_ledger.py` prints what it extracted and writes nothing until `--apply`.

The engine also has a standalone CLI with `compile`, `render`, `briefs`,
`provision`, `milestone`, `answer`, `check`, `polish`, `draft`, `lint`,
`list` and `jurisdictions` subcommands:

```bash
python core/utils/startup_os/main.py check --type business --name AcmeClinic
```

`check` is a CI gate: exit `0` clean, `1` evidence pending, `2` a certificate has
expired.

```bash
python core/utils/startup_os/main.py lint
```

`lint` reports drift between the question schema and the templates — a template
needing a field nothing collects, or a question nothing uses.

```bash
python core/utils/startup_os/main.py polish --type business --name AcmeClinic
```

```bash
python core/utils/startup_os/main.py render --type business --name AcmeClinic
```

`render` derives two binary artifacts from the same parsed answers and computed
figures that fill the markdown: `output/investor_pitch_deck.pptx` (a 12-slide
16:9 deck mirroring the pitch-deck annexure, coaching lines included where
answers are missing) and `output/financial_model.xlsx` (Assumptions,
Projections and Unit Economics sheets with *live formulas* over the parsed
inputs, each carrying the compiler-computed value as its cached result).
Both are generated stdlib-only, deterministically — same `questions.md` in,
byte-identical files out. The markdown stays canonical:
`compile --render` regenerates them alongside the documents, and a plain
`compile` prunes them as stale rather than leaving binaries that no longer
match the suite.

The deck is *brand-aware*. Drop a `brand/` folder beside `questions.md`
containing a designer design system — the file
`designer palette "#1a56db" "#f59e0b" --name Acme -o system.yaml` writes
(`system.json` is also accepted; a minimal stdlib parser reads exactly the
YAML subset designer emits) — plus an optional raster `logo.png` and an
`images/` folder. The deck then maps the token *roles* onto its slots
(first `surface` token → background, second → table banding, `ink` →
titles, `text` → body/muted, `accent` else `primary` → bars, bullets and
table headers, with text-on-accent honouring an `accent-ink` token or a
contrast pick), uses the first concrete family from the font whitelist,
puts the logo on the cover and a small mark on content slides, and uses
`images/cover.png` as the cover background and `images/slide04.png` (any
`slide<NN>` name) as that slide's background, behind a translucent scrim.
No `brand/` folder → the deck renders exactly as before and the compile
output carries a coaching line with the `designer palette` command. A
malformed `system.yaml`, logo or image is a *named error* — never a
half-branded deck. An svg-only logo is coached (`.pptx` embedding is
raster-only), not converted.

```bash
python core/utils/startup_os/main.py briefs --type business --name AcmeClinic
```

`briefs` exports machine-readable design briefs to `output/briefs/`
(`poster.json`, `pullup-banner.json`, `flyer.json`), mirroring the expo
brief schema of the RokctAI agent repo
(`lms/team/marketing/expo/briefs/*.json`: `id`, `asset_type`,
`dimensions_or_aspect`, `orientation`, `copy`, `visual_direction`,
`brand_refs`) so the designer engine's brief pipeline can consume them,
plus a `brand_system` reference pointing at the instance's
`brand/system.yaml`. Copy is the founder's *verbatim* marketing answers
(Brand Positioning, Core Value Proposition, Product Components, Pricing
Tiers...); a brief whose required answers are missing is skipped with a
coaching line naming the exact questions — never an empty brief — and
`cta` is `null` for the owner to supply.

`polish` is opt-in AI rephrasing of compiled prose via the Groq API (requires
`GROQ_API_KEY`; without it the command is a no-op). Every numeric token is
replaced with an opaque placeholder before any text leaves the machine — the
transmitted text contains *zero digits* — and tables, financials, compliance
sections and evidence are never sent at all. Responses are verified
deterministically and reverted on any mismatch, so no number can change.

```bash
python core/utils/startup_os/main.py draft --type business --name AcmeClinic
```

`draft` extends the same firewall from rephrasing to drafting: it writes a
first draft of four specific narrative slots (executive-summary opening,
competitive narrative, pitch-deck Problem and Solution prose) from the
founder's own masked answers, each under a hard word budget (150/120/60/60
words). A response over budget is rejected outright — the document keeps the
founder's text or coaching, nothing is truncated. Drafted sections are
visibly labeled "AI-drafted from founder answers (verified numbers
untouched)" and counted in the Document Control block. No `GROQ_API_KEY`
means a clean no-op.

The business suite covers the ten business-plan chapters, the on-a-page set,
the business profile, a **monthly investor update** (recompiled fresh each
month from the current answers and the milestone ledger), and annexures
including the pitch deck, a **cap table & funding history** (with a computed
ownership-sum check), a **due-diligence data-room index** (driven by the
compliance evidence on disk) and a **grant & tender application pack**
(evidence-gated registration, tax and B-BBEE blocks where the jurisdiction
has those regimes). The life suite covers the canvases and on-a-page set,
the CV/obituary pair, a **personal budget plan** (computed monthly cash
flow, savings rate and expense cover), an **emergency information page**
(ICE), and three never-polished legal drafts: the will, a **living will /
healthcare directive** and a **power of attorney** — each with execution
tracking that keeps an unsigned draft loudly labelled as one, and honest
jurisdiction caveats (e.g. ZA: living wills are not statutorily regulated;
an ordinary ZA power of attorney lapses on incapacity).

Every compiled business document carries a **Depth** line in its Document
Control block: documents compile at the deepest level the answers support —
Level 1 *foundation*, Level 2 *investor-ready*, Level 3 *diligence-grade* —
and the line names the exact unanswered questions that unlock the next
level. Level 3 answers (competitor pricing, CAC by channel, sales cycle,
retention cohorts, cap table, churn, funding history, hiring plan) unlock a
named-competitor pricing table in the market analysis and channel-level CAC
plus cohort/retention analysis in the financial model. No level ever renders
from guessed data.

## Environment

| Variable | Effect |
| :--- | :--- |
| `STARTUPOS_ROOT` | Workspace root |
| `STARTUPOS_COMPLIANCE_ROOT` | Directory holding per-instance compliance folders |
| `STARTUPOS_PROTOCOL_REF` | Pin the engine to a tag or commit instead of `main` |
| `STARTUPOS_OFFLINE=1` | Never fetch; run from the cached engine |
| `STARTUPOS_STRICT_ENGINE=1` | Abort if engine modules changed upstream since the last run |
| `STARTUPOS_FETCH_TIMEOUT` | Network timeout in seconds (default 15) |

The bootstrap records a SHA-256 of every fetched module in `core/engine.lock.json`
and reports changes on the next run. Use `STARTUPOS_STRICT_ENGINE=1` in CI:
fetching and importing remote code is remote execution by design, and an
unexplained module change is worth stopping on.

## Agent bridge

Every function validates its arguments. `instance_name` and `instance_type`
arrive from chat messages, so they are checked against an allowlist and the
resolved path is confirmed to sit inside the workspace before anything is
written. Writes are locked, snapshotted to `.history/`, and atomic.

```python
from core.agent_bridge import (
    auto_provision_profile,
    log_ambient_milestone,
    update_profile_answer,
)

path = auto_provision_profile(
    instance_type="business",
    instance_name="TableMountainTech",
    primary_base="Cape Town, South Africa",
    jurisdiction="ZA",
)

result = update_profile_answer(
    filepath=path,
    question_label="Core Value Proposition",
    new_answer="Sovereign edge-native AI services for emerging enterprise.",
)
if result.error:
    ...  # recompilation failed; the answer was still saved

log_ambient_milestone(
    filepath="StartupOS/instances/life/Amara/questions.md",
    category="Technical Mastery",
    entry_text="Led the payments platform migration to event sourcing.",
)
```

`update_profile_answer` raises `QuestionNotFoundError` rather than returning a
misleading success, and `BridgeResult.error` carries any recompilation failure —
a saved answer whose documents did not regenerate is reported, not swallowed.

## Adding a jurisdiction

Add an entry to `JURISDICTIONS` in `core/utils/startup_os/jurisdictions.py`:
name, currency, registry, tax authority, privacy law, and the compliance
features it supports. Templates gate on those features, so no template edit is
needed unless the country has a regime nothing else models.

## Tests

```bash
python core/utils/startup_os/tests/test_startup_os.py
```

Every test corresponds to a defect confirmed by execution, including the
schema-versus-template agreement checks that prevent a template asking for a
field the questionnaire never collects.

## Packaging (pip install)

The engine directory doubles as a pip-installable distribution via
`core/utils/startup_os/pyproject.toml`:

```bash
pip install path/to/The-Rokct-Protocol/core/utils/startup_os
```

That installs the same modules as the *startupos* import package plus a
`startupos` console script mapped to the CLI (`startupos compile`,
`startupos list`, ...). The wheel is stdlib-only — it declares no runtime
dependencies — and reads its version from the engine's `__version__`.

Both identities serve the same code:

- *Runtime mount* (this skill, the tests, the agent repo's plan builder):
  the directory is registered as the `core` package and consumers keep doing
  `from core.parser import parse_questions_md`. Nothing changed here.
- *Installed package* (the design_studio / RokctAI/designer integration):
  `import startupos; from startupos.parser import parse_questions_md` — a
  clean seam with no runtime GitHub fetch.

Engine modules import their siblings relatively (`from .errors import ...`),
which is what lets the one directory answer to either package name.
