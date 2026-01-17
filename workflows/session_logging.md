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

## 4. Long Sessions (The "Rolling" Strategy)
*   **Trigger**: If the session log exceeds ~200 lines (or feels too large).
*   **Action**:
    1.  **Summarize**: Write a "Context Anchor" (Current Status, Decisions, Next Steps).
    2.  **Archive**: Rename the file to `TaskName_Part1.md`.
    3.  **Continue**: Create `TaskName_Part2.md`. Paste the "Context Anchor" at the top.
*   **Deep Retrieval**: The archived parts (`Part1`, `Part2`) are **NOT DEAD**. They are "Reference Library".
    *   If you need a specific detail from weeks ago, **READ** the archived file.
    *   Do not guess. Go back and check the logs.

## 5. End a Session (Critical)
*   **Trigger**: You believe the task is complete.
*   **ACTION**: **ASK THE USER**: "Are we done with this session? Shall I archive it and update Memory?"
*   **PROHIBITED**: Do **NOT** close a session or assume the user is ready to move on without explicit permission.
*   **Reason**: The user may have unvoiced concerns, side-tasks, or just want to "hang out" in the current context longer.

## 6. Closing (Only after Approval)
*   **Extract**: Copy *only* reusable lessons to `.rokct/memory.md`.
*   **Close**: Mark the session file as `[CLOSED]`.
