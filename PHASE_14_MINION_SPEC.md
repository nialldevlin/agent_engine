# Phase 14: Security & Policy Layer - MINIMAL IMPLEMENTATION

## Goal
Implement basic policy evaluation framework for restricting tool usage and context visibility.

## Minimal Scope (Phase 14 v1)
- Basic policy schema and loader
- Simple deny/allow rules for tools
- Policy check before tool execution
- Telemetry events for policy denials
- **NO complex policy DSL** (future work)
- **NO runtime policy modification** (future work)

## Implementation

### 1. Policy Schema (`src/agent_engine/schemas/policy.py`)
```python
from dataclasses import dataclass, field
from typing import List, Optional
from enum import Enum

class PolicyAction(str, Enum):
    ALLOW = "allow"
    DENY = "deny"

class PolicyTarget(str, Enum):
    TOOL = "tool"
    CONTEXT = "context"  # Future
    NODE = "node"  # Future

@dataclass
class PolicyRule:
    target: PolicyTarget
    target_id: str  # tool name, node id, etc.
    action: PolicyAction
    reason: str = ""

@dataclass
class PolicySet:
    name: str
    rules: List[PolicyRule] = field(default_factory=list)
    enabled: bool = True
```

### 2. Policy Loader (`src/agent_engine/policy_loader.py`)
```python
def load_policy_manifest(config_dir: str) -> Optional[Dict]:
    # Load optional policy.yaml
    pass

def parse_policies(data: Optional[Dict]) -> List[PolicySet]:
    # Parse YAML into PolicySet objects
    # Return empty list if no policies
    pass
```

### 3. Policy Evaluator (`src/agent_engine/runtime/policy_evaluator.py`)
```python
class PolicyEvaluator:
    def __init__(self, policy_sets: List[PolicySet], telemetry=None):
        self.policy_sets = [ps for ps in policy_sets if ps.enabled]
        self.telemetry = telemetry

    def check_tool_allowed(self, tool_name: str, task_id: str = "") -> tuple[bool, str]:
        """Check if tool is allowed by policies.
        Returns: (allowed: bool, reason: str)
        """
        # Check all enabled policy sets
        # If any DENY rule matches, deny with reason
        # Otherwise allow
        pass

    def _emit_denial(self, target: str, reason: str):
        if self.telemetry:
            self.telemetry.emit_event("policy_denied", {...})
```

### 4. Integration into ToolRuntime
```python
# In ToolRuntime.__init__, add policy_evaluator parameter
# In execute_tool_plan, check policy before execution:
if self.policy_evaluator:
    allowed, reason = self.policy_evaluator.check_tool_allowed(tool_name, task_id)
    if not allowed:
        # Record denial, return error
        pass
```

### 5. Integration into Engine
```python
# Load policies in from_config_dir()
policy_data = load_policy_manifest(config_dir)
policy_sets = parse_policies(policy_data)
policy_evaluator = PolicyEvaluator(policy_sets, telemetry)

# Pass to ToolRuntime
tool_runtime = ToolRuntime(..., policy_evaluator=policy_evaluator)
```

### 6. Tests (15 tests minimum)
- Schema tests (3)
- Loader tests (3)
- Evaluator tests (6): allow, deny, multiple rules, telemetry
- Integration tests (3): tool denial, telemetry emission

## Files to Create
- src/agent_engine/schemas/policy.py
- src/agent_engine/policy_loader.py
- src/agent_engine/runtime/policy_evaluator.py
- tests/test_phase14_policy.py

## Files to Modify
- src/agent_engine/schemas/__init__.py (exports)
- src/agent_engine/runtime/__init__.py (exports)
- src/agent_engine/runtime/tool_runtime.py (policy check)
- src/agent_engine/engine.py (load and wire)

## Success Criteria
✅ Policies can deny tool usage
✅ Denials recorded in telemetry
✅ 15+ tests passing
✅ No regressions
