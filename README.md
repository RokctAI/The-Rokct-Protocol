# The Rokct Protocol

This repository is the **Single Source of Truth (SSO)** for AI agent behavior, constraints, and operational knowledge.

## How to Read This Repo (For Agents)

Process these rules in priority order:

1.  **[Core Rules](./core/README.md)**: Absolute mandates on authority, obedience, and communication.
2.  **[Coding Standards](./coding/standards.md)**: Technical constraints, stack preferences, and "no placeholder" policies.
3.  **[Design System](./coding/design_system.md)**: Aesthetic guidelines for "Premium" output.
4.  **[Templates](./templates/project_map.md)**: Templates for Memory, Context Map, and Active Session Pointer.
5.  **[Workflows](./workflows/README.md)**: SOPs, including Initialization and Session Logging.

---

## Creator's Guide (For Humans)

### 1. Installation

Quick install (Windows PowerShell):
```powershell
iwr -useb https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.ps1 | iex
```

Quick install (Unix / macOS / Linux):
```bash
curl -sSL https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.sh | bash
```

Or clone manually:

### 2. Initialization (The "Bootstrap")

**Quick install** uses the local profile automatically (installer assumes desktop/local environment):

```powershell
# Windows
iwr -useb https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.ps1 | iex

# Unix/macOS/Linux
curl -sSL https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.sh | bash
```

This downloads and runs `profiles/local/initiate.py`, which:
1.  Creates `.rokct/` in your project root.
2.  Fetches templates, skills, and rules from the protocol (no local clone needed).
3.  Prompts for a parent workspace repo if you want multi-repo sync.
4.  Auto-detects `RokctAI/*` repos and routes to the configured parent.

**For AI agents**: Tell your agent exactly this:

> "Initialize the Rokct Protocol using `The-Rokct-Protocol/workflows/init_protocol.md`."

The agent will read `init_protocol.md` and run the matching `initiate.py` (Local or Web profile based on its environment).

### 3. Profiles

| Profile | When to Use | Key Differences |
|---------|-------------|-----------------|
| **Local** | Desktop (VS Code, CLI, Windsurf) | Copies local-only skills, workflows, Safe ID from git config |
| **Web** | Cloud sandbox (Jules, Codespaces, Replit) | Skips local-only assets, no interactive prompts |

### 4. Workspace Mode (Multi-Repo)

If your project's working files should live in a central parent repo:

1.  `initiate.py` writes `.rokct/.workspace_config.json` pointing to the parent.
2.  `end_protocol.py` creates `.rokct/.sync_ready` after cleanup.
3.  CI (`sync_workspace.yml`) only syncs when `active_session.txt` is absent and `.sync_ready` is present.
4.  Sync is **append-only** — CI never overwrites parent files, only inserts new sections with markers.

### 5. End Protocol

When done working:

> "Run the end protocol."

The agent runs `.rokct/end_protocol.py`, which:
- Deletes pristine `skills/` and `workflows/` (untouched scaffolding).
- Keeps any modified working files (`memory.md`, `decision_log.md`, etc.).
- Leaves `.sync_ready` for CI to pick up.

### 6. Features You Get

*   **Infinite Memory**: Long sessions roll over automatically.
*   **Workspace Sync**: Multi-repo support — one central log for all your projects.
*   **Identity Aware**: The agent knows who you are but asks what to call you.
*   **Auto-Cleanup**: Stale scaffold files are removed after sessions.
*   **Skills**: Modular capability definitions for complex agent behaviors.
*   **No Submodules**: Copy-based initialization — no git submodule overhead.
