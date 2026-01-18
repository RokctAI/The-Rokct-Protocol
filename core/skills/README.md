# Rokct Skills

This directory follows the **Anthropic Skills Standard** (`anthropics/skills`).
Each folder contains a self-contained capability for the Agent.

## Structure
```text
skills/
└── [skill_name]/
    ├──- **SKILL.md** (required): The main instruction file with YAML frontmatter.
    └── **resources/** (optional): Templates or reference files.
```

*Note*: Complex scripts (`scripts/`) are supported but not currently used in the Core Skills.

## How to Use
*   **Agent**: When asked to perform a specific task (e.g., "Security Audit"), look for a matching folder in `skills/` and follow `SKILL.md`.
*   **Humans**: specific skills by copying folders from the standard repo.
