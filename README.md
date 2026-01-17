# Agent Rules & Context

This repository acts as the **Single Source of Truth (SSO)** for the AI agent's behavior, constraints, and operational knowledge.

## How to Read This Repo
The agent **MUST** process these rules in the following priority order:

1.  **[Core Rules](./core/README.md)**: Absolute mandates on authority, obedience, and communication.
    *   [Authority & Obedience](./core/01_authority.md)
    *   [Communication](./core/02_communication.md)
2.  **[Coding Standards](./coding/standards.md)**: Technical constraints, stack preferences, and "no placeholder" policies.
3.  **[Design System](./coding/design_system.md)**: Aesthetic guidelines for "Premium" output.
4.  **[Templates](./templates/project_map.md)**: Templates for Memory (`templates/memory.md`), Context Map (`templates/project_map.md`), and Decisions (`templates/decision_log.md`).
5.  **[Workflows](./workflows/README.md)**: SOPs, including [Initialization](./workflows/init_protocol.md).

## Purpose
To maximize productivity by enforcing a clear, predictable flow of user-agent interaction and high-quality output standards.
