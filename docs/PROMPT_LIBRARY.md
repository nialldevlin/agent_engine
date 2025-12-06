### LLM NOTICE: Do not read or modify this file unless explicitly instructed by the user.
# Prompt Library (Project-Agnostic)

## Plan Mode Prompts (Sonnet)

### 1. Implementation Brief Template
You are assisting with a software engineering task using **Cline Plan Mode**.

Goal:
<one-sentence objective>

Context:
<short summary of relevant files, subsystems, or the plan; @-paths encouraged>

Before creating the brief, FIRST check whether the Goal + Context contain required details.
If critical details are missing, output ONLY a list of clarifying questions and STOP.
Do NOT guess design decisions.

---

## TASK
Create an **IMPLEMENTATION BRIEF** with **THREE SECTIONS** in this exact order.
Do NOT write any full code. Keep everything concise, explicit, and mechanically actionable.
Assume that all implementation will be performed by a **local 7B model in Cline Act Mode**.
This means all instructions must eliminate ambiguity and avoid inference.

If this brief corresponds to a broader roadmap phase, use sub-phase numbering
(e.g., "Phase 2.A", "Phase 2.B") and keep numbering consistent throughout.

---

# **SECTION 1 — OVERVIEW & SUMMARY (FOR HUMAN USER)**

Provide 2–5 short paragraphs or structured bullet lists that contain:

1. Restatement of the Goal.
2. Summary of current state of relevant files (from Context).
3. Explicit assumptions, constraints, and success criteria.
4. Risks, unknowns, dependencies, and where ambiguity exists.
5. A brief rationale for the structure of the phased plan.

Keep this section interpretive, not prescriptive.

---

# **SECTION 2 — PHASED IMPLEMENTATION PLAN (FOR HUMAN SUPERVISION)**

Design a deterministic, multi-phase plan. Each phase must be small enough to run
reliably with a 7B model and contain **zero design ambiguity**.

For EACH PHASE, include:

### Phase N — <short name>
1. **Goal:** One sentence.
2. **Files to modify or create**  
   Use full @-paths (e.g., `@/src/module/file.py`).
3. **Functions/classes to add/modify/remove**  
   Give explicit signatures when relevant.
4. **Invariants and constraints**  
   Examples:  
   - “Do not modify any other files.”  
   - “Preserve existing behavior of X.”  
   - “Follow naming conventions as shown in <file>.”
5. **Edge cases & error modes to consider.**
6. **Out-of-scope items** to prevent drift.

Then list the exact **Steps** needed to complete the phase.

---

### **Steps Format**
Each step must specify whether it is:

- `[QWEN]` → executed by a local 7B model, must be extremely explicit  
- `[HUMAN]` → executed manually (tests, review, commands, approvals)

For example:

**Step K — [QWEN] <short description>**
- Exact file(s) to modify using @-paths.
- The precise change required (definitions, defaults, enum members, structural edits).
- Constraints: what must NOT change.
- Expected output: *“Return a unified diff for modified files only.”*
- No design inference allowed. All required details must be specified.

**Step K — [HUMAN] <short description>**
- Exact commands to run (e.g., `pytest tests/test_x.py`).
- What the human should verify in output, logs, diffs, or behavior.
- Branching logic if checks fail (e.g., “Return to Phase 1 Step 2 if X fails”).

Ensure:
- Steps are atomic (1 editing action per QWEN step).
- Ordering is deterministic.
- Later phases cannot depend on knowledge not introduced earlier.

---

# **SECTION 3 — QWEN IMPLEMENTATION PROMPTS (FOR CLINE ACT MODE)**

Produce a numbered list of prompts ready to paste directly into Cline Act Mode.

**Requirements:**

- One Qwen prompt per `[QWEN]` step in Section 2.
- Use the format:  
  **Qwen Prompt N (Phase X, Step Y — <short description>)**
- Preserve all numbering to maintain mapping integrity.
- Each prompt must contain:
  - Restatement of the Step goal.
  - Exact @-paths to target files.
  - Exact required edits (explicit text/fields/enums/behaviors).
  - Constraints:  
    - “Do not modify any other files or lines.”  
    - “Do not introduce new patterns or restructure logic.”  
    - “No inference — apply only what is explicitly stated.”
  - Required output format:  
    - “Return a unified diff for modified files only.”

### Example QWEN prompt structure
```text
Qwen Prompt N (Phase X, Step Y — <short description>)

Goal:
<one-sentence summary of the edit>

Target Files:
- @/path/to/file.py

Instructions:
<fully explicit description of the change, including exact names/types/fields>

Constraints:
- Do not alter any other file or line.
- Do not infer missing details.
- Apply only the changes described above.
- Return a unified diff for modified files only.

Output Format:
Unified diff only.
```

The final output of Section 3 must include **no code**, only prompts.
