# {{full_name}} — Emergency Information Page (ICE)

> [!NOTE]
> One page, for the person standing next to you in an emergency. Everything
> here is distilled from answers already in `questions.md` — keep those
> current and this page stays current. Print it; a locked phone helps
> nobody.

## 1. Call First

{{#if emergency_contacts}}
{{emergency_contacts}}
{{else}}
_No contacts recorded. Answer **Emergency Contacts** in questions.md — one
per line: name, relationship, phone. This is the single most useful answer
on this page._
{{/if}}

---

## 2. Medical

{{#if primary_doctor}}
*   **Doctor**: {{primary_doctor}}
{{else}}
*   **Doctor**: _not recorded — answer **Primary Doctor** (name and phone)._
{{/if}}
{{#if allergies_and_conditions}}
*   **Allergies, conditions & medication**:
    {{allergies_and_conditions}}
{{else}}
*   **Allergies, conditions & medication**: _not recorded — answer
    **Allergies And Conditions**, one per line. If there are none, say
    "None known" — an explicit none is information; a blank is a question
    mark over a stretcher._
{{/if}}
{{#if healthcare_proxy}}
*   **Healthcare proxy**: {{healthcare_proxy}}{{#if alternate_healthcare_proxy}} (alternate: {{alternate_healthcare_proxy}}){{/if}} — see the Living Will & Healthcare Directive in this suite.
{{/if}}
{{#if organ_donation_wishes}}
*   **Organ donation**: {{organ_donation_wishes}}
{{/if}}

---

## 3. Where Things Are

{{#if key_document_locations}}
{{key_document_locations}}
{{else}}
_No locations recorded. Answer **Key Document Locations** — where the will,
policies, identity document and medical aid details live, one per line._
{{/if}}
{{#if digital_asset_inventory}}

*   **Digital assets**: {{digital_asset_inventory}}
{{/if}}

---

## 4. If the Worst Has Happened

{{#if executor}}
*   **Executor**: {{executor}}{{#if alternate_executor}} (alternate: {{alternate_executor}}){{/if}}
{{/if}}
{{#if release_protocol}}
*   **Document release protocol**: {{release_protocol}}
{{else}}
*   **Document release protocol**: _not recorded — answer
    **Release Protocol** in questions.md: who verifies the event, over which
    channels, and after what waiting period._
{{/if}}
