# SOP: Re-initialize Rokct Protocol (Local)

**Trigger**: The protocol has ended, or you are returning to a project where `.rokct/` already exists but needs re-initialization.

## Procedure

1.  **Run the Local Initiator**:
    *   **Windows/Unix/macOS**:
        ```bash
        python .rokct/initiate.py
        ```

2.  **Confirm Setup**:
    *   The script will update templates and ensure all required protocol files are present.

3.  **Done**:
    *   The protocol is now re-initialized. You can proceed to start a new session.
