# SOP: Initialize Rokct Protocol (V8)

**Trigger**: You start working on a project and do NOT see a `.rokct/` folder.

## Procedure

0.  **Sync Protocol (Always First)**:
    *   Run `git submodule update --remote The-Rokct-Protocol`
    *   This ensures you are working with the latest version of the protocol before proceeding.

1.  **Run Profile Init Script**:
    *   **Select profile based on your environment**:
        *   **Local**: Running on your physical computer (VS Code, Windsurf, CLI) with full network/drive access.
        *   **Web**: Running in a cloud sandbox (Jules, Replit, GitHub Codespaces) that only sees this repo.
    *   Execute the corresponding script:
        ```bash
        python profiles/local/initiate.py
        # or
        python profiles/web/initiate.py
        ```

2.  **Register Identity**:
    *   Ask: *"What should I call you?"* (e.g. "Ray").
    *   Save to `.rokct/memory.md`.

3.  **Configuration**:
    *   **Identity**: Read `git config user.email` (If Local).
    *   **Safe ID**: Generate `[EmailPrefix].[MD5(Domain)][:6]`.
    *   **Update**: Write **Safe ID** to `.rokct/memory.md`.
    *   **Privacy Rule**: Do **NOT** store the raw email in `memory.md`. Use the Safe ID only.

4.  **End Session**:
    *   When done, run `python profiles/local/end_protocol.py` (or `profiles/web/end_protocol.py` if one exists) to clean up pristine scaffold files.
