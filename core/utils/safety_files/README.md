# Safety Files

Compiles a contractor's site safety file from one JSON profile. Pure Python, standard library only, no AI.

Buyers such as ACSA, Transnet/TNPA, Eskom, water boards and municipalities ask for a health and safety file on works and site-based contracts, usually before work starts. This tool lays that file out from the contractor's own information.

## Status: draft templates, legal review pending

The section wording in `templates.py` has **not** been reviewed by a registered South African OHS practitioner, and the notice wording has not been checked by a lawyer. Until that review is recorded in `templates.REVIEW`:

- every page of the binder carries a "not yet reviewed" header and the cover carries the full notice;
- the report's `status` is always `draft`, and the gap report lists "Practitioner review" as open.

The tool never says a file "complies" with the OHS Act, the Construction Regulations or a buyer's specification. A supporting document (COIDA letter, insurance, and so on) shows as provided only when the profile gives a reference, a listed file exists, and an expiring document has a future expiry date. Hazards, risk ratings and controls are always the user's own entries.

## Use

```bash
pip install core/utils/safety_files
safetyfiles status --profile profile.json            # gaps and expiries as JSON
safetyfiles build  --profile profile.json --out out/ # binder.md, binder.pdf, gap_report.json, expiry_log.json
```

From Python (what an SDK gateway cmd calls):

```python
from safetyfiles import builder
report = builder.build(profile, out_dir, base_dir=folder_with_uploads)
report = builder.status(profile)  # writes nothing
```

The tool keeps no state. The calling SDK owns the records (registers, training, uploads) and passes them in on every run.

## Profile

See `examples/sample_profile.json` (demo data only). Keys: `jurisdiction` (only `ZA`), `company`, `site`, `policy`, `people`, `hazards`, `procedures`, `training`, `medicals`, `registers.ppe|equipment|visitors`, `documents` (`type` is one of the keys in `templates.EVIDENCE_TYPES`), `incidents`.

## Output

- **Binder**: cover with open items, an index with page numbers, then one section per page: contractor and site details, policy, responsible people, risk assessment, safe work procedures, training, medicals, PPE, equipment and visitor registers (with blank rows for site use), incident report form, and supporting documents.
- **Gap report**: missing sections, an unsigned policy, supporting documents that are absent, expired or have no file, and the open practitioner review.
- **Expiry log**: training, medicals, equipment inspections and documents, each marked `expired`, `due_soon` (within 60 days) or `ok`.

## Tests

```bash
python -m pytest core/utils/safety_files/tests -q
```
