# Coding Schemas

**Usage**: When generating these artifacts, you **MUST** follow the JSON structure defined here.

## 1. Feature Implementation Plan
**Trigger**: "Create an implementation plan for [Feature]".

```json
{
  "feature_name": "String",
  "goal": "String",
  "verification_plan": {
    "automated_tests": ["String"],
    "manual_steps": ["String"]
  },
  "changes": [
    {
      "file": "path/to/file",
      "action": "CREATE|MODIFY|DELETE",
      "description": "String"
    }
  ]
}
```

## 2. Release Note
**Trigger**: "Generate release notes".

```json
{
  "version": "String",
  "type": "Major|Minor|Patch",
  "highlights": ["String"],
  "breaking_changes": ["String"]
}
```
