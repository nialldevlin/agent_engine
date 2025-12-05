# LLM NOTICE: Do not read or modify this file unless explicitly instructed by the user.
# Prompt Library (Project-Agnostic)

## Plan Mode Prompts (Sonnet)

### 1. Implementation Brief Template
<Goal: one-sentence objective>

<Context: short summary + attached files if any>

Task:
Create an IMPLEMENTATION BRIEF with:
- Overview & Summary
- Phased Implementation Plan with HUMAN and QWEN steps
- Qwen Prompts for Act mode

<Additional constraints or architectural notes>

### 2. Architecture Review Prompt
Goal: Analyze subsystem relationships.

Files:
<@/path/to/files>

Output:
- Responsibilities
- Dependencies
- Hidden invariants
- Risks & modification guidance
- Summary Brief for Act mode

### 3. Phase Refinement / Update Prompt
Goal: Update an existing plan.

Input:
<@/docs/plan.md>

Task:
- Rewrite unclear phases
- Add missing steps
- Mark dependencies
- Prepare updated Brief for Act mode

---

## Act Mode Prompts (Llama/Qwen)

### 1. Surgical Edit Prompt
Goal: Make minimal changes to specific files.

Files to modify:
<@/path/file1>
<@/path/file2>

Rules:
- Minimal localized edits
- Do not modify any other files
- Preserve behavior unless stated
Output: unified diff only.

### 2. Documentation Sync (from Git Diff)
Task:
- Review git diff
- Update <@/docs/status.md>
- Mark finished items with " - [x] ... ✅ "
- Commit only that file.

### 3. Plan Progress Checker
Task:
- Compare implementation plan to repo state
- Mark completed steps
- Summarize remaining tasks
- Commit updated plan.

### 4. Commit Message Generator
Input:
<git diff or summary>

Output:
- Subject line (<72 chars)
- Optional body (<4 lines)

### 5. Commit Executor
Task:
- Stage <file>
- Commit with given message
- Show final status

### 6. Multi-file Search / Reasoning Prompt
Goal: Inspect patterns across repo.

Query:
<search question>

Task:
- Grep-like reasoning
- Summaries only (no edits)

### 7. Refactor (Non-destructive)
Goal: Improve clarity without functional change.

File:
<@/path/file.py>

Rules:
- No API changes
- No new dependencies
- Minimal edits
Output: diff only.

### 8. Test Generation / Fixing
Goal:
Generate or update tests.

Files:
<@/tests/...>

Constraints:
- Follow existing patterns
Output: diff.

