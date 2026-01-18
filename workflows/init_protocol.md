# SOP: Initialize Rokct Protocol (V8)

**Trigger**: You start working on a project and do NOT see a `.rokct/` folder.

## Procedure
1.  **Create Directory**: Create `.rokct` in the project root.

2.  **Load Core (Universal)**:
    *   Copy `The-Rokct-Protocol/core/templates/memory.md` -> `.rokct/memory.md`
    *   Copy `The-Rokct-Protocol/core/templates/decision_log.md` -> `.rokct/decision_log.md`
    *   Copy `The-Rokct-Protocol/core/templates/project_map.md` -> `.rokct/project_map.md`
    *   Copy `The-Rokct-Protocol/core/templates/active_session.txt` -> `.rokct/active_session.txt`
    *   Copy `The-Rokct-Protocol/.cursorrules` -> `./.cursorrules`.

3.  **Load Profile (Identity)**:
    *   **Logic**: Agents struggle to self-identify (Sandbox feels "Local" to them).
    *   **Action**: Ask yourself the following **Strict Definitions**:
        > *   **Local Agents**: Run on the user's physical computer (VS Code, Windsurf, CLI) and have access to the user's full network/drive.
        > *   **Web Agents**: Run in a cloud sandbox (Jules, Replit, GitHub Codespaces) and only see this repo.
    *   **Decision**:
        *   If you are running in a Cloud Sandbox (Jules) -> **Web**.
        *   If you are running on the User's Windows/Mac Desktop -> **Local**.
    *   **install**: 
        *   Copy `The-Rokct-Protocol/profiles/[selection]/rules.md` -> `.rokct/profiles.md`.
        *   Copy `The-Rokct-Protocol/core/skills/` -> `.rokct/skills/` (Universal).
        *   (If Local) Copy `The-Rokct-Protocol/profiles/local/skills/` -> `.rokct/skills/`.

4.  **Register Identity**:
    *   Ask: *"What should I call you?"* (e.g. "Ray").
    *   Save to `.rokct/memory.md`.


5.  **Configuration**:
    *   **Identity**: Read `git config user.email` (If Local).
    *   **Safe ID**: Generate `[EmailPrefix].[MD5(Domain)][:6]`.
    *   **Update**: Write **Safe ID** to `.rokct/memory.md`.
    *   **Privacy Rule**: Do **NOT** store the raw email in `memory.md`. Use the Safe ID only.

6.  **Team Safety**:
    *   Create `.rokct/.gitignore`.
    *   Add `active_session.txt`.
