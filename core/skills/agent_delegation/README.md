# Agent Delegation Scripts

Thin wrappers and canonical implementation for delegating work to external AI agents or the Groq API.

## Entry Points

Wrappers (`call_jules.py`, `call_groq.py`) are thin redirects — they locate `The-Rokct-Protocol` on the filesystem and hand off to `delegate_to_agent.py`.

```bash
python .rokct/scripts/agent_delegation/call_jules.py create \
  --repo "sources/github/OWNER/REPO" \
  --prompt "Task description" \
  --title "Task Name"

python .rokct/scripts/agent_delegation/call_groq.py groq \
  --prompt "Your prompt" \
  --system "Optional system prompt"
```

## Canonical Implementation (`delegate_to_agent.py`)

### Jules / Agent Commands

| Subcommand | Arguments | Key | Description |
|---|---|---|---|
| `create` | `--repo`, `--prompt`, `--title`, `--branch`, `--require-approval`, `--automation-mode` | JULES / AGENT | Create a new Jules session |
| `status` | `--id` | JULES / AGENT | Fetch session status |
| `query` | `--id`, `--message` | JULES / AGENT | Send a follow-up message |
| `approve` | `--id` | JULES / AGENT | Approve a pending plan |
| `delete` | `--id` | JULES / AGENT | Cancel/delete a session |
| `list` | _(none)_ | JULES / AGENT | List all sessions |

### Groq Commands

| Subcommand | Arguments | Key | Description |
|---|---|---|---|
| `groq` | `--prompt`, `--system`, `--model` | GROQ | Call Groq chat completion |

### Global Arguments

| Argument | Description |
|---|---|
| `--api-key` | Explicit API key (overrides env) |
| `--env-file` | Local env file path (final fallback) |

### API Key Resolution (priority order)

1. `--api-key` CLI flag
2. Remote Vault — fetches `.env` from `RokctAI/monorepo` via GitHub API (requires `MONOREPO_PAT`)
3. Local env file — `Monorepo/.env/production.env` or `/.env/production.env`
4. Environment — `JULES_API_KEY` / `AGENT_API_KEY` / `GROQ_API_KEY`
5. `--env-file` fallback

## Supporting Scripts

### `handle_groq_output.py`

Parses Groq LLM output into job cards (`.rokct/agent/jobs/pending/`).

```bash
python handle_groq_output.py --level 0 --content "$GROQ_RESPONSE"
```

- **Level 0** — parses `theme | type` lines → creates job cards with deduplication (via `update_classifications.py`).
- **Level 1** — parses 5 ideas per card (extension point).

### `manage_sessions.py`

Reads `session_state.md` and `ledger.md`, detects stalled cards, counts active Jules sessions.

```bash
python manage_sessions.py
```

### `update_classifications.py`

Generates/updates classification reference files from pending job cards.

```bash
python update_classifications.py
```

Outputs: `.rokct/config/classifications/<project>_themes.txt` and `_genres.txt`.

## Project Layout

```text
Project .rokct/                         The-Rokct-Protocol/
 └─ agent_delegation/                   └─ core/skills/agent_delegation/scripts/
     ├─ call_jules.py ──────────────────► delegate_to_agent.py   (canonical)
     ├─ call_groq.py  ──────────────────► delegate_to_agent.py   (canonical)
     ├─ handle_groq_output.py            └─ utils/
     ├─ manage_sessions.py                    ├─ call_jules.py
     └─ update_classifications.py             ├─ call_groq.py
                                              ├─ handle_groq_output.py
                                              └─ manage_sessions.py
```
