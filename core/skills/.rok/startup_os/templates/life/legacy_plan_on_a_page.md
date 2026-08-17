# {{full_name}} — Legacy Plan on a Page

## 1. Stewardship Vision

{{#if legacy_vision}}
> **Long-Term Stewardship Goal**: {{legacy_vision}}
{{else}}
_No stewardship goal recorded. Answer **Legacy Vision** in questions.md — what
should outlast you, and in whose hands?_
{{/if}}
{{#if life_purpose}}

Aligned with the core purpose: _{{life_purpose}}_.
{{/if}}

---

## 2. Stewardship Profile

*   **Custodian**: {{full_name}}
*   **Stewardship Location**: {{primary_base}}
{{#if dependants}}
*   **Dependants**: {{dependants}}
{{/if}}
{{#if key_relationships}}
*   **Trusted Circle**: {{key_relationships}}
{{/if}}
{{#if executor}}
*   **Nominated Executor**: {{executor}}{{#if alternate_executor}} (alternate: {{alternate_executor}}){{/if}}
{{else}}
*   **Nominated Executor**: _not recorded — answer **Executor**; an estate
    without one is administered by a stranger._
{{/if}}

---

## 3. Digital & Document Estate

{{#if digital_asset_inventory}}
*   **Digital Asset Inventory**: {{digital_asset_inventory}}
{{else}}
*   **Digital Asset Inventory**: _not recorded — answer **Digital Asset
    Inventory**: the accounts, domains, wallets and repositories that matter,
    and where access is documented._
{{/if}}

---

## 4. Verification & Release Protocol

How sensitive documents — the will, policies, access instructions — are
released when the time comes. Release should never hang on one person's
memory or one channel.

{{#if release_protocol}}
{{release_protocol}}
{{else}}
_No protocol recorded. Answer **Release Protocol** — who verifies the event,
over which channels, and after what waiting period. The three-stage shape
below is a starting suggestion, not a description of your arrangements:_

| Stage | Event | Purpose |
| :--- | :--- | :--- |
| **Verify** | A nominated person confirms the death or incapacity | No release on rumour |
| **Notify & wait** | The owner (or a second verifier) is alerted over more than one channel, with a waiting period to stop a false trigger | A living owner can halt the release |
| **Release** | Documents pass to the executor and named recipients only | The right papers reach the right hands |

{{/if}}

---

## 5. Memorial Wishes

{{#if memorial_wishes}}
{{memorial_wishes}}
{{else}}
_No wishes recorded. Answer **Memorial Wishes** if you want a say — burial or
cremation, ceremony, tone. Unrecorded wishes are guessed at the worst time._
{{/if}}

---

## 6. The Will

{{#if will_execution_status}}
> [!NOTE]
> **Will execution recorded by the owner**: {{will_execution_status}}. Only
> the signed original has legal force — keep it safe, tell the executor where
> it is, and have any change professionally reviewed and re-executed.
{{else}}
> [!WARNING]
> **The draft will in this suite is UNSIGNED and has no legal force.** Have
> it reviewed by a qualified professional in {{jurisdiction_name}}, sign it
> with the required formalities, then record the date under **Will Executed**
> in questions.md.
{{/if}}
