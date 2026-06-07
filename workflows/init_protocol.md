# SOP: Initialize Rokct Protocol

**Trigger**: You start working on a project and do NOT see a `.rokct/` folder.

## Procedure

1.  **Run the Installer**:
    *   **Windows (PowerShell)**:
        ```powershell
        iwr -useb https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.ps1 | iex
        ```
    *   **Unix / macOS / Linux**:
        ```bash
        curl -sSL https://raw.githubusercontent.com/RokctAI/The-Rokct-Protocol/main/install.sh | bash
        ```

2.  **Answer the Prompts**:
    *   The installer will ask if this is for a **Local** (desktop) or **Web** (cloud sandbox) environment.
    *   If prompted, enter the parent workspace repo (e.g. `Owner/Repo`) or press Enter for standalone mode.

3.  **Done**:
    *   The installer downloads and runs the matching `initiate.py`, which:
        *   Creates `.rokct/` in your project root.
        *   Copies templates, skills, and rules into `.rokct/`.
        *   Sets up workspace config if a parent repo was provided.
        *   Copies `end_protocol.py` and `initiate.py` into `.rokct/` for later use.

4.  **When Finished**:
    *   Run `python .rokct/end_protocol.py` to clean up pristine scaffold files.
