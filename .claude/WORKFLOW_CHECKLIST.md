# LLM NOTICE: Do not modify this file unless explicitly instructed by the user.
# Cline Workflow Checklist (Project-Agnostic)

## DOs & DON'Ts (Sonnet vs Llama/Qwen)

### DO (Sonnet / Plan Mode)
- Use ONLY for planning, analysis, architecture.
- Ask for Implementation Briefs, phased plans.
- Never ask Sonnet to run tools or modify files.

### DON'T (Sonnet)
- Don't let it generate large code blocks.
- Don't use it in Act mode.
- Don't ask it to "implement", "apply diff", "run command".

---

### DO (Llama/Qwen / Act Mode)
- Use for file edits, diff generation.
- Provide explicit file paths.
- Ask for unified diffs.
- Keep tasks small (1–3 files).
- Ensure correctness before multi-step operations.

### DON'T (Act Mode)
- Don't let it touch files you didn't specify.
- Don't ask for repo-wide refactors.
- Don't switch to cloud models accidentally.

---

## Workflow Checklist (Every Session)

1. Confirm Models
- Sonnet = Plan mode
- Llama/Qwen local = Act mode

2. Start Work
- Review plan or generate new Brief
- Break into micro-steps

3. Implement Safely
- Use small Act-mode prompts
- Request surgical diffs
- Verify changes before commit

4. Validate
- Run tests, type checks
- Fix via small Act-mode prompts

5. Commit Often
- Small, meaningful commits
- Keep history clean

---

## Prompt Writing Checklist

### For Plan Mode (Sonnet)
- [ ] Goal defined
- [ ] Context minimal + relevant
- [ ] Specific files listed
- [ ] Success criteria defined
- [ ] Brief requested
- [ ] HUMAN/QWEN steps noted

### For Act Mode (Llama/Qwen)
- [ ] Exact file paths
- [ ] Minimal changes
- [ ] What NOT to touch
- [ ] Ask for diff only
- [ ] Confirm expected behavior

