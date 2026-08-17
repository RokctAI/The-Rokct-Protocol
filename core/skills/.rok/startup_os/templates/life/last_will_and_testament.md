# Last Will and Testament — {{#if legal_full_name}}{{legal_full_name}}{{else}}{{full_name}}{{/if}}

> [!IMPORTANT]
> **This is a working draft assembled from `questions.md` — it is not a will,
> and it is not legal advice.** Formal execution requirements — signing,
> witnessing, capacity, revocation — vary by jurisdiction and MUST be
> verified with a qualified professional in {{jurisdiction_name}} before
> anything is signed. An unsigned draft has no legal force, and a mistake in
> execution can invalidate a will entirely. Use this page to organise your
> wishes; use a professional to make them law.

{{#if will_execution_status}}
> [!NOTE]
> **Execution recorded by the owner**: {{will_execution_status}}. Even so,
> this compiled file remains a working copy — only the signed original has
> legal force. Keep it safe, tell the executor where it is, and have any
> change professionally reviewed and re-executed.
{{else}}
> [!WARNING]
> **Status: UNSIGNED DRAFT — no legal force.** Once the will has been
> formally signed and witnessed, record the date and place under
> **Will Executed** in questions.md so this suite reflects reality.
{{/if}}

---

## 1. Declaration and Revocation

{{#if legal_full_name}}
I, **{{legal_full_name}}**{{#if primary_base}}, of {{primary_base}}{{/if}}, declare this to be my last will and testament. I revoke all wills, codicils and testamentary writings previously made by me.
{{else}}
_Full legal name not recorded. Answer **Legal Full Name** in questions.md —
exactly as it appears on your identity document. A will that misnames its
testator invites a challenge._
{{/if}}

{{#if marital_status}}
*   **Marital Status**: {{marital_status}}
    _A marriage regime (in or out of community of property, accrual) changes
    what is yours to bequeath — confirm the effect with your adviser._
{{else}}
*   **Marital Status**: _not recorded — answer **Marital Status**, including
    the regime; it decides what the estate actually contains._
{{/if}}
{{#if spouse_or_partner_name}}
*   **Spouse / Partner**: {{spouse_or_partner_name}}
{{/if}}
{{#if children}}
*   **Children**: {{children}}
{{/if}}

---

## 2. Executor

{{#if executor}}
I appoint **{{executor}}** as the executor of my estate.
{{#if alternate_executor}}
Should they be unable or unwilling to act, I appoint **{{alternate_executor}}** in their place.
{{else}}
_No alternate recorded. Answer **Alternate Executor** — a will with a single
point of failure in its executor is a fragile will._
{{/if}}

I direct that my executor have all powers permitted by the law of
{{jurisdiction_name}} to administer, realise and distribute my estate.
_Whether the executor may act free of security (bond) and how their fees are
set are jurisdiction-specific — have your adviser add the correct wording._
{{else}}
_No executor recorded. Answer **Executor** in questions.md — without a
nominated executor the estate is administered by an official appointee, on
the state's schedule, not yours._
{{/if}}

---
{{#if has_minor_children}}

## 3. Guardianship of Minor Children

{{#if guardian_nomination}}
Should any child of mine be a minor at my death and no surviving parent hold
guardianship, I nominate **{{guardian_nomination}}** as guardian.
_Guardianship nominations are subject to confirmation by the competent
authority in {{jurisdiction_name}}; discuss the nomination with the person
named before signing._
{{else}}
_Your **Children** answer marks at least one minor, but no guardian is
recorded. Answer **Guardian Nomination** — a guardian chosen by you beats one
chosen for you._
{{/if}}

---
{{/if}}

## 4. Specific Bequests

{{#if will_bequests_list}}
I make the following specific bequests, each free of estate expenses unless
stated otherwise:

{{will_bequests_list}}
{{else}}
_No specific bequests recorded — the residue clause below governs the whole
estate. To leave particular items or amounts to particular people, answer
**Specific Bequests**, one per line. No recipient is ever assumed._
{{/if}}

---

## 5. Residue of the Estate

{{#if residue_beneficiaries}}
I leave the residue of my estate — everything not disposed of above — as
follows:

{{residue_beneficiaries}}
{{#if alternate_heirs}}

Should a named heir not survive me, their share passes as follows:
{{alternate_heirs}}
{{else}}

_No alternates recorded. Answer **Alternate Heirs** — say where a share goes
if its heir dies before you, or the law will decide by default._
{{/if}}
{{else}}
_No residue beneficiaries recorded. Answer **Residue Beneficiaries** — this
is the clause that disposes of everything not specifically bequeathed. A will
without it leaves the bulk of the estate to the default rules of intestate
succession. No heir is ever invented for you._
{{/if}}

---

## 6. Survivorship

A beneficiary who does not survive me by thirty days is treated as having
predeceased me, and their benefit passes under the alternate provisions of
this will. _A survivorship period is standard drafting, but confirm the
period and wording for {{jurisdiction_name}} with your adviser._

---

## 7. Execution and Witnesses

{{#if_jurisdiction ZA}}
> [!IMPORTANT]
> **South Africa (Wills Act 7 of 1953)**: the testator must sign the will in
> the presence of **two or more competent witnesses** (14 years or older)
> who are present at the same time and who sign in the presence of the
> testator. Sign **every page**, with the full signatures at the end.
> A witness (or a witness's spouse) who is also a beneficiary or the
> nominated executor risks being **disqualified from benefiting** — use
> independent witnesses. Confirm the final execution with a qualified
> professional before signing.
{{else}}
> [!IMPORTANT]
> Execution formalities in {{jurisdiction_name}} are not encoded in this
> engine. Most jurisdictions require the testator to sign before independent
> adult witnesses who are not beneficiaries, all present together — but the
> number of witnesses, page-signing rules and notarisation requirements
> differ. **Verify the exact formalities with a qualified professional
> before signing.**
{{/if_jurisdiction}}

Signed at ______________________ on this ______ day of ______________________.

**Testator / Testatrix**: _____________________________
({{#if legal_full_name}}{{legal_full_name}}{{else}}{{full_name}}{{/if}})

**Witness 1**: Name ______________________ Signature ______________________
Address ________________________________________________

**Witness 2**: Name ______________________ Signature ______________________
Address ________________________________________________
