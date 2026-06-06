# Licensed under the MIT License.
# Copyright 2024 RokctAI

import os
import yaml
from pathlib import Path
from datetime import datetime

def manage_sessions():
    """Reads session_state.md and ledger.md to manage active Jules sessions."""
    print("🗓️ Running Session Scheduler...")

    state_path = Path('.rokct/agent/session_state.md')
    ledger_path = Path('.rokct/agent/log/ledger.md')

    if not state_path.exists():
        print("⚠️ session_state.md not found.")
        return

    # 1. Parse session_state.md
    with open(state_path, 'r') as f:
        content = f.read()
        parts = content.split('---')
        if len(parts) < 3:
            print("⚠️ Invalid session_state.md format.")
            return
        state = yaml.safe_load(parts[1])

    # 2. Check for stalled cards in ledger
    stalled_found = False
    if ledger_path.exists():
        with open(ledger_path, 'r') as f:
            for line in f:
                if 'stalled' in line:
                    print(f"⚠️ STALLED JOB DETECTED: {line.strip()}")
                    stalled_found = True

    if stalled_found:
        print("ℹ️ Stalled jobs require human review. Reset iterations to 0 and status to 'writing' to resume.")

    # 3. Count currently active sessions from ledger
    active_count = 0
    if ledger_path.exists():
        with open(ledger_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            # Only look at the last few lines for active status (simplified)
            for line in lines[-20:]:
                if any(status in line for status in ['writing', 'evaluating', 'rules_generating']):
                    # This is a bit naive but works for a historical log check
                    active_count += 1

    print(f"📊 Active sessions detected: {active_count}")

    # 4. Update state
    if state.get('active_sessions') == active_count:
        print("ℹ️ No change in active sessions. Skipping update to reduce noise.")
        return

    state['active_sessions'] = active_count
    state['last_updated'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    # 5. Save updated state
    new_content = "---\n" + yaml.dump(state) + "---\n"
    with open(state_path, 'w') as f:
        f.write(new_content)

    print("✅ session_state.md updated.")

if __name__ == "__main__":
    manage_sessions()
