# LLM NOTICE: Do not read or modify this file unless explicitly instructed by the user.
# Prompt Library (Project-Agnostic)

## Plan Mode Prompts (Sonnet)

### 1. Implementation Brief Template
Goal: <one-sentence objective>

Context: <short summary + attached files if any>

Task:
Create an IMPLEMENTATION BRIEF with the following THREE SECTIONS, in order.
Do NOT write any full code. Keep everything concise, explicit, and actionable.
Assume the implementation will be done by a smaller model (Qwen2.5-Coder-7B)
using Cline Act mode, so be very clear and step-by-step.

If this brief is for a phase of a larger roadmap, treat the phases you define
as sub-phases of that parent phase (e.g., "Phase 2.A", "Phase 2.B"), and keep
all references consistent.

SECTION 1 — OVERVIEW & SUMMARY (FOR HUMAN USER)
- Briefly restate the Goal.
- Summarize the current state of the relevant code/docs.
- Clarify assumptions, constraints, and success criteria.
- Call out any risks, unknowns, or prerequisites.
- Keep this section short (2–6 short paragraphs or bullet lists).

SECTION 2 — PHASED IMPLEMENTATION PLAN WITH STEPS (FOR HUMAN USER)
Design a phased plan that a human can follow and supervise.

For each phase:
- Use the format: "Phase N — <short phase name>" (or "Phase 2.A", etc. if part of a larger plan).
- Describe the goal of the phase.
- List the exact files to modify or create (with full paths).
- List the functions/classes to add, modify, or remove (with signatures where relevant).
- State the invariants and constraints that must be preserved.
- List important edge cases to consider.
- Include any notes about ordering or dependencies between phases.

Then, for EACH PHASE, define a numbered list of STEPS that fully cover the work
for that phase.

For each step:
- Use the format: "Step K — [QWEN] <short step name>" OR "Step K — [HUMAN] <short step name>".
- Ensure each [QWEN] step corresponds to a single focused Qwen Act-mode call.
- Ensure each [HUMAN] step is something the human can do: e.g., run a command,
  inspect output, adjust a config, or review changes.

For [QWEN] steps, briefly specify:
- Target files and @-paths (e.g., @/src/module/file.py).
- The concrete change or addition Qwen should make (functions, behavior, tests).
- Any important constraints ("do not touch X", "preserve Y", "follow interface Z").
- Expected output format (e.g., "unified diff", "patched files only") at a high level.

For [HUMAN] steps, briefly specify:
- Exact commands to run (e.g., `pytest path::test_name`, `npm test`).
- Any manual checks or review criteria (what to look for in logs, diffs, or UI).
- Any branching logic (e.g., "If tests fail, return to Phase 1, Step 2").

Phases should:
- Be small enough to implement in 1–3 focused coding sessions.
- Be ordered so that later phases depend on earlier ones, not vice versa.
- Cover all work needed to achieve the Goal.

SECTION 3 — QWEN IMPLEMENTATION PROMPTS (FOR CLINE ACT MODE)
Create a numbered list of concrete prompts that can be pasted into Cline
Act mode for Qwen2.5-Coder-7B to implement the plan step-by-step.

For this section:
- Create ONE prompt per [QWEN] step from SECTION 2.
- Preserve the same phase and step numbering so mapping is obvious.
- Use the format: "Qwen Prompt N (Phase X, Step Y — <short description>)".

Inside each prompt:
- Reference the relevant phase and step explicitly.
- Reference the exact files using @-paths (e.g., @/src/module/file.py).
- Specify what Qwen MUST do (e.g., "implement function X with behavior Y").
- Specify what Qwen MUST NOT do (e.g., "do not modify any other files").
- Request the correct output format (e.g., "output a unified diff only").
- Keep each prompt small in scope (ideally 1–2 files and one clear task).

Example structure for each Qwen prompt (adapt to the specific task):

Qwen Prompt N (Phase X, Step Y — <short description>)
```text
<exact prompt to paste into Cline Act mode, including:
- Summary of the goal for this step.
- @-paths for relevant files.
- Specific instructions on changes to make.
- Constraints and invariants to respect.
- Required output format (e.g., "Return a unified diff for the modified files only").>
```

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

