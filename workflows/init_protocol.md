# SOP: Initialize Rokct Protocol

**Trigger**: You start working on a project and do NOT see a `.rokct/` folder in the project root.

## Procedure
1.  **Create Directory**: Create a folder named `.rokct` in the project root.
    *   *Note*: This folder is for your brain (Memory, Logs). It stays with the project.
2.  **Copy Templates**:
    *   Copy `SSO/agent-rules/templates/memory.md` -> `.rokct/memory.md`
    *   Copy `SSO/agent-rules/templates/decision_log.md` -> `.rokct/decision_log.md`
    *   Copy `SSO/agent-rules/templates/project_map.md` -> `.rokct/project_map.md`
    *   Copy `SSO/agent-rules/templates/active_session.txt` -> `.rokct/active_session.txt`
    *   **Create Folder**: `.rokct/sessions/` (Keep empty for new logs).
    *   **Activate Rules**: Copy `SSO/agent-rules/.cursorrules` -> `./.cursorrules` (Project Root). This ensures the IDES (Cursor/Windsurf) see the rules.
3.  **Configuration (Identity)**:
    *   **Auto-Detect**: Agent runs `git config user.name` and `git config user.email`.
    *   **Fallback**: If detection fails, ask the User.
    *   **Update**: Write the Name and Email into `.rokct/memory.md` under `User Profile`.
4.  **Team Safety (GitIgnore)**:
    *   Create `.rokct/.gitignore`.
    *   Add `active_session.txt` to it.
    *   *Reason*: Your "Active Session" pointer is local to YOUR machine. You don't want to force your teammate's agent to switch context just because you did.
5.  **Register**:
    *   Ask user if they want to commit the rest of `.rokct/` (Memory/Sessions).

## Why?
This ensures you have a dedicated place to `Write` your thoughts without messing up the clean `SSO` submodule.
