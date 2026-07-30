# {{company_name}} — Company Description

## 1. Corporate Identity

{{#if_feature company_registry}}
*   **{{company_name_status}}**: {{company_name}}
*   **Trading Name**: {{trading_name}}
*   **{{registry_name}} Registration Number**: {{reg_number}}
*   **Registration Date**: {{reg_date}}
*   **Registered Office**: {{registered_office}}
{{#if_feature tax_clearance}}
*   **{{tax_authority}} Tax Reference**: {{tax_number}}
{{/if_feature}}
{{else}}
*   **Trading Name**: {{trading_name}}
*   **Jurisdiction**: {{jurisdiction_name}}
{{/if_feature}}
{{#if establishment_date}}
*   **Established**: {{establishment_date}}
{{/if}}
*   **Primary Base**: {{primary_base}}
{{#if head_office}}
*   **Head Office**: {{head_office}}
{{/if}}
{{#if secondary_locations}}
*   **Additional Sites**: {{secondary_locations}}
{{/if}}
{{#if industry}}
*   **Industry**: {{industry}}
{{/if}}
*   **Shareholders**: {{shareholder_distribution}}
*   **Directors**: {{board_directors}}
*   **Headcount**: {{personnel_count}}
{{#if key_suppliers}}
*   **Strategic Suppliers**: {{key_suppliers}}
{{/if}}
{{#if intellectual_property}}
*   **Intellectual Property**: {{intellectual_property}}
{{/if}}

{{#if_feature bbee}}
{{#if bee_level}}
*   **B-BBEE Status**: {{bee_level}} — {{bee_procurement_recognition}} procurement
    recognition, {{bee_black_ownership}} black ownership, {{bee_youth_owned}} youth
    owned. Certificate {{bee_cert_number}}, valid to {{bee_expiry_date}}.
{{else}}
*   **B-BBEE Status**: no certificate on file. No contribution level is claimed
    for this entity.
{{/if}}
{{/if_feature}}

{{#if_feature trademarks}}
{{#if trademarks_details}}
*   **Registered Trade Marks**:
{{trademarks_details}}
{{/if}}
{{/if_feature}}

---

## 2. Mission, Vision and Philosophy

### Mission
{{#if mission_statement}}
{{mission_statement}}
{{else}}
_Not yet recorded. Answer **Mission Statement** in questions.md — what the
venture does, for whom, and why._
{{/if}}

### Vision
{{#if vision_statement}}
{{vision_statement}}
{{else}}
_Not yet recorded. Answer **Vision Statement** in questions.md._
{{/if}}

{{#if core_philosophy}}
### Operating Philosophy
{{core_philosophy}}
{{/if}}

{{#if brand_positioning}}
### Positioning
{{brand_positioning}}
{{/if}}

---

## 3. What We Build and How

{{#if core_value_proposition}}
{{core_value_proposition}}
{{/if}}

{{#if product_components}}
### Components
{{product_components}}
{{/if}}

{{#if technical_architecture}}
### Delivery Architecture
{{technical_architecture}}
{{/if}}

{{#if hardware_or_equipment}}
### Hardware & Equipment
{{hardware_or_equipment}}
{{/if}}

{{#if key_processes}}
### Core Operating Processes
{{key_processes}}
{{/if}}

{{#unless technical_architecture}}
{{#unless product_components}}
_How the offering is built and delivered has not been recorded. Answer
**Product Components** and **Technical Architecture** in questions.md — a
funder or partner reading this document will look for it here._
{{/unless}}
{{/unless}}

---

## 4. Standards & Compliance

{{#if quality_standards}}
*   **Standards and certifications**: {{quality_standards}}
{{/if}}
{{#if privacy_law}}
*   **Data protection**: {{privacy_law}} applies to personal data handled by
    this venture.
{{/if}}
{{#if standards_body}}
*   **National standards body**: {{standards_body}}
{{/if}}
{{#if_feature company_registry}}
*   **Corporate filings**: maintained with {{registry_name}}.
{{/if_feature}}
{{#unless quality_standards}}
{{#unless privacy_law}}
_No standards or certifications recorded._
{{/unless}}
{{/unless}}
