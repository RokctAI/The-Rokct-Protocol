# Copyright (c) 2026 RokctAI
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

# Licensed under the MIT License.
# Copyright 2024 RokctAI
# compliance-ignore-file: structural-special-dirs
# These scripts live under .rokct/ ONLY at runtime: initiate.py fetches
# this canonical copy from The-Rokct-Protocol into .rokct/skills/ at the
# start of a workflow run, and end_protocol.py deletes it at the end.
# Nothing here is committed under .rokct/ in this repo (that path is
# gitignored) - this IS the checked-in source, at its permanent,
# allowed location.

from pathlib import Path
from datetime import datetime
from scanners import scan_registry
from updaters import (
    update_readme,
    update_audit_log,
    update_json_meta,
    update_json_tenders,
    save_jules_todo,
)

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve()
while not (BASE_DIR / ".rokct").exists():
    BASE_DIR = BASE_DIR.parent

REGISTRIES = {
    "Equity": BASE_DIR / "01_equity",
    "Grants": BASE_DIR / "02_grants",
    "Tenders": BASE_DIR / "03_tenders",
    "EEIP": BASE_DIR / "04_eeip",
}
README_PATH = BASE_DIR / "README.md"
AUDIT_LOG_PATH = BASE_DIR / "03_tenders" / "registry_audit_log.md"
META_PATH = BASE_DIR / "published" / "api" / "meta.json"
TENDERS_PATH = BASE_DIR / "published" / "api" / "tenders.json"


def run_orchestration():
    print(f"[{datetime.now().strftime('%H:%M:%S')}] --- Registry Orchestration ---")

    stats = {}
    tender_categories = {}
    all_advanced_data = {}

    tenders_todo = []
    equity_todo = []
    grants_todo = []
    eeip_todo = []

    for name, path in REGISTRIES.items():
        total, verified, incomplete, cats, advanced, todo = scan_registry(
            name, path, BASE_DIR
        )
        stats[name] = (total, verified, incomplete, cats, advanced, todo)

        if name == "Tenders":
            tender_categories = cats
            all_advanced_data = advanced
            tenders_todo = todo
        elif name == "Equity":
            equity_todo = todo
        elif name == "Grants":
            grants_todo = todo
        elif name == "EEIP":
            eeip_todo = todo

    # Trigger Updaters
    update_readme(README_PATH, stats)
    update_audit_log(
        AUDIT_LOG_PATH, stats["Tenders"][0], stats["Tenders"][1], stats["Tenders"][2]
    )
    update_json_meta(META_PATH, stats, all_advanced_data)
    update_json_tenders(TENDERS_PATH, REGISTRIES["Tenders"])

    # Save specialized task queues
    save_jules_todo(
        BASE_DIR,
        tenders_todo,
        filename="todo.json",
        title_prefix="Tender Enrichment Queue",
    )
    save_jules_todo(
        BASE_DIR,
        equity_todo,
        filename="equity_todo.json",
        title_prefix="Equity Audit Queue",
    )
    save_jules_todo(
        BASE_DIR,
        grants_todo,
        filename="grants_todo.json",
        title_prefix="Grants Verification Queue",
    )
    save_jules_todo(
        BASE_DIR,
        eeip_todo,
        filename="eeip_todo.json",
        title_prefix="EEIP Verification Queue",
    )

    print(f"[{datetime.now().strftime('%H:%M:%S')}] Orchestration Complete.")


if __name__ == "__main__":
    run_orchestration()
