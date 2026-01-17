# SOP: Session Management

**Rule**: Use `sessions/` to log detailed work. Keep `memory.md` for high-level lessons only.

## 1. Start a Session
*   **When**: You start a new complex task (e.g., "Designing Auth System").
*   **Action**: Create `.rokct/sessions/YYYY-MM-DD_TaskName.md`.
*   **Log**: Record your steps, thoughts, and partial decisions there.

## 2. During the Session
*   **Focus**: Stay on the user's current focus.
*   **Detours**: If the user switches focus (e.g., "Fix .github first"), **stay in the current session**. Do not try to force them back to the original plan. Adapt the session log to the new reality.

## 3. End a Session (Critical)
*   **Trigger**: You believe the task is complete.
*   **ACTION**: **ASK THE USER**: "Are we done with this session? Shall I archive it and update Memory?"
*   **PROHIBITED**: Do **NOT** close a session or assume the user is ready to move on without explicit permission.
*   **Reason**: The user may have unvoiced concerns, side-tasks, or just want to "hang out" in the current context longer.

## 4. Archiving (Only after Approval)
*   **Extract**: Copy *only* reusable lessons to `.rokct/memory.md`.
*   **Close**: Mark the session file as `[CLOSED]`.
