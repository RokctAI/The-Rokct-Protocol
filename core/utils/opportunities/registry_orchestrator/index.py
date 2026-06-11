# Licensed under the MIT License.
# Copyright 2024 RokctAI

from pathlib import Path
from datetime import datetime
from scanners import scan_registry
from updaters import update_readme, update_audit_log, update_json_meta, save_jules_todo

# --- CONFIGURATION ---
BASE_DIR = Path(__file__).resolve()
while not (BASE_DIR / '.rokct').exists():
    BASE_DIR = BASE_DIR.parent

REGISTRIES = {
    "Equity": BASE_DIR / "01_equity",
    "Grants": BASE_DIR / "02_grants",
    "Tenders": BASE_DIR / "03_tenders",
    "EEIP": BASE_DIR / "04_eeip"
}
README_PATH = BASE_DIR / "README.md"
AUDIT_LOG_PATH = BASE_DIR / "03_tenders" / "registry_audit_log.md"
META_PATH = BASE_DIR / "published" / "api" / "meta.json"

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
        total, verified, cats, advanced, todo = scan_registry(name, path, BASE_DIR)
        stats[name] = (total, verified, cats, advanced, todo)

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
    update_audit_log(AUDIT_LOG_PATH, stats["Tenders"][0], stats["Tenders"][1])
    update_json_meta(META_PATH, stats, all_advanced_data)

    # Save specialized task queues
    save_jules_todo(BASE_DIR, tenders_todo, filename="todo.json", title_prefix="Tender Enrichment Queue")
    save_jules_todo(BASE_DIR, equity_todo, filename="equity_todo.json", title_prefix="Equity Audit Queue")
    save_jules_todo(BASE_DIR, grants_todo, filename="grants_todo.json", title_prefix="Grants Verification Queue")
    save_jules_todo(BASE_DIR, eeip_todo, filename="eeip_todo.json", title_prefix="EEIP Verification Queue")
    
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Orchestration Complete.")

if __name__ == "__main__":
    run_orchestration()
