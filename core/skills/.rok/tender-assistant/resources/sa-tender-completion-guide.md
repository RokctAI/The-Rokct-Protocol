# The South African Tender Pack: A Complete Working Guide

*Version 2.0. This guide was built from a systematic analysis of ~1,198 real South African tender packs — 37 analysed in depth plus a large-scale delta verification across the wider corpus (2026-08) — spanning national and provincial departments, municipalities, and state-owned entities. It is practical guidance distilled from that corpus, not legal advice; always verify against the specific pack in front of you and take professional advice where the stakes warrant it.*

**Who this is for:** a capable person or small business preparing a bid for any South African public-sector tender — municipal, provincial, national, or state-owned entity. It assumes no procurement-law background.

**Where it comes from:** a systematic deep analysis of ~37 real tender packs spanning municipalities (Bergrivier to eThekwini), provinces (Free State, KZN, Limpopo, Northern Cape), national departments and colleges, and SOEs (Eskom, Transnet, SANRAL, ACSA, DBSA, and others), then verified and recalibrated against a corpus of ~1,198 packs. Where a rule is universal across that corpus, the guide says so. Where it is buyer-specific, the guide says that too — **never assume a rule from one pack applies to another.**

**The one-sentence thesis:** most bids do not lose — they die. They die on formalities: a missing certified copy, an unpriced line, an unsigned form, a bid box locked one second after noon. Winning starts with not dying, and the rest of the margin comes from evidence-backed functionality scores and disciplined pricing.

---

## 1. Start here: identify what kind of pack you are holding

Before you fill in anything, spend the first hour classifying the pack. Almost everything downstream — which forms, which registrations, which traps — follows from this triage.

### 1.1 Formal bid or RFQ? Judge by content, not the cover page

The label is unreliable. One pack in the corpus titled "RFQ" (acsa-power-retic-maint-rfq) was in fact a full CIDB-governed construction bid with a 70% functionality threshold, NEC3 contract, and compulsory briefing. Classify by what is inside:

- **Full formal bid** if you see any of: CIDB Standard Conditions of Tender ("F-clauses"), a scored functionality matrix with a minimum threshold, an NEC or GCC contract form, a compulsory briefing/site meeting, or a large returnable-forms schedule.
- **Simple RFQ** if you see: a short form set (sometimes only SBD 4 + SBD 6.1), no functionality scoring, 60–90 day validity, and email or bid-box submission. The core kill-rules (late = dead, defaulters lists, declaration forms) still apply in full.
- **RFI** — market sounding: no returnables, but register your interest or you won't receive addenda or the later closed process.
- **EOI** — ranges from a non-binding market test (Eskom) to a full three-phase scored pipeline; judge by content, exactly as with the RFQ label.

And the label warning is not construction-specific: SOE "RFQs" can carry full scored functionality gates (Transnet crane repair, SABC).

### 1.2 SBD or MBD? The forms prefix is the fastest regime identifier

- **MBD forms → municipal regime** (MFMA + Municipal SCM Regulations). Expect the full spread of separate forms (MBD 1, 2, 3.x, 4, 5 if over R10m, 6.1, 7, 8, 9, sometimes 10), plus municipal-only requirements: rates-and-taxes clearance for the company **and every director**, and often a strict returnable-documents checklist that is itself fatal if not followed (bergrivier: "Non adherence to this checklist will invalidate your offer!").
- **SBD forms → national/provincial/PFMA regime**. Modern SBD packs are consolidated: SBD 1 + 4 + 6.1 (+3.x), with the old SBD 8 and 9 content absorbed into the post-2022 SBD 4 Bidder's Disclosure.
- **Buyer-branded forms wrapping SBD content → SOE with its own SCM policy** (SANRAL's Form D1 = SBD 6.1; Tshwane's RD.A series wraps MBD forms; Eskom uses Annexures A–J). **Match forms by title and purpose, never by number** — SBD 5 (National Industrial Participation) and MBD 5 (procurement above R10m declaration) are entirely different forms, and one pack's "SBD 8" was actually the GCC.

**Trap:** entity names lie. Joburg Theatre "(SOC) Ltd" is a *municipal* entity running MBD forms; SALGA serves municipalities but is a PFMA Schedule 3A entity on SBD forms. Check which Act the conditions cite, not the buyer's name.

### 1.3 Which sector regime is layered on top?

- **Construction/works:** look for a CIDB grading requirement (e.g. "6CE", "7GB", "3ME") in the eligibility clause **first**. If you don't hold that grade, active and in good standing, do not proceed — this is the earliest possible gate as a default assumption, but check the eligibility clause for a registration grace period before self-eliminating: some buyers (Eskom, Joe Gqabi DM) accept bidders "capable of being registered within 21 working days" of closing — proof of application at closing, registration by award. Housing adds NHBRC; expect COIDA, OHS s37(2) agreements, performance guarantees, and Bills of Quantities. **EPWP/labour-intensive roadworks add their own overlay** (typical for municipal roads, confirmed at kokstad): supervisory staff must hold a CETA-accredited NQF Level 5 labour-intensive-construction (LIC) qualification — an eligibility and scoring item that takes **months** to acquire, not weeks — plus binding job-creation declarations (minimum local-labour content, e.g. 7.71% of contract value, with financial penalties for shortfall) and EPWP data-reporting duties tied to payment. Some packs also demand a bid-stage Health & Safety Plan prepared against the pack's H&S Specification, and a Quality Control Plan that is scored (sometimes with ISO 9001 bonus points) — check for both even if the pack's own checklist omits them.
- **Professional services:** a named statutory registration (ECSA, SACQSP, SACPCMP, LPC + Fidelity Fund, HPCSA, SAIOSH) plus Professional Indemnity insurance at a stated cover level are gates; CVs and registration certificates then double as the scored functionality evidence.
- **Security:** PSIRA grades for the company AND directors (vaalcentral). **ICT:** OEM/partner authorisation letters, certified engineers, POPIA/hosting rules, sometimes a live demo/POC. **Anything touching a regulated profession:** the regulator's registration is a hard pass/fail gate, usually for named individuals too.

### 1.4 The day-one triage read (do this before drafting anything)

- [ ] Find the closing date, time, and **exact** submission channel (which physical box, which portal, which email address). Sweep for internal contradictions across **all** requirement classes, not just dates: conflicting dates/times/validity periods (8+ packs), VAT basis, preference system, functionality thresholds and their point bases, escalation rules, document-freshness windows, quotas, and broken cross-references (a document referenced to "Section J" may actually sit in Section K). Where two tender-specific clauses conflict, satisfy the **strictest** reading and log each conflict as a written clarification with the SCM contact.
- [ ] Find the **clarification cut-off**: most packs only oblige the buyer to answer questions received a set number of working days before closing. Read the pack's own clause every time: CIDB packs run 3–5 working days, the Tender Data frequently overrides the CIDB-standard five, the bidder-question cut-off and the addenda-issuance cut-off can be two different dates, and some buyers anchor the window to the briefing date, not the closing date. Diarise each separately and front-load every contradiction/VAT/threshold question so it is lodged in writing before that date — a question discovered during final assembly is a question you will have to guess at.
- [ ] Find out whether a briefing/site meeting exists and whether it is compulsory. Diarise it immediately — for construction and site-based services, assume compulsory until proven otherwise.
- [ ] Extract every clause containing "disqualif", "non-responsive", "invalid", "will not be accepted", "will not be considered", "rejected", "compulsory", "mandatory", "eligib", "qualify"/"qualifying criteria", and "shall/must … to be" into a single gate register with an owner and due date per item. **Keyword extraction alone is not enough for eligibility gates:** the hardest requirements often live under bland eligibility language (CIDB packs put them in clause F.2.1 — grading, JV formalities, personnel qualifications, financial capacity). Read the eligibility/qualifying-criteria clause of any CIDB or construction pack **in full** and register every criterion in it as a hard gate.
- [ ] Find the functionality matrix (if any) and its threshold. Compute your realistic score before committing bid costs (see Section 5).
- [ ] Build your **master returnables checklist from a page-by-page sweep of the whole pack** — flag every "returnable", "schedule", "form", "attach", "submit with the tender" — then reconcile it against the pack's own checklist(s). Pack checklists are frequently incomplete (they can omit entire schedule series that are elsewhere fatal or score-bearing), so treat them as a **floor you must also complete**, never as the master inventory. Where a pack checklist demands a form the pack does not actually contain, request the form in writing from the SCM contact before the clarification cut-off and keep proof of the request.
- [ ] Note the bid validity period — mode 90 days; 30–180 days all common (120 nearly as common as 90; 180 calendar or business days at SOEs/metros; 30 at small RFQs; outliers to 365). Some packs ask YOU to state a validity. If the pack states two different numbers — about one pack in ten does — price for the longer one and ask the clarification question in writing.
- [ ] Check for a document purchase fee or portal pre-registration that gates access itself (fees run R300–R2,300+ across the corpus; DBSA only issues its submission link after an emailed request).

---

## 2. HOW BIDS DIE — the disqualification league table

Across the corpus, these are the causes that actually kill bids, ranked by how often they appear as explicit disqualification triggers. Read this section twice. Every later section exists to defend against something on this list.

| Rank | Cause | How common |
|---|---|---|
| 1 | **Late submission** — measured in seconds, zero tolerance | Universal (every pack that states bid conditions). One buyer (DBSA) reserves sole discretion to accept a late bid where the lateness was the buyer's own fault, box access was denied, or a major incident occurred — never plan on it |
| 2 | **Missing/incomplete/unsigned mandatory returnables** | Universal in effect |
| 3 | Bidder or a director on the **Register for Tender Defaulters / List of Restricted Suppliers** | Universal in effect |
| 4 | **Fraudulent preference-points claim** (up to 10-year blacklisting) | Common |
| 5 | **False or incomplete SBD/MBD 4 disclosure** | Common |
| 6 | **Collusion / attempts to influence** (incl. untrue SBD/MBD 9) | Universal in effect |
| 7 | **Uninitialled corrections, Tipp-Ex, pencil, wrong ink** | About half of packs |
| 8 | Submission by **fax/email/wrong channel** | Recurring — a rare exception exists (SIU accepts faxed and emailed tenders); channel rules are per-pack even here |
| 9 | **Incomplete pricing schedule** — blanks, dashes, unpriced lines | About half |
| 10 | **Unsigned Form of Offer / no proof of signing authority** | About a third |
| 11 | **Functionality score below threshold** | Wherever functionality is scored |
| 12 | **Qualified bid / own conditions attached** — non-responsive; treat "never qualify" as the default (a rare pack expressly permits qualifying the bid where an alteration is necessary — DWS boilerplate) | About a third |
| 13 | **Retyped or photocopied forms** instead of the official ones | About a third |
| 14 | **Missed clarification/cure window** (24 hours – 7 days) | About a third |
| 15 | **Missed or arrived late at compulsory briefing** | Wherever a briefing is held |

The remaining tail: wrong tender box or unsealed/mislabelled envelope, page removal or tampering, CSD inactive at closing, persons in the service of the state, municipal rates in arrears (municipal buyers), sector-registration lapses, pricing leaking into a technical envelope, JV defects (no signed JV agreement before submission), missing addenda acknowledgements, and **unsanctioned alternative offers** — distinct from a qualified bid: several buyers ban alternatives outright (acsa-power, mkhondo, tshwane), sanral allows them only with prior permission AND a compliant base offer submitted alongside, and kokstad treats offering fixed rates in lieu of the CPA escalation formula as a prohibited alternative. **One bid per entity:** submitting more than one bid (solo or via JV) voids ALL your submissions, and JVs sharing directors/shareholders with another bidder are ineligible (eThekwini, SANRAL, Eskom) — check related-company exposure before two group companies bid the same tender. Some buyers add cooling-off bans for ex-employees/board members (SABC: 12 months; 5 years if dismissed).

**Five verbatim warnings worth memorising:**

> "The tender box shall be locked at exactly 12:00 Noon and tenders arriving only a second after 12:00 or any time thereafter will not be accepted under any circumstance." (joburgtheatre)
>
> "Reject a non-responsive tender offer, and not allow it to be subsequently made responsive by correction or withdrawal of the non-conforming deviation." (CIDB standard wording, multiple packs)
>
> "Items against which N/A, left blank or – (dash) is entered are to be considered as incomplete and will also invalidate the tender." (raynkonyeni-mgodlwa-bridge)
>
> "I understand that the accompanying bid will be disqualified if this disclosure is found not to be true and complete in every respect." (SBD/MBD 4, verbatim in 10+ packs)
>
> "Digitally completing any part of the returnable documents will not be accepted and will lead to disqualification." (fs-publicworks — a buyer-specific handwriting rule; check your pack)

Two structural insights: **first**, buyers split into "second-chance" and "no-second-chance" cultures — and the split tracks buyer sophistication, not regime. Mature SOEs and large metros (Eskom, Transnet, SANRAL, City of Tshwane — a metro municipality running an SOE-style tiered regime) tier their returnables — some fatal at closing, some curable on request within 48 hours to 7 days — and several provincial buyers (FS Public Works, Limpopo) also run 7-day cure windows. Smaller municipal and provincial buyers are the ones most reliably single-shot: everything must be in the box at closing. Never assume a cure window exists. **Second**, even where a cure window exists, it is the "second chance you can still blow" — missing a 48-hour clarification deadline converts a curable defect into disqualification. Monitor the named contact email daily after submission.

---

## 3. The registrations you need BEFORE bidding

Split these into the universal set (keep permanently green — required in effectively every pack) and the conditional set (required by sector or buyer type).

### 3.1 The universal hard gates — maintain these continuously, not per-bid

- [ ] **CSD (Central Supplier Database) registration** — appears in essentially every full pack (30/37 in the corpus). "No award will be made to a supplier... not registered on the Central Supplier Database" is the mildest form; several buyers disqualify at evaluation if you are not registered **at closing time** (kzn-publicworks-office-lease). Keep banking, directors, and address details current — "incorrect or outdated information may be a cause for disqualification." Watch the buyer-specific sub-rules on the *report* you print: freshness limits range from 7 days to 3 months, and several buyers reject the **summary** report and demand the FULL registration report (fs-publicworks, vaalcentral) — while at least one asks for the summary. Read each pack.
- [ ] **SARS tax compliance — TCS PIN** — in every pack with bid conditions (33/37). Keep eFiling in order year-round; generate a current TCS PIN per bid. When it bites varies: some buyers invalidate at closing (raynkonyeni), most verify at award with a 7-working-day cure window, and several buyers demand an **original** tax clearance certificate (often via an MBD 2 returnable), rejecting certified copies — a recurring older-template trait (mpofana and others), not a one-off. In a JV, **each partner and each subcontractor needs its own PIN**.
- [ ] **Not listed on the Register for Tender Defaulters or List of Restricted Suppliers** — automatic, no-cure disqualification (27/37 packs, near-identical wording). This extends to directors, members, shareholders, and trustees. Check National Treasury's lists for the entity and every director before committing bid costs.
- [ ] **No director "in the service of the state"** — about half of packs bar bids from state employees and companies with state-employed directors outright. If a director is a state employee, obtain the executive-authority approval for outside remunerative work and file it — one pack accepts that route (limpopo).
- [ ] **CIPC registration documents + director IDs + authority to sign** — company registration certificate, director ID copies, share certificates, and a board resolution naming the authorised signatory. Have these **pre-certified by a Commissioner of Oaths and re-certified every 90 days** as a standing defensive routine. The explicit under-3-months rejection rule is a municipal/checklist-buyer trait seen in about 8 packs (joburgtheatre x2, mkhondo, nkomazi among them), and several of those also reject "copies of certified copies" entirely — but the 90-day cycle keeps you safe everywhere.

**And the one universal *soft* gate — B-BBEE evidence.** A SANAS-accredited certificate (large enterprises) or a sworn affidavit on the DTIC template (EMEs/QSEs, valid 12 months from commissioning). This does NOT belong with the hard gates above: in the great majority of packs, missing it costs you the 10 or 20 preference points, never the bid — "Failure to submit... will not render your bid non-responsive, but the bidder will score 0 points for B-BBEE" (bergrivier, sanral, and many others). **Exception:** where the pack lists the B-BBEE certificate/level inside a pass/fail pre-qualification or administrative-compliance table (Eskom cl. 3.17-style, where missing proof at closing "will be disqualified"; TASEZ demands a minimum Level 3), missing or expired proof disqualifies outright — check which table the certificate sits in before relying on the still-submit rule. Also: some specific-goals tables award zero points for B-BBEE at all — read the buyer's table. In a close 80/20 race, zero points is usually fatal to *winning* anyway, so keep it current — but if it isn't ready at deadline and B-BBEE is not a pre-qualification gate in this pack, **still submit the bid**.

### 3.2 Common conditional gates — obtain when the work type triggers them

- [ ] **COIDA Letter of Good Standing** (Compensation Fund) — appears in roughly a third of packs, concentrated in works and site-based services. The stage at which it bites varies by buyer: bid-stage disqualifier at some (fs-publicworks; mvula verifies it **online on evaluation day**, so "valid at submission" is not enough), contract-signing condition at others (acsa-power). If you have no employees, keep a commissioned no-employee exemption affidavit ready — some buyers require even that to be lodged with the bid.
- [ ] **Municipal rates and taxes clearance — company AND every director** — the signature municipal-regime gate (all municipal packs, plus TVET colleges and municipal entities). The arrears threshold is buyer-specific — 90 days at some (Kokstad, which demands proof per director and calls failure "automatic disqualification"), one month at others (Kouga, including arrears with any other municipality). Some buyers demand the clearance only from the recommended bidder, not from every bidder at submission — check the certificate's own wording and when it bites. Renting? A certified lease plus (at some buyers) an affidavit works. Start collecting director proofs on day one — this is the most commonly fatal municipal document and takes days.
- [ ] **CIDB contractor grading** — construction only, but an absolute eligibility gate where present: the exact class and designation (6CE, 7GB, 3ME...), **active and in good standing at close and throughout the validity period** — "AN 'INACTIVE' OR 'SUSPENDED' REGISTRATION STATUS WILL INVALIDATE THE TENDER" (kokstad-franklin-roads). Keep that zero-tolerance reading as the default, but some buyers (Eskom, Joe Gqabi DM) accept bidders "capable of being so registered within twenty-one (21) working days from the closing date" — proof of application suffices at closing, registration due by award, and this CIDB cure clock can exceed the pack's general cure window. Check the eligibility clause before self-eliminating. JV rules: combined grading per CIDB rules, lead partner within one grade of the requirement, and a **signed JV agreement before submission** — a letter of intent to formalise later is expressly rejected. **Check the required legal form of the JV document per pack:** some buyers demand a formation document **authenticated by a notary public** (or an official deputed to witness sworn statements), defining duration, representation, and participation, plus a power of attorney signed by all partners (raynkonyeni-style). A signed-but-unnotarised agreement fails eligibility at those buyers — book the notary as another early dependency alongside the Commissioner of Oaths.
- [ ] **Sector statutory registrations** — always pass/fail where they appear: PSIRA (security — company and directors, certified unexpired copies), NHBRC (housing), ECSA / SACQSP / SACPCMP (built environment professionals), LPC + Fidelity Fund (legal), HPCSA/SANC (health), Banks Act (banking), waste licences, OEM authorisations (ICT). Proof must be certified, current, and match the exact grade/class demanded — often for named individuals, not just the firm.
- [ ] **Insurance** — Professional Indemnity and/or Public Liability at stated cover levels. Buyer-specific in amount and stage: some want the certificate (or a broker's letter of intent) in the bid; others make it a post-award deliverable with a hard deadline — SANRAL treats failure to insure within 14 days of acceptance as repudiation **plus an automatic 12-month bar from all its tenders**.

### 3.3 Subcontracting — banned, capped, or mandatory: find out before structuring the bid

Subcontracting rules appear in 29 of the 37 packs and cut in every direction, so check the pack's stance **before** you design the delivery model:

- [ ] **Banned outright at some buyers** — vaalcentral: any subcontracting renders the bid non-compliant. If your model depends on subcontractors, that pack is not for you. A related stance: **100% pass-through is banned** (Eskom) — you cannot subcontract the whole works.
- [ ] **Consent-gated by default elsewhere** — GCC boilerplate: no subcontracting without the buyer's prior written consent. Treat this as a fourth stance alongside banned/capped/mandatory.
- [ ] **Capped elsewhere** — e.g. 25% of project scope (dbsa/IFISA), and a standard preference-points-linked cap: you may not subcontract more than 25% of contract value to an enterprise that does not qualify for the same or more equity-ownership points (dlrrd and the SBD 6.1 boilerplate). The boilerplate cap reads 25% OR 30% depending on the pack — read the number. Transnet penalises undisclosed subcontracting at up to 10% of contract value.
- [ ] **Mandatory at others** — compulsory subcontracting of a minimum 30% of contract value to Black-owned/local emerging enterprises on higher-value contracts (kokstad: 30% to local Level 1 CIDB Black-owned emerging contractors; ethekwini: 30% to 51% Black-owned enterprises with an implementation plan), **with financial penalties for shortfall** — price and programme for it. Some packs add local-first sourcing hierarchies (raynkonyeni). Mandatory 30% thresholds can bite from as low as R4m (KwaDukuza); CIDB CSDG/CPG gazetted goals trigger automatically at value/duration/grade thresholds and can be small (5%); and mandatory-quota relief mechanisms exist (Engineer-approved motivated application).
- [ ] **Disclose every intended subcontractor** — SBD/MBD 4 and dedicated schedules ask for intended subcontractors and the value of subcontracted work; non-disclosure is treated as a false declaration.
- [ ] **Assemble a per-subcontractor compliance pack**: each subcontractor typically needs its own CSD registration, TCS PIN, B-BBEE evidence, CIPC documents, and CIDB grading where relevant (dbsa, kokstad).

### 3.4 Financial standing — MBD 5, audited financials, and bank letters

- [ ] **MBD 5 (procurement above R10 million)** — municipal packs above R10m demand this declaration plus **three years of audited annual financial statements** (or AFS since incorporation if younger), with municipal-debt and prior-contract-performance disclosures (ethekwini, nkomazi, raynkonyeni, tshwane). If your AFS are not audited, resolve this months ahead — it cannot be fixed in a bid window.
- [ ] **Bank rating letters** — several buyers score or gate on a bank letter with a tight freshness window (within **1 month** at nc-coghsta) and all-or-nothing bands (Grade A–C = 12 points, D–E = 0). Vaalcentral rejects bank ratings entirely and wants bank statements or credit approval — read the evidence spec.
- [ ] **Confirm you can carry the contract's financial terms before committing bid costs**: where the pack demands a 5–10% performance guarantee within days of acceptance plus retention on interim payments, the buyer is signalling it expects real balance-sheet/bonding capacity — verify with your bank or insurer that you can raise the guarantee and absorb the retention cash-flow before you spend a cent on the bid.

**Practical system:** keep an "always-green" compliance file with the five universal hard gates plus the B-BBEE soft gate above, a renewal calendar for every certificate, and a standing 90-day re-certification cycle at a Commissioner of Oaths. Then rebuild the *conditional* gate list from scratch for every pack — this is where compliant, capable bidders actually get eliminated.

---

## 4. How to complete each common form — and the exact traps

### 4.0 Rules that apply to every form in the pack

- **Use only the official issued forms.** Never retype, redraft, reformat, or substitute — about a third of packs make this an explicit kill ("ALL BIDS MUST BE SUBMITTED ON THE OFFICIAL FORMS PROVIDED – NOT TO BE RE-TYPED"). Do not remove pages, unbind, insert pages, or "dismember" the document. Return the complete document; mark inapplicable sections "N/A" rather than removing them.
- **Ink discipline:** black non-erasable ink unless the pack says otherwise; no pencil, no red ink. **Never use correction fluid/Tipp-Ex** — a per-se disqualifier in a dozen packs; Tshwane disqualifies for Tippex on the price schedule specifically. Correct errors the one accepted way: single line through, rewrite next to it, **all signatories initial the correction**. Joburg Theatre additionally requires a letter on company letterhead explaining any alteration to the price.
- **Initial every page** where required (footer or top right, as instructed) — pack checklists explicitly audit this, and at least one buyer requires it even for electronic submissions (salga/ocds-165124).
- **No electronic signatures** unless expressly allowed; some buyers (fs-publicworks) go further and require the entire returnable set completed **by hand in black pen** — digitally completed forms are disqualified there. This is buyer-specific: check.
- **Signing authority is not optional.** Every pack requires the signatory's authority proven by a board/members'/partners' resolution — via the SBD1/MBD1 proof-of-authority line or a dedicated form. Failure is fatal, not curable: "Failure to submit proof of signing authority renders the tender non-responsive" (tshwane). Some buyers require the resolution signed by ALL directors.
- **Consistency across documents:** names, ownership percentages, and addresses must match across CIPC, CSD, the B-BBEE certificate/affidavit, and the forms. One buyer zeroes preference points outright where CIPC ownership data and the B-BBEE affidavit disagree, calling it misrepresentation.
- **Sign every buyer-specific declaration form included in the pack** — including confidentiality/non-disclosure undertakings where they appear as returnables (acsa-power's Form A11 NDA is part of the bid, with a penalty clause attached). Skipping a form because it looks like legal furniture is a missing-returnable kill.

### 4.1 SBD 1 / MBD 1 — Invitation to Bid (the cover form)

Fill **every** field: bidder identity, VAT number, TCS PIN, CSD/MAAA number, B-BBEE tick-boxes. Traps:
- **Write the TOTAL BID PRICE on the face of the form**, carried over exactly from the pricing schedule — "bidders who do not put prices on MBD 1 will be eliminated" (kokstad).
- Sign, date, state the **capacity** in which you sign, and attach the proof of authority.
- Foreign suppliers: complete the Part B questionnaire.
- The form's own warning is real: "FAILURE TO PROVIDE / OR COMPLY WITH ANY OF THE ABOVE PARTICULARS MAY RENDER THE BID INVALID."

### 4.2 SBD 4 / MBD 4 — Declaration of Interest / Bidder's Disclosure

The most universal form in the corpus (33/34 packs with form data), and one of the deadliest:
- **Answer every question individually** — yes or no, plus particulars for any yes. "Every question must be answered individually... Failure to do so will invalidate your tender/bid" (ocds-9t57fa-162578). A blank is a kill.
- List ALL directors/trustees/members/shareholders with ID numbers, tax reference numbers, and Persal numbers where state-employed.
- Newer SBD 4 versions demand disclosure of **all CSD-registered companies linked to any director — even companies unrelated to this bid**. "Failure to disclose all CSD-registered active companies linked to all Directors will lead to disqualification" (verbatim in four packs, e.g. cge-wan-voip).
- The post-2022 SBD 4 also contains the anti-collusion declaration (absorbing old SBD 8/9). Treat it with the same care.
- JVs: one form **per partner** (or a combined form only where the buyer expressly allows it).
- The standing threat: the bid is disqualified if the disclosure is later found "not true and complete in every respect" — understatement risks blacklisting, not just this bid.

### 4.3 SBD 6.1 / MBD 6.1 — Preference Points Claim Form

- Confirm the system from the **tender-specific** clause, not the boilerplate: **80/20 for tender value up to and including R50 million — all applicable taxes included — and 90/10 above it.** At least one pack's generic template contradicted its own Terms of Reference (limpopo-dsd-catering said both 90/10 and 80/20 — the tender-specific text governs). And note the deferred-determination case: some packs (sanral, vaalcentral) state that the applicable system is **determined only after tenders are received**, from the lowest/highest acceptable tender against the R50m threshold — no clause in the pack can settle it in advance. If your price could straddle R50 million, build a points strategy that works under both systems and ask the SCM contact in writing which applies.
- Read the buyer's actual specific-goals table — under the 2022 regulations every buyer defines its own (Black ownership, women, youth, disability, locality...). Do not assume the standard B-BBEE Level 1–8 scale; one SOE gives Level 1 only 5 of 20 points, another gives Level 1 all 20, a third gives 20 points only to Levels 1–2 and zero to everyone else.
- **Claim explicitly: write the number of points claimed against each goal** — some buyers reject ticks (kokstad), and "non-claiming of points on this form will lead to zero even if means of verification... is attached" (limpopo). The reverse also holds: a claim without the attached proof scores zero.
- Attach the exact proof per goal: B-BBEE certificate or EME/QSE sworn affidavit; for ownership goals often ALSO shareholding certificates, certified shareholder IDs, CIPC documents, and a current CSD report; a doctor's/Department of Labour letter for disability; a municipal account, lease, or councillor letter for locality (address must match CSD/CIPC exactly).
- Sign and date. **Never inflate a claim:** fraudulent preference claims carry disqualification, contract cancellation, up to 10-year restriction from all public-sector business, and criminal referral.
- Missing proof only zeroes the points — **so if your B-BBEE paperwork isn't ready at deadline, still submit the bid** and compete on price and functionality.

### 4.3.1 SBD/MBD 6.2 — Declaration of Local Production and Content (designated sectors)

If the tender falls in a **designated sector** (steel products, textiles, furniture, and other DTIC-designated categories), the SBD/MBD 6.2 Declaration Certificate plus its local-content annexes (Annexes C/D/E, calculated per SATS 1286) are **pass/fail returnables**: at least one pack in the corpus (Eskom) states the bid may be disqualified if the Declaration Certificate and Annex C are not submitted by the stipulated deadline. Most packs mark local content **N/A** — confirm the marking and move on. Where a pack's checklist demands the 6.2 form but the pack does not contain it, request it in writing from the SCM contact before the clarification cut-off (Section 1.4) and keep proof of the request.

### 4.4 SBD/MBD 8 and 9 — Past Practices and Independent Bid Determination

Universal as separate returnables in **every** municipal (MBD) pack; in modern SBD packs the content lives inside SBD 4. Where they appear:
- **8:** yes/no questionnaire on restricted-supplier listing, fraud convictions, prior contract terminations (municipal versions add rates arrears). Furnish particulars for any yes; sign.
- **9:** certificate that the bid was arrived at independently — no communication with competitors on prices, markets, or intent to bid. Must be signed by an authorised signatory; omission makes the bid non-responsive (kokstad).

### 4.5 SBD 3.x / MBD 3.x — Pricing Schedules

Covered in depth in Section 6. Form-mechanics traps: price every line, keep the printed format, state firm vs escalation basis, and reconcile the total to SBD1/MBD1 and the Form of Offer.

### 4.6 SBD 7 / MBD 7 — Contract Form (and CIDB C1.1)

- Where included as a returnable, the bidder completes and signs Part 1 at bid stage; the buyer countersigns after award. Filled **in duplicate, both signed in the original**, with two witnesses per party where required.
- Construction packs replace this with the **C1.1 Form of Offer and Acceptance**: sign the Offer with the total price in words AND figures, witnessed; failure to sign it, or to carry the price over from the pricing/activity schedule, renders the tender invalid/non-responsive (mvula). Tshwane nuance: C1.1 pages are initialled only by the *successful* tenderer after acceptance — follow the pack's own instruction.

### 4.7 The Commissioner of Oaths — book early

Sworn affidavits (B-BBEE EME/QSE, no-employee COIDA, employment-status), certified copies (under 3 months old, from originals), and commissioned declaration sections (stamp plus witnesses at some colleges) cannot be fixed on closing day. Schedule a commissioning session in the final week, and keep a standing relationship with a local police station or attorney.

### 4.8 Other mandatory returnables now confirmed corpus-wide

Sweep for these by title — each is fatal or score-bearing where it appears:

- **POPIA consent/processing form** — near-cross-sector (construction, municipal, SOE), mandatory at multiple buyers.
- **DPIP/FPPO politically-exposed-persons declaration** (SANRAL Form A5, Transnet) — "tender may be rendered invalid" if omitted.
- **Buyer-branded Integrity Pact** IN ADDITION to SBD/MBD 9 (Gauteng Treasury, Eskom, Transnet).
- **Litigation-history disclosure** (SANRAL Form A8).
- **GCC/SCC "ACCEPT ALL" tick-box** — an independent kill: failure to tick = disqualification.
- **Certificate of Single Tender Submission.**
- **MBD 2 original tax clearance certificate** — original-only, no certified copies (Section 3.1).
- **SBD/MBD 3.2 method-of-pricing form** — mandatory firm/non-firm option selection; blank = not considered (Section 6.1).
- **MBD 6.4 local-content bonus-points form.**
- **Third-party sourcing declaration** with unconditional undertaking.
- **Lot/field tick-box tables** — an unticked lot = disqualified for that lot.

---

## 5. Functionality scoring — evidence beats claims

About two-thirds of the corpus (24/37 packs) scores "functionality" (technical merit) in some form — among full formal bids the share is higher still, though the exact count depends on whether you include the handful of packs that run technical criteria as pass/fail gates rather than a weighted matrix. Simple RFQs and goods tenders usually skip it. Three universal truths about it:

1. **It is an elimination gate, not part of the final score.** The pipeline is usually: compliance (pass/fail) → functionality scored against a minimum threshold → only survivors go to 80/20 price-and-preference. A cheap, B-BBEE-strong bid below the threshold is dead; its price envelope is often never opened. But a sizeable minority of full formal bids — including multi-year service bids and CIDB construction packs — run no functionality stage at all ("FUNCTIONALITY will not be used"), and DBSA-style RFPs score price first with a pass/fail risk review after. Check the Tender Data's functionality clause explicitly; never infer it from pack size or sector.
2. **Claims without the prescribed documentary evidence score ZERO.** No partial credit, no benefit of the doubt. "Unsupported claims of experience score zero" (tshwane); documentation "not attached to or clearly cross-referenced from the applicable Returnable Schedule... is deemed not submitted" (vaalcentral).
3. **Scoring is mechanical and banded on countable facts** — number of qualifying projects, years since professional registration, number of compliant reference letters — with steep, non-cumulative tiers. One extra compliant reference letter or one more year of a nominated person's experience routinely swings 10–40 points.

### 5.1 Read the matrix first, bid second

- [ ] Extract the matrix and threshold on day one. Thresholds run roughly 40% to over 80% — one pack (cge) requires 50/60 ≈ 83% — with **70% still the mode for formal bids**, but municipal panel/RFQ-style tenders regularly set 50–55% (Mogale 15/30, 36/65) and one sits at a minimum of 40 points. Read the number; a sub-60% bar is not a typo. SOEs and metros *tend* toward 75–80%, but only as a tendency: two municipal buyers (namakwa, joburgtheatre) sit at 80% while SOE packs (acsa-power, saws) sit at 70% — read the number per pack. With few line items, a 70–80% bar means near-full marks on almost every criterion — weakness in one area cannot be offset.
- [ ] Check each criterion's **qualifying filters** before counting a project: sector/scope definition (one buyer counts only maintenance work, excluding new installation), recency window (3–10 years), minimum Rand value, and whose letterhead the proof must be on. Filters silently discard references.
- [ ] Hunt for sub-thresholds and hidden second gates: a per-criterion minimum that stops all further scoring (fs-publicworks), a site-visit gate unlocked only above a score, a second 75% inspection phase (vaalcentral). If you cannot realistically clear the bar, fix the gap (JV, more senior CVs, more references) or do not bid.
- [ ] **Zero anywhere can kill:** some buyers disqualify for a zero on ANY criterion or sub-criterion even after the overall threshold is met, and some per-criterion minimums equal the criterion maximum (full marks or dead). Check for this wording separately from the overall threshold.

### 5.2 Build the evidence library (a standing asset)

- [ ] **Matched sets per project:** appointment letter + completion certificate + client reference letter for the SAME project — "one without the other scores zero" at several buyers (joburgtheatre-ahu).
- [ ] **Reference-letter format code:** on the CLIENT's letterhead, signed (often stamped), dated within the recency window, with contactable referee, project scope, value, and duration. Several buyers **explicitly reject purchase orders, appointment letters, award letters, SLAs, and invoices** as proof of experience (acsa-power) — but at least one wants POs specifically, so read each pack's evidence spec.
- [ ] Target the top band: the max tier is typically "5+ projects/letters"; one more compliant letter is cheap and can be worth a whole band.
- [ ] Certified copies of qualifications: certification within 3–6 months, no re-certified photocopies. Where financial capacity is scored or gated: bank rating letter within its stated freshness window (as tight as 1 month, stamped) and audited annual financial statements where demanded (see Section 3.4) — the bands are often all-or-nothing.
- [ ] Warn referees they may be phoned, and verify their contact details still work — buyers do call.

### 5.3 Personnel

- [ ] Nominate the most senior professionally registered people available — bands cliff at 8+/10+/15+ years post-registration, and juniors often score 0, not partial. Registration is verified online during evaluation.
- [ ] Per named person: CV (signed by the person AND the bidder's signatory where required; respect page limits — some cap at 1–3 pages), certified qualifications, valid registration certificate, employment proof or a signed letter of intent to employ, and any required affidavit. A CV alone can net zero.
- [ ] Where the buyer scores only the best N people, extra senior CVs are costless — include them.

### 5.4 Methodology, demos, and assembly

- [ ] Mirror the published rubric: structure the methodology under the exact headings/stages the pack scores, with explicit deliverables and timelines. Generic boilerplate is expressly capped below the top band at some buyers. Respect page caps.
- [ ] ICT: the live demo/POC is often the single biggest lever (30–40 of 100 points) — rehearse against each named sub-criterion.
- [ ] **Cross-reference everything:** build an index mapping each criterion to an exact page/annexure. Compulsory at one buyer (namakwa: "The completion of specific page reference is compulsory"), effectively required everywhere — "not cross-referenced = not submitted."
- [ ] **Locate the pack's submission/filing clause before binding** (in CIDB packs typically an F.2.13.x clause). A pack-level filing rule — e.g. all supporting documentation in a separate labelled file with a table of contents — **overrides** per-form "attach proof to this page" instructions, and non-compliance can be declared non-responsive. The cross-reference index is your bridge between the two: file where the pack-level rule says, and point to it from each schedule.
- [ ] Photograph what must be photographed (uniforms, PPE, equipment); document plant *ownership* where ownership scores more than hire.
- [ ] Prepare for verification: real premises, real fleet, team members available for interviews at short notice (one buyer gives 2 days' notice and disqualifies for an absent team member). Verification failures disqualify — they don't just deduct.
- [ ] Even in RFQs with no scored stage, the same evidence types (reference letters, experience minimums) frequently reappear as **pass/fail gates** — attach them in full regardless.

---

## 6. The pricing schedule — how to fill it, pitfalls, preference points

### 6.1 Fill it defensively

- [ ] **Use the issued format verbatim.** No substituted spreadsheets, no reformatting — deviation from the prescribed schedule is a named non-responsiveness trigger at many buyers (hda, ethekwini).
- [ ] **Price every single line.** Blanks, "N/A", and dashes count as unpriced and can invalidate the whole tender (raynkonyeni); grouping items into a lump sum is equally fatal there. Write R0.00 deliberately if that is your price. Construction packs add **rate-only items** — no quantity, but a rate is still mandatory. And honour explicit "NO QUOTE" blocks — pricing everything blindly is also an error (limpopo).
- [ ] **Firm prices in Rand unless the pack issues a non-firm schedule:** "non-firm prices (including prices subject to rates of exchange variations) will not be considered" is standard wording in most packs — but some packs issue SBD/MBD 3.2 *non-firm* schedules with mandatory escalation/rate-of-exchange formulas, and where a method-of-pricing form offers a firm/non-firm option, selecting one is mandatory (blank = not considered). No currency conditions, no qualifications attached to your price.
- [ ] **Resolve the VAT basis before pricing.** Whether line items are VAT-inclusive or exclusive differs by buyer, and several packs contradict themselves internally — get written clarification rather than guessing. The evaluated total is almost always VAT-inclusive at 15%; watch zero-rated/exempt projects. Several buyers DEEM prices above a threshold (R1m–R2.3m) VAT-inclusive regardless of what you wrote — the total stays fixed and an exclusive-priced bidder absorbs the 15%. Non-vendors whose win would push turnover past R1m must price VAT in and register with SARS within ~21 days of award. Simple RFQs often default to VAT-EXCLUSIVE if silent. Check the pack's default-if-silent and deeming clauses, not just inclusive/exclusive labels.
- [ ] **Bake in ALL costs:** delivery, freight, insurance, travel, disbursements, uniforms/PPE, relievers, statutory levies (PAYE/UIF/SDL). The recurring rule: anything not itemised in the schedule cannot be recovered later.
- [ ] **Price the post-award contract terms too** — nearly half the packs carry penalty regimes (fixed Rand-per-day late-completion penalties, 0.1%/day GCC penalties, percentage penalties for missed subcontracting or PDI/job-creation commitments), and construction packs demand a 5–10% (or a flat Rand sum — check) **performance guarantee** within 14–21 days of acceptance plus **5–10% retention** on interim payments; on contracts under ~R1m the "guarantee" is often a 5% payment-reduction retention instead of a bond. Read the security clause, not the rule of thumb. Also price for: SOE master agreements with most-favoured-customer price-matching and termination rights; buyers that refuse ALL arithmetic corrections (PPECB: the submitted total is final); a separate Price Declaration Form that governs over the schedule on mismatch; and withdrawal after acceptance costing you the price gap to the next-ranked bid. The guarantee's cost, the retention's cash-flow drag, and your realistic penalty exposure all belong in the price — and in the go/no-go decision (Section 3.4).
- [ ] **Never submit an alternative price basis** — including fixed rates in lieu of a prescribed CPA/escalation formula — unless the pack expressly permits alternatives, and then only alongside a fully compliant base offer. An unsanctioned alternative kills the whole tender at several buyers (Section 2).
- [ ] **Multi-year contracts:** check whether escalation exists at all. Many terms are hard-fixed for 24–36 months (price the inflation in); where a CPI/CPA mechanism is offered, SUBMIT the formula — omission usually locks you into fixed prices for the whole term (cge, eskom). Wage-based services: price labour at or above the Sectoral Determination / minimum wage — underpricing labour triggers responsiveness challenges.
- [ ] Don't pad contingency lines (often fenced or excluded from the evaluated price) and don't unbalance rates (rejection ground at sanral, vaalcentral). Discounts: unconditional or not at all — conditional discounts are ignored in evaluation.
- [ ] Panels and rate contracts: estimated quantities are **not** guaranteed volume — price each unit to be viable at any volume. Panel/framework tenders also run their own two-stage mechanics, recurring across municipal and SOE packs: a functionality-only gate to join the panel (sometimes no price submitted at panel stage at all), then per-order RFQ mini-competitions at 80/20 among panelists, cascades to the next-ranked panelist on decline, ongoing performance-penalty/greylisting regimes, one-area/lot caps, leased-equipment cross-checks against other bidders' fleets, and exclusion for repeatedly ignoring RFQ invitations. Panel entry buys the right to compete, not revenue — factor that into bid cost.
- [ ] **Locality is not only points.** It can also be (a) a hard eligibility gate ("only bidders residing within X will be considered"), (b) a scored functionality criterion, and (c) a post-award LEVY — Mogale City deducts a 2% "Corporate Social Responsibility" levy from every payment to non-local winners, with a signed acceptance declaration as a returnable. Price it; don't just score it.

### 6.2 Arithmetic and reconciliation — self-audit before sealing

- [ ] Recompute every rate x quantity extension, subtotal, VAT line, and grand total.
- [ ] Know which convention governs in *this* pack: words vs figures (usually words govern, but at least one buyer says figures), and line-total vs rate on discrepancies (both conventions exist in the corpus).
- [ ] **Reconcile the schedule total to the Form of Offer / MBD1 / cover form in both words and figures** — a missing or mismatched carry-over eliminates bids outright (kokstad, mvula).
- [ ] Remember: typically only the top-ranked bid gets error-checked, you bear the risk of corrections either way, and refusing a correction can mean rejection.

### 6.3 How price converts to points

Once past functionality, scoring is: lowest responsive price takes all 80 (or 90) points; everyone else scores on the formula Ps = 80 × (1 − (Pt − Pmin)/Pmin). Proximity to the lowest acceptable price dominates; the 20 (or 10) preference points decide among close prices. Two consequences:
- Being ranked 2nd or 3rd still carries real award probability — several buyers negotiate down the ranking or cascade if the winning price isn't market-related.
- Preference points are worth real money: know your points position (Section 4.3) before setting margin.
- **Tie-breaks cascade preference-first:** where total points are equal, several packs (bergrivier, dlrrd, nkomazi) award to the bidder with the higher specific-goals/preference points, then the higher functionality score, and only then a draw of lots — so maximising claimable goals and functionality margin matters even when you expect to win on price.
- Near the R50 million boundary, remember the system itself may only be fixed after opening (Section 4.3) — your price and preference strategy must survive both 80/20 and 90/10.
- **For disposal/leasing/income-generating tenders the formula inverts** — the highest acceptable offer scores full points (Ps = 80/90 × (1 + (Pt − Pmax)/Pmax)). And "best and final offer" negotiation rounds mean the submitted price is not always the evaluated price; award cascades to the next-ranked bidder on decline or delivery default at several buyers — 2nd place stays live past award.
- **The "Objective Criteria" override (PPPFA s2(1)(f)):** many buyers (Transnet, Eskom, SANRAL, DBSA, CSIR, PPECB, Johannesburg Water...) reserve a named post-scoring stage that can pass over the top-ranked bidder: poor track record with that buyer, litigation against the buyer, supplier rotation, financial-ratio risk analysis, insolvency/business rescue, director fraud charges, or lookback windows (18 months post-termination at DBSA). Winning on points is necessary, not sufficient. Related: post-scoring security/integrity vetting — SIU Internal Integrity Unit + SSA vetting "irrespective of the points scored", SANRAL SSA screening, Transnet security clearances for staff and subcontractors, original fingerprints for National Key Point work, SA-citizen-only personnel clauses — can also override a winning score. Flag security-adjacent buyers at go/no-go.

### 6.4 Two-envelope systems

A minority of (mostly SOE/DFI) buyers separate technical and financial submissions into sealed envelopes or folders. Where they do, **any price figure appearing in the technical envelope is an explicit disqualification trigger** (hda, dbsa). Sweep the technical volume for stray pricing — including in CVs, org charts, and past-project descriptions — before sealing. Other buyers explicitly do NOT run two envelopes; never assume either way.

---

## 7. Briefings and submission logistics

### 7.1 Briefings and site meetings

Roughly 43% of the corpus holds a briefing, with compulsory outnumbering non-compulsory about 5:1; where it is compulsory (typical for construction and site-based services), attendance is a pass/fail gate in every single case. Assume compulsory for construction until proven otherwise — but some CIDB packs hold no briefing at all, and notice headers can say "non-compulsory" while the body says "compulsory": clarify in writing. Some buyers publish an explicit grace period (doors close +10 min) — never rely on it.

- [ ] Diarise it with a buffer and **arrive/join 15+ minutes early** — lateness counts as absence at several buyers ("if you join once the meeting has already started you will not be allowed into meeting"), and content is not repeated for latecomers. Complete any pre-registration or link-request step days in advance.
- [ ] **Sign the attendance register in the exact name of the bidding entity** — not the rep's name, not a sister company. Some buyers evaluate only entities on the register and issue addenda only to them (ethekwini).
- [ ] Get the Certificate of Attendance signed (Form A1/A3/Section D, per pack) and file it into the bid immediately — it is a returnable document.
- [ ] Where BOTH a clarification meeting AND a site visit are compulsory (nc-coghsta), attend both. Bring what the notice demands (ID document, full PPE).
- [ ] Verbal answers at briefings are not binding. Get every material clarification confirmed as a **written addendum**, then sign and return the Record of Addenda with copies of each addendum attached, and update the BoQ/pricing where an addendum changes it — failure is non-responsive at kokstad.

### 7.2 Submission — the deadline is absolute

- [ ] **Target delivery/upload at least 24 hours early.** Every pack rejects late bids; the strictest lock the box to the second. The bid must be *physically in the box / showing "complete" on the portal* at closing — proof of posting or courier dispatch is universally NOT proof of delivery, and courier risk is yours. If couriering, instruct the courier to put the bid in the tender box, not at reception.
- [ ] **Only the prescribed channel counts.** Physical buyers void fax/email/telegraphic submissions; portal buyers void everything off-platform ("Any bidder who fails to submit via the e-Tender platform will be disqualified" — saws). Municipal ≈ physical box; SOE/national ≈ portal; small RFQ ≈ email — but verify per pack: a rare buyer accepts fax/email (SIU), and packs can contradict themselves on the channel itself (advert says portal-only while boilerplate still describes a bid box) — add "submission channel" to the Section 1.4 contradiction sweep.
- [ ] Physical: sealed envelope endorsed exactly as prescribed — bid number, description, closing date, bidder name/address (some want it on the back). One bid per envelope; defective labelling is itself a rejection ground. Confirm the copy count: original only, original + N copies (one buyer disqualifies for a missing single copy — raynkonyeni), USB/flash-drive twins, or CIDB-style separate sealed ORIGINAL and COPY packages.
- [ ] Portals: register your **own** company profile well in advance (bidding through another company's profile is banned at Transnet), respect file-size limits and formats — the traps are concrete and buyer-specific: 30MB per upload at Transnet, 4MB per file at Sasria (with all schedules required), zip files REQUIRED at DBSA versus banned at Eskom, alphanumeric filenames only, PDF-only buyers, and cloud-transfer links banned at one buyer while required at another (with link-expiry reconfiguration duties at SABC). Verify the submission status shows "complete," and know that resubmission voids earlier versions. Technical-failure risk sits with you — including a broken CD/USB. Email submissions: exact address, subject-line format, attachment-size splits.
- [ ] Assorted logistics traps: samples packaged separately from the bid documents where demanded; English translations required for foreign-language documents; document fees run R300–R2,300+, not a narrow band; complaint/objection processes can carry fees and a dedicated Ombudsman (Transnet: R5m threshold, bad-faith complaints risk blacklisting); and the handwritten-only completion rule is a recurring municipal template (Mogale, fs-publicworks, multiple packs) that can be scoped to just the BoQ — while at least one buyer expressly permits digital completion, so check rather than assume either way.
- [ ] Dual-channel buyers split two ways: identical-or-invalid at some, versus a **precedence rule** at others — eThekwini and ERWAT declare the hard copy the governing/ruling version if the two differ (and at eThekwini the bid is invalid without the hard copy even if uploaded). Check which regime the pack states.
- [ ] After submission: monitor the named contact email daily (cure windows of 24 hours – 7 days are enforced literally), and communicate **only** with the designated contact — approaching other officials or councillors is a disqualifying offence at several buyers, with blacklisting at the extreme.
- [ ] Answer any bid-validity extension request in writing before expiry regardless — but check which way the silence-default runs: at most buyers silence = exclusion, at Limpopo DoH silence = acceptance of the extension, and eThekwini's SCM policy auto-extends validity 12 months unless the bidder objects in writing. Silence can bind you to a stale price rather than exclude you. Also: agreeing to extend can bar any modification of your tender (Eskom).

---

## 8. What varies by buyer and type — quick reference

| Dimension | Municipal (MBD) | National/Provincial (SBD) | SOE / public entity | Construction overlay | RFQ |
|---|---|---|---|---|---|
| Forms | Full MBD 1–10 spread; 8 & 9 always separate | Consolidated SBD 1+4+6.1 (+3.x); older packs still split 8/9 | SBD content in buyer-branded wrappers (match by title) | CIDB C1.1 Form of Offer, T/A-series schedules, NEC/GCC contract | Minimal — sometimes only SBD 4 + 6.1 |
| Extra gates | Rates clearance for company AND every director; MBD 10; local-presence rules | State-employee bans explicit; checklist-driven | Portal-only channels; tiered curable vs fatal returnables; insurance regimes | CIDB grading (active!), NHBRC, COIDA, OHS s37(2), performance guarantee, signed JV agreement pre-submission | Core kill-rules still apply in full |
| Functionality | Scored for services/works | Scored for services | Demos/POCs in ICT | Plant schedules, CIDB pre-gate, scored quality/H&S plans | Usually none — pass/fail gates instead |
| Threshold | Thresholds do NOT sort by buyer type: the corpus runs 60% / 70% / 75% / 80%+ (one at ≈83%), with 70% the mode — municipal buyers reach 80% and SOEs sit at 70%. Read it per pack (Section 5.1). | ← same | ← same | ← same | — |
| Preference | Specific goals incl. locality points (up to 10) | Specific goals; occasional locality | Often pure B-BBEE level table, non-standard point maps | — | Same 80/20 rules |
| Submission | Physical bid box, exact sealing/copy rules; public opening common | Box or eTenders portal | Own portal (Eskom, Transnet, SALGA...) or email | ORIGINAL + COPY sealed packages | Email or box; short validity (60–90 days) |
| Cure culture | Mostly single-shot (small buyers); Tshwane metro runs 7-day tiers | Mixed; 7-day tax cure common (FS, Limpopo) | Formal tiers: fatal vs curable in 48h–7 days | Single-shot on responsiveness | Follows the issuing buyer's regime — SOE RFQs can carry tiered cure windows (Transnet); assume single-shot only for small municipal/departmental RFQs |

Cross-cutting cautions: entity classification follows the governing statute, not the name (Section 1.2); the RFQ label is unreliable (Section 1.1); internal contradictions between boilerplate and tender-specific data occur in a substantial minority of packs — **the tender-specific data governs**, and you should log a written clarification; implementing agents (Mvula, PURCO, DBSA) impose their own overlay on top of whichever regime funds the work; and localisation obligations (local office, compulsory 30% subcontracting with shortfall penalties, EPWP job-creation declarations, local recruitment quotas, and locality *levies* such as Mogale City's 2% deduction from every payment to non-local winners) are buyer-specific contract terms — read for them, never assume, and see Sections 1.3, 3.3, and 6.1 for the construction, subcontracting, and levy versions.

---

## 9. Final pre-submission checklist (print this)

Work through in order, then have a **second person independently re-verify every line** against the physical or electronic pack before sealing. Where the pack contains its own checklist, complete that one too — at some buyers, non-adherence to the checklist itself invalidates the offer.

### A. Eligibility confirmed (do not proceed past this block with a "no")

- [ ] CSD registration active; details current; correct report type (FULL vs summary) printed within this buyer's freshness window
- [ ] SARS TCS PIN current; per JV partner/subcontractor where applicable
- [ ] Entity and every director checked against Register for Tender Defaulters / Restricted Suppliers
- [ ] No director in the service of the state (or approval letter attached)
- [ ] Sector registrations valid, active, correct class/grade (CIDB, PSIRA, NHBRC, professional councils, OEM letters) — for the entity AND named individuals
- [ ] Municipal buyer: rates clearance for company AND every director (arrears threshold buyer-specific — 1 to 3 months — or settlement arrangement)
- [ ] Compulsory briefing/site visit attended, on time, register signed in entity name; Certificate of Attendance in the pack
- [ ] JV: signed JV agreement (not a letter of intent) — notarised/authenticated formation document plus all-partner power of attorney where the pack demands it; per-partner CSD/TCS/SBD4; lead-partner grading rule met
- [ ] Subcontracting stance checked: banned, capped (incl. the 25% preference-points-linked cap), or mandatory (30% regimes with penalties) — bid structured accordingly
- [ ] Financial capacity confirmed: able to raise the stated performance guarantee and absorb retention/penalty exposure (Section 3.4)

### B. Forms complete

- [ ] SBD/MBD 1: every field filled; TOTAL price on the form matching the schedule; signed with capacity stated
- [ ] Board resolution / authority to sign attached (signed by all directors where required); certified ID of signatory
- [ ] SBD/MBD 4: every question answered individually; all directors listed with ID/tax numbers; all CSD-linked companies disclosed; signed
- [ ] SBD/MBD 6.1: points WRITTEN against each claimed goal; signed; proof attached per goal; claims match CIPC/CSD/B-BBEE records
- [ ] SBD/MBD 8 & 9 (or SBD 4 equivalents): completed, signed
- [ ] Contract form (SBD/MBD 7 or C1.1): Part 1/Offer signed in original ink, witnessed where required; price carried over correctly
- [ ] All returnables from YOUR page-by-page master checklist present, completed, signed — the pack's own checklist completed as well (Section 1.4)
- [ ] Every intended subcontractor disclosed (SBD/MBD 4 and schedules) with a per-subcontractor compliance pack: own CSD, TCS PIN, B-BBEE, CIPC, CIDB where relevant
- [ ] Confidentiality/NDA undertaking signed where the pack includes one
- [ ] MBD 5 + three years' audited AFS where procurement exceeds R10m (municipal); bank rating letter within its freshness window where demanded
- [ ] Preference-points proof as demanded by THIS pack's specific-goals table, per goal — a B-BBEE certificate/affidavit only where that is the named proof; otherwise the actual named evidence (detailed CSD report for ownership, locality/lease documents, practitioner letters for disability), valid at closing (see Section 4.3's warning)
- [ ] All certified copies: Commissioner of Oaths, under 3 months, from originals (no copies of certified copies); originals where the pack demands originals

### C. Document integrity

- [ ] Official forms only — nothing retyped, no pages removed, issued order preserved
- [ ] Black non-erasable ink; handwritten where the pack demands it; no pencil, no Tipp-Ex anywhere
- [ ] Every correction: single line-through, rewritten, initialled by all signatories (+ letterhead letter where required)
- [ ] Every page initialled where required
- [ ] No electronic signatures unless expressly allowed
- [ ] Record of Addenda signed; every addendum copy attached; BoQ/pricing updated for addenda

### D. Pricing

- [ ] Every line priced — including rate-only items and sub-items; no blanks/dashes/"N/A"; "NO QUOTE" blocks respected
- [ ] Issued format kept; firm Rand prices; correct VAT basis; all costs baked in
- [ ] Arithmetic recomputed: extensions, subtotals, VAT, grand total; words and figures agree
- [ ] Total reconciled to SBD/MBD 1 AND Form of Offer exactly
- [ ] Escalation/CPA formula submitted where the pack provides for one
- [ ] Two-envelope regime: technical volume swept — zero price information outside the financial envelope/folder

### E. Functionality evidence (where scored)

- [ ] Realistic self-score ≥ threshold, criterion by criterion, including sub-thresholds
- [ ] Matched evidence sets attached per claimed project (appointment letter + completion certificate + client-letterhead reference with contactable referee, scope, value, dates)
- [ ] CVs signed, within page limits; certified qualifications; registration certificates; employment proof/letters of intent; required affidavits
- [ ] Every criterion cross-referenced to an exact page/annexure; index included
- [ ] Photos/ownership proof for plant, fleet, uniforms where scored; referees warned; team briefed for possible interviews/site inspection
- [ ] Construction: bid-stage Health & Safety Plan per the pack's H&S Specification, and Quality Control Plan (with ISO certification where it scores) — included even if the pack's own checklist omits them
- [ ] Evidence filed per the pack's submission/filing clause (separate labelled supporting-documentation file where prescribed), with the cross-reference index pointing from each schedule to it

### F. Packaging and delivery

- [ ] Correct channel confirmed (which box / which portal / which email); no other channel used
- [ ] Envelope sealed and endorsed exactly as prescribed; correct number of copies + USB/PDF twins; ORIGINAL/COPY packages where required; hard and soft copies identical where both required
- [ ] Bid validity stated correctly (never shorter than demanded); internal contradictions clarified in writing
- [ ] Delivery/upload scheduled ≥ 24 hours before closing; portal status verified "complete"; receipt/proof of lodgement kept
- [ ] Complete copy of the entire submission retained
- [ ] Post-submission watch: named contact email monitored daily for clarification/cure requests (24 hours – 7 days); validity-extension requests answered in writing (check which way the silence-default runs — Section 7.2); renewal dates diarised for every certificate submitted

**Last rule, worth repeating:** the universal gates are cheap to keep green and fatal to miss; the buyer-specific rules are where good bidders actually die. Rebuild the gate register from the specific pack every single time — never reuse the last bid's.
