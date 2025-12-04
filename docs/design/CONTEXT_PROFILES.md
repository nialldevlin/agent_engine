# Context Profiles and Retrieval Policies

**Date:** 2025-12-03
**Status:** Design Complete
**Related:** MEMORY_ARCHITECTURE.md, RESEARCH.md §2.1, §2.2

---

## 1. Overview

Context retrieval is a **first-class design problem** for multi-agent systems. Different agents (knight, squire, royalty, peasant) need different **views of memory** tailored to their roles and tasks.

This document specifies:
1. **ContextProfile**: Agent-specific memory preferences
2. **ContextPolicy**: Task-aware retrieval logic
3. **ContextFingerprint**: Task characterization for routing and evolution
4. Integration with the multi-tier memory system

### Key Principles (from RESEARCH.md)

- **Agent-aware**: Knights need code+tests, Royalty needs summaries+decisions
- **Task-aware**: Bug fix vs. refactor vs. new feature require different context
- **Telemetry-driven**: Log profiles + fingerprints to correlate with success/failure

---

## 2. ContextProfile Schema

```python
@dataclass
class ContextProfile:
    """Defines what context an agent prefers.

    Each agent kind (knight/squire/royalty/peasant) has a default profile
    that can be overridden per task.
    """
    profile_id: str

    # Memory tier weights (how much of budget to allocate)
    task_weight: float = 0.4      # Task memory importance
    project_weight: float = 0.4   # Project memory importance
    global_weight: float = 0.2    # Global memory importance

    # Content preferences (what kinds of items to prioritize)
    preferred_kinds: List[str] = field(default_factory=list)
    # Examples: ["code", "test", "reasoning", "decision", "convention"]

    excluded_kinds: List[str] = field(default_factory=list)
    # Examples: ["verbose_log", "raw_conversation"]

    # Importance thresholds
    min_importance: float = 0.0   # Filter out low-importance items

    # Compression preferences
    allow_compression: bool = True
    compression_aggressiveness: float = 0.5  # 0=conservative, 1=aggressive

    # HEAD/TAIL preservation
    preserve_head: int = 2  # Always keep top N most important items
    preserve_tail: int = 2  # Always keep bottom N most recent items

    # Metadata
    description: str = ""
    tags: List[str] = field(default_factory=list)
```

---

## 3. Default Profiles by Agent Kind

### 3.1 Knight Profile (Code Implementer)

**Role**: Implements code, runs tools, mutates workspace

**Context needs**:
- **High priority**: Code, tests, recent tool outputs, current task plan
- **Medium priority**: Project conventions, design decisions
- **Low priority**: Conversation history, summaries, preferences

```python
KNIGHT_PROFILE = ContextProfile(
    profile_id="knight_default",
    task_weight=0.5,      # Focus on current task
    project_weight=0.3,   # Some project context
    global_weight=0.2,    # Minimal global context

    preferred_kinds=["code", "test", "tool_output", "plan", "convention"],
    excluded_kinds=["conversation", "summary", "preference"],

    min_importance=0.3,   # Filter out low-importance items
    allow_compression=True,
    compression_aggressiveness=0.6,  # Moderate compression

    preserve_head=3,
    preserve_tail=3,

    description="Code-focused profile for implementation agents",
    tags=["knight", "implementation"]
)
```

### 3.2 Squire Profile (Reviewer/Helper)

**Role**: Reviews plans, provides feedback, assists with analysis

**Context needs**:
- **High priority**: Plans, reasoning, decisions, failures
- **Medium priority**: Code, tests (for review)
- **Low priority**: Tool outputs, verbose logs

```python
SQUIRE_PROFILE = ContextProfile(
    profile_id="squire_default",
    task_weight=0.4,
    project_weight=0.4,
    global_weight=0.2,

    preferred_kinds=["plan", "reasoning", "decision", "failure", "review"],
    excluded_kinds=["tool_output", "verbose_log"],

    min_importance=0.4,
    allow_compression=True,
    compression_aggressiveness=0.4,  # Conservative compression

    preserve_head=4,
    preserve_tail=2,

    description="Analysis-focused profile for review agents",
    tags=["squire", "review"]
)
```

### 3.3 Royalty Profile (High-Level Planner)

**Role**: Decomposes tasks, makes architectural decisions, delegates

**Context needs**:
- **High priority**: Summaries, decisions, conventions, user preferences
- **Medium priority**: Plans, high-level architecture
- **Low priority**: Raw code, tool outputs, implementation details

```python
ROYALTY_PROFILE = ContextProfile(
    profile_id="royalty_default",
    task_weight=0.2,      # Less focus on current task details
    project_weight=0.5,   # Strong focus on project knowledge
    global_weight=0.3,    # More user preferences

    preferred_kinds=["summary", "decision", "convention", "preference", "pattern"],
    excluded_kinds=["code", "tool_output", "test"],

    min_importance=0.5,   # Only high-importance items
    allow_compression=True,
    compression_aggressiveness=0.3,  # Very conservative

    preserve_head=5,
    preserve_tail=1,

    description="Strategic profile for planning agents",
    tags=["royalty", "planning"]
)
```

### 3.4 Peasant Profile (LLM Tool)

**Role**: Narrow helper tasks (ranking, summarization, JSON repair)

**Context needs**:
- **High priority**: Only what's directly relevant to the helper task
- **Very minimal context** (peasants are cheap, focused helpers)

```python
PEASANT_PROFILE = ContextProfile(
    profile_id="peasant_default",
    task_weight=0.8,      # Hyper-focused on immediate task
    project_weight=0.1,
    global_weight=0.1,

    preferred_kinds=["task_input"],  # Only what's needed for the helper task
    excluded_kinds=["code", "test", "decision", "summary"],

    min_importance=0.0,   # Take whatever is provided
    allow_compression=False,  # No compression (already minimal)
    compression_aggressiveness=0.0,

    preserve_head=1,
    preserve_tail=1,

    description="Minimal profile for helper LLM tools",
    tags=["peasant", "helper"]
)
```

---

## 4. ContextPolicy: Task-Aware Retrieval

```python
@dataclass
class ContextPolicy:
    """Determines how to retrieve context based on task + agent combination."""

    def build_context_request(
        self,
        task: Task,
        profile: ContextProfile,
        budget_tokens: int
    ) -> ContextRequest:
        """Build a ContextRequest from task spec + profile.

        Process:
        1. Analyze task spec for hints (mode, metadata, mentioned files)
        2. Combine with profile preferences
        3. Generate filters and budget allocation
        4. Return ContextRequest for ContextAssembler
        """

        # Extract task characteristics
        task_mode = task.spec.mode
        task_tags = task.spec.metadata.get("tags", [])
        mentioned_files = self._extract_mentioned_files(task.spec.request)

        # Adjust profile weights based on task mode
        weights = self._adjust_weights_for_mode(
            profile,
            task_mode
        )

        # Build filters based on profile + task
        filters = {
            "kind": {"$in": profile.preferred_kinds} if profile.preferred_kinds else {},
            "importance": {"$gte": profile.min_importance},
            "tags": {"$in": task_tags} if task_tags else {}
        }

        # Boost importance of mentioned files
        boost_sources = [f"file:{f}" for f in mentioned_files]

        return ContextRequest(
            context_request_id=f"req-{task.task_id}",
            budget_tokens=budget_tokens,
            filters=filters,
            boost_sources=boost_sources,
            weights=weights,
            head_preserve=profile.preserve_head,
            tail_preserve=profile.preserve_tail,
            compression_allowed=profile.allow_compression,
            compression_ratio=profile.compression_aggressiveness
        )

    def _extract_mentioned_files(self, request: str) -> List[str]:
        """Extract file paths mentioned in task request.

        Simple heuristic: look for patterns like:
        - src/foo/bar.py
        - /absolute/path/file.ts
        - file.ext
        """
        import re
        # Match file-like patterns (simplified)
        pattern = r'[\w/\-\.]+\.\w{1,4}\b'
        matches = re.findall(pattern, request)
        return matches

    def _adjust_weights_for_mode(
        self,
        profile: ContextProfile,
        mode: TaskMode
    ) -> Dict[str, float]:
        """Adjust memory tier weights based on task mode.

        Examples:
        - CHEAP mode: increase compression
        - IMPLEMENT mode: increase task memory weight
        - PLAN mode: increase project memory weight
        """
        weights = {
            "task": profile.task_weight,
            "project": profile.project_weight,
            "global": profile.global_weight
        }

        if mode == TaskMode.IMPLEMENT:
            # Implementation needs more task context
            weights["task"] *= 1.2
            weights["project"] *= 0.9
        elif mode == TaskMode.ANALYSIS_ONLY:
            # Analysis needs more project context
            weights["task"] *= 0.9
            weights["project"] *= 1.2

        # Normalize to sum to 1.0
        total = sum(weights.values())
        return {k: v / total for k, v in weights.items()}
```

---

## 5. ContextFingerprint: Task Characterization

```python
@dataclass
class ContextFingerprint:
    """Characterizes a task for routing and evolution.

    Logged with every task outcome to correlate context mix with success/failure.
    """
    fingerprint_id: str

    # Task characteristics
    mode: TaskMode
    complexity_estimate: str  # "simple", "moderate", "complex"
    file_count: int
    mentioned_files_hash: str  # Hash of sorted file list

    # Context characteristics
    profile_id: str
    total_context_tokens: int
    context_kinds: List[str]  # What kinds of items were included
    compression_ratio: float

    # Memory tier breakdown
    task_items_count: int
    project_items_count: int
    global_items_count: int

    # Tags for clustering
    tags: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """Serialize for telemetry logging."""
        return {
            "fingerprint_id": self.fingerprint_id,
            "mode": self.mode.value,
            "complexity": self.complexity_estimate,
            "file_count": self.file_count,
            "files_hash": self.mentioned_files_hash,
            "profile": self.profile_id,
            "tokens": self.total_context_tokens,
            "kinds": self.context_kinds,
            "compression": self.compression_ratio,
            "tier_counts": {
                "task": self.task_items_count,
                "project": self.project_items_count,
                "global": self.global_items_count
            },
            "tags": self.tags
        }
```

---

## 6. Integration with ContextAssembler

The updated `ContextAssembler` will:

1. **Accept a ContextProfile** when building context
2. **Use ContextPolicy** to transform (Task + Profile) → ContextRequest
3. **Generate ContextFingerprint** from the assembled package
4. **Log fingerprint** to telemetry for later analysis

```python
class ContextAssembler:
    def __init__(self, ...):
        self.policy = ContextPolicy()
        self.default_profiles = {
            "knight": KNIGHT_PROFILE,
            "squire": SQUIRE_PROFILE,
            "royalty": ROYALTY_PROFILE,
            "peasant": PEASANT_PROFILE
        }

    def build_context_with_profile(
        self,
        task: Task,
        agent_kind: str,  # "knight", "squire", "royalty", "peasant"
        budget_tokens: int,
        profile_override: Optional[ContextProfile] = None
    ) -> Tuple[ContextPackage, ContextFingerprint]:
        """Build context using agent-specific profile."""

        # Get profile (use override or default for agent kind)
        profile = profile_override or self.default_profiles.get(agent_kind)

        # Generate ContextRequest using policy
        request = self.policy.build_context_request(task, profile, budget_tokens)

        # Build context package (existing multi-tier logic)
        package = self.build_context(task, request)

        # Generate fingerprint
        fingerprint = self._generate_fingerprint(task, profile, package)

        return package, fingerprint

    def _generate_fingerprint(
        self,
        task: Task,
        profile: ContextProfile,
        package: ContextPackage
    ) -> ContextFingerprint:
        """Create fingerprint from task + context package."""
        import hashlib

        # Extract mentioned files from task request
        mentioned_files = self.policy._extract_mentioned_files(task.spec.request)
        files_hash = hashlib.md5(
            "|".join(sorted(mentioned_files)).encode()
        ).hexdigest()[:8]

        # Count items by tier
        tier_counts = {"task": 0, "project": 0, "global": 0}
        kinds = set()
        for item in package.items:
            kinds.add(item.kind)
            if "task/" in item.source:
                tier_counts["task"] += 1
            elif "project/" in item.source:
                tier_counts["project"] += 1
            elif item.source == "global":
                tier_counts["global"] += 1

        # Estimate complexity
        complexity = "simple"
        if len(mentioned_files) > 5:
            complexity = "complex"
        elif len(mentioned_files) > 2:
            complexity = "moderate"

        return ContextFingerprint(
            fingerprint_id=f"fp-{task.task_id}",
            mode=task.spec.mode,
            complexity_estimate=complexity,
            file_count=len(mentioned_files),
            mentioned_files_hash=files_hash,
            profile_id=profile.profile_id,
            total_context_tokens=sum(i.token_cost or 0 for i in package.items),
            context_kinds=list(kinds),
            compression_ratio=package.compression_ratio or 1.0,
            task_items_count=tier_counts["task"],
            project_items_count=tier_counts["project"],
            global_items_count=tier_counts["global"],
            tags=task.spec.metadata.get("tags", [])
        )
```

---

## 7. Usage Examples

### Example 1: Knight implementing a bug fix

```python
# Task: Fix bug in src/parser.py
task = Task(
    task_id="fix-parser-bug",
    spec=TaskSpec(
        task_spec_id="bugfix-1",
        request="Fix null pointer exception in src/parser.py line 42",
        mode=TaskMode.IMPLEMENT
    ),
    status=TaskStatus.PENDING,
    pipeline_id="bugfix",
    metadata={"project_id": "my-project", "tags": ["bugfix", "parser"]}
)

# Build context for knight
assembler = ContextAssembler()
package, fingerprint = assembler.build_context_with_profile(
    task=task,
    agent_kind="knight",
    budget_tokens=4000
)

# Knight gets:
# - High weight on task memory (current investigation)
# - src/parser.py boosted (mentioned file)
# - Code + test items prioritized
# - Minimal conversation history
```

### Example 2: Royalty planning a refactor

```python
# Task: Plan refactoring of authentication system
task = Task(
    task_id="refactor-auth",
    spec=TaskSpec(
        task_spec_id="refactor-1",
        request="Plan refactoring of authentication to use JWT instead of sessions",
        mode=TaskMode.ANALYSIS_ONLY
    ),
    status=TaskStatus.PENDING,
    pipeline_id="refactor",
    metadata={"project_id": "my-project", "tags": ["refactor", "auth"]}
)

# Build context for royalty
package, fingerprint = assembler.build_context_with_profile(
    task=task,
    agent_kind="royalty",
    budget_tokens=8000
)

# Royalty gets:
# - High weight on project memory (decisions, conventions)
# - Summaries and high-level architecture
# - NO raw code or tool outputs
# - User preferences about auth patterns
```

### Example 3: Squire reviewing a plan

```python
# Task: Review implementation plan
task = Task(
    task_id="review-plan",
    spec=TaskSpec(
        task_spec_id="review-1",
        request="Review the implementation plan for new API endpoint",
        mode=TaskMode.ANALYSIS_ONLY
    ),
    status=TaskStatus.PENDING,
    pipeline_id="review",
    metadata={"project_id": "my-project", "tags": ["review", "api"]}
)

# Build context for squire
package, fingerprint = assembler.build_context_with_profile(
    task=task,
    agent_kind="squire",
    budget_tokens=3000
)

# Squire gets:
# - Balanced task/project memory
# - Plans, reasoning, decisions prioritized
# - Some code for context
# - Past failures and lessons learned
```

---

## 8. Telemetry Integration

Every context assembly logs:

```python
{
    "event": "context_assembled",
    "task_id": "fix-parser-bug",
    "agent_kind": "knight",
    "profile_id": "knight_default",
    "fingerprint": {
        "mode": "implement",
        "complexity": "simple",
        "file_count": 1,
        "files_hash": "a3b2c1d4",
        "tokens": 3847,
        "kinds": ["code", "test", "tool_output"],
        "compression": 0.65,
        "tier_counts": {"task": 8, "project": 4, "global": 2}
    },
    "items_selected": 14,
    "items_available": 47,
    "budget_tokens": 4000
}
```

This enables:
- **Routing optimization**: "Tasks with fingerprint X succeed 90% with knight Y"
- **Profile tuning**: "Knight profile should increase task_weight for bugfix tasks"
- **Evolution**: "Knight variant with higher test preference performs better on complex tasks"

---

## 9. Implementation Checklist

Phase 2 tasks from PLAN_SONNET_MINION.md:

- [ ] **Task 2.1 (Sonnet)**: ✅ Design complete (this document)
- [ ] **Task 2.2 (Minion 5)**: Implement `ContextProfile` schema in `src/agent_engine/schemas/context.py`
- [ ] **Task 2.3 (Minion 6)**: Implement `ContextPolicy` + `ContextFingerprint` in `src/agent_engine/runtime/context_policy.py`
- [ ] **Task 2.4 (Sonnet)**: Integrate profiles into `ContextAssembler.build_context_with_profile()`
- [ ] **Task 2.5 (Minion 7)**: Create default profile constants and tests in `src/agent_engine/runtime/context_profiles.py`

---

## 10. Future Enhancements

1. **Learned Profiles**: Use telemetry to automatically tune profile weights for different task types
2. **Dynamic Profiles**: Adjust profile mid-task based on outcomes (e.g., if knight fails, increase project context)
3. **User-Custom Profiles**: Let users define custom profiles for specific projects or agents
4. **Profile Inheritance**: Allow profiles to inherit from base profiles with overrides
5. **Context Diff**: Show users what context each agent sees (debugging/transparency)

---

**Status: Design Complete → Ready for Implementation**
