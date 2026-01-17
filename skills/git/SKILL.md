---
name: Git Standard
description: Best practices for version control, committing, and branching.
version: 1.0.0
---

# Git Standard Skill

## Context
You are a DevOps Engineer. You rely on clean git history for automation.

## 1. Commit Messages (Conventional Commits)
**Rule**: All commits MUST follow `type(scope): description`.

*   **Types**:
    *   `feat`: New feature (Correlation with Minor version).
    *   `fix`: Bug fix (Correlation with Patch version).
    *   `docs`: Documentation only.
    *   `style`: Formatting (missing semi-colons, etc).
    *   `refactor`: Code change that neither fixes a bug nor adds a feature.
    *   `perf`: A code change that improves performance.
    *   `test`: Adding missing tests.
    *   `chore`: Maintain.
*   **Example**: `feat(auth): add google login provider`

## 2. Branching Strategy
*   `main`: Production ready. Protected.
*   `develop`: Integration branch (if applicable).
*   `users/[name]/[feature]`: Your working branch.

## 3. Pull Requests
*   **Title**: Matches the commit standard (e.g., `feat: Add Login`).
*   **Description**:
    *   **Context**: Why this PR?
    *   **Changes**: What changed?
    *   **Testing**: How did you test it?
    *   **Breaking**: [Yes/No]

## 4. Safety
*   **Never** commit secrets (`.env`).
*   **Always** `git pull --rebase` before pushing to avoid merge commits.
