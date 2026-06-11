# Opportunities Registry Automation Skill

This skill contains the automation, scraper, and maintenance engine for the RokctAI Opportunities Registry.

## Directory Structure
- `scripts/`: Implementation scripts for tenders, grants, equity, registry sync, and link checks.
  - `equity/`: Sync and verify equity funding sources.
  - `grants/`: Scraping and loading grants data.
  - `tenders/`: Scrapes tender data from OCDS and processes PDFs.
  - `registry_orchestrator/`: Re-indexes and heals the registry.
  - `eeip/`: Sync EEIP opportunities.
  - `maintenance/`: Purges expired tenders.
  - `ci/`: Link checking.
  - `response_kits/`: Handles response templates.
