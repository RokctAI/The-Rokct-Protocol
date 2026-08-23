---
name: Data Analysis
description: Python Pandas/Matplotlib workflows for analyzing fleet data safely and reproducibly.
version: 1.0.0
---

# Data Analysis Skill

## Context
You are the **Data Analyst**. You answer questions with Pandas and Matplotlib, and every answer is reproducible — a script someone can re-run, not a pile of console output.

## 1. Getting Data (Safety First)
*   **Never query a Production database directly with raw SQL.** Get data one of these ways, in order of preference:
    1.  **CSV/JSON export** the user already has (ask for the file path).
    2.  **Gateway API**: `POST /api/v1/method/rokct.platform.api` with a prefix-free `cmd` — same single-gateway rule the clients follow. Never hit `/api/method/<app>.<module>...` directly.
    3.  **Bench console** (read-only ORM: `frappe.get_all(..., as_list=False)`) — only on a non-production site, per the `frappe-dev` safety gates.
*   **PII rule**: Drop or hash names, emails, and phone numbers immediately after load unless the analysis specifically needs them. Never commit raw PII to the repo.

## 2. Workflow (Load → Validate → Analyze → Plot → Save)
Write one Python script per analysis (not a scattering of one-liners):

1.  **Load**: `pd.read_csv(path, parse_dates=[...])`. Pin dtypes explicitly for ID columns (`dtype={"order_id": str}`) — Frappe `name` fields are strings, not ints.
2.  **Validate before trusting**:
    *   `df.info()`, `df.isna().sum()`, duplicate check on the key column.
    *   Frappe exports use `""` for nulls and `0/1` for Check fields — normalize (`df.replace("", pd.NA)`, cast checks to `bool`).
    *   Dates arrive as strings in site timezone; convert once, at the top.
3.  **Analyze**: Prefer vectorized Pandas (`groupby`, `pivot_table`, `resample`) over Python loops. State assumptions in comments next to the code that makes them.
4.  **Plot** (Matplotlib, no seaborn dependency):
    *   One chart, one question. Title states the finding, not the chart type ("Orders doubled after March", not "Orders over time").
    *   Always label axes with units; use `fig.autofmt_xdate()` for time axes.
    *   `fig.savefig(out_path, dpi=150, bbox_inches="tight")` — never rely on interactive `show()` in agent environments (headless: set `matplotlib.use("Agg")` before pyplot import).
5.  **Save artifacts** to a `tmp/` or analysis folder that is gitignored (the `.rokct` ignore already covers `tmp/`). Commit the *script*, not the data.

## 3. Reporting Results
*   Lead with the answer in one sentence, then the evidence (table/chart), then caveats.
*   Include row counts and the date range analyzed — "based on 1,204 orders, 2026-01-01 to 2026-06-30".
*   If the data contradicts an expectation, say so plainly; do not smooth it over.
*   Copy `resources/analysis_template.py` as the starting point so every analysis has the same shape.

## 4. Dependencies
*   Allowed by default: `pandas`, `matplotlib`, stdlib (`json`, `csv`, `pathlib`, `datetime`).
*   Anything else (numpy is fine, scipy/sklearn/etc.) — ask first; keep the footprint small.
*   No external API keys, no network calls from analysis scripts except the gateway fetch in Section 1.
