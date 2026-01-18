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
    *   **Logic**:
        *   Do you generally have unrestricted Internet/Push access? -> **Local**.
        *   Are you in a restricted Cloud Sandbox? -> **Web**.
    *   **Action**: If unsure, **ASK THE USER**: *"Am I identifying as a [Local] agent or a [Web] agent?"*
    *   **install**: Copy `The-Rokct-Protocol/profiles/[selection]/rules.md` -> `.rokct/profiles.md`.
    *   (If Local) Copy `The-Rokct-Protocol/profiles/local/skills/` -> `.rokct/skills/`.

4.  **Register Identity**:
    *   Ask: *"What should I call you?"* (e.g. "Ray").
    *   Save to `.rokct/memory.md`.


5.  **Configuration**:
    *   **Identity**: `git config user.email` (If Local).
    *   **Safe ID**: Generate `[EmailPrefix].[MD5(Domain)][:6]`.
    *   **Update**: Write to `.rokct/memory.md`.

6.  **Team Safety**:
    *   Create `.rokct/.gitignore`.
    *   Add `active_session.txt`.
