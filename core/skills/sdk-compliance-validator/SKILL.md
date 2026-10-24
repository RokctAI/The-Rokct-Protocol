---
name: sdk-compliance-validator
description: Run sdk_validator.py --compliance before pushing any SDK change and fix violations in the files you touched.
version: 1.0.0
---

# SDK compliance validator
**When:** before pushing any SDK change, and when Ray says "the sdk validator will check".

1. Clone or pull RokctAI/shared-workflows into /home/user/shared-workflows.
2. Run `python3 scripts/sdk_validator.py --compliance --root <repo>` before and after your change, and report both.
3. Fix every violation in the files you touched. For example, `obs-db-tracing` on DB reads needs a structured stderr `[Trace: <id>]` line, as `validate_kyc` does.
4. The validator writes logs, docs and `.rokct/evidence/` into the tree. Remove them or exclude them locally (`.git/info/exclude`), and never commit them.
