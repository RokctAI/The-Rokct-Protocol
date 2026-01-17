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
3.  **Register**:
    *   Add `.rokct/` to `.gitignore` (Optional, ask user if they want to commit their agent memory).

## Why?
This ensures you have a dedicated place to `Write` your thoughts without messing up the clean `SSO` submodule.
