# Cline Prompt & Workflow Cheat Sheet

A short, skimmable guide for using **Claude Sonnet** (planning) + **Qwen2.5-Coder** (implementation) inside **Cline**.

---

## ✔️ Quick Workflow Checklist (Every Session)

1. **Open the repo + create a new branch**
   ```
   git checkout -b task/<name>
   ```
2. **Identify the scope**
   - 1–3 files max per implementation step.
   - For large tasks: break into micro-phases: *Analyze → Plan → Implement → Review*.
3. **Plan with Sonnet**
   - Generate a *Brief* summarizing:  
     - Objective  
     - Affected files  
     - Required functions/classes  
     - Constraints & invariants  
4. **Switch to Qwen2.5-Coder (Act Mode)**
   - Implement **only** according to the Brief.
   - Keep edits minimal and localized.
5. **After each change**
   - Run tests / lint / type-check.
   - Ask Sonnet for review if unsure.
6. **Commit often**
   ```
   git add -p
   git commit -m "Implement X"
   ```
7. **Repeat in small cycles**  
   Large jumps = large mistakes.

---

## ✔️ Prompt Checklist (Planning With Sonnet)

Before hitting Enter, confirm your prompt:

- [ ] Did I clearly define the **goal**?  
- [ ] Did I list **specific files** involved?  
- [ ] Did I give the **relevant context** (not the whole repo)?  
- [ ] Did I define what **success looks like**?  
- [ ] Did I ask for output in a **Brief format**?  
- [ ] Did I avoid asking Sonnet to write large code directly?

---

## ✔️ Prompt Checklist (Implementing With Qwen2.5-Coder)

Before sending a task to Qwen:

- [ ] Is the task **small enough** (1–3 files)?  
- [ ] Did I supply the **Brief** or relevant snippet?  
- [ ] Did I explicitly say **what NOT to touch**?  
- [ ] Did I request **minimal, surgical edits**?  
- [ ] Did I ask for a **diff or unified patch**?  
- [ ] Did I remind it to follow the Brief exactly?

---

## 💬 Planning Prompt (Sonnet) — Template

```
You are assisting with a software engineering task using Cline Plan mode.

Goal:
<one-sentence objective for this task or phase>

Context:
<short summary of the relevant files, subsystems, or plan>
<optional: @/file/paths.md references that Cline will attach>

Task:
Create an IMPLEMENTATION BRIEF with the following THREE SECTIONS, in order.
Do NOT write any full code. Keep everything concise, explicit, and actionable.
Assume the implementation will be performed automatically by Qwen2.5-Coder-7B
in Cline Act mode, so your plan must be safe for auto-execution.

If this brief covers a sub-phase of a larger roadmap, name phases accordingly
(e.g., "Phase 2.A", "Phase 2.B") and maintain consistent numbering.

----------------------------------------------------------------
SECTION 1 — OVERVIEW & SUMMARY (FOR HUMAN USER)
----------------------------------------------------------------
- Briefly restate the Goal in your own words.
- Summarize the current state of the relevant code/docs.
- Clarify assumptions, constraints, and success criteria.
- Call out any risks, unknowns, or prerequisites.
- Keep this section short (2–6 short paragraphs or bullet lists).

----------------------------------------------------------------
SECTION 2 — PHASED IMPLEMENTATION PLAN WITH STEPS (FOR HUMAN USER)
----------------------------------------------------------------
Design a phased plan that a human can supervise and Qwen can safely auto-execute.

For each phase:
- Use the format: "Phase N — <short phase name>"
- Describe the goal of the phase.
- List exact files to modify or create (full paths required).
- List any functions/classes to add, modify, or remove (with signatures).
- State invariants and constraints that must be preserved.
- List important edge cases.
- Note any ordering/dependencies between phases.

Every phase MUST begin with:

### Step 1 — [HUMAN] Pre-flight verification  
This step must describe what the human must confirm *before* any automatic code
modification occurs. Examples:
- Confirm file paths exist.
- Confirm architectural assumptions still hold.
- Confirm the phase should proceed without structural changes.
Cline will pause on HUMAN steps, preventing unintended automatic execution.

After Step 1, define the implementation steps for that phase:

For EACH step:
- Use the format:

  **Step K — [QWEN] <short step name>**  
  OR  
  **Step K — [HUMAN] <short step name>**

- [HUMAN] steps may be: running commands, reviewing diffs, validating tests,
  adjusting configs, or making yes/no decisions.

- [QWEN] steps MUST:
  - Be small, atomic, and safe to auto-execute.
  - Affect **no more than 1–2 files** per step.
  - Include explicit @-paths for all file modifications.
  - Describe only the specific changes needed (no broad refactors).
  - Preserve invariants.
  - Request only diff-style or minimal output.
  - Avoid touching unrelated files.
  - Represent a standalone Act-mode call that can run unattended.

Phases should:
- Fit within 1–3 focused coding sessions.
- Follow correct dependency ordering.
- Cover all work required to achieve the Goal.

----------------------------------------------------------------
SECTION 3 — QWEN IMPLEMENTATION PROMPTS (FOR CLINE ACT MODE)
----------------------------------------------------------------
Generate one Qwen prompt for **every [QWEN] step** defined in Section 2.

For each Qwen prompt:
- Use the format:

  **Qwen Prompt N (Phase X, Step Y — <short description>)**

- Include a code block containing EXACT text to paste into Act mode.
- Repeat all constraints and file paths explicitly.
- Specify:
  - The goal of this step.
  - The exact @-paths to the files being modified.
  - The function/class signatures or sections to update.
  - The invariants that must be preserved.
  - What Qwen MUST NOT modify.
  - Required output format (e.g., “Return a unified diff for modified files only.”)

Important notes for Qwen prompts:
- These prompts will AUTO-EXECUTE sequentially in Act mode.
- DO NOT create any [QWEN] step that is unsafe for automatic execution.
- Prefer many small steps over a large one.
- Every prompt must be deterministic and reversible.

----------------------------------------------------------------
General Requirements
----------------------------------------------------------------
- Do NOT include actual code implementations anywhere in this brief.
- Ensure all phases, steps, and Qwen prompts align with the Goal and Context.
- Assume Qwen has limited reasoning: be explicit, redundant, and precise.
- Design each QWEN step so auto-execution cannot cause cascading failures.
- HUMAN steps should act as checkpoints between major transitions.
```

---

## 💬 Implementation Prompt (Qwen2.5-Coder) — Template

```
Follow this Implementation Brief strictly:

<PASTE BRIEF>

Your task:
Modify ONLY the following files:
- <file1.py>
- <file2.py>

Constraints:
- Make minimal, localized edits.
- Preserve all existing behavior unless the Brief specifies otherwise.
- Do not edit any other files.
- Do not invent new modules unless instructed.

Output:
- A unified diff patch ONLY.
- No explanations unless an error prevents producing a diff.
```

---

## 💬 Status Prompt (Qwen2.5-Coder) — Template

Use this *after* Qwen has produced a diff or completed an implementation task.

```
You just implemented changes according to this brief:

<PASTE BRIEF OR SHORT SUMMARY>

And produced the following diff or set of edits:

<PASTE DIFF OR SHORT DESCRIPTION OF CHANGES>

Now write a STATUS UPDATE in plain text (no code, no diff) that includes:
- What was changed (files, functions, modules)
- Why it was changed (link back to the brief)
- Any tests added/updated or commands that should be run
- Any follow-up work or TODOs

Format:
STATUS:
- <bullet points>

COMMIT MESSAGE (short, imperative):
- <one-line commit message>
```

---

## 💬 Refactor Prompt (Qwen2.5-Coder)

```
Goal: Refactor <file> to improve clarity and maintainability
without changing external behavior.

Rules:
- Do NOT modify public APIs.
- Do NOT introduce new dependencies.
- Keep style consistent with current code.
- Only modify this file.

Provide:
- A unified diff patch implementing the refactor.
```

---

## 💬 Multi-File Reasoning (Sonnet → Qwen Workflow)

**Sonnet Prompt:**

```
Analyze these files and summarize:
- Responsibilities
- Dependencies
- Hidden invariants
- Risks during modification

Output a short BRIEF telling Qwen exactly what to change.
```

**Qwen Prompt:**

```
Apply the BRIEF to modify the following files:
<file1> <file2>

Make surgical changes. Output a diff only.
```

---

## ✔️ Git + Safety Workflow

1. Commit before AI edits:
   ```
   git add -A && git commit -m "before AI changes"
   ```
2. After each diff:
   ```
   git apply patch.diff
   ```
3. Test:
   ```
   pytest
   mypy .
   ```
4. If things break:
   ```
   git restore .
   ```
   or  
   ```
   git reset --hard HEAD
   ```

---

## ✔️ When to Use Which Model

### **Use Sonnet For:**
- Planning & architecture  
- Multi-file reasoning  
- Writing BRIEFs  
- Reviewing complex changes  

### **Use Qwen2.5-Coder For:**
- Implementing code  
- Editing 1–3 files  
- Refactors & cleanup  
- Generating diffs  

---

## ⚠️ Common Pitfalls To Avoid

- Don’t ask Qwen to reason about the whole repo at once.  
- Don’t let Sonnet write giant code sections—always ask for a Brief.  
- Don’t skip specifying **exact files**.  
- Don’t combine “plan + implement” in a single prompt.  
- Don’t trust either model to track invariants unless stated clearly.

---

## ✔️ Quick Mental Model

**Sonnet = Architect.  
Qwen = Construction Worker.  
You = Project Manager.**

Keep the architect and worker separated.  
Never let the worker “design” or the architect “build.”

---

Enjoy your happy gremlin coding loops.
