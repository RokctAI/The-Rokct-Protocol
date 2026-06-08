---
name: StartupOS Compiler & Conversational Bridge
description: Dynamic ROKCT Nexus compilation framework that generates Business and Life plans on WhatsApp, Web, and other channels, coupled with real-time AI memory updating and automated profile provisioning.
---

# StartupOS Compiler & Conversational Bridge Skill

This core skill houses the **StartupOS Dual Engine Compiler Pipeline** and the **Hermes Agent Bridge**. It represents the functional heart of the **Nexus Architecture**, connecting unstructured conversation histories with structured, venture-grade strategy documents.

## Directory Structure

```text
The-Rokct-Protocol/core/skills/startup_os/
├── SKILL.md                    # Main skill capability specification
└── scripts/
    ├── main.py                 # Command line CLI interface
    └── core/                   # Core Python engines
        ├── compiler.py         # Main interpolation & compilation pipeline
        ├── parser.py           # Structure-preserving question parser
        └── agent_bridge.py     # Hermes programmatic read/write/provision APIs
```

## Features

1.  **Dual Engine Compilation**: Dynamically resolves both `--type business` and `--type life` profiles using clean double-curly brace substitution (`{{variable_name}}`).
2.  **Conversational Agent Bridge (`agent_bridge.py`)**: Equips the Hermes agent (`nous' hermes-agent`) to write answers, log milestones, and auto-provision folders directly using Python hooks in conversational loops.
3.  **Automated Compliance & CIPC Sourcing**: Automatically extracts registration numbers, B-BBEE parameters, and tax IDs from local PDFs or dynamically formats suffixes (e.g., `(Pty) Ltd` or `CC`) based on South African legal codes.
4.  **Version Control & Bidirectional Mappings**: Automatically appends ROKCT Document version control blocks (`sinyage.1aedb8`) and builds dynamic hypertext links between downstream canvases and plans.

## Usage Scenarios

### A. Dynamic Profile Provisioning (Conversation Trigger)
When a user signs up on WhatsApp or Next.js and mentions an entity name (e.g. *Table Mountain Tech*), Hermes invokes:
```python
from core.skills.startup_os.scripts.agent_bridge import auto_provision_profile

questions_file = auto_provision_profile(
    instance_type="business",
    instance_name="TableMountainTech",
    primary_base="Cape Town, South Africa"
)
```

### B. Ambient Achievement Logging (The Living Ledger)
When a user shares a personal achievement verbally (e.g., *"Hey Rok, I just finished writing the multi-tenant solar battery integration guidelines!"*), Hermes routes it to:
```python
from core.skills.startup_os.scripts.agent_bridge import log_ambient_milestone

log_ambient_milestone(
    filepath="instances/life/Rendani/questions.md",
    category="Technical Mastery",
    entry_text="Successfully engineered isolated multi-tenant Solar routing systems."
)
```

### C. Programmatic Update & Re-compilation
When answers change, update the profile and compile downstream deliverables:
```python
from core.skills.startup_os.scripts.agent_bridge import update_profile_answer
from core.skills.startup_os.scripts.compiler import compile_instance

update_profile_answer(
    filepath="instances/business/ROKCT/questions.md",
    question_label="Core Value Proposition",
    new_answer="Sovereign edge-native AI services for emerging enterprise."
)

compile_instance(instance_type="business", instance_name="ROKCT")
```
