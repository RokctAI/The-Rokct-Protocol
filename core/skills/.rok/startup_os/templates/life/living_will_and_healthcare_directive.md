# Living Will & Healthcare Directive — {{#if legal_full_name}}{{legal_full_name}}{{else}}{{full_name}}{{/if}}

> [!IMPORTANT]
> **This is a working draft assembled from `questions.md` — it is not legal
> advice, and its legal effect varies sharply by jurisdiction.** It speaks
> for you only while you are alive and unable to speak for yourself; it is
> not a will and disposes of nothing. Review it with a qualified
> professional in {{jurisdiction_name}}, and with your doctor, before
> signing — and give copies to the people who would need it at 2am.

{{#if_jurisdiction ZA}}
> [!WARNING]
> **South Africa**: living wills are **not statutorily regulated** — no
> statute gives this document binding force. In practice it serves as
> persuasive evidence of your wishes and treating teams generally seek to
> honour a clear, informed, recent directive, but they are not compelled to
> by statute. Discuss it with your doctor, keep it current, and make sure
> your healthcare proxy holds a copy — a directive nobody can produce
> persuades nobody.
{{else}}
> [!WARNING]
> The rules for advance healthcare directives in {{jurisdiction_name}} are
> not encoded in this engine — whether this document binds a treating team,
> and what formalities it needs, must be **verified with a qualified
> professional** before you rely on it.
{{/if_jurisdiction}}

{{#if living_will_execution_status}}
> [!NOTE]
> **Execution recorded by the owner**: {{living_will_execution_status}}.
> This compiled file remains a working copy — only the signed original
> carries whatever force your jurisdiction gives it. Tell your proxy and
> your doctor where it is.
{{else}}
> [!WARNING]
> **Status: UNSIGNED DRAFT.** Once the directive has been signed and
> witnessed, record the date and place under **Living Will Executed** in
> questions.md so this suite reflects reality.
{{/if}}

---

## 1. Declaration

{{#if legal_full_name}}
I, **{{legal_full_name}}**{{#if primary_base}}, of {{primary_base}}{{/if}}, make this directive while of sound mind, to speak for me if illness or injury leaves me unable to make or communicate my own healthcare decisions. It expresses my own considered wishes.
{{else}}
_Full legal name not recorded. Answer **Legal Full Name** in questions.md —
exactly as it appears on your identity document._
{{/if}}

---

## 2. Healthcare Proxy

{{#if healthcare_proxy}}
I ask that **{{healthcare_proxy}}** be consulted as my healthcare proxy and
that my wishes below guide their decisions.
{{#if alternate_healthcare_proxy}}
Should they be unavailable or unwilling, I name **{{alternate_healthcare_proxy}}** in their place.
{{else}}
_No alternate recorded. Answer **Alternate Healthcare Proxy** — a directive
with a single point of failure in its proxy is a fragile directive._
{{/if}}

_Whether a nominated proxy has formal decision-making authority in
{{jurisdiction_name}} is a question for your adviser — in some jurisdictions
this nomination guides the treating team rather than binding it._
{{else}}
_No proxy recorded. Answer **Healthcare Proxy** in questions.md — the person
who should speak for you when you cannot. Without one, that role falls to
whoever the law or the hospital designates by default._
{{/if}}

---

## 3. Treatment Preferences

{{#if life_sustaining_treatment}}
*   **Life-sustaining treatment**: {{life_sustaining_treatment}}
{{else}}
*   **Life-sustaining treatment**: _not recorded — answer
    **Life Sustaining Treatment** in your own words; this is the clause the
    whole document exists for._
{{/if}}
{{#if resuscitation_preference}}
*   **Resuscitation (CPR)**: {{resuscitation_preference}}
{{else}}
*   **Resuscitation (CPR)**: _not recorded — answer
    **Resuscitation Preference**, including any conditions._
{{/if}}
{{#if pain_relief_priority}}
*   **Pain relief**: {{pain_relief_priority}}
{{else}}
*   **Pain relief**: _not recorded — answer **Pain Relief Priority** — e.g.
    whether comfort takes priority even at the cost of alertness._
{{/if}}

No preference is ever assumed: an unanswered question above is a gap in this
directive, not a default.

---

## 4. Organ & Tissue Donation

{{#if organ_donation_wishes}}
{{organ_donation_wishes}}

_Registering formally with your jurisdiction's donor registry, and telling
your family, matters more in practice than this paragraph — families are
usually consulted at the moment of decision._
{{else}}
_No wishes recorded. Answer **Organ Donation Wishes** — either way, a
recorded wish spares your family a guess at the worst possible moment._
{{/if}}

---

## 5. Signing

Signed at ______________________ on this ______ day of ______________________.

**Signature**: _____________________________
({{#if legal_full_name}}{{legal_full_name}}{{else}}{{full_name}}{{/if}})

**Witness 1**: Name ______________________ Signature ______________________

**Witness 2**: Name ______________________ Signature ______________________

_Witnessing requirements for a directive vary by jurisdiction and are not
encoded here; independent adult witnesses who are not your healthcare
providers or beneficiaries are a sensible baseline — confirm with your
adviser._
