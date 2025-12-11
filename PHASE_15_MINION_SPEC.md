# Phase 15: Provider/Adapter Management - MINIMAL IMPLEMENTATION

## Goal
Basic adapter metadata tracking and version recording.

## Minimal Scope (Phase 15 v1)
- Adapter metadata schema
- Track adapter name, version, type
- Store in engine metadata
- **NO dynamic adapter loading** (future work)
- **NO health checks** (future work)
- **NO credential management** (that's Phase 20)

## Implementation

### 1. Adapter Schema (`src/agent_engine/schemas/adapter.py`)
```python
from dataclasses import dataclass
from enum import Enum

class AdapterType(str, Enum):
    LLM = "llm"
    TOOL = "tool"
    MEMORY = "memory"

@dataclass
class AdapterMetadata:
    name: str
    type: AdapterType
    version: str = "unknown"
    provider: str = ""  # e.g., "openai", "anthropic"
    enabled: bool = True
```

### 2. Enhance EngineMetadata
```python
# In src/agent_engine/schemas/metadata.py
# Add adapter_metadata field to EngineMetadata:
adapter_metadata: List[AdapterMetadata] = field(default_factory=list)
```

### 3. Adapter Registry Enhancement
```python
# In src/agent_engine/adapters.py
class AdapterRegistry:
    def get_adapter_metadata(self) -> List[AdapterMetadata]:
        """Return metadata for all registered adapters."""
        # For Phase 15, return hardcoded stub metadata
        return [
            AdapterMetadata(name="mock_llm", type=AdapterType.LLM, version="1.0.0"),
            AdapterMetadata(name="mock_tool", type=AdapterType.TOOL, version="1.0.0")
        ]
```

### 4. Metadata Collector Enhancement
```python
# In src/agent_engine/runtime/metadata_collector.py
def collect_adapter_versions(adapter_registry) -> Dict[str, str]:
    """Collect versions from registered adapters."""
    if not adapter_registry:
        return {}

    metadata_list = adapter_registry.get_adapter_metadata()
    return {m.name: m.version for m in metadata_list}

def collect_adapter_metadata(adapter_registry) -> List[AdapterMetadata]:
    """Collect full adapter metadata."""
    if not adapter_registry:
        return []
    return adapter_registry.get_adapter_metadata()
```

### 5. Engine Integration
```python
# In collect_engine_metadata(), add adapter_metadata:
metadata = EngineMetadata(
    ...
    adapter_metadata=collect_adapter_metadata(adapter_registry)
)
```

### 6. Tests (10 tests minimum)
- Schema tests (2)
- Registry tests (3)
- Metadata collection tests (3)
- Engine integration tests (2)

## Files to Create
- src/agent_engine/schemas/adapter.py
- tests/test_phase15_adapters.py

## Files to Modify
- src/agent_engine/schemas/__init__.py (export AdapterMetadata, AdapterType)
- src/agent_engine/schemas/metadata.py (add adapter_metadata field)
- src/agent_engine/adapters.py (add get_adapter_metadata)
- src/agent_engine/runtime/metadata_collector.py (enhance collection)

## Success Criteria
✅ Adapter metadata tracked
✅ Versions recorded in engine metadata
✅ 10+ tests passing
✅ No regressions
