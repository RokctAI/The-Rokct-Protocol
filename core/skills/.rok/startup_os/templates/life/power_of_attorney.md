# Power of Attorney (Draft) — {{#if legal_full_name}}{{legal_full_name}}{{else}}{{full_name}}{{/if}}

> [!IMPORTANT]
> **This is a working draft assembled from `questions.md` — it is not a
> power of attorney, and it is not legal advice.** Execution formalities,
> what a bank or deeds office will accept, and whether special wording or
> notarisation is needed all vary by jurisdiction and by institution. Have
> a qualified professional in {{jurisdiction_name}} settle the final
> wording before anything is signed.

{{#if_jurisdiction ZA}}
> [!CAUTION]
> **South Africa — the assumption most people make here is wrong.** A power
> of attorney **lapses the moment the principal loses legal capacity** —
> exactly the moment most people expect it to start working. South African
> law does not currently recognise an "enduring" power of attorney that
> survives incapacity; planning for incapacity needs other instruments
> (such as curatorship or an administrator under the Mental Health Care
> Act), which need professional advice. Do not rely on this document as an
> incapacity plan.
{{else}}
> [!WARNING]
> In many jurisdictions an ordinary power of attorney **lapses if the
> principal loses capacity**, unless a special durable or enduring form is
> used. Whether {{jurisdiction_name}} recognises a durable form, and what
> it requires, is not encoded in this engine — **verify with a qualified
> professional** before relying on this document for incapacity planning.
{{/if_jurisdiction}}

{{#if poa_execution_status}}
> [!NOTE]
> **Execution recorded by the owner**: {{poa_execution_status}}. This
> compiled file remains a working copy — only the signed original has legal
> force, and institutions will demand the original or a certified copy.
{{else}}
> [!WARNING]
> **Status: UNSIGNED DRAFT — no legal force.** Once the power of attorney
> has been signed (and witnessed or notarised where required), record the
> date and place under **POA Executed** in questions.md.
{{/if}}

---

## 1. Principal

{{#if legal_full_name}}
I, **{{legal_full_name}}**{{#if primary_base}}, of {{primary_base}}{{/if}}, (the principal) make this appointment.
{{else}}
_Full legal name not recorded. Answer **Legal Full Name** in questions.md —
exactly as it appears on your identity document; institutions verify it
against the document._
{{/if}}

---

## 2. Agent (Attorney-in-Fact)

{{#if attorney_in_fact}}
I appoint **{{attorney_in_fact}}** as my agent and attorney-in-fact.
{{#if alternate_attorney_in_fact}}
Should they be unable or unwilling to act, I appoint **{{alternate_attorney_in_fact}}** in their place.
{{else}}
_No alternate recorded. Answer **Alternate Attorney In Fact** — an agent who
emigrates, falls ill or declines leaves this document useless without one._
{{/if}}
{{else}}
_No agent recorded. Answer **Attorney In Fact** in questions.md — the person
authorised to act for you. No agent is ever assumed._
{{/if}}

---

## 3. Powers Granted

{{#if powers_granted}}
{{powers_granted}}

_From **Powers Granted**. The narrower and more specific the wording, the
more readily institutions accept it — "general authority" often triggers
extra scrutiny where a named account and named transaction would not._
{{else}}
_No powers recorded. Answer **Powers Granted** — general authority, or
special powers one per line (a named bank account, a property transaction, a
company filing). A power of attorney that grants nothing specific does
nothing specific._
{{/if}}

---

## 4. Commencement & Conditions

{{#if poa_effective_conditions}}
{{poa_effective_conditions}}

_From **POA Effective Conditions**._
{{else}}
_Not recorded. Answer **POA Effective Conditions** — from when the power
operates and under what conditions: immediately, from a date, or only for a
named transaction or period._
{{/if}}

This power may be revoked by me at any time while I have capacity, by
written notice to my agent and to any institution relying on it.

---

## 5. Signing

Signed at ______________________ on this ______ day of ______________________.

**Principal**: _____________________________
({{#if legal_full_name}}{{legal_full_name}}{{else}}{{full_name}}{{/if}})

**Agent (acceptance)**: Name ______________________ Signature ______________________

**Witness 1**: Name ______________________ Signature ______________________

**Witness 2**: Name ______________________ Signature ______________________

_Some institutions and registries require their own forms, certified copies
or notarisation — ask each institution that will rely on this power what it
accepts **before** signing._
