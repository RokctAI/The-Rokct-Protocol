# Copyright (c) 2026 ROKCT INTELLIGENCE (PTY) LTD
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as published
# by the Free Software Foundation, version 3.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public License
# along with this program. If not, see <https://www.gnu.org/licenses/>.

# Copyright 2024 ROKCT INTELLIGENCE (PTY) LTD
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
    if BASE_DIR.parent == BASE_DIR:
        # No .rokct anywhere up the tree (misconfigured checkout) - fall
        # back to CWD, which CI sets to the repo root, instead of spinning
        # forever at the filesystem root.
        BASE_DIR = Path.cwd()
        break
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

    # Trigger Updaters — each isolated so one failing output (e.g. a
    # README regex mismatch) can't stop the published JSON from updating,
    # and vice versa. Every updater writes atomically, so a failure here
    # always leaves the previous published file intact.
    for label, update in (
        ("README", lambda: update_readme(README_PATH, stats)),
        (
            "audit log",
            lambda: update_audit_log(
                AUDIT_LOG_PATH,
                stats["Tenders"][0],
                stats["Tenders"][1],
                stats["Tenders"][2],
            ),
        ),
        ("meta.json", lambda: update_json_meta(META_PATH, stats, all_advanced_data)),
        (
            "tenders.json",
            lambda: update_json_tenders(TENDERS_PATH, REGISTRIES["Tenders"]),
        ),
    ):
        try:
            update()
        except Exception as e:
            print(f"[Error] {label} update failed (previous file kept): {e}")

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
