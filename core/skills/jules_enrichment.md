# Skill: Jules Batch Enrichment
# Version: 2.0 (Modular Engine)

## Objective
To perform advanced AI enrichment on new opportunities discovered by the automated sync engine.

## Step 1: Locate the Queue
Before starting, you MUST read the current work list:
- **Path**: `.rokct/agent/todo.json`

## Step 2: Batch Processing Logic
For each file path listed in `todo.json["files"]`:
1. **Open the File**: Read the markdown content of the tender.
2. **Deep Research**: Analyze the tender description and linked documents.
3. **Advanced Tasks**: Populate the `## AI Checklist (Jules)` section with 3-5 high-value, specific proposal tasks.
4. **Enrichment Marker**: Ensure the tasks are unique and detailed (this automatically marks the tender as **ADVANCED** for the frontend).
5. **Save**: Overwrite the markdown file with your enriched version.

## Step 3: Success Criteria
- Do NOT modify the `Quick Stats` or `Audit & Status` sections.
- Preserve all existing content above the `## AI Checklist` header.
- Use the detailed task format: `- [ ] Task Name | Weight`.

## Step 4: Completion
Once you have processed all files in the list, commit your changes with the message:
`feat(jules): advanced enrichment for batch [YYYY-MM-DD]`
