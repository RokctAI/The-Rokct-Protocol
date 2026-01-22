# SOP: Setup Workspace Root

**Trigger**: You are a Local Agent and you want to enable "Workspace Awareness" for your multi-repo setup.

## Procedure
1.  **Navigate**: Go to your Workspace Root (Parent of your repos).
    *   e.g. `cd C:\Users\Ray\Work\Repos`
2.  **Create Config**:
    *   Create a folder named `.rokct`.
    *   Create `.rokct/sessions/` directory.
3.  **Initialize Memory**:
    *   Create `.rokct/memory.md` (Copy form `The-Rokct-Protocol/core/templates/memory.md`).
    *   Create `.rokct/active_session.txt` (Empty).

## Verification
1.  Go to a child repo (e.g. `rcore`).
2.  Run `Get-ChildItem ../.rokct`.
3.  If successful, Workspace Mode is ready to be detected.
