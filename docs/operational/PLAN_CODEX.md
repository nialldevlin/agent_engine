# PLAN_CODEX: Systematic Implementation & Documentation

**Lead:** GPT-5.1 Codex / Codex Max
**Focus:** Large-scale systematic code patterns, documentation, and well-defined algorithms

**Date:** 2025-12-03
**Based on:** RESEARCH.md implementation checklists + current codebase analysis

---

## Overview

This plan implements **systematic, well-defined work** that Codex/Codex Max excels at:
- Large-scale documentation generation from code
- Systematic refactoring patterns across multiple files
- Well-defined algorithmic implementations
- Comprehensive test suite generation
- Structured configuration and examples

These tasks are **best suited for Codex Max** because they:
- Follow well-defined patterns
- Require systematic application across many files
- Have clear specifications and success criteria
- Benefit from Codex's code understanding and generation speed

**Can run in PARALLEL with PLAN_SONNET_MINION.md**

---

## Current State: What Codex Will Complete

### ✅ Already Implemented (Codex Will Enhance)
- Basic example working but needs fixes
- Basic documentation exists but incomplete
- Test coverage good but needs expansion
- Schemas complete but missing validation tests

### 🎯 Codex Max Tasks (This Plan)

**Category A: Fix & Enhance Example (URGENT)**
1. Fix schema registration bug - "Unknown schema 'gather_context_output'" error
2. Fix security gate blocking - "Workspace mutation not permitted" error
3. Add review stage to workflow - complete the 8-stage pipeline
4. Create comprehensive E2E test - validate full workflow

**Category B: Complete Documentation (HIGH ROI for Codex)**
5. API Reference - extract all public APIs systematically
6. Config Reference - document all manifest formats
7. Example README - comprehensive example documentation
8. Architecture diagrams - generate visual documentation

**Category C: Research-Driven Algorithmic Work**
9. Prompt compression module (LLMLingua-style) - RESEARCH §1.3
10. Prompt template management system - RESEARCH §5.1
11. JSON error categorization and repair tiers - RESEARCH §7.1

**Category D: Test Suite Expansion**
12. Schema validation test generation
13. Integration test suite for all major flows
14. Benchmark suite skeleton - RESEARCH §6.2
15. Security policy enforcement tests

**Category E: Systematic Refactoring & Enhancement**
16. Enhanced error handling patterns - systematic error handling across runtime
17. Structured output enforcement - RESEARCH §5.2
18. CI/CD pipeline enhancement - tests, linting, coverage

**Category F: Telemetry, UX/Cost, and Schema Hardening**
19. Enforce schemas on stage inputs/outputs and agent/tool boundaries
20. Prompt template regression + telemetry (template_version coverage)
21. Context paging + compression telemetry (head/tail preserved vs. dropped)
22. UX/cost/carbon instrumentation (proxies + docs) - RESEARCH §9 / Appendix A.5-A.6

---

## CATEGORY A: Fix & Enhance Example (CRITICAL PATH)

**Goal:** Get basic_llm_agent example working perfectly
**Current State:** Example runs but has 3 bugs blocking full functionality
**Priority:** URGENT - blocks other work and user adoption

### Task A1: Fix Schema Registration Bug
**Recommended Model:** Standard Codex (simple fix)
**Estimated Time:** 15-20 minutes

**Problem:** "Unknown schema 'gather_context_output'" error in gather_context stage

**Investigation Steps:**
1. Read `src/agent_engine/schemas/registry.py`
2. Read `configs/basic_llm_agent/stages.yaml`
3. Identify missing schema registration
4. Check all stage output schemas are registered

**Fix:**
- Register all required schemas in registry
- Add validation to ensure referenced schemas exist
- Update stages.yaml if schema IDs are incorrect

**Test:**
```bash
PYTHONPATH=/home/ndev/agent_engine/src:$PYTHONPATH \
python3 -m examples.basic_llm_agent.cli "test request"
```

**Success Criteria:** gather_context stage completes without schema error

---

### Task A2: Fix Security Gate Blocking
**Recommended Model:** Standard Codex
**Estimated Time:** 30-45 minutes

**Problem:** "Workspace mutation not permitted" in execution stage

**Investigation Steps:**
1. Read `src/agent_engine/security.py`
2. Read `examples/basic_llm_agent/cli.py` execution_handler
3. Check if security.yaml exists in configs/basic_llm_agent/
4. Understand security policy enforcement

**Fix Options:**
- Create `configs/basic_llm_agent/security.yaml` with appropriate permissions
- OR update example to use read-only operations
- OR make execution_handler respect security mode properly

**Recommended Approach:**
```yaml
# configs/basic_llm_agent/security.yaml
security:
  default_mode: safe_execute
  capabilities:
    workspace_read: true
    workspace_write: false  # example is read-only
    network: false
    shell: false
  tool_permissions:
    execution:
      allowed_operations: [list, read, search]
      denied_operations: [write, delete, modify]
```

**Test:**
```bash
PYTHONPATH=/home/ndev/agent_engine/src:$PYTHONPATH \
python3 -m examples.basic_llm_agent.cli "list files and search for README"
```

**Success Criteria:** execution stage runs without security error

---

### Task A3: Add Review Stage
**Recommended Model:** Codex Max (moderate complexity)
**Estimated Time:** 45-60 minutes

**Problem:** Missing review stage in workflow (interpretation → ... → execution → **review** → results)

**Files to Modify:**
1. `configs/basic_llm_agent/workflow.yaml` - add review stage and edge
2. `configs/basic_llm_agent/stages.yaml` - add review stage definition
3. `configs/basic_llm_agent/agents.yaml` - add reviewer agent (or reuse existing)
4. `examples/basic_llm_agent/cli.py` - add review handling to ExampleLLMClient

**Implementation:**

**workflow.yaml:**
```yaml
stages:
  # ... existing stages ...
  - id: review
    label: "Review Results"
    type: AGENT
    config:
      agent_id: reviewer

edges:
  # ... existing edges ...
  - from_stage_id: execution
    to_stage_id: review  # NEW
  - from_stage_id: review
    to_stage_id: results  # MODIFIED (was execution → results)
```

**stages.yaml:**
```yaml
stages:
  # ... existing ...
  - stage_id: review
    label: "Review Execution Results"
    kind: AGENT
    agent_id: reviewer
    input_contract: execution_output
    output_contract: review_output
```

**agents.yaml:**
```yaml
agents:
  # ... existing ...
  - id: reviewer
    role: SQUIRE
    model_backend_id: default_reasoning_model
    prompt_template_id: reviewer_v1
    capabilities: [review]
```

**cli.py ExampleLLMClient.generate():**
```python
if stage_id == "review":
    execution_result = prompt.get("execution_result", {})
    return {
        "approved": True,
        "findings": ["Results look reasonable"],
        "recommendations": ["Consider adding more detail"],
        "quality_score": 0.8
    }
```

**Test:**
```bash
PYTHONPATH=/home/ndev/agent_engine/src:$PYTHONPATH \
python3 -m examples.basic_llm_agent.cli "analyze project structure"
```

**Success Criteria:**
- Pipeline executes all 8 stages: user_input → gather_context → interpretation → decomposition → planning → execution → **review** → results
- Each stage completes without error
- Review stage produces sensible output

---

### Task A4: Comprehensive E2E Integration Test
**Recommended Model:** Codex Max
**Estimated Time:** 60-90 minutes

**Goal:** Create robust end-to-end test for the example

**File:** `tests/test_basic_llm_agent_e2e.py` (new)

**Test Structure:**
```python
"""End-to-end integration test for basic_llm_agent example."""

import pytest
from pathlib import Path

from agent_engine.config_loader import load_engine_config
from agent_engine.runtime.agent_runtime import AgentRuntime
from agent_engine.runtime.context import ContextAssembler, ContextStore
from agent_engine.runtime.pipeline_executor import PipelineExecutor
from agent_engine.runtime.router import Router
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.runtime.tool_runtime import ToolRuntime
from agent_engine.schemas import ContextItem, ContextRequest, TaskMode, TaskSpec, TaskStatus
from agent_engine.telemetry import TelemetryBus
from examples.basic_llm_agent.cli import (
    ExampleLLMClient,
    gather_context_handler,
    execution_handler,
)

@pytest.fixture
def engine_components():
    """Build all engine components for testing."""
    config_dir = Path(__file__).parents[1] / "configs" / "basic_llm_agent"
    manifests = {
        "agents": config_dir / "agents.yaml",
        "tools": config_dir / "tools.yaml",
        "stages": config_dir / "stages.yaml",
        "workflow": config_dir / "workflow.yaml",
        "pipelines": config_dir / "pipelines.yaml",
        "memory": config_dir / "memory.yaml",
    }
    engine_config, err = load_engine_config(manifests)
    assert err is None, f"Config load failed: {err}"

    # ... build all components ...
    return engine_config, executor, context_store

def test_full_pipeline_execution(engine_components):
    """Test complete pipeline execution through all 8 stages."""
    engine_config, executor, context_store = engine_components

    spec = TaskSpec(
        task_spec_id="test-full",
        request="list and analyze project files",
        mode=TaskMode.IMPLEMENT
    )

    # ... execute pipeline ...

    assert final_task.status == TaskStatus.COMPLETED

    # Verify all 8 stages executed
    expected_stages = [
        "user_input",
        "gather_context",
        "interpretation",
        "decomposition",
        "planning",
        "execution",
        "review",  # NEW
        "results"
    ]

    for stage_id in expected_stages:
        assert stage_id in final_task.stage_results
        result = final_task.stage_results[stage_id]
        assert result.error is None, f"Stage {stage_id} failed: {result.error}"
        assert result.output is not None, f"Stage {stage_id} has no output"

    # Verify review stage specifically
    review_result = final_task.stage_results["review"]
    assert "approved" in review_result.output
    assert "findings" in review_result.output

def test_pipeline_with_various_requests(engine_components):
    """Test pipeline with different types of requests."""
    test_cases = [
        "list all Python files",
        "search for imports",
        "read README.md",
        "analyze project structure",
    ]

    for request in test_cases:
        # ... test each request type ...
        pass

def test_error_handling_and_fallback(engine_components):
    """Test that pipeline handles errors gracefully."""
    # ... test error scenarios ...
    pass

def test_telemetry_and_events(engine_components):
    """Verify telemetry events are emitted correctly."""
    # ... verify event emission ...
    pass
```

**Coverage Requirements:**
- All 8 stages execute successfully
- Various request types work
- Error handling works
- Telemetry is correct
- Security policies are enforced

**Test:**
```bash
python3 -m pytest tests/test_basic_llm_agent_e2e.py -v
```

**Success Criteria:** All tests pass, demonstrating robust example

---

## CATEGORY B: Complete Documentation (HIGH ROI)

**Goal:** Generate comprehensive, accurate documentation from codebase
**Why Codex Max:** Excels at systematic extraction and documentation generation

### Task B1: API Reference Generation
**Recommended Model:** **Codex Max** (high value, large-scale)
**Estimated Time:** 2 hours → **30 minutes with Codex Max** (4x speedup)

**File:** `docs/canonical/API_REFERENCE.md`

**Scope:** Document ALL public APIs systematically

**Structure:**
```markdown
# Agent Engine API Reference

## Table of Contents
1. Schemas
2. Runtime Modules
3. Config Loader
4. Utilities

## 1. Schemas

### 1.1 Task Schemas (`agent_engine.schemas.task`)

#### TaskSpec
**Purpose:** Normalized user request specification

**Fields:**
- `task_spec_id: str` - Unique identifier for this task specification
- `request: str` - The user's request text
- `mode: TaskMode` - Execution mode (ANALYZE, IMPLEMENT, etc.)
- `metadata: Dict[str, Any]` - Additional metadata

**Usage Example:**
```python
from agent_engine.schemas import TaskSpec, TaskMode

spec = TaskSpec(
    task_spec_id="req-001",
    request="Add unit tests for parser",
    mode=TaskMode.IMPLEMENT
)
```

... (continue for ALL schemas)

## 2. Runtime Modules

### 2.1 TaskManager (`agent_engine.runtime.task_manager`)

**Purpose:** Manages task lifecycle and state transitions

**Class: TaskManager**

**Methods:**

#### `create_task(spec: TaskSpec, pipeline_id: str) -> Task`
Create a new task from a specification.

**Parameters:**
- `spec` - Task specification with request and mode
- `pipeline_id` - ID of pipeline to execute

**Returns:** New Task object with pending status

**Example:**
```python
manager = TaskManager()
task = manager.create_task(spec, pipeline_id="linear_pipeline")
```

... (continue for ALL runtime modules)
```

**Codex Max Instructions:**
1. Scan all Python files in `src/agent_engine/`
2. Extract all public classes, methods, functions
3. Extract docstrings and type hints
4. Generate structured documentation with examples
5. Organize by module and purpose
6. Include cross-references
7. Add usage examples for complex APIs

**Validation:**
- Every public class documented
- Every public method has signature + description
- Type hints preserved
- Examples for complex APIs

**Success Criteria:**
- Complete API reference
- Searchable and navigable
- Accurate type signatures
- Practical examples

---

### Task B2: Config Reference Generation
**Recommended Model:** **Codex Max** (high value, systematic)
**Estimated Time:** 2 hours → **30 minutes with Codex Max** (4x speedup)

**File:** `docs/canonical/CONFIG_REFERENCE.md`

**Scope:** Document all manifest formats (agents, tools, workflow, pipelines, memory, security)

**Structure:**
```markdown
# Agent Engine Configuration Reference

## Overview
Agent Engine is configured via YAML/JSON manifests in these categories:
- Agents - Define agent types and behaviors
- Tools - Define available tools
- Stages - Define workflow stages
- Workflow - Define stage graph (DAG)
- Pipelines - Define execution paths
- Memory - Configure context and memory
- Security - Define permissions and policies

---

## 1. Agents Manifest (`agents.yaml`)

### Purpose
Define agents with roles, capabilities, and behavioral parameters.

### Schema
```yaml
agents:
  - id: string (required)              # Unique agent identifier
    role: AgentRole (required)         # knight | squire | peasant | royalty
    profile: dict (optional)           # Agent-specific profile settings
    manifest: KnightManifest (optional) # Behavioral parameters
    schema_id: string (optional)       # Expected output schema
    version: string (default: "0.0.1") # Agent version
    metadata: dict (optional)          # Additional metadata
```

### AgentRole Values
- `knight` - Primary reasoning and implementation agents
- `squire` - Specialized helper agents (review, repair, etc.)
- `peasant` - Simple deterministic or LLM-based tools
- `royalty` - High-level decision makers and coordinators

### KnightManifest Parameters
```yaml
manifest:
  reasoning_steps: int (optional)     # Number of reasoning iterations
  tool_bias: ToolBias (default: balanced) # prefer_tools | prefer_text | balanced
  verbosity: Verbosity (default: normal)  # terse | normal | verbose
  tests_emphasis: Emphasis (default: medium) # low | medium | high
```

### Complete Example
```yaml
agents:
  - id: planner_knight
    role: knight
    profile:
      specialization: planning
      domain: software_engineering
    manifest:
      reasoning_steps: 3
      tool_bias: prefer_text
      verbosity: normal
      tests_emphasis: high
    schema_id: planner_output_v1
    version: "1.0.0"
    metadata:
      author: agent_engine_team
      description: "Knight specialized in task planning"
```

---

## 2. Tools Manifest (`tools.yaml`)
... (continue for all manifest types)
```

**Codex Max Instructions:**
1. Read all config schemas from `src/agent_engine/schemas/`
2. Read example configs from `configs/basic_llm_agent/`
3. Extract field definitions, types, defaults, constraints
4. Generate complete reference with:
   - Field-by-field documentation
   - Valid value ranges
   - Default values
   - Complete examples
   - Common patterns
5. Add validation rules where applicable

**Validation:**
- Every manifest type covered
- Every field documented with type
- Complete working examples
- Default values specified

**Success Criteria:**
- User can write manifests from scratch using only this doc
- All fields have clear descriptions
- Examples are copy-pasteable and valid

---

### Task B3: Example README
**Recommended Model:** Standard Codex
**Estimated Time:** 45 minutes

**File:** `examples/basic_llm_agent/README.md`

**Structure:**
```markdown
# Basic LLM Agent Example

## Overview
This example demonstrates a complete linear workflow through the Agent Engine:

```
user_input → gather_context → interpretation → decomposition
           → planning → execution → review → results
```

The example implements a simple LLM-powered agent that can:
- List files in the current directory
- Read file contents
- Search for text across files
- Analyze project structure

## Architecture

### Workflow Graph
The example uses a linear DAG (Directed Acyclic Graph) with 8 stages:

1. **user_input** - Capture user request
2. **gather_context** - Collect workspace information (TOOL stage)
3. **interpretation** - Understand request intent (AGENT stage)
4. **decomposition** - Break down into steps (AGENT stage)
5. **planning** - Create execution plan (AGENT stage)
6. **execution** - Execute plan with tools (TOOL stage)
7. **review** - Review results (AGENT stage)
8. **results** - Produce final output (AGENT stage)

... (continue with complete documentation)
```

**Codex Instructions:**
1. Read all example files (cli.py, manifests)
2. Understand the workflow
3. Document each stage
4. Explain how to run
5. Explain how to customize
6. Add troubleshooting section

**Success Criteria:**
- New developer can understand and run example
- Customization paths are clear
- Troubleshooting covers common issues

---

### Task B4: Getting Started Guide Enhancement
**Recommended Model:** Standard Codex
**Estimated Time:** 30 minutes

**File:** `docs/GETTING_STARTED_AGENT_ENGINE.md`

**Tasks:**
1. Read current guide
2. Test all installation steps
3. Verify all examples work
4. Add missing sections:
   - Quick start (5 minutes to first run)
   - Detailed installation
   - Running examples
   - Creating first custom project
   - Common patterns
   - Troubleshooting
5. Add command reference

**Success Criteria:**
- Works on clean system
- Takes user from zero to running example
- Clear next steps for building custom projects

---

## CATEGORY C: Research-Driven Algorithms

**Goal:** Implement well-defined algorithmic features from RESEARCH.md
**Why Codex Max:** These have clear algorithmic specifications

### Task C1: Prompt Compression Module
**Recommended Model:** **Codex Max**
**Estimated Time:** 3-4 hours → **1 hour with Codex Max** (3x speedup)
**Reference:** RESEARCH.md §1.3 (LLMLingua-inspired)

**File:** `src/agent_engine/runtime/compression.py` (new)

**Specification:**

**Goal:** Compress context items by 10-20× while preserving key information

**Algorithm (based on LLMLingua):**
1. Score each sentence/chunk by importance (using heuristics or small model)
2. Preserve structural tokens and key entities
3. Prune low-importance text under token budget
4. Return compressed text + compression ratio

**Implementation:**

```python
"""Prompt compression module based on LLMLingua research."""

from typing import List, Dict, Tuple
from dataclasses import dataclass

from agent_engine.schemas import ContextItem, CompressionPolicy

@dataclass
class CompressionResult:
    compressed_text: str
    original_tokens: int
    compressed_tokens: int
    compression_ratio: float
    importance_scores: Dict[str, float]

class PromptCompressor:
    """Compress context items while preserving key information."""

    def __init__(self, policy: CompressionPolicy):
        self.policy = policy
        self.mode = policy.mode  # cheap | balanced | max_quality

    def compress_item(self, item: ContextItem, budget: int) -> CompressionResult:
        """Compress a single context item to fit budget.

        Algorithm:
        1. Tokenize text into sentences/chunks
        2. Score each chunk by importance
        3. Preserve high-importance chunks
        4. Summarize or drop low-importance chunks
        5. Reassemble within budget
        """
        text = self._extract_text(item)
        chunks = self._chunk_text(text)

        # Score chunks
        scores = self._score_chunks(chunks, item)

        # Select chunks to preserve based on mode
        target_ratio = self._get_target_ratio()
        selected = self._select_chunks(chunks, scores, budget, target_ratio)

        # Compress selected chunks
        compressed = self._assemble_compressed(selected)

        return CompressionResult(
            compressed_text=compressed,
            original_tokens=self._count_tokens(text),
            compressed_tokens=self._count_tokens(compressed),
            compression_ratio=self._count_tokens(compressed) / self._count_tokens(text),
            importance_scores=scores
        )

    def _score_chunks(self, chunks: List[str], item: ContextItem) -> Dict[str, float]:
        """Score chunks by importance.

        Importance factors:
        - Contains code/technical terms (higher)
        - Contains question words (higher)
        - Contains entities from task (higher)
        - Redundancy (lower)
        - Position (first/last higher)
        """
        scores = {}
        for i, chunk in enumerate(chunks):
            score = 0.0

            # Position bonus (HEAD/TAIL)
            if i < 2 or i >= len(chunks) - 2:
                score += 0.3

            # Code/technical bonus
            if self._has_code(chunk):
                score += 0.4

            # Entity bonus (from item tags)
            for tag in item.tags:
                if tag.lower() in chunk.lower():
                    score += 0.3

            # Length penalty for very long chunks
            if len(chunk) > 500:
                score -= 0.1

            scores[chunk] = max(0.0, min(1.0, score))

        return scores

    def _select_chunks(
        self,
        chunks: List[str],
        scores: Dict[str, float],
        budget: int,
        target_ratio: float
    ) -> List[str]:
        """Select chunks to keep based on budget and target ratio."""
        # Sort by score (descending)
        sorted_chunks = sorted(chunks, key=lambda c: scores[c], reverse=True)

        selected = []
        current_tokens = 0
        target_tokens = int(budget * target_ratio)

        for chunk in sorted_chunks:
            chunk_tokens = self._count_tokens(chunk)
            if current_tokens + chunk_tokens <= target_tokens:
                selected.append(chunk)
                current_tokens += chunk_tokens

            if current_tokens >= target_tokens:
                break

        # Restore original order
        return [c for c in chunks if c in selected]

    def _get_target_ratio(self) -> float:
        """Get compression target based on mode."""
        if self.mode == "cheap":
            return 0.1  # 10× compression
        elif self.mode == "balanced":
            return 0.25  # 4× compression
        else:  # max_quality
            return 0.5  # 2× compression

    # ... helper methods for tokenization, code detection, etc. ...

def compress_context_items(
    items: List[ContextItem],
    policy: CompressionPolicy,
    budget: int
) -> Tuple[List[ContextItem], float]:
    """Compress a list of context items to fit within budget.

    Returns compressed items and overall compression ratio.
    """
    compressor = PromptCompressor(policy)
    compressed_items = []
    total_original = 0
    total_compressed = 0

    for item in items:
        result = compressor.compress_item(item, budget // len(items))

        # Create compressed copy of item
        compressed_item = ContextItem(
            context_item_id=item.context_item_id,
            kind=item.kind,
            source=item.source,
            timestamp=item.timestamp,
            tags=item.tags,
            importance=item.importance,
            token_cost=result.compressed_tokens,
            payload={"compressed": result.compressed_text},
            metadata={
                **item.metadata,
                "compressed": True,
                "compression_ratio": result.compression_ratio,
            }
        )

        compressed_items.append(compressed_item)
        total_original += result.original_tokens
        total_compressed += result.compressed_tokens

    overall_ratio = total_compressed / total_original if total_original > 0 else 1.0
    return compressed_items, overall_ratio
```

**Tests:** `tests/test_compression.py`
- Test compression at different ratios
- Verify key information preserved
- Test with various content types
- Measure compression ratios

**Integration:** Wire into ContextAssembler for tight budget scenarios

**Success Criteria:**
- Achieves target compression ratios
- Preserves code and entities
- Tests pass with various inputs

---

### Task C2: Prompt Template Management System
**Recommended Model:** Codex Max
**Estimated Time:** 2-3 hours
**Reference:** RESEARCH.md §5.1

**Goal:** Centralized, versioned prompt template system

**Files:**
- `src/agent_engine/runtime/templates.py` (new)
- `configs/templates/` (new directory)

**Implementation:**

```python
"""Prompt template management with versioning."""

from typing import Dict, Any
from pathlib import Path
from dataclasses import dataclass

@dataclass
class PromptTemplate:
    template_id: str
    version: str
    role: AgentRole
    sections: Dict[str, str]  # role_header, constraints, tools, context, output

    def render(self, **kwargs) -> str:
        """Render template with variables."""
        prompt_parts = []

        # Role header
        if "role_header" in self.sections:
            prompt_parts.append(self.sections["role_header"].format(**kwargs))

        # Constraints and mode
        if "constraints" in self.sections:
            prompt_parts.append(self.sections["constraints"].format(**kwargs))

        # Tools
        if "tools" in self.sections and kwargs.get("tools"):
            prompt_parts.append(self.sections["tools"].format(**kwargs))

        # Task description
        if "task" in self.sections:
            prompt_parts.append(self.sections["task"].format(**kwargs))

        # Context
        if "context" in self.sections:
            prompt_parts.append(self.sections["context"].format(**kwargs))

        # Output contract
        if "output" in self.sections:
            prompt_parts.append(self.sections["output"].format(**kwargs))

        return "\n\n".join(prompt_parts)

class TemplateManager:
    """Manage and version prompt templates."""

    def __init__(self, template_dir: Path):
        self.template_dir = template_dir
        self.templates: Dict[str, PromptTemplate] = {}
        self._load_templates()

    def _load_templates(self):
        """Load all templates from directory."""
        # ... scan template_dir and load YAML templates ...

    def get_template(self, template_id: str, version: str = "latest") -> PromptTemplate:
        """Get template by ID and version."""
        key = f"{template_id}:{version}"
        return self.templates.get(key)

    def render_prompt(
        self,
        template_id: str,
        version: str,
        **variables
    ) -> str:
        """Render a prompt from template."""
        template = self.get_template(template_id, version)
        return template.render(**variables)
```

**Template Format:** `configs/templates/knight_v1.yaml`
```yaml
template_id: knight_default
version: v1
role: knight
sections:
  role_header: |
    You are a Knight agent in the Agent Engine system.
    Your role: {role_description}

  constraints: |
    Mode: {mode}
    Capabilities: {capabilities}

  tools: |
    Available tools:
    {tool_list}

  task: |
    Task: {task_description}

  context: |
    Context:
    {context_package}

  output: |
    Output must be valid JSON matching this schema:
    {output_schema}
```

**Integration:** Update AgentRuntime to use TemplateManager

**Tests:**
- Template loading
- Versioning
- Rendering with variables
- Regression tests for template changes

**Success Criteria:**
- Templates are centralized and versioned
- Changes tracked in telemetry
- Regression suite validates template variants

---

### Task C3: JSON Error Categorization & Repair Tiers
**Recommended Model:** Codex Max
**Estimated Time:** 2 hours
**Reference:** RESEARCH.md §7.1

**Goal:** Systematic JSON error handling with repair tiers

**File:** `src/agent_engine/json_engine.py` (enhance existing)

**Enhancement:**

```python
"""Enhanced JSON Engine with error categorization and repair tiers."""

from enum import Enum
from typing import Any, Dict, Tuple, Optional

class JSONErrorCategory(str, Enum):
    SYNTAX = "syntax"  # Invalid JSON syntax
    MINOR_SCHEMA = "minor_schema"  # Schema mismatch, repairable
    MAJOR_SCHEMA = "major_schema"  # Schema mismatch, not repairable
    EMPTY = "empty"  # Empty or missing output

class RepairTier(str, Enum):
    NONE = "none"  # No repair attempted
    SYNTAX_FIX = "syntax_fix"  # Fix syntax only
    MINOR_REPAIR = "minor_repair"  # Fix minor schema issues
    RE_ASK = "re_ask"  # Re-prompt with error message
    ESCALATE = "escalate"  # Escalate to different agent/handler

@dataclass
class JSONValidationResult:
    success: bool
    data: Optional[Any]
    error: Optional[EngineError]
    error_category: Optional[JSONErrorCategory]
    repair_tier_used: RepairTier
    raw_payload: str

class JSONEngine:
    """Enhanced JSON Engine with categorization and repair."""

    def validate_with_repair(
        self,
        schema_id: str,
        raw_text: str,
        max_repair_tier: RepairTier = RepairTier.MINOR_REPAIR
    ) -> JSONValidationResult:
        """Validate and repair JSON with tiered approach."""

        # Tier 0: Direct parse
        try:
            data = json.loads(raw_text)
            valid, error = self._validate_schema(schema_id, data)
            if valid:
                return JSONValidationResult(
                    success=True,
                    data=data,
                    error=None,
                    error_category=None,
                    repair_tier_used=RepairTier.NONE,
                    raw_payload=raw_text
                )
            else:
                # Schema validation failed
                category = self._categorize_schema_error(error)
                if category == JSONErrorCategory.MINOR_SCHEMA and \
                   max_repair_tier >= RepairTier.MINOR_REPAIR:
                    # Try tier 2 repair
                    return self._repair_minor_schema(schema_id, data, raw_text)
                else:
                    # Major schema error
                    return JSONValidationResult(
                        success=False,
                        data=None,
                        error=error,
                        error_category=category,
                        repair_tier_used=RepairTier.NONE,
                        raw_payload=raw_text
                    )

        except json.JSONDecodeError as e:
            # Syntax error - try tier 1 repair
            if max_repair_tier >= RepairTier.SYNTAX_FIX:
                return self._repair_syntax(schema_id, raw_text, e)
            else:
                return JSONValidationResult(
                    success=False,
                    data=None,
                    error=self._create_error(e),
                    error_category=JSONErrorCategory.SYNTAX,
                    repair_tier_used=RepairTier.NONE,
                    raw_payload=raw_text
                )

    def _repair_syntax(
        self,
        schema_id: str,
        raw_text: str,
        parse_error: json.JSONDecodeError
    ) -> JSONValidationResult:
        """Tier 1: Fix JSON syntax errors."""
        # Trim leading/trailing junk
        trimmed = raw_text.strip()
        if trimmed.startswith("```json"):
            trimmed = trimmed[7:]
        if trimmed.endswith("```"):
            trimmed = trimmed[:-3]
        trimmed = trimmed.strip()

        # Try to fix common issues
        # - Missing closing braces
        # - Trailing commas
        # - Single quotes instead of double
        repaired = self._apply_syntax_fixes(trimmed)

        try:
            data = json.loads(repaired)
            valid, error = self._validate_schema(schema_id, data)

            return JSONValidationResult(
                success=valid,
                data=data if valid else None,
                error=error if not valid else None,
                error_category=None if valid else self._categorize_schema_error(error),
                repair_tier_used=RepairTier.SYNTAX_FIX,
                raw_payload=raw_text
            )
        except json.JSONDecodeError as e2:
            # Syntax repair failed
            return JSONValidationResult(
                success=False,
                data=None,
                error=self._create_error(e2),
                error_category=JSONErrorCategory.SYNTAX,
                repair_tier_used=RepairTier.SYNTAX_FIX,
                raw_payload=raw_text
            )

    def _repair_minor_schema(
        self,
        schema_id: str,
        data: Dict,
        raw_text: str
    ) -> JSONValidationResult:
        """Tier 2: Fix minor schema mismatches."""
        # Add missing optional fields with defaults
        # Coerce types (string "123" -> int 123)
        # Remove extra fields not in schema

        schema = self._get_schema(schema_id)
        repaired = self._apply_schema_repairs(data, schema)

        valid, error = self._validate_schema(schema_id, repaired)

        return JSONValidationResult(
            success=valid,
            data=repaired if valid else None,
            error=error if not valid else None,
            error_category=None if valid else JSONErrorCategory.MAJOR_SCHEMA,
            repair_tier_used=RepairTier.MINOR_REPAIR,
            raw_payload=raw_text
        )

    def _categorize_schema_error(self, error: EngineError) -> JSONErrorCategory:
        """Categorize schema validation errors."""
        # Analyze error to determine if minor or major
        # Minor: missing optional field, wrong type but coercible
        # Major: missing required field, incompatible structure
        # ... implementation ...
        pass

    # ... helper methods ...
```

**Tests:** `tests/test_json_engine_repair.py`
- Test each repair tier
- Test error categorization
- Test repair limits

**Integration:** Update AgentRuntime to use tiered repair

**Success Criteria:**
- Errors correctly categorized
- Appropriate repair tier selected
- Telemetry shows tier usage

---

## CATEGORY D: Test Suite Expansion

**Goal:** Comprehensive test coverage
**Why Codex Max:** Systematic test generation from specifications

### Task D1: Schema Validation Test Generation
**Recommended Model:** Codex Max
**Estimated Time:** 1-2 hours

**File:** `tests/test_schemas_validation.py` (enhance)

**Generate tests for:**
- Every schema class
- Required field validation
- Optional field defaults
- Type validation
- Enum value validation
- Nested structure validation
- Serialization/deserialization

**Codex Instructions:**
1. Read all schemas from `src/agent_engine/schemas/`
2. For each schema, generate:
   - Valid instance test
   - Missing required field test
   - Invalid type test
   - Invalid enum value test
   - Serialization round-trip test
3. Use parametrized tests where applicable

**Success Criteria:** >95% schema coverage

---

### Task D2: Integration Test Suite
**Recommended Model:** Codex Max
**Estimated Time:** 2-3 hours

**Files:** `tests/integration/` (new directory)

**Generate tests for:**
- Full pipeline execution (various workflows)
- Error handling and fallback
- Tool execution and security
- Memory and context assembly
- Routing decisions
- Telemetry emission

**Success Criteria:** All major flows tested end-to-end

---

### Task D3: Benchmark Suite Skeleton
**Recommended Model:** Codex Max
**Estimated Time:** 2-3 hours
**Reference:** RESEARCH.md §6.2

**Files:** `benchmarks/` (new directory)

**Structure:**
```
benchmarks/
  README.md
  suite.py
  tasks/
    task_001_simple_refactor.yaml
    task_002_bug_fix.yaml
    task_003_documentation.yaml
    ...
  scripts/
    run_benchmark.py
    analyze_results.py
```

**Implementation:**
- Task definition format
- Runner script
- Scoring logic
- Result storage and analysis

**Success Criteria:** Can run benchmark suite against agents

---

### Task D4: Security Policy Tests
**Recommended Model:** Standard Codex
**Estimated Time:** 1-2 hours

**File:** `tests/test_security_enforcement.py`

**Test Coverage:**
- Tool capability enforcement
- Mode-based restrictions
- Permission denials
- Audit logging
- Security policy loading

**Success Criteria:** All security policies tested

---

## CATEGORY E: Systematic Refactoring

**Goal:** Apply systematic improvements across codebase
**Why Codex Max:** Excels at consistent refactoring patterns

### Task E1: Enhanced Error Handling Patterns
**Recommended Model:** **Codex Max**
**Estimated Time:** 2-3 hours → **1 hour with Codex Max**
**Reference:** UNIFIED_PRODUCTION_PLAN.md Phase C1

**Files to Refactor:**
- `src/agent_engine/runtime/pipeline_executor.py`
- `src/agent_engine/runtime/agent_runtime.py`
- `src/agent_engine/runtime/tool_runtime.py`
- `src/agent_engine/schemas/errors.py`

**Pattern to Apply:**
```python
# Standardize error handling
try:
    result = execute_stage(...)
except EngineError as e:
    # Engine errors are already structured
    return handle_engine_error(e, task, stage)
except Exception as e:
    # Convert unexpected errors to EngineError
    engine_err = EngineError(
        error_id=generate_id(),
        code=EngineErrorCode.UNKNOWN,
        message=str(e),
        source=EngineErrorSource.RUNTIME,
        severity=Severity.ERROR,
        details={"exception_type": type(e).__name__},
        stage_id=stage.stage_id,
        task_id=task.task_id
    )
    return handle_engine_error(engine_err, task, stage)
```

**Apply Systematically:**
- All runtime modules use consistent error handling
- All errors are EngineError instances
- All errors include context (task_id, stage_id)
- All errors are logged to telemetry

**Tests:** Verify error handling in all modules

---

### Task E2: Structured Output Enforcement
**Recommended Model:** Codex Max
**Estimated Time:** 1-2 hours
**Reference:** RESEARCH.md §5.2

**Files:**
- All agent stage handlers
- AgentRuntime
- Schema definitions

**Enhancements:**
- All agent outputs validated against schemas
- Use constrained decoding where available
- Schema IDs logged in telemetry
- Clear error messages on schema violations

**Success Criteria:** Zero schema violations in tests

---

### Task E3: CI/CD Pipeline Enhancement
**Recommended Model:** Standard Codex
**Estimated Time:** 1-2 hours
**Reference:** UNIFIED_PRODUCTION_PLAN.md Phase D4

**Files:** `.github/workflows/` (enhance)

**Enhancements:**
- Test on Python 3.10, 3.11, 3.12
- Add linting (ruff, mypy)
- Add coverage reporting (>80% target)
- Add security scanning
- Add automated releases
- Add benchmark runs (optional)

**Success Criteria:** CI validates all PRs comprehensively

---

## CATEGORY F: Telemetry, UX/Cost, and Schema Hardening

**Goal:** Close remaining gaps vs. AGENT_ENGINE_OVERVIEW and RESEARCH (structured boundaries, template/telemetry, UX/cost signals).
**Why Codex Max:** Systematic, cross-cutting changes with clear specs.

### Task F1: Enforce Schemas on All Boundaries
- Validate tool inputs as well as outputs; require `inputs_schema_id`/`outputs_schema_id` on all stages and agents.
- Add config validation to fail fast when stages/tools reference null/unknown schemas.
- Telemetry: log schema IDs per call for downstream analysis.

### Task F2: Prompt Template Regression + Telemetry
- Introduce regression suite for template variants and structured-output adherence.
- Log `template_version` and schema IDs in telemetry; add coverage targets for prompts.
- Document change-control process for templates (Codex Max can draft playbook).

### Task F3: Context Paging + Compression Telemetry
- Instrument `ContextAssembler` to emit what was kept/dropped, head/tail preservation, and `compression_ratio`.
- Add a debug flag to print/record paging decisions for reproducibility.
- Wire telemetry fields for compression policy/mode (cheap/balanced/max_quality).

### Task F4: UX/Cost/Carbon Instrumentation (RESEARCH §9, Appendix A.5-A.6)
- Add lightweight cost/latency/energy proxies (model size, token counts, batch stats) to telemetry.
- Add UX signals scaffold (override frequency, interruption count, acceptance/skip rates where applicable).
- Document reporting schema and hooks for future carbon-aware scheduling.

**Success Criteria:** Every pipeline boundary has schemas enforced, template versions tracked, context paging decisions visible, and cost/UX telemetry fields wired.

---

## Summary: Codex Task Matrix

| Category | Tasks | Recommended Model | Estimated Time | Speedup with Codex Max |
|----------|-------|-------------------|----------------|------------------------|
| **A: Fix Example** | 4 tasks (A1-A4) | Standard Codex / Codex Max | 2.5-3.5 hours | Minimal (small tasks) |
| **B: Documentation** | 4 tasks (B1-B4) | **Codex Max for B1-B2** | 5-6 hours → **2-3 hours** | **3-4x speedup** |
| **C: Algorithms** | 3 tasks (C1-C3) | **Codex Max** | 7-9 hours → **4-5 hours** | **2x speedup** |
| **D: Tests** | 4 tasks (D1-D4) | **Codex Max** | 6-8 hours → **3-4 hours** | **2x speedup** |
| **E: Refactoring** | 3 tasks (E1-E3) | Codex Max for E1-E2 | 4-7 hours → **2-4 hours** | **2x speedup** |
| **F: Telemetry/UX/Schema** | 4 tasks (F1-F4) | **Codex Max** | 3-4 hours → **2-3 hours** | **1.5x speedup** |

**Total Estimated Time:**
- Without Codex Max: **27-37 hours**
- With Codex Max: **15-22 hours**
- **Overall Speedup: ~2x with Codex Max**

---

## Execution Strategy

### Week 1: Critical Path (Category A)
**Priority:** URGENT
- Task A1: Fix schema bug (15-20 min)
- Task A2: Fix security gate (30-45 min)
- Task A3: Add review stage (45-60 min)
- Task A4: E2E test (60-90 min)
**Total:** ~3 hours

**Dependencies:** Blocks example usage

---

### Week 2: Documentation (Category B)
**Priority:** HIGH (High ROI for Codex Max)
- **Task B1: API Reference (Codex Max)** - 30 min
- **Task B2: Config Reference (Codex Max)** - 30 min
- Task B3: Example README - 45 min
- Task B4: Getting Started - 30 min
**Total:** ~2-3 hours (vs 5-6 hours manual)

**Can run in PARALLEL with PLAN_SONNET_MINION.md Phase 1**

---

### Week 3: Algorithms & Tests (Categories C & D)
**Priority:** MEDIUM
- **Category C: Research algorithms (Codex Max)** - 4-5 hours
- **Category D: Test expansion (Codex Max)** - 3-4 hours
**Total:** ~7-9 hours (vs 13-17 hours manual)

**Can run in PARALLEL with PLAN_SONNET_MINION.md Phases 2-3**

---

### Week 4: Refactoring (Category E)
**Priority:** MEDIUM
- **Task E1: Error handling (Codex Max)** - 1 hour
- **Task E2: Structured outputs (Codex Max)** - 1-2 hours
- Task E3: CI/CD - 1-2 hours
**Total:** ~2-4 hours (vs 4-7 hours manual)

**Can run in PARALLEL with PLAN_SONNET_MINION.md Phases 4-5**

---

## Coordination with PLAN_SONNET_MINION.md

**Parallel Execution Safe:**
- Codex focuses on: Documentation, tests, algorithms, refactoring
- Sonnet+Minions focus on: Architecture, integration, complex features

**Potential Conflicts (Coordinate):**
- Both touch schemas → use feature branches
- Both touch runtime modules → clear module boundaries
- Sync on schema changes before implementation

**Integration Points:**
- Codex provides documentation for Sonnet's features
- Codex provides tests for Sonnet's implementations
- Regular merges and integration testing

---

## Success Criteria

### Category A Complete:
✅ Example works end-to-end with review stage
✅ All 8 stages execute without errors
✅ Comprehensive E2E test passing

### Category B Complete:
✅ Complete API reference (all public APIs)
✅ Complete config reference (all manifests)
✅ Example fully documented
✅ Getting started guide validated

### Category C Complete:
✅ Prompt compression module working (10-20× compression)
✅ Template management system operational
✅ JSON repair tiers implemented and tested

### Category D Complete:
✅ Schema validation tests (>95% coverage)
✅ Integration tests for major flows
✅ Benchmark suite skeleton ready
✅ Security tests comprehensive

### Category E Complete:
✅ Consistent error handling across all modules
✅ Structured output enforcement everywhere
✅ CI/CD validating all PRs

### ALL CATEGORIES COMPLETE:
✅ Example production-ready
✅ Documentation complete and accurate
✅ Test coverage >80%
✅ Research algorithms implemented
✅ Codebase systematically enhanced
✅ Codex tasks integrate with Sonnet work

---

**End of PLAN_CODEX.md**

**Note:** Use **Codex Max** for tasks marked **bold** for maximum efficiency.
Standard Codex sufficient for smaller tasks.

**Estimated Total Time Savings:** ~15 hours (45% reduction) when using Codex Max strategically.
