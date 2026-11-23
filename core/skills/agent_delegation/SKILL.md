---
name: Agent Delegation
description: Automates offloading structured generation work to direct Groq API calls.
---

# Agent Delegation Skill

This skill delegates work to the Groq API. It uses a **thin-wrapper → shared-script** architecture.

## Architecture

```text
Project .rokct/                         The-Rokct-Protocol/
 └─ agent_delegation/                   └─ core/utils/agent_delegation/
     ├─ call_groq.py  ──────────────────► delegate_to_agent.py   (canonical)
     ├─ handle_groq_output.py            (project-specific in .rokct)
     └─ update_classifications.py        (project-specific in .rokct)
```

- **Thin wrapper** (`call_groq.py`) lives in the project's `.rokct/agent_delegation/scripts/`. It fetches `delegate_to_agent.py` pinned to `PROTOCOL_REF`, verifies its SHA-256 and runs it.
- **`delegate_to_agent.py`** is the single canonical implementation, so it is excluded from project copies during `init_protocol`.
- **`scripts/`** holds scaffold/reference copies (`call_groq.py`, `handle_groq_output.py`, ...). Projects are initialised from here via `init_protocol`.
- **`handle_groq_output.py`** is scaffolded project-side from `scripts/`. Uses `update_classifications.py` (same project directory) for topic deduplication.
- **`update_classifications.py`** is project-specific — generates classification files for `.rokct/config/classifications/<project>_themes.txt`.

## Prerequisites
- **Groq API Key**: `GROQ_API_KEY` (env, `.env`, or remote vault).
- **Monorepo Access**: `MONOREPO_PAT` (CI / remote vault key resolution).
- **Dependencies**: `requests`, `python-dotenv`, `pyyaml`.

## API Key Resolution (delegate_to_agent.py)

Order of fallback:

1. **Environment** — `GROQ_API_KEY`.
2. **Remote Vault** (`MONOREPO_PAT` set) — fetches `.env` from `RokctAI/monorepo` via GitHub API.
3. **Local env file** — `--env-file`, `Monorepo/.env/production.env` or `/.env/production.env`.

## delegate_to_agent.py Subcommands

| Subcommand | Key | Description |
|---|---|---|
| `groq` | GROQ | Call Groq chat completion |

## Project Layouts

| Project | Groq wrapper |
|---|---|
| **factory** | `.rokct/skills/agent_delegation/scripts/call_groq.py` |
| **opportunities** | `.rokct/scripts/agent_delegation/call_groq.py` |

## How to Use

```bash
python .rokct/scripts/agent_delegation/call_groq.py groq \
  --prompt "Your prompt here" \
  --system "Optional system prompt" \
  --model "llama-3.3-70b-versatile"
```

## Init Protocol Reference

When `init_protocol` runs for a new project it:

1. Creates `.rokct/agent_delegation/scripts/` in the project.
2. Copies `scripts/call_groq.py` into the project's `agent_delegation/scripts/`.
3. Leaves `delegate_to_agent.py` out of the project copy (the wrapper fetches the pinned protocol copy).
4. Scaffolds project-specific scripts (`handle_groq_output.py`, `update_classifications.py`) as needed per project.

## Decision Framework
- **Direct (Antigravity)**: Architecture design, UI/UX, multi-repo sync, complex discovery.
- **Groq**: Fast LLM calls for theme generation and structured output.
