---
name: film-proposal-generator
description: Generates a broadcast-ready eTV documentary proposal .docx from a film production bible.
---
# Film Proposal Generator Skill

This skill compiles the production bible under `film/{project}/` in a consumer
repository into a submission-ready documentary proposal (`proposal.docx`) —
cover page, numbered sections, production plan, budget and checklist tables.

## Usage

Run the script from the **consumer repo root** (the directory containing
`film/`). The repo root is resolved from the current working directory, not
from the script location, because provisioned skill scripts execute from
variable paths.

```bash
pip install python-docx
python3 .rokct/skills/.rok/film_proposal/scripts/generate_proposal.py [project] [out.docx]
```

Defaults: `project` → `venda_nga_december`, output → `film/{project}/proposal.docx`.

## Inputs

- `film/{project}/00_index.md` — logline, production company
- `film/{project}/metarules/world_rules.md` — the central question
- `film/{project}/characters/*.md` — character roles, fees, archive bubbles
- `film/{project}/scenes/all_scenes.md` — narrative arc
- `film/{project}/themes/all_themes.md`, `film/{project}/bubbles/*.md`

Update any bible file, rerun, and the proposal is regenerated.
