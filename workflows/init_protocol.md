# SOP: Initialize Rokct Protocol

**Trigger**: You start working on a project and do NOT see a `.rokct/` folder in the project root.

## Procedure
1.  **Create Directory**: Create a folder named `.rokct` in the project root.
    *   *Note*: This folder is for your brain (Memory, Logs). It stays with the project.
2.  **Copy Templates**:
    *   Copy `The-Rokct-Protocol/templates/memory.md` -> `.rokct/memory.md`
    *   Copy `The-Rokct-Protocol/templates/decision_log.md` -> `.rokct/decision_log.md`
    *   Copy `The-Rokct-Protocol/templates/project_map.md` -> `.rokct/project_map.md`
    *   Copy `The-Rokct-Protocol/templates/active_session.txt` -> `.rokct/active_session.txt`
    *   **Create Folder**: `.rokct/sessions/` (Keep empty for new logs).
    *   **Activate Rules**: Copy `The-Rokct-Protocol/.cursorrules` -> `./.cursorrules` (Project Root). This ensures the IDES (Cursor/Windsurf) see the rules.
3.  **Configuration (Identity)**:
    *   **Identity**: Run `git config user.email`.
    *   **Persona**: Ask the User: *"What should I call you?"* (e.g., "Ray").
    *   **Safe ID**: Generate `[EmailPrefix].[MD5(Domain)][:6]`.
        *   `ray.dev@rokct.ai` -> `ray.dev.9ac2b1`
        *   *Why*: Readable user, private domain, collision-proof.
    *   **Update**: Write **Preferred Name**, **Email**, and **Safe ID** into `.rokct/memory.md`.
    *   **Retention**: Ask: *"How long should I keep closed session logs?"* (Default: Forever).
    *   **Update**: Write **Preferred Name**, **Email**, and **Retention Policy** into `.rokct/memory.md`.
4.  **Team Safety (GitIgnore)**:
    *   Create `.rokct/.gitignore`.
    *   Add `active_session.txt` to it.
    *   *Reason*: Your "Active Session" pointer is local to YOUR machine. You don't want to force your teammate's agent to switch context just because you did.
5.  **Register**:
    *   Ask user if they want to commit the rest of `.rokct/` (Memory/Sessions).

## Why?
This ensures you have a dedicated place to `Write` your thoughts without messing up the clean `SSO` submodule.
