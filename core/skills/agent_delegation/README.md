# Agent Delegation Scripts

Thin wrappers and canonical implementation for delegating work to the Groq API.

## Entry Point

`call_groq.py` is a thin redirect: it fetches `delegate_to_agent.py` pinned to `PROTOCOL_REF`, verifies it and hands off.

```bash
python .rokct/scripts/agent_delegation/call_groq.py groq \
  --prompt "Your prompt" \
  --system "Optional system prompt"
```

## Canonical Implementation (`delegate_to_agent.py`)

| Subcommand | Arguments | Key | Description |
|---|---|---|---|
| `groq` | `--prompt`, `--system`, `--model` | GROQ | Call Groq chat completion |

Global argument: `--env-file` (local env file path, final fallback).

### API Key Resolution (priority order)

1. Environment — `GROQ_API_KEY`
2. Remote Vault — fetches `.env` from `RokctAI/monorepo` via GitHub API (requires `MONOREPO_PAT`)
3. Local env file — `--env-file`, `Monorepo/.env/production.env` or `/.env/production.env`

## Supporting Scripts

### `handle_groq_output.py`

Parses Groq LLM output into job cards (`.rokct/agent/jobs/pending/`).

```bash
python handle_groq_output.py --level 0 --content "$GROQ_RESPONSE"
```

- **Level 0** — parses `theme | type` lines → creates job cards with deduplication (via `update_classifications.py`).
- **Level 1** — parses 5 ideas per card (extension point).

### `update_classifications.py`

Generates/updates classification reference files from pending job cards.

```bash
python update_classifications.py
```

Outputs: `.rokct/config/classifications/<project>_themes.txt` and `_genres.txt`.

## Project Layout

```text
Project .rokct/                         The-Rokct-Protocol/
 └─ agent_delegation/                   └─ core/utils/agent_delegation/
     ├─ call_groq.py  ──────────────────► delegate_to_agent.py (canonical)
     ├─ handle_groq_output.py
     └─ update_classifications.py
                                        └─ core/skills/agent_delegation/scripts/ (scaffolds)
                                                 ├─ call_groq.py
                                                 ├─ handle_groq_output.py
                                                 └─ update_classifications.py
