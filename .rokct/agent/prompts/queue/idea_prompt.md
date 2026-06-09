# Idea Session: Protocol Self-Improvement

You are running a self-improvement idea session for The Rokct Protocol.

## Step 1 — Read the Codebase
Read the entire protocol codebase carefully before proposing anything:
- All files in `core/`
- All files in `modes/`
- All files in `profiles/`
- All files in `workflows/`

## Step 2 — Read Rejected Ideas
Read every file in `.rokct/agent/rejected/`.
Do **NOT** propose anything with a similar title, goal, or approach to what is already there.

## Step 3 — Generate 10 Ideas
Generate exactly 10 improvement ideas. For each idea write a separate JSON file to `.rokct/agent/prompts/queue/` using the template at `.rokct/agent/idea_template.json`.

### Rules for ideas:
- Each idea must target a specific, actionable improvement — not vague suggestions
- Ideas must be scoped to the protocol repo only — not other repos
- Each prompt must be detailed enough for an agent to execute without asking questions
- Follow the TASK → BACKGROUND → CRITICAL RULES → SPECIFIC TASKS → GOAL structure from the template
- Rate honestly out of 10 — do not inflate ratings to avoid rejection
- Write the rationale field honestly — explain why this improvement matters

## Step 4 — Do Nothing Else
Do **NOT** implement any ideas.
Do **NOT** open a PR.
Do **NOT** modify any existing protocol files.
Your only output is the JSON files written to `.rokct/agent/prompts/queue/`.
