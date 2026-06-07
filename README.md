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

No submodule needed. Copy the protocol into your project:

```bash
# Clone this repo somewhere accessible
git clone https://github.com/RokctAI/The-Rokct-Protocol.git

# Or reference it as a remote in your project
```

### 2. Initialization (The "Bootstrap")

**First-time setup**: Tell your AI agent exactly this:

> "Initialize the Rokct Protocol using `The-Rokct-Protocol/workflows/init_protocol.md`."

Do NOT just tell it "use the protocol" — you must hand it the explicit path to `init_protocol.md`, or it won’t know where to start.

The agent will:
1.  Create `.rokct/` in your project root.
2.  Run the matching `initiate.py` (Local or Web profile).
3.  Copy templates, skills, and rules into `.rokct/`.
4.  Auto-detect if your repo is `RokctAI/*` and set the workspace parent to `RokctAI/occultation`.
5.  If your repo is NOT `RokctAI/*`, the agent will ask you which parent workspace repo to use.

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

**Non-RokctAI repos**: During init, the agent will ask you to provide the parent workspace repo (e.g. `Owner/Repo`). RokctAI-owned repos auto-detect and route to the configured parent.

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
