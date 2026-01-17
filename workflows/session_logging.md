# SOP: Session Management

**Rule**: Use `sessions/` to log detailed work. Keep `memory.md` for high-level lessons only.

## 1. Start a Session
*   **When**: You start a new complex task (e.g., "Designing Auth System").
*   **Action**: Create `.rokct/sessions/YYYY-MM-DD_TaskName.md`.
*   **Log**: Record your steps, thoughts, and partial decisions there.

## 2. During the Session
*   **Focus**: Stay on the user's current focus.
*   **Detours (Minor)**: If the user makes a small request (e.g., "Fix .github first") related to the project but not the specific task, **stay in the current session**. Log it as a detour.
*   **Context Switch (Major)**: If the user requests a *completely unrelated* task (e.g., stopping UI work to build a backend feature):
    1.  **PAUSE**: Write `[PAUSED]` at the end of the current log.
    2.  **SWITCH**: Update `.rokct/active_session.txt` to point to a NEW or different session file (e.g., `sessions/Backend_Feature.md`).
    3.  **RESUME**: When the user returns to the UI, switch the pointer back to the original file.
*   **Do NOT mix contexts**: Never put Backend Feature logs into a UI Design session file.

## 3. End a Session (Critical)
*   **Trigger**: You believe the task is complete.
*   **ACTION**: **ASK THE USER**: "Are we done with this session? Shall I archive it and update Memory?"
*   **PROHIBITED**: Do **NOT** close a session or assume the user is ready to move on without explicit permission.
*   **Reason**: The user may have unvoiced concerns, side-tasks, or just want to "hang out" in the current context longer.

## 4. Archiving (Only after Approval)
*   **Extract**: Copy *only* reusable lessons to `.rokct/memory.md`.
*   **Close**: Mark the session file as `[CLOSED]`.
