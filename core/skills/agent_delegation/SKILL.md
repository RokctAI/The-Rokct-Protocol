---
name: Agent Delegation
description: Automates the offloading of repetitive or large-scale coding tasks to an AI agent (Jules) or direct Groq API calls.
---

# Agent Delegation Skill

This skill delegates work to external AI agents (Jules) or the Groq API. It uses a **thin-wrapper → shared-script** architecture.

## Architecture

```
Project .rokct/                         The-Rokct-Protocol/
 └─ agent_delegation/                   └─ core/skills/agent_delegation/scripts/
     ├─ call_jules.py ──────────────────► delegate_to_agent.py   (canonical)
     ├─ call_groq.py  ──────────────────► delegate_to_agent.py   (canonical)
     ├─ handle_groq_output.py            └─ utils/               (scaffold scripts)
     │                                      ├─ call_jules.py
     │                                      ├─ call_groq.py
     │                                      ├─ handle_groq_output.py
     │                                      └─ manage_sessions.py
     ├─ manage_sessions.py ──────────────► manage_sessions.py   (scaffold)
     └─ update_classifications.py        (project-specific)
```

- **Thin wrappers** (`call_jules.py`, `call_groq.py`) live in the project's `.rokct/agent_delegation/scripts/`. They locate `The-Rokct-Protocol` by walking up the directory tree and redirect to `delegate_to_agent.py`.
- **`delegate_to_agent.py`** is the single canonical implementation. Wrapper scripts in the project redirect to this, so **`delegate_to_agent.py` is excluded from project copies during `init_protocol`**.
- **`utils/`** holds scaffold/reference copies (`call_jules.py`, `call_groq.py`, `handle_groq_output.py`, `manage_sessions.py`). Projects are initialised from here via `init_protocol` — they copy to the project's wrapper directory and update paths accordingly.
- **`handle_groq_output.py`** is scaffolded project-side from `utils/`. Uses `update_classifications.py` (same project directory) for topic deduplication.
- **`manage_sessions.py`** is scaffolded project-side from `utils/`. Reads `session_state.md` + `ledger.md`, detects stalled cards, counts active Jules sessions.
- **`update_classifications.py`** is project-specific — generates classification files for `.rokct/config/classifications/<project>_themes.txt`.

## Prerequisites
- **Jules API Key**: `JULES_API_KEY` or `AGENT_API_KEY` (env, `.env`, or remote vault).
- **Groq API Key**: `GROQ_API_KEY` (only needed for `groq` subcommand).
- **Monorepo Access**: `MONOREPO_PAT` (CI / remote vault key resolution).
- **Dependencies**: `requests`, `python-dotenv`, `pyyaml`.

## API Key Resolution (delegate_to_agent.py)

Order of fallback:

1. **Remote Vault** (`MONOREPO_PAT` set) — fetches `.env` from `RokctAI/monorepo` via GitHub API.
2. **Local env file** — `Monorepo/.env/production.env` or `/.env/production.env`.
3. **Explicit** — `--api-key` CLI flag.
4. **Environment** — `JULES_API_KEY` / `AGENT_API_KEY`.
5. **`.env`** — `--env-file` fallback.

## delegate_to_agent.py Subcommands

| Subcommand | Key | Description |
|---|---|---|
| `create` | JULES / AGENT | Create a new Jules session |
| `status` | JULES / AGENT | Fetch session status |
| `query` | JULES / AGENT | Send a follow-up message |
| `approve` | JULES / AGENT | Approve a pending plan |
| `delete` | JULES / AGENT | Cancel/delete a session |
| `list` | JULES / AGENT | List all sessions |
| `groq` | GROQ | Call Groq chat completion |

## Init Protocol Reference

When `init_protocol` runs for a new project it:

1. Creates `.rokct/agent_delegation/scripts/` in the project.
2. Copies `utils/call_jules.py` and `utils/call_groq.py` into the project's `agent_delegation/scripts/`, updating their lookup paths to point to the project's directory.
3. Deletes `delegate_to_agent.py` from the project copy (wrappers already redirect to the protocol copy).
4. Also scaffolds/manages project-specific scripts (`handle_groq_output.py`, `update_classifications.py`, `manage_sessions.py`) as needed per project.

## Decision Framework
- **Delegate (Agent)**: Bulk refactors, library migrations, boilerplate, sub-repo work, mid-task fixes.
- **Direct (Antigravity)**: Architecture design, UI/UX, multi-repo sync, complex discovery.
- **Groq**: Fast LLM calls without a Jules session (theme generation, structured output).

## Best Practices
- **Repo format**: Always use full source name (`sources/github/Owner/Repo`).
- **Context**: Mention specific file paths or patterns to narrow Jules' scope.
