\# SOP: Update Protocol



\*\*Trigger\*\*: Called by `start\_session.md` when `The-Rokct-Protocol/version.json` differs from `.rokct/protocol\_version.json`.



\## Procedure



1\.  \*\*Recopy Structural Files\*\*:

&nbsp;   \*   Overwrite `.rokct/profiles.md` from `The-Rokct-Protocol/profiles/\[current profile]/rules.md`.

&nbsp;       \*   Read `.rokct/profiles.md` to determine current profile (Local or Web) before overwriting.

&nbsp;   \*   Overwrite `.rokct/workspace\_handshake.md` from `The-Rokct-Protocol/profiles/local/workflows/workspace\_handshake.md` (Local only).

&nbsp;   \*   Overwrite `.rokct/skills/` from `The-Rokct-Protocol/core/skills/` (Universal).

&nbsp;   \*   (If Local) Overwrite `.rokct/skills/` with additions from `The-Rokct-Protocol/profiles/local/skills/`.



2\.  \*\*Do NOT touch\*\*:

&nbsp;   \*   `.rokct/memory.md` — live user data

&nbsp;   \*   `.rokct/decision\_log.md` — live project data

&nbsp;   \*   `.rokct/active\_session.txt` — live session state

&nbsp;   \*   `.rokct/sessions/` — session history

&nbsp;   \*   `.rokct/project\_map.md` — live project data

&nbsp;   \*   `.rokct/agent/` — agent queue and ledger



3\.  \*\*Update Version\*\*:

&nbsp;   \*   Copy `The-Rokct-Protocol/version.json` → `.rokct/protocol\_version.json`

&nbsp;   \*   This marks the update as complete so it won't run again until the next protocol release.



4\.  \*\*Log the Update\*\*:

&nbsp;   \*   Append to `.rokct/memory.md` under Lessons Learned:

&nbsp;       \*   `\*\*\[Date]\*\* - Protocol updated to v\[version].`

