# Tender Assistant Skill: Definitive Filling & Execution (ZA)
# Version: 1.0

**Philosophy**
A South African tender response is an exercise in "Defensive Compliance." The technical solution gets you the invitation, but the administrative rigour gets you the award. After studying over 500 registry tenders and analyzing specific documents from Eskom, Jhb Water, Musina, and dozens of Municipalities, this guide defines the exact tactical steps to pass the evaluation gates.

---

## 1. The Institutional Hierarchy of Compliance

### State-Owned Companies (Eskom, Transnet, RAF)
- **The Quality Gate (QMS):** Eskom and Transnet do not just want ISO certificates. They require a **draft Contract Quality Plan (CQP)** and evidence of **Internal Audit Procedures**. If you submit a generic manual, you score 0 on Quality.
- **Safety First (SHEQ):** The **Letter of Good Standing (COIDA)** must be valid at the time of *award*. If yours expires next month, renew it now.
- **CPA (Multi-year Bids):** For contracts >12 months, you must provide a **Contract Price Adjustment (CPA)** formula. A "Fixed Price" for a 5-year contract signals high financial risk and is often disqualified.

### Municipalities (Musina, Jhb Water, Khai/Garib, etc.)
- **The Initialling Law:** The "Overberg Rule"—initial the bottom right of **every single page** of the tender document, including the General Conditions of Contract (GCC) and all blank pages.
- **Locality Proof:** "Locality" is a major specific goal. You need:
    1. A municipal account for the **Company**.
    2. Municipal accounts for **Every Director** listed on the CSD.
    - *Common Fail:* Providing a utility bill older than 90 days.
- **Modern Evidence:** Many municipalities now require **Geotagged Site Imagery** (Pre, During, and Post installation) as part of the technical returnable to prevent fraud.

---

## 2. Mastering the SBD/MBD Suite

### SBD 1 / MBD 1: The Formal Offer
- **The "Match" Law:** The "Total Bid Price" on SBD 1 must match the **Form of Offer** and the **Pricing Schedule** to the cent. Discrepancies lead to "Ambiguity Disqualification."

### SBD 4 / MBD 4: The Integrity Gate
- **Audit-Proofing:** Evaluators run director ID numbers through the PERSAL system. Declare **everything**—even if a spouse is a part-time teacher. Disclosure > Discovery.

### SBD 6.1 / MBD 6.1: Preference Points
- **The Evidence Trap:** Claiming points for BBBEE or "Specific Goals" (Youth, Disability) without attaching the **CSD Summary** and **Medical Certificates/IDs** results in a 0 score for preference.

### SBD 6.2 / MBD 6.2: Local Content
- **The Annexure C Rule:** If the sector is "Designated" (Steel, Furniture, Transformers), signing the SBD 6.2 is not enough. You **must** attach a fully completed **Annexure C**. No Annexure C = Instant Disqualification.

---

## 3. Technical Functionality (The "Trinity of Evidence")

Evaluators score 0, 1, 3, or 5. To get a 5:
- **CVs:** Create a **Qualification Summary Table** at the start of the CV section that explicitly sums "Total Relevant Experience" for every required role.
- **Track Record:** For construction/EP, a "Reference Letter" is secondary. You need the **Trinity of Evidence**: (1) Appointment Letter, (2) Signed Service Level Agreement, and (3) Completion/Handover Certificate.
- **Methodology:** Mirror the client's "Scope of Work" numbering. If their SOW has Section 4.1 to 4.9, your methodology must have Section 4.1 to 4.9 exactly.

---

## 4. Automation Utility: `extract_requirements.py`
The repository includes a Python utility at `.rokct/scripts/tenders/extract_requirements.py` that uses `pdfplumber` to automatically extract:
1.  **Gate 1 Checklist:** Mandatory SBD/MBD forms and certificates.
2.  **Gate 2 Weights:** Scoring criteria and functionality thresholds.
3.  **Pricing System:** (80/20 vs 90/10).

**The Final Golden Rule:** If I read your SBD 1, your Pricing Schedule, and your Methodology, do they all tell the same story about the same scope at the same price? If yes, you have a winning bid.
