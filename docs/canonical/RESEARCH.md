# LLM NOTICE: Do not modify this file unless explicitly instructed by the user.

# Agent Engine – Consolidated Research Notes

**LIBRARY NOTE**: This document is a compilation of research from various papers and sources that inform Agent Engine design. It serves as a reference library for understanding architectural choices and background concepts. **Not all information in this document is in scope for current implementation.** When implementing features, refer to the canonical spec (`AGENT_ENGINE_SPEC.md`) and architecture (`AGENT_ENGINE_OVERVIEW.md`) to determine what is required. Treat this file as background material to prevent scope creep.

---

This document is the single source of research grounding for the Agent Engine orchestrator ("Agent Engine"). It replaces earlier files (`RESEARCH.md`, `RESEARCH_NOTES.md`, `RESEARCH_ALIGNMENT.md`, `PROMPT_WRAPPING.md`) and is meant to be stable enough that other plans and design docs can cite it directly.

The goal is to keep implementation decisions tightly linked to published work or clearly stated heuristics. Where possible, each subsection ends with an **"Implementation checklist"** that you can turn into concrete tasks.

---

## 1. Context, Memory, and Compression

### 1.1 Long‑context behavior and “Lost in the Middle”

**Key results**  
- Large models show a **U‑shaped performance curve** over position in context: they do well on information near the beginning and end of the context window but perform poorly on material in the **middle**, especially for long inputs.  
- This pattern appears across multiple model families and persists even with fine‑tuning and RLHF; smaller models tend to be purely recency‑biased.

**Implications for Agent Engine**  
- Treat the **system prompt + key summaries** (HEAD) and **latest user turns + current task** (TAIL) as first‑class citizens.
- Avoid dumping long, unstructured context in the middle of prompts.
- When near the token limit, **preserve HEAD + TAIL, aggressively compress the middle** (older history, verbose logs).

**Implementation checklist**
- [ ] Implement a “HEAD/TAIL” policy in the context manager: never evict the system wrapper or the most recent N user/agent turns unless forced to.  
- [ ] Add an explicit “middle compression” stage for long histories (see 1.2–1.3).  
- [ ] Expose a debug flag to visualize which segments were dropped or compressed for each call.

### 1.2 Memory hierarchies and virtual context (MemGPT + memory surveys)

**Key results**  
- **MemGPT** introduces a virtual memory model for LLMs: separate **fast context** (current prompt), **slower persistent memory**, and an **interrupt‑driven controller** that pages data in and out, inspired by OS design.  
- Modern surveys on memory in LLM agents emphasize **multi‑tier memory** (ephemeral / short‑term / long‑term), explicit **retrieval policies**, and the need to treat memory as a module with its own design space (representation, write policies, read policies, evaluation).

**Implications for Agent Engine**  
- The context manager should behave like an **OS‑style pager**, not a simple sliding window.  
- Memory should be split into:  
  - **Task memory** (per‑run, ephemeral artifacts like plans and partial results).  
  - **Short‑term conversational memory** (last K turns).  
  - **Long‑term project memory** (design decisions, conventions, important failures).  
  - **Global memory** (user preferences, reusable patterns across projects).  
- Page between these tiers using explicit policies rather than ad‑hoc truncation.

**Implementation checklist**
- [ ] Define a `ContextItem` schema with: `kind`, `source`, `timestamp`, `tags`, `importance`, and `token_cost`.  
- [ ] Implement separate stores for `task`, `project`, and `global` memory, with clear APIs.  
- [ ] Add a simple policy engine: given a `ContextRequest` (budget, domains, mode), compute which items to page into the prompt.  
- [ ] Log “paging decisions” into telemetry so you can later correlate success/failure with specific memory policies.

### 1.3 Prompt compression (LLMLingua and related work)

**Key results**  
- **LLMLingua** shows that you can compress prompts by up to ~10–20× while maintaining high task performance by:  
  - scoring token importance using a smaller model,  
  - iteratively pruning low‑importance tokens under a budget,  
  - aligning compressed prompts with the target model’s distribution.  
- Compression works best when you preserve **instructions, key entities, and structural tokens**, while aggressively pruning redundancy.

**Implications for Agent Engine**  
- For cost‑sensitive modes, compress **supporting context** (logs, long docs, older turns) instead of whole prompts.  
- Compression should be **semantic** (retain structure and entities), not naive truncation.

**Implementation checklist**
- [ ] Add a compression module that can:  
  - score sentences or chunks by importance;  
  - drop or summarize low‑importance text when token budgets are tight.  
- [ ] Gate compression by mode: `CHEAP` heavily compresses context, `BALANCED` uses mild compression, `MAX_QUALITY` attempts to keep more raw text.  
- [ ] Add a telemetry field `compression_ratio` and correlate it with success/failure to tune thresholds.

---

## 2. Context Retrieval and Multi‑Agent Memory

### 2.1 Context engineering and retrieval policies

**Key results**  
- Recent “context engineering” work treats **context assembly** (what to retrieve, how to structure it, how to budget it) as a core design problem for agents, distinct from simple prompt engineering.  
- Surveys on memory and planning for LLM agents decompose context handling into: **retrieval**, **processing/compression**, and **management** (policies and hierarchies).  
- Multi‑agent surveys emphasize that each agent type (planner, task_runner, reviewer) may need a **different view of memory**.

**Implications for Agent Engine**  
- Retrieval must be **task‑aware** (bug‑fix vs. doc rewrite vs. refactor) and **agent‑aware** (different agent roles (planner vs. implementer vs. reviewer)).  
- Context engineering is a module: given a normalized task spec, it produces a **`ContextPackage`** tailored to that step and agent.

**Implementation checklist**
- [ ] Introduce lightweight `ContextProfile`s per agent kind (planner/implementer/reviewer/assistant).  
- [ ] Add a `ContextPolicy` that takes `(task_spec, mode, agent_profile)` and returns a `ContextRequest` (`domains`, `files`, `history_types`, `budget`).  
- [ ] Implement scoring or heuristics that bias retrieval toward:  
  - directly mentioned files/paths;  
  - recent design decisions;  
  - history tagged as `bug_root_cause` or `design_constraint`.

### 2.2 Agent‑specific retrieval and context fingerprints

**Key results**  
- Multi‑agent system surveys and MoA work show that **specialized agents** perform better given **tailored context** and that performance varies significantly by task type and domain.  
- Telemetry‑driven systems treat each task as a **fingerprint** (features of context + tools + outcome) to learn which agents work best in which regions.

**Implications for Agent Engine**  
- Agents, analysts, assistants, and strategist should have different **default context mixes**. For example:  
  - Agents: code + tests + minimal prior conversation.  
  - Strategist: summaries, decisions, user preferences, almost no raw code.  
- Context fingerprints can drive both **routing** and **evolution** (which agent variants survive).

**Implementation checklist**
- [ ] Define a `ContextFingerprint` struct (e.g., hashes of key files, tags, mode, approximate complexity).  
- [ ] Log the fingerprint with each task outcome in telemetry.  
- [ ] Use fingerprints in router/evolution logic to preferentially route similar tasks to agents that historically perform well there.

---

## 3. Tool Use, Planning, and Action

### 3.1 Learning when and how to use tools (Toolformer, surveys)

**Key results**  
- **Toolformer** shows that a language model can **teach itself where to insert API calls** by annotating text with tool calls and training on the resulting data. This yields improved performance while keeping tools optional and composable.  
- Surveys of LLM agents identify **tool use** and **planning** as key modules, and classify planning methods into: **task decomposition**, **plan selection**, **external modules**, **reflection**, and **memory**.

**Implications for Agent Engine**  
- Tool use should be driven by a **structured plan** (even if produced in‑context), not ad‑hoc calls embedded in free text.  
- Agents should generate **`ToolPlan` JSON** (sequence of steps with tool IDs, inputs, and reasons) that is then executed by deterministic code.  
- Some tool usage patterns can be turned into **macro‑tools** for common workflows (scan → edit → test).

**Implementation checklist**
- [ ] Add a `ToolPlan` schema (steps with `tool_id`, `inputs`, `reason`, `kind`).  
- [ ] Wrap agent prompts to require a `ToolPlan` when `mode=implement` or when tools are allowed.  
- [ ] Implement an task_runner that:  
  - runs `ToolPlan` deterministically;  
  - logs each call with results and errors;  
  - supports rollback when workspace is mutated (see 7.2).

### 3.2 ReAct‑style reasoning + acting and external modules

**Key results**  
- **ReAct** (Reason + Act) interleaves chain‑of‑thought reasoning with tool calls, showing that explicit intermediate thoughts improve tool selection and robustness on multi‑step tasks.  
- Planning surveys argue for **separating a planner module** from the task_runner, especially for complex tasks that involve external tools and long‑horizon reasoning.

**Implications for Agent Engine**  
- Pipeline stages (Interpreter, Planner/Todo, TaskRunner) should be explicit and their artifacts passed as **typed JSON**, not buried in raw text.  
- For non‑trivial tasks, agents should perform at least a **mini ReAct loop** internally (reason → act → observe → adjust), but expose only the final, structured outputs to the pipeline.

**Implementation checklist**
- [ ] Require `analysis_only` tasks to output a plan but no tools; `implement` tasks must output both a plan and a `ToolPlan`.  
- [ ] Allow a small number of internal “reason + act” cycles per agent call, but enforce a hard cap and log counts.  
- [ ] Add a analyst or reviewer mode that can inspect `ToolPlan` + tool logs for obviously unsafe or redundant steps.

### 3.3 Deterministic vs. LLM‑based tools and assistants

**Key results**  
- Many agent frameworks distinguish between **deterministic tools** (file operations, compilation, tests) and **LLM‑based helpers** used as sub‑agents (rankers, summarizers, JSON repairers).  
- Mixed‑initiative designs show better safety by letting the LLM propose tool usage but keeping final execution and gating deterministic.

**Implications for Agent Engine**  
- Assistants (LLM tools) should be **narrow**, with strict schemas and no further agent calls.  
- Agents should prefer deterministic tools when possible and treat assistants as **advisors** (e.g., for ranking or compression), not direct actors on the workspace.

**Implementation checklist**
- [ ] Mark tools with capabilities and risk levels (`deterministic_safe`, `workspace_mutation`, `external_network`, `expensive`).  
- [ ] Enforce that assistants can only call deterministic tools (no recursive agent calls).  
- [ ] Require agents to justify risky tool usage in `ToolPlan`, so consent prompts and reviewers have structured reasons.

---

## 4. Routing, Multi‑Agent Architectures, and Fallback

### 4.1 Mixture‑of‑Agents and multi‑agent surveys

**Key results**  
- **Mixture‑of‑Agents (MoA)** approaches show that combining multiple specialized LLM agents with a router can outperform a single model, especially when agents specialize on different domains or behaviors.  
- Surveys of LLM‑based multi‑agent systems highlight common components: **profiles**, **perception**, **self‑action**, **mutual interaction**, and **evolution** across agents.

**Implications for Agent Engine**  
- Agent Engine’s strategist/agent/analyst/assistant hierarchy fits well into a MoA framing: multiple expert agents plus a router and reviewers.  
- Routing should be informed by **task features and telemetry**, not only hand‑written rules.  
- Critical tasks can benefit from **parallel agents** plus a reviewer that chooses or fuses outputs.

**Implementation checklist**
- [ ] Define a router interface that takes a normalized `TaskSpec` + `ContextFingerprint` and returns `(primary_agent, backups, confidence)`.  
- [ ] Start with a simple heuristic/router (rules + small classifier), log routing decisions and outcomes.  
- [ ] For high‑risk tasks (large diff, critical files), optionally run 2–3 agents in parallel and use a reviewer analyst to compare outputs.  
- [ ] Maintain per‑agent fitness scores by domain (files, tags) and feed them back into routing.

### 4.2 Fallbacks and failure signatures

**Key results**  
- Robust agent systems treat failures as **first‑class signals** with structured categories (planning failure, tool failure, JSON failure, evaluation failure) and explicit fallback policies.  
- Evolutionary prompt/agent systems use failures and telemetry as data for **self‑improvement**.

**Implications for Agent Engine**  
- Every major failure mode (JSON parse error, tool crash, plan invalid, tests fail) should map to a **failure signature** with a recommended response.  
- Fallbacks might include: retry with the same agent, switch to a more conservative agent, escalate to Agent Engine, or ask the user for guidance.

**Implementation checklist**
- [ ] Define a `FailureSignature` schema and attach it to telemetry when tasks fail.  
- [ ] Implement a fallback matrix: for each signature, specify allowed actions (retry, switch agent, escalate).  
- [ ] Log which fallback path was chosen and whether the second attempt succeeded.

---

## 5. Prompt Wrapping and Structured Outputs

### 5.1 Prompt templates as first‑class artifacts

**Key results**  
- Empirical work on prompt templates shows that **small changes in template wording** can significantly affect accuracy, robustness, and evaluation scores, even when the task is unchanged.  
- Real‑world systems treat prompts as **parameterized templates** with separate components (role, constraints, examples, outputs) rather than monolithic strings.

**Implications for Agent Engine**  
- Prompt wrapping should be centralized in a `build_prompt(agent, task)` function that:  
  - applies a shared skeleton per agent kind (agent, analyst, assistant, strategist);  
  - inserts `mode` semantics;  
  - lists allowed tools;  
  - injects context;  
  - defines the output schema.  
- Template changes are **config changes** and must be versioned and tested, not edited casually.

**Implementation checklist**
- [ ] Implement a wrapper that structures prompts as: kind header → persona → mode & capabilities → tools → task description → context package → output contract.  
- [ ] Include a `template_version` in each call and log it in telemetry.  
- [ ] Create a small regression suite that runs representative tasks under multiple template variants and compares JSON adherence and success metrics.

### 5.2 Structured outputs and JSON contracts

**Key results**  
- Production systems increasingly rely on **structured outputs** (JSON schemas or tool schemas) to guarantee parseable, validated responses and reduce the need for ad‑hoc repair logic.  
- Schema‑aligned parsing and “strict” modes for tools/JSON are effective at eliminating many classes of JSON errors and simplifying downstream code.

**Implications for Agent Engine**  
- JsonContracts and structured outputs should be the **primary** mechanism for IO between agents, tools, and the orchestrator.  
- Repair logic should focus on **syntax and mild schema fixes**, not hallucinating missing data.

**Implementation checklist**
- [ ] Ensure every pipeline boundary has an explicit JsonContract/schema, referenced by ID in telemetry.  
- [ ] Use constrained decoding / structured outputs where available; fall back to a repair analyst only on parse or minor schema errors.  
- [ ] Track which backend and which repair tier was used for each call to inform future template or schema tweaks.

---

## 6. Evolution, Scoring, and Self‑Improvement

### 6.1 Prompt and agent evolution (PromptBreeder and beyond)

**Key results**  
- **PromptBreeder** treats prompts as **self‑evolving artifacts**: mutate prompts, evaluate performance, keep beneficial variants.  
- Evolutionary loops can discover better prompts and strategies than hand‑tuned ones, particularly for reasoning and classification tasks.

**Implications for Agent Engine**  
- Agents (and possibly analysts) can be treated as **evolving species**: manifests and wrappers mutate over time under telemetry‑based selection.  
- Evolution should operate over **explicit parameters** (e.g., reasoning steps, tool usage guidelines, verbosity), not random strings.

**Implementation checklist**
- [ ] Define a `AgentManifest` parameter space (e.g., emphasis on tests, exploration vs. conservatism, verbosity).  
- [ ] Periodically spawn challenger agents with small manifest/prompt mutations.  
- [ ] Route a small fraction of tasks to challengers in parallel, score performance, and either promote or retire them.  
- [ ] Record evolution lineage so you can trace where a successful agent came from.

### 6.2 Telemetry, benchmarks, and SWE‑style evaluation

**Key results**  
- Benchmarks like **SWE‑bench** and **SWE‑bench Verified/Pro** evaluate agents on realistic software issues, measuring end‑to‑end ability to produce working patches.  
- Strong systems use both **synthetic regression tests** and **real‑task benchmarks** to guide evolution and template changes.

**Implications for Agent Engine**  
- Telemetry should make it easy to compute per‑agent fitness scores and to run periodic evaluation suites.  
- Even if you don’t integrate SWE‑bench directly, you can mirror the pattern: repo snapshots + issue → patch + tests.

**Implementation checklist**
- [ ] Design a simple internal benchmark suite (Python refactors, ROS launch fixes, doc rewrites, etc.) and run it against agents regularly.  
- [ ] Store scores and link them to `template_version`, `manifest_version`, and evolution lineage.  
- [ ] Use scores as part of the fitness function for evolution and routing decisions.

---

## 7. Error Recovery, JSON Repair, and Post‑Mortems

### 7.1 JSON and schema error handling

**Key results**  
- Structured‑output systems often layer **multiple tiers** of enforcement and repair: constrained decoding, schema validation, minimal repair, then full re‑ask with explicit error messages.  
- Practical guides recommend limiting repair logic to syntax/structure to avoid compounding hallucinations.

**Implications for Agent Engine**  
- JsonContracts and a small **JSON repair analyst** are enough to handle most malformed outputs if used judiciously.  
- Retries should be **error‑type‑aware**: cosmetic issues get deterministic fixes, major mismatches trigger new calls with better error signals.

**Implementation checklist**
- [ ] Categorize JSON errors into: syntax, minor schema mismatch, major mismatch/empty.  
- [ ] For each category, define a retry/repair policy (repair, re‑ask, escalate).  
- [ ] Attach error category and chosen tier to telemetry for later analysis.

### 7.2 Root‑cause analysis and failure tagging

**Key results**  
- Post‑mortem style analysis (even done by a small LLM analyst) can turn raw logs into structured **root‑cause tags** that are useful for evolution and debugging.  
- Surveys on feedback in LLM agents treat **self‑analysis and external feedback** as key components for stable long‑term behavior.

**Implications for Agent Engine**  
- Every serious failure should produce a compact **post‑mortem artifact**: what failed, why, and where in the pipeline it originated.  
- These artifacts can later inform routing, evolution, and template changes.

**Implementation checklist**
- [ ] Create a “post‑mortem analyst” that, given the plan, tool logs, and errors, outputs a short root‑cause summary plus tags (`bad_plan`, `context_miss`, `tool_failure`, etc.).  
- [ ] Store post‑mortems in telemetry; display them in developer tooling when debugging recurring issues.  
- [ ] Use root‑cause stats to prioritize improvements (e.g., if many failures are `context_miss`, focus on context engineering).

---

## 8. Autonomy, Overrides, and Safety

### 8.1 Natural‑language overrides and user control

**Key insights from broader agent work**  
- Agent surveys and feedback‑mechanism studies treat user feedback and overrides as a first‑class signal: controlling routing, planning depth, and risk level.  
- Free‑form overrides must be parsed into **structured control signals** to avoid brittle, purely prompt‑based hacks.

**Implications for Agent Engine**  
- Natural language directives like “remember this”, “be more concise”, or “analysis only” should be parsed into structured **`OverrideSpec`** objects controlling memory scope, routing, and modes.  
- “Remember this” should default to **project‑scoped** memory, with global scope only for obvious user preferences.

**Implementation checklist**
- [ ] Implement a small override parser (could be an LLM analyst) that maps raw text to `OverrideSpec { kind, scope, target, severity }`.  
- [ ] Add confirmation flows for potentially dangerous overrides (e.g., retiring agents, skipping safety checks, global memory writes).  
- [ ] Log overrides and their effects alongside task telemetry.

### 8.2 Global vs. project memory and preferences

**Key results**  
- Memory surveys stress separating **long‑term, global knowledge** from **task‑/project‑specific memory** to prevent interference and unintended transfer of information.  
- Practical systems keep user preferences (style, verbosity, format) global but keep project‑specific decisions local.

**Implications for Agent Engine**  
- Project memory should hold repo‑specific conventions and decisions.  
- Global memory should hold user preferences and generic strategies (e.g., “always explain ROS launch changes”).

**Implementation checklist**
- [ ] Maintain distinct namespaces for `global` and `project/<slug>` memory.  
- [ ] Route “preferences” overrides to global by default unless the user explicitly says “for this project only”.  
- [ ] Provide tooling to inspect and edit both global and project memories.

---

## 9. Gaps and Suggested Future Research

This section lists areas where the current research basis is thinner or mostly heuristic, and where it would help to read or experiment more before making hard architectural bets.

1. **Automated routing vs. rule‑based routing** ([Appendix A.1](#appx-a1))  
   - You’re currently planning a heuristic/classifier hybrid router. There is ongoing work on **learning routers** for MoE/MoA systems that optimize both performance and cost. It would be useful to investigate:  
     - training small routers on your telemetry;  
     - comparing them with LLM‑based routers;  
     - safety considerations when routers themselves are non‑deterministic.

2. **Formal evaluation of context policies** ([Appendix A.2](#appx-a2))  
   - Context engineering is mostly guided by heuristics. Future work:  
     - define a small set of **context‑ablation experiments** to measure how much each context type (files, design decisions, logs) contributes to success;  
     - explore more recent work on **learned context selection** and “context bandits.”

3. **Multi‑agent collaboration patterns beyond MoA** ([Appendix A.3](#appx-a3))  
   - Most references focus on MoA‑style ensembles or simple planner/task_runner/reviewer decompositions. There is active research on **social‑simulation‑style multi‑agent systems** (negotiation, argumentation, consensus) that could inform more advanced agent‑coordination strategies, if you ever need them.

4. **Safety, alignment, and capability control for self‑evolving agents** ([Appendix A.4](#appx-a4))  
   - PromptBreeder provides a template for prompt evolution, but applying evolutionary mechanisms to a multi‑agent system that has **file write and tool access** raises additional safety issues. Future reading: safe RL, alignment‑focused agent frameworks, and methods for bounding the behavior of self‑evolving systems.

5. **Formal metrics for “developer UX”** ([Appendix A.5](#appx-a5))  
   - Many design choices (routing, review depth, verbosity) affect not only objective success but also how usable Agent Engine is as a collaborator. There is comparatively little formal literature on **UX metrics for AI coding assistants**; gathering your own structured feedback and logs (time saved, manual corrections, user ratings) will likely matter as much as benchmark scores.

6. **Carbon and cost‑aware orchestration** ([Appendix A.6](#appx-a6))  
   - As the system grows, cost and energy use become more important. There is emerging work on **LLM cost/latency/energy tradeoffs** and model compression beyond prompt compression. Future research could guide policies for when to use smaller models, how aggressively to compress, and when to run parallel agents.

---

## 10. References (Primary Sources)

This list is intentionally non‑exhaustive; it focuses on references that directly inform the design decisions above.

- Liu, N. F., et al. (2024). **Lost in the Middle: How Language Models Use Long Contexts.** *TACL 12.*  
- Packer, C., et al. (2024). **MemGPT: Towards LLMs as Operating Systems.** arXiv:2310.08560.  
- Jiang, H., et al. (2023). **LLMLingua: Compressing Prompts for Accelerated Inference of Large Language Models.** *EMNLP 2023.*  
- Schick, T., et al. (2023). **Toolformer: Language Models Can Teach Themselves to Use Tools.** arXiv:2302.04761.  
- Yao, S., et al. (2022). **ReAct: Synergizing Reasoning and Acting in Language Models.** arXiv:2210.03629.  
- Fernando, C., et al. (2024). **Self‑Referential Self‑Improvement via Prompt Evolution (PromptBreeder).** *Journal of Machine Learning Research.*  
- Wang, J., et al. (2024). **Mixture‑of‑Agents Enhances Large Language Model Performance.** arXiv:2406.04692.  
- Zhang, Z., et al. (2024). **A Survey on the Memory Mechanism of Large Language Model‑Based Agents.** arXiv:2404.13501.  
- Huang, X., et al. (2024). **Understanding the Planning of LLM Agents: A Survey.** arXiv:2402.02716.  
- Li, X., et al. (2025). **A Review of Prominent Paradigms for LLM‑Based Agents: Tool Use, Planning, and Feedback Learning.** *COLING 2025.*  
- Jimenez, C. E., et al. (2023). **SWE‑bench: Can Language Models Resolve Real‑World GitHub Issues?** arXiv:2310.06770.  
- Anthropic (2025). **Effective Context Engineering for AI Agents.** Anthropic Engineering Blog.  
- Anthropic (2025). **Structured Outputs on the Claude Developer Platform.** Claude Platform Docs.

---

## Appendix A – Additional References for Gaps & Future Work

This appendix lists concrete papers and reports that deepen the six “Gaps & Suggested Future Research” areas in §9. Each item includes a short note on how it can inform Agent Engine’s design, plus explicit notes where further research is required before implementation.

<a id="appx-a1"></a>
### A.1 Automated Routing vs. Rule-Based Routing

**Zhang et al., 2025 – “Mixture of Routers (MoR)”**  
J. C. Zhang, Y. Pu, Y. Li, *Mixture of Routers (MoR)*, arXiv:2503.23362 (2025).  
- Proposes a Mixture-of-Routers architecture that learns multiple sub-routers and a meta-router jointly, improving routing quality in MoE models.  
- Relevant to Agent Engine for learning small, telemetry-trained routers that outperform static hand-written rules while still being compact and controllable.

Further research required before implementation:  
- Establish telemetry features for routing (task fingerprints, domain tags, cost/latency).  
- Evaluate data volume sufficiency for training small routers; consider semi-supervised labeling from failure signatures.  
- Define safety constraints for non-deterministic routing decisions (confidence thresholds, deterministic fallbacks).

**Dikkala et al., 2023 – “On the Benefits of Learning to Route in Mixture-of-Experts Models”**  
N. Dikkala et al., *On the Benefits of Learning to Route in Mixture-of-Experts Models*, EMNLP 2023.  
- Provides theoretical and empirical evidence that learned routing in MoE can adapt to latent cluster structure and significantly outperform data-independent routing.  
- Suggests that a learned router over agents (or agent families) can discover latent “task clusters” in your codebase/workload that hand-written rules miss.

Further research required before implementation:  
- Verify whether Agent Engine’s task distribution exhibits latent clusters; run cluster analyses on telemetry.  
- Compare learned vs. heuristic routing on offline replay to validate gains and cost trade-offs.

---

<a id="appx-a2"></a>
### A.2 Formal Evaluation of Context Policies

**Wang et al., 2024 – “Learning to Retrieve In-Context Examples for Large Language Models”**  
L. Wang et al., *Learning to Retrieve In-Context Examples for Large Language Models*, EACL 2024.  
- Trains dense retrievers to select high-utility in-context examples specifically optimized for LLM performance.  
- Maps directly onto learned context selection for Agent Engine: you can treat “files/snippets to fetch” as in-context examples and train a retriever on telemetry labeled with success/failure.

Further research required before implementation:  
- Define gold labels for “useful context” from success/failure telemetry; ensure leakage controls.  
- Evaluate retrieval quality vs. prompt compression interaction (avoid compressing away key exemplars).  
- Add ablation protocols for context types (files, decisions, logs) to quantify utility.

**Xia et al., 2025 – “PURPLE: Optimizing User Profiles via Contextual Bandits for LLM Personalization”**  
Y. Xia et al., *PURPLE: A contextual bandit framework that optimizes user profiles for LLM personalization*, OpenReview (2025).  
- Shows that relevance ≠ utility and uses contextual bandits to pick an optimal subset of records for a user profile.  
- This is a concrete template for “context bandits” in Agent Engine: treat candidate context items as records and learn which subset actually improves outcomes rather than assuming “more context is better”.

Further research required before implementation:  
- Frame context selection as a bandit: define arms (context items), reward (task success + UX metrics), constraints (token budget).  
- Pilot offline bandit evaluation using historical tasks before live deployment.

---

<a id="appx-a3"></a>
### A.3 Multi-Agent Collaboration Patterns Beyond Simple MoA

**Liang et al., 2024 – “Encouraging Divergent Thinking in Large Language Models through Multi-Agent Debate (MAD)”**  
T. Liang et al., *Encouraging Divergent Thinking in Large Language Models through Multi-Agent Debate*, EMNLP 2023.  
- Introduces the MAD framework where multiple agents debate to encourage divergent thinking and improve truthfulness/robustness.  
- Provides concrete debate protocols you can adapt for “agent vs agent + reviewer” workflows, especially for high-risk or ambiguous tasks.

Further research required before implementation:  
- Identify task classes where debate improves accuracy enough to justify cost/latency.  
- Design aggregation policies (vote, reviewer adjudication) with deterministic tie-break rules.

**Smit et al., 2024 – “Should We Be Going MAD? A Look at Multi-Agent Debate …”**  
A. P. Smit et al., *Should We Be Going MAD? A Look at Multi-Agent Debate in LLMs*, PMLR 2024.  
- Benchmarks multiple debate/aggregation strategies and analyzes cost vs. accuracy trade-offs.  
- Useful as a design reference when deciding when debate is worth the extra tokens/latency vs. simple MoA voting/single-expert routing.

Further research required before implementation:  
- Build a small benchmark of Agent Engine tasks to compare parallel agents + debate vs. single agent + reviewer.  
- Add budget-aware toggles to activate debate only on high-risk tasks (large diffs, critical files).

---

<a id="appx-a4"></a>
### A.4 Safety & Alignment for Self-Evolving, Tool-Using Agents

**Sha et al., 2025 – “Agent Safety Alignment via Reinforcement Learning”**  
Z. Sha et al., *Agent Safety Alignment via Reinforcement Learning*, arXiv:2507.08270 (2025).  
- Proposes a unified safety framework for tool-using agents with a tri-modal taxonomy (benign/malicious/sensitive) and sandboxed RL for policy learning.  
- Offers a direct blueprint for Agent Engine’s “tool sandbox + safety policy” layer, including how to reason about threats from both user prompts and tool outputs.

Further research required before implementation:  
- Define Agent Engine’s tool safety taxonomy and mapping to policies (deny, review, allow).  
- Prototype a sandbox for risky tools (workspace mutation, external network) with audit logging and policy enforcement.  
- Evaluate alignment RL feasibility with available telemetry; start with rule-based safety monitors.

**Brunke et al., 2022 – “Safe Learning in Robotics: From Learning-Based Control to Safe RL”**  
L. Brunke et al., *Safe Learning in Robotics: From Learning-Based Control to Safe Reinforcement Learning*, Annual Review of Control, Robotics, and Autonomous Systems 5, 411–444 (2022).  
- Surveys safe learning and safe RL techniques for real-world robotic systems, including safety certificates, constraint handling, and runtime safety monitors.  
- Provides theoretical and practical patterns you can adapt for bounding self-evolving agents and tool-using agents (e.g., safety layers that veto unsafe plans).

Further research required before implementation:  
- Translate robotics-style safety monitors to developer tooling (plan vetoes, write guards).  
- Define measurable safety constraints (e.g., file scopes, test coverage thresholds) for agent actions.

---

<a id="appx-a5"></a>
### A.5 Developer UX Metrics for AI Coding Assistants

**Hou et al., 2024 – “A Large-Scale Survey on the Usability of AI Programming Assistants”**  
(Hou et al. / ACM Digital Library), *A Large-Scale Survey on the Usability of AI Programming Assistants*, CHI/related venue, 2024.  
- Large survey of developers using AI coding assistants, analyzing motivation, perceived productivity, friction points, and UX pain.  
- Gives you concrete dimensions (trust, interruption cost, mental load, perceived control) to track in Agent Engine’s telemetry and future user studies.

Further research required before implementation:  
- Instrument telemetry for UX dimensions (e.g., interruption count, suggestion acceptance rate, override frequency).  
- Design lightweight user feedback prompts tied to tasks to gather qualitative UX signals.

**Bian et al., 2025 – “Examining the Use and Impact of an AI Code Assistant in the Workplace”**  
(Bian et al.), *Examining the Use and Impact of an AI Code Assistant in the Workplace*, arXiv:2412.06603 (2025).  
- Mixed-methods case study on how an AI assistant affects perceived productivity, workflow, and responsibility for generated code.  
- Useful for designing internal metrics: time-to-completion, edit distance from suggestions, how often users override or ignore Agent Engine, etc.

Further research required before implementation:  
- Define a minimal metrics pipeline (time-to-completion, edit distance, override rate) and privacy boundaries.  
- Consider optional reference: Tang et al., *An Empirical Study of Developer Behaviors for Validating and Repairing AI-Generated Code*, PLATEAU 2022.

---

<a id="appx-a6"></a>
### A.6 Carbon & Cost-Aware Orchestration

**Liu et al., 2025 – “Energy Considerations of Large Language Model Inference”**  
Y. Liu et al., *Energy Considerations of Large Language Model Inference*, arXiv:2504.17674 (2025).  
- Quantifies how common inference optimizations (quantization, batching, caching, pruning, etc.) affect energy usage and latency for LLM serving.  
- Gives you a basis for configuring Agent Engine’s cost modes (CHEAP/BALANCED/MAX) in terms of actual energy/latency trade-offs, not just token count.

Further research required before implementation:  
- Define energy/latency proxies accessible in your deployment (e.g., model size, batching stats, token throughput).  
- Map these proxies to mode policies and expose approximate cost/energy telemetry per session.

**Jeanquartier et al., 2026 – “Assessing the Carbon Footprint of Language Models”**  
F. Jeanquartier et al., *Assessing the Carbon Footprint of Language Models*, Ecological Informatics (in press, 2026).  
- Analyzes training vs. inference emissions for different model sizes and emphasizes transparency and standardized reporting.  
- Can inform a future “carbon-aware” scheduler for Agent Engine (e.g., preferring smaller models or lighter modes when tasks are non-critical, or exposing approximate footprint per session).

Further research required before implementation:  
- Develop a transparent reporting schema for carbon/cost metrics at task level.  
- Prototype a scheduler that can prefer smaller models or lower-cost modes under non-critical conditions.

