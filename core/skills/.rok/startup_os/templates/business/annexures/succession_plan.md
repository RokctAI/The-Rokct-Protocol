# {{company_name}} — Succession Plan

## 1. Purpose
How {{company_name}} continues if a person the business depends on becomes
unavailable — through illness, departure or death.

---

## 2. Current Leadership
{{#if executive_team}}
{{executive_team}}
{{else}}
{{#if board_directors}}
*   **Directors**: {{board_directors}}
{{else}}
_No leadership recorded._
{{/if}}
{{/if}}
{{#if shareholder_distribution}}

**Shareholding**: {{shareholder_distribution}}
{{/if}}

---

## 3. Key-Person Dependencies
{{#if key_person_dependencies}}
{{key_person_dependencies}}
{{else}}
_Not assessed. Answer **Key Person Dependencies** in questions.md — name each
person and what would stop if they were unavailable tomorrow._
{{/if}}

---

## 4. Succession Arrangements
{{#if succession_arrangements}}
{{succession_arrangements}}
{{else}}
_Not recorded. Answer **Succession Arrangements** — who steps into each role,
what authority they need, and how they would be given it._
{{/if}}

---

## 5. What a Successor Needs
Record and keep current, in a place a successor can reach:

*   Banking mandates and signatory changes
*   {{#if_feature company_registry}}{{registry_name}} filing credentials and director-change procedure{{else}}Corporate registry credentials{{/if_feature}}
{{#if_feature tax_clearance}}
*   {{tax_authority}} e-filing access and tax representative details
{{/if_feature}}
*   Customer and supplier contracts, with renewal dates
*   System and infrastructure credentials
{{#if intellectual_property}}
*   Intellectual property registrations: {{intellectual_property}}
{{/if}}
*   Insurance policies and claim procedures
{{#if key_suppliers}}
*   Supplier relationships and terms: {{key_suppliers}}
{{/if}}

---

## 6. Shareholding on Death or Exit
{{#if shareholder_distribution}}
Current shareholding: {{shareholder_distribution}}
{{/if}}

Record the answers to these — where they are undecided, the default is whatever
the law of {{jurisdiction_name}} imposes, which is rarely what the founders
intended:

*   Is there a shareholders' agreement, and does it cover death and incapacity?
*   Is there a buy-sell arrangement, and is it funded?
*   Who values the shares, and on what basis?
*   Do surviving shareholders have pre-emptive rights?

> [!IMPORTANT]
> Succession touches company law, tax and estate law. This document records
> intent; it is not a legal instrument. Have a qualified professional in
> {{jurisdiction_name}} draft the agreements it describes.
