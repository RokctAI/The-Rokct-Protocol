# Agent Rules & Context (SSO)

This repository acts as the **Single Source of Truth (SSO)** for the AI agent's behavior, constraints, and operational knowledge.

## How to Read This Repo (For Agents)
The agent **MUST** process these rules in the following priority order:

1.  **[Core Rules](./core/README.md)**: Absolute mandates on authority, obedience, and communication.
    *   [Authority & Obedience](./core/01_authority.md)
    *   [Communication](./core/02_communication.md)
2.  **[Coding Standards](./coding/standards.md)**: Technical constraints, stack preferences, and "no placeholder" policies.
3.  **[Design System](./coding/design_system.md)**: Aesthetic guidelines for "Premium" output.
4.  **[Templates](./templates/project_map.md)**: Templates for Memory, Context Map, and **Active Session Pointer** (`active_session.txt`).
5.  **[Workflows](./workflows/README.md)**: SOPs, including [Initialization](./workflows/init_protocol.md) and [Session Logging](./workflows/session_logging.md).

---

## Creator's Guide (For Humans)

### 1. Installation
Add this repository as a submodule to your project (e.g., your Next.js or Frappe app):

```bash
git submodule add <URL_TO_THIS_REPO> agent-rules
```

### 2. Initialization (The "Bootstrap")
Once the folder `agent-rules` is in your project, open your AI Editor (Cursor/Windsurf) and tell the agent:

> "Initialize the Rokct Protocol using `agent-rules/workflows/init_protocol.md`."

The agent will:
1.  Create a `.rokct/` folder in your project root (for Memory).
2.  Copy the `.cursorrules` file to your project root.
3.  Set up the Session Logging structure.

### 3. Usage
**Do nothing.**
Once initialized, the `.cursorrules` file in your root will automatically instruct the AI to:
*   Check `.rokct/memory.md` for your preferences.
*   Log its work in `.rokct/sessions/`.
*   Follow the "Rokct Protocol".
