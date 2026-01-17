# SOP: Session Management

**Rule**: Use `sessions/` to log detailed work. Keep `memory.md` for high-level lessons only.

## 1. Start a Session
*   **When**: You start a new complex task (e.g., "Designing Auth System").
*   **Action**: Create `.rokct/sessions/YYYY-MM-DD_TaskName.md`.
*   **Log**: Record your steps, thoughts, and partial decisions there.

## 2. During the Session
*   **Focus**: Stay on the user's current focus.
*   **Detours (Minor)**: If the user makes a small request (e.g., "Fix .github first") related to the project but not the specific task, **stay in the current session**. Log it as a detour.
*   **Context Switch (Major)**: If the user requests a *completely unrelated* task:
    1.  **Ask**: "Is this a new session or related to the current task?" (If ambiguous).
    2.  **PAUSE/SWITCH**: Only if user confirms it is separate.
    3.  **Full Stack Exception**: If moving from Backend -> Frontend for the *same feature*, **STAY** in the current session. Context is needed.
*   **Do NOT mix contexts**: Truly unrelated tasks (e.g., "Fixing Billing" vs "Designing Chat") must remain separate.

## 3. End a Session (Critical)
*   **Trigger**: You believe the task is complete.
*   **ACTION**: **ASK THE USER**: "Are we done with this session? Shall I archive it and update Memory?"
*   **PROHIBITED**: Do **NOT** close a session or assume the user is ready to move on without explicit permission.
*   **Reason**: The user may have unvoiced concerns, side-tasks, or just want to "hang out" in the current context longer.

## 4. Archiving (Only after Approval)
*   **Extract**: Copy *only* reusable lessons to `.rokct/memory.md`.
*   **Close**: Mark the session file as `[CLOSED]`.
