# The Rokct Protocol

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
git submodule add https://github.com/RokctAI/The-Rokct-Protocol The-Rokct-Protocol
git commit -m "Install Rokct Protocol"
```

### 2. Initialization (The "Bootstrap")
Once the folder `The-Rokct-Protocol` is in your project, open your AI Editor (Cursor/Windsurf) and tell the agent:

> "Initialize the Rokct Protocol using `The-Rokct-Protocol/workflows/init_protocol.md`."

The agent will:
1.  Create a `.rokct/` folder in your project root (for Memory).
2.  Copy the `.cursorrules` file to your project root.
3.  Set up the Session Logging structure.

### 3. Features You Get
*   **Infinite Memory**: Long sessions "roll over" automatically. You never lose context.
*   **Team Safe**: Session files are namespaced by user (e.g., `@ray.dev`) to prevent merge conflicts.
*   **Identity Aware**: The agent knows who you are but asks what to call you.
*   **Auto-Cleanup**: Old session logs are deleted based on your Retention Policy (Default: Forever).

### 4. How to Work
Once initialized, simply tell your Agent to start working:

> **"Start a new session for [Task Name]"**
> *(e.g., "Start a new session for Auth Flow")*

The Agent will automatically:
1.  **Update**: Pull the latest Protocol rules (`git submodule update`).
2.  **Branch**:
    *   **Local**: Switches to context branch `users/[Name]/[Task]`.
    *   **Cloud**: Stays on current branch (Prevention of Agent Error).
3.  **Create**: A namespaced session log (e.g., `.rokct/sessions/2026-05-21_@Ray_Auth.md`).
4.  **Work**: Log its thoughts and follow the rules.
