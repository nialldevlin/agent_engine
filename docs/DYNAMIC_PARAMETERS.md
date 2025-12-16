# Dynamic Parameters in Agent Engine

Runtime configuration of LLM models, tool availability, and execution settings without restarting the engine.

---

## Overview

Dynamic parameters enable runtime configuration of LLM models, tool availability, and execution settings without restarting the engine. This allows applications to adapt workflows based on user preferences, cost constraints, or execution modes.

**Key capabilities:**

- **Model switching** - Switch between cloud providers (Anthropic, OpenAI) and local models (Ollama) without code changes
- **Cost optimization** - Use faster, cheaper models (Haiku) for simple tasks and smarter models for complex ones
- **Tool management** - Enable or disable tools dynamically (e.g., read-only mode by disabling writes)
- **Hyperparameter tuning** - Adjust temperature, max_tokens, and timeouts at runtime
- **Per-task customization** - Override parameters for specific tasks without affecting others

**When to use:**

Use dynamic parameters when you need to:
- Support different execution modes (development, testing, production)
- Optimize costs based on task complexity or user tier
- Run workflows in restricted modes (analysis-only, dry-run)
- Debug issues with specific parameter combinations
- Adapt to user preferences without redeploying

---

## Quick Start

### Switch from Anthropic Claude to Local Ollama in 30 Seconds

```python
from agent_engine import Engine

# Create engine normally
engine = Engine.from_config_dir("config")

# Switch to local model for development
engine.set_agent_model("analyzer", "ollama/llama2")

# Run normally - now uses local model instead of Anthropic
result = engine.run({"request": "analyze code"})

# Switch back to cloud for production
engine.set_agent_model("analyzer", "anthropic/claude-opus-4-5")
result = engine.run({"request": "analyze code"})
```

### Environment-Based Configuration

```python
import os
from agent_engine import Engine

def setup_engine(config_dir):
    engine = Engine.from_config_dir(config_dir)

    # Use local model in development, cloud in production
    if os.getenv("ENV") == "development":
        engine.set_agent_model("analyzer", "ollama/llama2")
    else:
        engine.set_agent_model("analyzer", "anthropic/claude-opus-4-5")

    return engine

# Typical usage
engine = setup_engine("config")
result = engine.run({"request": "analyze this code"})
print(result["output"])
```

### Cost-Optimized Workflow

```python
from agent_engine import Engine

def analyze_with_cost_optimization(engine, code, complexity):
    if complexity == "simple":
        # Use fast, cheap model for simple analysis
        engine.set_agent_model("analyzer", "anthropic/claude-3-5-haiku")
    else:
        # Use smarter model for complex analysis
        engine.set_agent_model("analyzer", "anthropic/claude-opus-4-5")

    result = engine.run({"request": f"analyze: {code}"})
    return result

engine = Engine.from_config_dir("config")

# Automatically picks cheaper model for simple tasks
simple_result = analyze_with_cost_optimization(engine, "print('hello')", "simple")

# Uses better model for complex tasks
complex_result = analyze_with_cost_optimization(engine, """
def complex_algorithm():
    # Multi-threaded processing with async patterns
    ...
""", "complex")
```

---

## Concepts

### Override Scopes

Overrides can be set at three scopes with different persistence levels:

| Scope | Persistence | Use For | Resets | Priority |
|-------|-------------|---------|--------|----------|
| **Global** | Persistent | Default model for all runs | Manual via `clear_overrides()` | 3rd |
| **Project** | Persistent | Project-specific defaults | Project cleanup | 2nd |
| **Task** | Per-run | Temporary overrides for one execution | After task completes | 1st |

**Example: Understanding scopes**

```python
# Global scope: applies to ALL tasks
engine.set_agent_model("analyzer", "anthropic/claude-3-5-haiku")  # Global

# Project scope: applies to tasks in this project
engine.set_agent_model("analyzer", "anthropic/claude-opus-4-5", scope="project")

# Task scope: applies only to this specific execution
task_id = "task-123"
engine.set_task_parameters(task_id, agent_id="analyzer", temperature=0.0)

# Execute with all three scopes active
# Task scope wins: uses claude-opus-4-5 with temperature=0.0
result = engine.run({"request": "analyze code"})
```

### Priority System

When multiple scopes have overrides, the most specific wins:

```
TASK (1st) > PROJECT (2nd) > GLOBAL (3rd) > MANIFEST (base)
```

**Example: Temperature resolution**

```python
# Manifest defines temperature: 0.7
# Global override: 0.5
# Project override: 0.3
# Task override: 0.1

# When executing task with all three set:
# Result: temperature = 0.1 (task scope wins)

engine.set_agent_hyperparameters("analyzer", temperature=0.5)  # Global
engine.set_agent_hyperparameters("analyzer", temperature=0.3, scope="project")
engine.set_task_parameters("task-123", agent_id="analyzer", temperature=0.1)

result = engine.run({"request": "analyze"})
# Uses temperature=0.1 from task scope
```

### Per-Run Behavior (Task Scope Resets)

Task-scoped overrides are automatically cleared after task execution completes:

```python
# Set task-specific parameters
engine.set_task_parameters("task-1", temperature=0.0)
result1 = engine.run({"request": "task 1"})

# Task scope is automatically cleared
# Next run reverts to global/project/manifest settings
result2 = engine.run({"request": "task 2"})
# Uses original global settings, not task-1's overrides
```

### Manifest as Ceiling

Override parameters cannot exceed the limits defined in your manifests:

**agents.yaml**
```yaml
agents:
  - id: "analyzer"
    llm: "anthropic/claude-3-5-haiku"
    config:
      max_tokens: 4000  # Manifest upper limit
```

**Valid overrides:**
```python
# OK: Setting LOWER than manifest
engine.set_agent_hyperparameters("analyzer", max_tokens=2000)  # ✓

# ERROR: Exceeds manifest ceiling
engine.set_agent_hyperparameters("analyzer", max_tokens=5000)
# ValueError: max_tokens 5000 exceeds manifest limit 4000
```

---

## API Reference

### set_agent_model()

Override the LLM model for an agent.

**Signature:**
```python
engine.set_agent_model(
    agent_id: str,           # Agent identifier
    model: str,              # Format: "provider/model-name"
    scope: str = "global"    # "global", "project", or "task"
) -> None
```

**Parameters:**

| Parameter | Type | Required | Description |
|-----------|------|----------|-------------|
| `agent_id` | str | Yes | Must match an agent defined in agents.yaml |
| `model` | str | Yes | Format: "anthropic/claude-3-5-haiku", "ollama/llama2", etc. |
| `scope` | str | No | Override scope (default: "global") |

**Supported Models:**

| Provider | Models |
|----------|--------|
| **anthropic** | claude-3-5-haiku, claude-3-5-sonnet, claude-opus-4-5 |
| **ollama** | llama2, llama3, mistral, neural-chat |
| **openai** | gpt-4, gpt-3.5-turbo |

**Exceptions:**

```python
ValueError  # If agent_id not found
ValueError  # If model format invalid (must be provider/model)
```

**Examples:**

```python
from agent_engine import Engine

engine = Engine.from_config_dir("config")

# Switch to local model for development
engine.set_agent_model("analyzer", "ollama/llama2")
result = engine.run({"request": "analyze code"})

# Switch to powerful model for complex tasks
engine.set_agent_model("analyzer", "anthropic/claude-opus-4-5")
result = engine.run({"request": "complex analysis"})

# Use Sonnet for general tasks
engine.set_agent_model("analyzer", "anthropic/claude-3-5-sonnet")

# OpenAI model
engine.set_agent_model("analyzer", "openai/gpt-4")
```

---

### set_agent_hyperparameters()

Override LLM hyperparameters for an agent.

**Signature:**
```python
engine.set_agent_hyperparameters(
    agent_id: str,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    top_p: Optional[float] = None,
    timeout: Optional[float] = None,
    scope: str = "global"
) -> None
```

**Parameters:**

| Parameter | Type | Range | Description |
|-----------|------|-------|-------------|
| `agent_id` | str | - | Agent identifier |
| `temperature` | float | 0.0 - 1.0 | Lower = more deterministic, higher = more creative |
| `max_tokens` | int | 1 - 200,000 | Maximum response length |
| `top_p` | float | 0.0 - 1.0 | Nucleus sampling parameter (diversity control) |
| `timeout` | float | > 0 | Execution timeout in seconds |
| `scope` | str | - | Override scope (default: "global") |

**Exceptions:**

```python
ValueError  # If agent_id not found
ValueError  # If parameters out of valid ranges
```

**Examples:**

```python
from agent_engine import Engine

engine = Engine.from_config_dir("config")

# Deterministic mode for testing (always same output)
engine.set_agent_hyperparameters("analyzer", temperature=0.0)
result = engine.run({"request": "test"})

# Cost optimization: shorter responses
engine.set_agent_hyperparameters("analyzer", max_tokens=500)
result = engine.run({"request": "brief analysis"})

# Creative mode for brainstorming
engine.set_agent_hyperparameters("analyzer", temperature=0.9, top_p=0.95)
result = engine.run({"request": "brainstorm ideas"})

# Increase timeout for long-running tasks
engine.set_agent_hyperparameters("analyzer", timeout=300)  # 5 minutes

# Balanced settings for production
engine.set_agent_hyperparameters(
    "analyzer",
    temperature=0.7,
    max_tokens=2000,
    top_p=0.9,
    timeout=60
)
```

---

### enable_tool()

Enable or disable a tool at runtime.

**Signature:**
```python
engine.enable_tool(
    tool_id: str,
    enabled: bool = True,
    scope: str = "global"
) -> None
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `tool_id` | str | Tool identifier (must exist in tools.yaml) |
| `enabled` | bool | True to enable, False to disable |
| `scope` | str | Override scope (default: "global") |

**Exceptions:**

```python
ValueError  # If tool_id not found in configuration
```

**Examples:**

```python
from agent_engine import Engine

engine = Engine.from_config_dir("config")

# Enable read-only mode (disable all write operations)
engine.enable_tool("write_file", enabled=False)
engine.enable_tool("delete_file", enabled=False)
engine.enable_tool("modify_file", enabled=False)

# Run analysis (can read but not write)
result = engine.run({"request": "analyze code"})
print(result["output"])

# Re-enable writes after analysis
engine.enable_tool("write_file", enabled=True)

# Disable network access for offline testing
engine.enable_tool("http_request", enabled=False)
result = engine.run({"request": "test offline"})

# Disable shell for security in untrusted environments
engine.enable_tool("run_shell", enabled=False)
result = engine.run({"request": "safe execution"})
```

---

### set_node_timeout()

Override execution timeout for a workflow node.

**Signature:**
```python
engine.set_node_timeout(
    node_id: str,
    timeout_seconds: float,
    scope: str = "global"
) -> None
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `node_id` | str | Node identifier (must exist in workflow.yaml) |
| `timeout_seconds` | float | Timeout in seconds (must be > 0) |
| `scope` | str | Override scope (default: "global") |

**Exceptions:**

```python
ValueError  # If node_id not found in workflow
ValueError  # If timeout_seconds <= 0
```

**Examples:**

```python
from agent_engine import Engine

engine = Engine.from_config_dir("config")

# Give analyze node more time for complex tasks
engine.set_node_timeout("analyze", timeout_seconds=120)
result = engine.run({"request": "complex analysis"})

# Strict timeout for quick tasks
engine.set_node_timeout("validate", timeout_seconds=10)
result = engine.run({"request": "validate"})

# Different timeouts per node
engine.set_node_timeout("fetch_data", timeout_seconds=30)
engine.set_node_timeout("process", timeout_seconds=60)
engine.set_node_timeout("store_result", timeout_seconds=10)
result = engine.run({"request": "process pipeline"})
```

---

### set_task_parameters()

Set parameters for a specific task (highest priority).

**Signature:**
```python
engine.set_task_parameters(
    task_id: str,
    agent_id: Optional[str] = None,
    temperature: Optional[float] = None,
    max_tokens: Optional[int] = None,
    tools_enabled: Optional[List[str]] = None,
    timeout_seconds: Optional[float] = None
) -> None
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `task_id` | str | Task identifier to apply overrides to |
| `agent_id` | str | Agent ID to set LLM config for (optional) |
| `temperature` | float | Temperature parameter 0.0-1.0 (optional) |
| `max_tokens` | int | Maximum tokens for response (optional) |
| `tools_enabled` | List[str] | List of tool IDs to enable (optional, others disabled) |
| `timeout_seconds` | float | Timeout in seconds (optional) |

**Exceptions:**

```python
ValueError  # If task_id or agent_id invalid
ValueError  # If parameters out of range
ValueError  # If tools_enabled contains non-existent tool IDs
```

**Examples:**

```python
from agent_engine import Engine

engine = Engine.from_config_dir("config")

# Create task
task_id = "my-task-123"

# Set task-specific parameters before running
engine.set_task_parameters(
    task_id=task_id,
    agent_id="analyzer",
    temperature=0.1,  # Deterministic
    max_tokens=1000,
    tools_enabled=["read_file", "http_request"],
    timeout_seconds=60
)

# Run task with configured parameters
result = engine.run({"request": "analyze code"})

# Example: Dry-run mode (read-only)
engine.set_task_parameters(
    task_id="dry-run-task",
    agent_id="executor",
    tools_enabled=["read_file"],  # Only allow reading
    timeout_seconds=30
)

# Example: Analysis mode with temporary settings
engine.set_task_parameters(
    task_id="analysis-task",
    agent_id="analyzer",
    temperature=0.3,  # More deterministic
    max_tokens=5000
)

# Example: Testing with strict constraints
engine.set_task_parameters(
    task_id="test-task",
    agent_id="tester",
    temperature=0.0,
    timeout_seconds=10
)
```

---

### clear_overrides()

Clear parameter overrides.

**Signature:**
```python
engine.clear_overrides(
    scope: str = "global",
    agent_id: Optional[str] = None,
    tool_id: Optional[str] = None
) -> None
```

**Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| `scope` | str | Scope to clear ("global", "project", "task") |
| `agent_id` | str | If specified, only clear overrides for this agent (optional) |
| `tool_id` | str | If specified, only clear overrides for this tool (optional) |

**Exceptions:**

```python
ValueError  # If scope is invalid
```

**Examples:**

```python
from agent_engine import Engine

engine = Engine.from_config_dir("config")

# Clear all global overrides
engine.clear_overrides(scope="global")

# Clear only analyzer agent overrides
engine.clear_overrides(scope="global", agent_id="analyzer")

# Clear specific tool overrides
engine.clear_overrides(scope="global", tool_id="write_file")

# Clear all project scope overrides
engine.clear_overrides(scope="project")

# Clear task scope (usually automatic, but manual reset available)
engine.clear_overrides(scope="task")

# Example: Testing with cleanup
def test_with_overrides():
    engine = Engine.from_config_dir("config")

    # Set test overrides
    engine.set_agent_model("analyzer", "ollama/llama2")
    engine.set_agent_hyperparameters("analyzer", temperature=0.0)

    # Run tests
    result = engine.run({"request": "test"})
    assert result["status"] == "success"

    # Clean up: reset to manifest defaults
    engine.clear_overrides(scope="global")
```

---

## Use Cases

### Use Case 1: Cost Optimization

Use faster, cheaper models for simple tasks and smarter models for complex ones.

**Problem:** Cloud LLM calls are expensive. Need to optimize costs based on task complexity.

**Solution:** Route simple tasks to Haiku (fast, cheap), complex tasks to Opus (powerful, expensive).

```python
from agent_engine import Engine
from enum import Enum

class TaskComplexity(Enum):
    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"

def analyze_with_cost_optimization(engine, code, complexity):
    """Route to appropriate model based on complexity."""

    if complexity == TaskComplexity.SIMPLE:
        # Use fast, cheap model for simple analysis
        engine.set_agent_model("analyzer", "anthropic/claude-3-5-haiku")
        engine.set_agent_hyperparameters("analyzer", max_tokens=500)

    elif complexity == TaskComplexity.MODERATE:
        # Use mid-tier model for moderate tasks
        engine.set_agent_model("analyzer", "anthropic/claude-3-5-sonnet")
        engine.set_agent_hyperparameters("analyzer", max_tokens=2000)

    else:  # COMPLEX
        # Use powerful model for complex analysis
        engine.set_agent_model("analyzer", "anthropic/claude-opus-4-5")
        engine.set_agent_hyperparameters("analyzer", max_tokens=4000)

    result = engine.run({"request": f"analyze: {code}"})
    return result

# Usage
engine = Engine.from_config_dir("config")

# Automatically picks cheaper model for simple tasks
simple_result = analyze_with_cost_optimization(
    engine,
    "print('hello world')",
    TaskComplexity.SIMPLE
)
print(f"Simple task cost: ~$0.0002 (Haiku)")

# Uses better model for complex tasks
complex_result = analyze_with_cost_optimization(
    engine,
    "implement async batch processor with exponential backoff",
    TaskComplexity.COMPLEX
)
print(f"Complex task cost: ~$0.003 (Opus)")
```

**Benefits:**
- Reduce API costs by 80% for simple tasks
- Only pay for Opus-level reasoning when needed
- Transparent cost optimization without changing business logic

---

### Use Case 2: Cloud ↔ Local Development

Develop locally with Ollama, deploy with Anthropic.

**Problem:** Need to develop without cloud API costs, but want cloud models in production.

**Solution:** Environment-based model switching via overrides.

```python
import os
from agent_engine import Engine

def setup_engine(config_dir):
    """Initialize engine with environment-based model selection."""
    engine = Engine.from_config_dir(config_dir)

    env = os.getenv("ENV", "development").lower()

    if env == "development":
        print("Development mode: Using local Ollama")
        engine.set_agent_model("analyzer", "ollama/llama2")
        # Fast timeout for local testing
        engine.set_agent_hyperparameters("analyzer", timeout=30)

    elif env == "staging":
        print("Staging mode: Using Sonnet")
        engine.set_agent_model("analyzer", "anthropic/claude-3-5-sonnet")
        # Moderate timeout
        engine.set_agent_hyperparameters("analyzer", timeout=60)

    elif env == "production":
        print("Production mode: Using Opus")
        engine.set_agent_model("analyzer", "anthropic/claude-opus-4-5")
        # Generous timeout for complex tasks
        engine.set_agent_hyperparameters("analyzer", timeout=180)

    return engine

# Initialization
engine = setup_engine("config")
result = engine.run({"request": "analyze this code"})
print(result["output"])

# Running with different environments:
# ENV=development python script.py  # Uses Ollama
# ENV=staging python script.py      # Uses Sonnet
# ENV=production python script.py   # Uses Opus
```

**Benefits:**
- No cloud API costs during development
- Test with cloud models before production
- One codebase for all environments
- Easy switching without redeployment

---

### Use Case 3: Read-Only Mode

Enable analysis without allowing writes (compliance, auditing, safety).

**Problem:** Need to run untrusted workflows in read-only mode for safety/compliance.

**Solution:** Disable all write tools while enabling read tools.

```python
from agent_engine import Engine

def run_analysis_only(engine, request):
    """Run workflow in read-only analysis mode."""

    # Disable all write operations
    write_tools = ["write_file", "delete_file", "modify_file", "run_shell"]
    for tool in write_tools:
        try:
            engine.enable_tool(tool, enabled=False)
        except ValueError:
            pass  # Tool doesn't exist, skip

    # Enable only read tools
    read_tools = ["read_file", "list_files", "http_request"]
    for tool in read_tools:
        try:
            engine.enable_tool(tool, enabled=True)
        except ValueError:
            pass  # Tool doesn't exist, skip

    # Run analysis (agent can read but not write)
    result = engine.run({"request": request})

    return result

# Usage
engine = Engine.from_config_dir("config")

# Safe analysis without write capability
result = run_analysis_only(engine, "analyze the codebase for vulnerabilities")
print(f"Analysis: {result['output']}")

# Reset to normal mode
engine.clear_overrides(scope="global")
result = engine.run({"request": "now you can write"})
```

**Use cases:**

```python
# Audit mode: User analysis without modifications
engine.enable_tool("write_file", enabled=False)
audit_result = engine.run({"request": "audit user account"})

# Sandbox mode: Test in isolation
engine.enable_tool("run_shell", enabled=False)
engine.enable_tool("http_request", enabled=False)
sandbox_result = engine.run({"request": "test safely"})

# Preview mode: Show what would happen without doing it
engine.set_agent_hyperparameters("planner", temperature=0.0)
engine.enable_tool("write_file", enabled=False)
preview = engine.run({"request": "preview the changes"})
```

---

### Use Case 4: Debugging & Testing

Lower temperature for reproducible outputs, disable network for testing.

**Problem:** Need reproducible outputs for testing and debugging without network calls.

**Solution:** Lower temperature for determinism, disable network tools.

```python
from agent_engine import Engine

def test_workflow(engine, test_input):
    """Run workflow in test mode."""

    # Deterministic output (temperature=0.0)
    engine.set_agent_hyperparameters(
        "analyzer",
        temperature=0.0,  # Exact same output every run
        timeout=30
    )

    # Disable network to prevent external API calls
    try:
        engine.enable_tool("http_request", enabled=False)
    except ValueError:
        pass

    # Run test
    result = engine.run(test_input)
    return result

# Usage
engine = Engine.from_config_dir("config")

# Test 1: Deterministic behavior
test_input = {"request": "analyze: x = 1 + 1"}
result1 = test_workflow(engine, test_input)
result2 = test_workflow(engine, test_input)

# Both results should be identical (temperature=0.0)
assert result1["output"] == result2["output"], "Output should be deterministic"

# Test 2: Offline mode
engine.set_agent_hyperparameters("executor", temperature=0.0)
engine.enable_tool("http_request", enabled=False)
engine.enable_tool("run_shell", enabled=False)

offline_result = engine.run({"request": "run offline task"})
print(f"Offline result: {offline_result['output']}")

# Example: Comprehensive test setup
def setup_test_engine():
    engine = Engine.from_config_dir("config")

    # All test agents use deterministic output
    engine.set_agent_hyperparameters("analyzer", temperature=0.0)
    engine.set_agent_hyperparameters("executor", temperature=0.0)

    # Disable risky operations
    engine.enable_tool("run_shell", enabled=False)
    engine.enable_tool("http_request", enabled=False)
    engine.enable_tool("delete_file", enabled=False)

    # Short timeouts for failing fast
    engine.set_node_timeout("analyze", timeout_seconds=10)
    engine.set_node_timeout("execute", timeout_seconds=10)

    return engine

engine = setup_test_engine()
test_result = engine.run({"request": "test case 1"})
```

**Benefits:**
- Reproducible test results (no flakiness)
- Fast test execution (short timeouts)
- Offline testing (no external dependencies)
- Safe testing (disabled dangerous operations)

---

## Scopes Explained

### Global Scope

**Persistence:** Persistent across all runs until manually cleared.
**Use for:** Default model and parameters for the entire application.
**Resets:** Manual via `clear_overrides(scope="global")`.
**Priority:** Lowest (overridden by project and task scopes).

```python
# Set once, applies to all tasks
engine.set_agent_model("analyzer", "anthropic/claude-3-5-haiku")
engine.set_agent_hyperparameters("analyzer", temperature=0.7)

# Both tasks use these settings
result1 = engine.run({"request": "task 1"})
result2 = engine.run({"request": "task 2"})

# Clear when switching behavior
engine.clear_overrides(scope="global")
```

**When to use:**
- Development/testing environment configuration
- Default model for deployment
- Organization-wide policies (e.g., max token limits)
- Cost optimization rules across all workflows

---

### Project Scope

**Persistence:** Persistent within a project/namespace.
**Use for:** Project-specific defaults that override global settings.
**Resets:** During project cleanup or manual clear.
**Priority:** Medium (overridden by task scope, overrides global).

```python
# Global: Haiku (cost optimization)
engine.set_agent_model("analyzer", "anthropic/claude-3-5-haiku")

# Project: This project needs Opus
engine.set_agent_model("analyzer", "anthropic/claude-opus-4-5", scope="project")

# All tasks in this project use Opus (project wins)
result = engine.run({"request": "task"})
```

**When to use:**
- Different models for different projects
- Premium vs. standard tier workflows
- Department-specific policies
- Temporary testing within a project

---

### Task Scope

**Persistence:** Per-run only, reset after task completes.
**Use for:** One-time overrides for a specific execution.
**Resets:** Automatically after task completes.
**Priority:** Highest (overrides all other scopes).

```python
# Global/project settings remain unchanged
engine.set_agent_model("analyzer", "anthropic/claude-3-5-haiku")

# Only this task uses Opus
engine.set_task_parameters(
    task_id="special-task",
    agent_id="analyzer",
    temperature=0.1
)

result1 = engine.run({"request": "special task"})  # Uses Opus with temp=0.1

# Next task reverts to global/project settings
result2 = engine.run({"request": "normal task"})  # Uses Haiku
```

**When to use:**
- One-time special handling
- A/B testing specific parameters
- User-specific customization
- Emergency escalation (use better model just for this task)

---

### Scope Priority Examples

**Example 1: Temperature resolution**

```python
# Manifest: temperature=0.7
engine.set_agent_hyperparameters("analyzer", temperature=0.5)  # Global
engine.set_agent_hyperparameters("analyzer", temperature=0.3, scope="project")
engine.set_task_parameters("task-1", agent_id="analyzer", temperature=0.1)

result = engine.run({"request": "analyze"})
# Temperature: 0.1 (task > project > global > manifest)
```

**Example 2: Model resolution**

```python
# Manifest: model=anthropic/claude-3-5-haiku
engine.set_agent_model("analyzer", "anthropic/claude-3-5-sonnet")  # Global
engine.set_agent_model("analyzer", "anthropic/claude-opus-4-5", scope="project")

result = engine.run({"request": "analyze"})
# Model: claude-opus-4-5 (project > global > manifest)

# Task override wins
engine.set_task_parameters("task-1", agent_id="analyzer", ...)
# Task scope would win if set
```

---

## Constraints & Safety

### Manifest as Ceiling

Override parameters cannot exceed limits defined in manifests. This prevents accidental resource exhaustion or security violations.

**agents.yaml Example:**
```yaml
agents:
  - id: "analyzer"
    llm: "anthropic/claude-3-5-haiku"
    config:
      max_tokens: 4000  # Manifest defines this as upper limit
      temperature: 0.7
```

**Valid overrides (lower than manifest):**
```python
engine.set_agent_hyperparameters("analyzer", max_tokens=2000)  # ✓ OK
engine.set_agent_hyperparameters("analyzer", temperature=0.5)   # ✓ OK
```

**Invalid overrides (exceed manifest):**
```python
engine.set_agent_hyperparameters("analyzer", max_tokens=5000)
# ValueError: max_tokens 5000 exceeds manifest limit 4000

engine.set_agent_hyperparameters("analyzer", temperature=1.5)
# ValueError: temperature must be in range [0.0, 1.0], got 1.5
```

**Why this matters:**
- Prevents accidental cost explosion
- Enforces security policies
- Maintains resource constraints
- Honors manifest intentions

---

### TaskMode Restrictions

Certain task modes enforce restrictions that cannot be overridden:

**DRY_RUN mode:**
- Disables shell access
- Disables write operations
- Safe preview mode

**ANALYSIS_ONLY mode:**
- Disables network access
- Disables write operations
- Read-only analysis

These restrictions are enforced at the router level and cannot be overridden by parameter overrides.

```python
# In DRY_RUN mode, shell is always disabled
# Can't override even if you set enable_tool("run_shell", enabled=True)

# In ANALYSIS_ONLY mode, network is always disabled
# Can't override even if you set enable_tool("http_request", enabled=True)
```

---

### Permission Escalation Prevention

Overrides cannot grant permissions beyond what the manifest allows:

**tools.yaml Example:**
```yaml
tools:
  - id: "file_ops"
    permissions:
      allow_network: false    # Manifest: no network
      allow_shell: true       # Manifest: shell allowed
```

**Invalid override (permission escalation):**
```python
# Can't grant network permission if manifest doesn't allow it
engine.enable_tool("file_ops", enabled=True)
# Works fine, but network still disabled by manifest

# Trying to escalate permission:
override = ParameterOverride(
    kind=ParameterOverrideKind.TOOL_CONFIG,
    scope="tool/file_ops",
    parameters={"permissions": {"allow_network": True}}
)
# Validation fails: Override grants permission not in manifest
```

---

### Validation and Error Handling

All overrides are validated before application:

```python
from agent_engine import Engine

engine = Engine.from_config_dir("config")

# Example 1: Invalid temperature
try:
    engine.set_agent_hyperparameters("analyzer", temperature=1.5)
except ValueError as e:
    print(f"Error: {e}")
    # Output: temperature must be in range [0.0, 1.0], got 1.5

# Example 2: Non-existent agent
try:
    engine.set_agent_model("nonexistent", "ollama/llama2")
except ValueError as e:
    print(f"Error: {e}")
    # Output: Agent 'nonexistent' not found in configuration

# Example 3: Invalid model format
try:
    engine.set_agent_model("analyzer", "claude-haiku")  # Missing provider
except ValueError as e:
    print(f"Error: {e}")
    # Output: model format invalid or model format must be provider/model-name

# Example 4: Exceeds manifest limit
try:
    engine.set_agent_hyperparameters("analyzer", max_tokens=999999)
except ValueError as e:
    print(f"Error: {e}")
    # Output: max_tokens 999999 exceeds manifest limit 4000
```

---

### Common Validation Rules

| Check | Error Condition | Example |
|-------|-----------------|---------|
| Agent exists | Agent ID not in agents.yaml | `set_agent_model("invalid_id", ...)` |
| Tool exists | Tool ID not in tools.yaml | `enable_tool("invalid_tool", ...)` |
| Node exists | Node ID not in workflow.yaml | `set_node_timeout("invalid_node", ...)` |
| Temperature range | Not in [0.0, 1.0] | `temperature=1.5` |
| Max tokens | Must be >= 1 | `max_tokens=0` |
| Top-p range | Not in [0.0, 1.0] | `top_p=1.5` |
| Timeout | Must be > 0 | `timeout_seconds=-10` |
| Model format | Must be "provider/model" | `"claude-haiku"` (missing provider) |
| Manifest ceiling | Can't exceed manifest | `max_tokens > manifest_max_tokens` |

---

## Best Practices

### 1. Use Global Scope for Deployment Configuration

Set deployment-level defaults once at application startup:

```python
from agent_engine import Engine
import os

def initialize_app(config_dir):
    engine = Engine.from_config_dir(config_dir)

    # Set deployment-level defaults (once at startup)
    env = os.getenv("ENV", "production")

    if env == "production":
        # Production: Use powerful model
        engine.set_agent_model("analyzer", "anthropic/claude-opus-4-5")
    elif env == "development":
        # Development: Use cheap local model
        engine.set_agent_model("analyzer", "ollama/llama2")

    return engine

# Use throughout application
app_engine = initialize_app("config")
```

**Benefits:**
- Clean startup configuration
- No per-request overhead
- Easy to see all defaults in one place

---

### 2. Use Task Scope for Temporary Overrides

Only use task scope when you need one-time special handling:

```python
def run_special_task(engine, task_request, priority="normal"):
    task_id = f"task-{priority}-{time.time()}"

    if priority == "high":
        # Temporary: Use powerful model for this task only
        engine.set_task_parameters(
            task_id=task_id,
            agent_id="analyzer",
            temperature=0.1  # Deterministic
        )

    result = engine.run(task_request)
    # Task scope automatically cleared after run

    return result
```

**Benefits:**
- No pollution of other tasks
- Automatic cleanup
- Clear intent (one-time override)

---

### 3. Always Validate in Tests

Test parameter validation and fallback behavior:

```python
def test_parameter_validation():
    engine = Engine.from_config_dir("config")

    # Test 1: Invalid temperature should raise
    with pytest.raises(ValueError):
        engine.set_agent_hyperparameters("analyzer", temperature=1.5)

    # Test 2: Non-existent agent should raise
    with pytest.raises(ValueError):
        engine.set_agent_model("nonexistent", "ollama/llama2")

    # Test 3: Manifest ceiling enforcement
    with pytest.raises(ValueError):
        engine.set_agent_hyperparameters("analyzer", max_tokens=999999)

def test_override_application():
    engine = Engine.from_config_dir("config")

    # Override to local model
    engine.set_agent_model("analyzer", "ollama/llama2")

    # Run and verify it worked
    result = engine.run({"request": "test"})
    assert result["status"] == "success"
```

---

### 4. Clear Overrides When Done

Explicitly clear overrides after special modes to reset to defaults:

```python
def analyze_safely(engine, code):
    # Enter read-only mode
    engine.enable_tool("write_file", enabled=False)

    try:
        result = engine.run({"request": f"analyze: {code}"})
        return result
    finally:
        # Always reset to normal mode
        engine.clear_overrides(scope="global")
```

**Benefits:**
- Prevents accidental state leakage
- Clear exit points
- Predictable behavior

---

### 5. Document Why Overrides Are Needed

Include comments explaining business logic:

```python
def cost_optimized_analysis(engine, code, complexity):
    # Override model based on complexity to optimize costs:
    # - Simple tasks: Haiku (~60% cheaper than Opus)
    # - Complex tasks: Opus (better quality for complex analysis)

    if complexity == "simple":
        engine.set_agent_model("analyzer", "anthropic/claude-3-5-haiku")
    else:
        engine.set_agent_model("analyzer", "anthropic/claude-opus-4-5")

    return engine.run({"request": f"analyze: {code}"})
```

**Benefits:**
- Future maintainers understand decisions
- Easier to refactor or remove
- Clear cost/quality tradeoffs

---

## Examples

### Example 1: Switch Between Models

```python
from agent_engine import Engine

engine = Engine.from_config_dir("config")

# Local development
print("Using local model...")
engine.set_agent_model("analyzer", "ollama/llama2")
result = engine.run({"request": "hello world"})
print(f"Result: {result['output']}")

# Switch to cloud for accuracy test
print("\nSwitching to Anthropic...")
engine.set_agent_model("analyzer", "anthropic/claude-3-5-haiku")
result = engine.run({"request": "hello world"})
print(f"Result: {result['output']}")

# Use powerful model for complex task
print("\nUsing powerful model...")
engine.set_agent_model("analyzer", "anthropic/claude-opus-4-5")
result = engine.run({"request": "analyze complex algorithm"})
print(f"Result: {result['output']}")
```

---

### Example 2: Optimize for Cost

```python
from agent_engine import Engine
from enum import Enum

class Tier(Enum):
    FREE = "free"         # Haiku only
    STANDARD = "standard" # Haiku/Sonnet
    PREMIUM = "premium"   # Any model

def create_user_engine(tier: Tier):
    engine = Engine.from_config_dir("config")

    if tier == Tier.FREE:
        engine.set_agent_model("analyzer", "anthropic/claude-3-5-haiku")
        engine.set_agent_hyperparameters("analyzer", max_tokens=500)

    elif tier == Tier.STANDARD:
        engine.set_agent_model("analyzer", "anthropic/claude-3-5-sonnet")
        engine.set_agent_hyperparameters("analyzer", max_tokens=2000)

    elif tier == Tier.PREMIUM:
        engine.set_agent_model("analyzer", "anthropic/claude-opus-4-5")
        engine.set_agent_hyperparameters("analyzer", max_tokens=4000)

    return engine

# Usage
free_engine = create_user_engine(Tier.FREE)
result = free_engine.run({"request": "analyze code"})
```

---

### Example 3: Read-Only Analysis

```python
from agent_engine import Engine

def analyze_untrusted_code(engine, code):
    """Safely analyze code without allowing modifications."""

    # Disable all dangerous operations
    dangerous_tools = ["write_file", "delete_file", "modify_file", "run_shell"]
    for tool in dangerous_tools:
        try:
            engine.enable_tool(tool, enabled=False)
        except ValueError:
            pass

    # Run analysis
    result = engine.run({"request": f"analyze: {code}"})

    # Clean up
    engine.clear_overrides(scope="global")

    return result

# Usage
engine = Engine.from_config_dir("config")
result = analyze_untrusted_code(engine, """
import os
os.system('rm -rf /')  # Potentially dangerous code
""")
print(f"Analysis: {result['output']}")
```

---

### Example 4: Development Mode

```python
from agent_engine import Engine
import os

def create_dev_engine():
    """Create engine configured for local development."""
    engine = Engine.from_config_dir("config")

    # Use local models (no API costs)
    engine.set_agent_model("analyzer", "ollama/llama2")

    # Faster timeouts (quick feedback loop)
    engine.set_agent_hyperparameters("analyzer", timeout=30)

    # Deterministic output (reproducible debugging)
    engine.set_agent_hyperparameters("analyzer", temperature=0.0)

    # Shorter responses (faster iteration)
    engine.set_agent_hyperparameters("analyzer", max_tokens=1000)

    # Disable network (offline development)
    try:
        engine.enable_tool("http_request", enabled=False)
    except ValueError:
        pass

    return engine

# Usage in development
if __name__ == "__main__":
    engine = create_dev_engine()

    # Quick iteration loop
    result = engine.run({"request": "debug this"})
    print(f"Debug result: {result['output']}")
```

---

## Troubleshooting

### Override Not Applied

**Symptom:** Set override but it's not being used.

**Checklist:**

1. Check override scope matches your usage
   ```python
   # Global scope (default)
   engine.set_agent_model("analyzer", "ollama/llama2")
   result1 = engine.run({"request": "task 1"})  # Uses override
   result2 = engine.run({"request": "task 2"})  # Uses override (persistent)

   # Task scope (per-run only)
   engine.set_task_parameters("task-123", agent_id="analyzer", ...)
   result = engine.run({"request": "task 123"})  # Uses override
   result = engine.run({"request": "task 456"})  # Does NOT use override (cleared)
   ```

2. Check agent ID matches exactly
   ```python
   # Wrong: typo in agent ID
   engine.set_agent_model("analyse", "ollama/llama2")  # Not 'analyzer'

   # Correct: exact match
   engine.set_agent_model("analyzer", "ollama/llama2")
   ```

3. Check scope priority
   ```python
   # If multiple scopes set, task > project > global
   # Task scope takes precedence
   engine.set_agent_model("analyzer", "haiku")  # Global
   engine.set_task_parameters("task-1", agent_id="analyzer", ...)  # Task
   # Uses task scope, not global
   ```

---

### Invalid Model Error

**Symptom:** `ValueError: model ... not in supported list`

**Solution:** Check model name format and supported list.

```python
# Wrong: missing provider
engine.set_agent_model("analyzer", "claude-haiku")

# Correct: include provider
engine.set_agent_model("analyzer", "anthropic/claude-haiku")

# Supported models:
# anthropic/claude-3-5-haiku
# anthropic/claude-3-5-sonnet
# anthropic/claude-opus-4-5
# ollama/llama2
# ollama/llama3
# ollama/mistral
# openai/gpt-4
# openai/gpt-3.5-turbo
```

---

### Permission Error

**Symptom:** `ValueError: exceeds manifest limit`

**Solution:** Check manifest for parameter limits.

```python
# Error: max_tokens exceeds manifest limit
engine.set_agent_hyperparameters("analyzer", max_tokens=5000)

# Solution:
# 1. Check agents.yaml for manifest limit:
#    config:
#      max_tokens: 4000  # This is the ceiling

# 2. Override lower value:
engine.set_agent_hyperparameters("analyzer", max_tokens=2000)  # Within limit
```

---

### Task Scope Not Persisting

**Symptom:** Task-scoped override doesn't persist to next run.

**Expected behavior:** Task scope clears after each task completes.

```python
# This is EXPECTED behavior:
engine.set_task_parameters("task-1", agent_id="analyzer", temperature=0.0)
result1 = engine.run({"request": "task 1"})   # Uses temperature=0.0

result2 = engine.run({"request": "task 2"})   # DOES NOT use temperature=0.0
# Task scope was cleared automatically

# Solution: Use global or project scope if you need persistence
engine.set_agent_hyperparameters("analyzer", temperature=0.0)  # Global
result1 = engine.run({"request": "task 1"})   # Uses temperature=0.0
result2 = engine.run({"request": "task 2"})   # Still uses temperature=0.0
```

---

## See Also

- **[GETTING_STARTED.md](./GETTING_STARTED.md)** - Basic engine setup
- **[API_REFERENCE.md](./API_REFERENCE.md)** - Complete API documentation
- **[ARCHITECTURE.md](./ARCHITECTURE.md)** - System design and components
- **[SECURITY.md](./SECURITY.md)** - Security considerations and constraints

---

## Summary

Dynamic parameters provide powerful runtime configuration without code changes:

1. **Quick to implement** - Just call `set_agent_model()`, `set_agent_hyperparameters()`, etc.
2. **Safe by default** - Manifest constraints prevent accidental violations
3. **Flexible** - Global, project, and task scopes cover all use cases
4. **Production-ready** - Used in deployment, development, testing, and emergency escalation
5. **Well-documented** - Clear error messages for invalid overrides

Use this feature to:
- Optimize costs
- Support multiple environments
- Enable special modes (read-only, dry-run, testing)
- Debug complex issues
- Adapt to user preferences
