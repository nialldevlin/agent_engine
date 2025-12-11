# PHASE_9_IMPLEMENTATION_PLAN.md

## SECTION 1 — Phase Summary

**Phase 9: Plugin System v1 (Read-Only Observers)**

This phase implements the plugin architecture per PROJECT_INTEGRATION_SPEC §3.6 and AGENT_ENGINE_OVERVIEW §5.

**Goal**: Provide a read-only plugin system that observes engine events without modifying execution flow, task state, or DAG routing.

**Key Components**:
1. **Plugin Schema**: `plugins.yaml` configuration format
2. **Plugin Loader**: ConfigLoader enhancement for plugin loading
3. **Plugin Registry**: Plugin management and registration
4. **Plugin Interface**: Standardized `on_event(event: Event)` interface
5. **Plugin Event Bus**: Event dispatcher to registered plugins
6. **Plugin Sandbox**: Isolation preventing mutations and side effects
7. **Integration**: Wire plugin system into Engine

**Scope**: Complete read-only plugin system with comprehensive error handling. Plugins cannot mutate state, modify routing, or affect execution.

---

## SECTION 2 — Requirements & Invariants

### 2.1 Canonical Requirements

Per PROJECT_INTEGRATION_SPEC §3.6 (Plugins):

Plugins are read-only observers on events. They:
- Receive task lifecycle events
- Receive node execution events
- Receive routing decisions
- Receive error events
- Cannot modify workflow behavior
- Cannot modify DAG structure
- Cannot mutate task state

Per PLAN_BUILD_AGENT_ENGINE.md (Phase 9 Tasks):

Plugins must:
- be configured via `plugins.yaml`
- receive deterministic events
- keep engine fully deterministic
- never alter routing or task behavior
- have failures never alter execution

### 2.2 Current State Analysis

**Already Implemented**:
- TelemetryBus with full event emission (Phase 8)
- Event schema and EventType enum
- Event emission in Router, NodeExecutor, DAGExecutor
- Engine.get_events() access methods

**Missing (Phase 9 Must Implement)**:
- Plugin schema (PluginConfig)
- Plugin interface (PluginBase or Protocol)
- Plugin loader from plugins.yaml
- Plugin registry
- Plugin event dispatcher
- Plugin error handling
- Plugin sandbox/isolation mechanism
- Integration with Engine

### 2.3 Plugin System Architecture

**Plugin Configuration** (plugins.yaml):
```yaml
plugins:
  - id: logging_plugin
    module: "my_app.plugins.LoggingPlugin"
    enabled: true
    config: {}

  - id: metrics_plugin
    module: "my_app.plugins.MetricsPlugin"
    enabled: true
    config:
      sample_rate: 0.1
```

**Plugin Interface**:
```python
class PluginBase:
    """Base class for plugins (read-only observers)."""

    def __init__(self, plugin_id: str, config: dict = None):
        self.plugin_id = plugin_id
        self.config = config or {}

    def on_event(self, event: Event) -> None:
        """Handle engine event (read-only)."""
        pass

    def on_startup(self) -> None:
        """Called when plugin is registered."""
        pass

    def on_shutdown(self) -> None:
        """Called when plugin is unregistered."""
        pass
```

**Plugin Isolation Guarantees**:
1. Plugin cannot access task internal state directly
2. Plugin cannot mutate Event objects
3. Plugin cannot access Router/DAGExecutor internals
4. Plugin exceptions caught and isolated
5. Plugin execution never affects task flow

### 2.4 Invariants

1. **Read-Only**: Plugins only receive events; cannot mutate state
2. **Determinism**: Plugin execution does not affect task execution
3. **Error Isolation**: Plugin failures never propagate to engine
4. **Event Immutability**: Events passed to plugins are immutable/copies
5. **Execution Order**: Plugins called synchronously after event emission
6. **No Side Effects**: Plugin errors logged but engine continues
7. **Lazy Loading**: Plugins loaded on demand, discarded after use
8. **Configuration Validation**: All plugins validated at load time

---

## SECTION 3 — LLM Implementation Plan

### Step 1: Create Plugin Schema

**File**: `src/agent_engine/schemas/plugin.py`

**Create new file** with:

1. **PluginConfig schema**:
   ```python
   @dataclass
   class PluginConfig:
       """Plugin configuration from plugins.yaml."""
       id: str
       module: str
       enabled: bool = True
       config: dict = None

       def validate(self) -> None:
           """Validate plugin config."""
           if not self.id:
               raise ValueError("Plugin id required")
           if not self.module:
               raise ValueError("Plugin module required")
           if not isinstance(self.enabled, bool):
               raise ValueError("Plugin enabled must be boolean")
   ```

2. **Plugin base interface**:
   ```python
   from abc import ABC, abstractmethod

   class PluginBase(ABC):
       """Base class for all plugins (read-only observers)."""

       def __init__(self, plugin_id: str, config: dict = None):
           self.plugin_id = plugin_id
           self.config = config or {}

       @abstractmethod
       def on_event(self, event: Event) -> None:
           """Handle engine event (read-only).

           Args:
               event: Immutable event from engine

           Note:
               Plugin must not mutate event or access engine internals.
               Any exceptions raised here are caught and logged.
           """
           pass

       def on_startup(self) -> None:
           """Called when plugin is registered."""
           pass

       def on_shutdown(self) -> None:
           """Called when plugin is unregistered."""
           pass
   ```

3. **Register in registry**: Update `src/agent_engine/schemas/__init__.py` to export PluginConfig and PluginBase

---

### Step 2: Create Plugin Loader

**File**: `src/agent_engine/config/plugin_loader.py`

**Create new file** with:

1. **PluginLoader class**:
   ```python
   import importlib
   from pathlib import Path
   from typing import List, Dict, Type

   class PluginLoader:
       """Loads plugins from plugins.yaml."""

       def __init__(self):
           self._loaded_plugins: Dict[str, PluginBase] = {}

       def load_plugins_from_yaml(self, yaml_path: Path) -> List[PluginBase]:
           """Load plugins from plugins.yaml file.

           Args:
               yaml_path: Path to plugins.yaml

           Returns:
               List of initialized plugin instances

           Raises:
               FileNotFoundError: If plugins.yaml not found
               ValueError: If plugin config invalid or module not found
           """
           # Read YAML file
           if not yaml_path.exists():
               return []  # Optional plugins

           with open(yaml_path, 'r') as f:
               data = yaml.safe_load(f) or {}

           plugins_config = data.get('plugins', [])
           plugins = []

           for plugin_conf in plugins_config:
               try:
                   plugin = self._load_single_plugin(plugin_conf)
                   if plugin:
                       plugins.append(plugin)
               except Exception as e:
                   raise ValueError(f"Failed to load plugin {plugin_conf.get('id', 'unknown')}: {e}")

           return plugins

       def _load_single_plugin(self, plugin_conf: dict) -> PluginBase:
           """Load a single plugin instance.

           Args:
               plugin_conf: Plugin config dict from YAML

           Returns:
               Initialized PluginBase instance
           """
           # Validate config
           plugin_config = PluginConfig(
               id=plugin_conf.get('id'),
               module=plugin_conf.get('module'),
               enabled=plugin_conf.get('enabled', True),
               config=plugin_conf.get('config', {})
           )
           plugin_config.validate()

           if not plugin_config.enabled:
               return None

           # Dynamically import module and get plugin class
           module_path, class_name = self._parse_module_path(plugin_config.module)
           try:
               module = importlib.import_module(module_path)
               plugin_class = getattr(module, class_name)

               if not issubclass(plugin_class, PluginBase):
                   raise ValueError(f"Plugin {plugin_config.id} does not inherit from PluginBase")

               # Instantiate plugin
               plugin_instance = plugin_class(
                   plugin_id=plugin_config.id,
                   config=plugin_config.config
               )

               return plugin_instance

           except ImportError as e:
               raise ValueError(f"Cannot import plugin module {module_path}: {e}")

       def _parse_module_path(self, module_str: str) -> tuple:
           """Parse module path to module and class name.

           Args:
               module_str: "my_app.plugins.LoggingPlugin"

           Returns:
               (module_path, class_name)
           """
           parts = module_str.rsplit('.', 1)
           if len(parts) != 2:
               raise ValueError(f"Invalid module path: {module_str}. Expected 'module.ClassName'")

           return parts[0], parts[1]
   ```

---

### Step 3: Create Plugin Registry

**File**: `src/agent_engine/runtime/plugin_registry.py`

**Create new file** with:

1. **PluginRegistry class**:
   ```python
   import logging
   from typing import List, Dict
   from copy import deepcopy

   logger = logging.getLogger(__name__)

   class PluginRegistry:
       """Manages registered plugins and event dispatch."""

       def __init__(self):
           self.plugins: Dict[str, PluginBase] = {}

       def register(self, plugin: PluginBase) -> None:
           """Register a plugin.

           Args:
               plugin: PluginBase instance
           """
           if plugin.plugin_id in self.plugins:
               logger.warning(f"Plugin {plugin.plugin_id} already registered, overwriting")

           self.plugins[plugin.plugin_id] = plugin

           # Call plugin startup hook
           try:
               plugin.on_startup()
           except Exception as e:
               logger.error(f"Error in plugin {plugin.plugin_id} startup: {e}")

       def unregister(self, plugin_id: str) -> None:
           """Unregister a plugin.

           Args:
               plugin_id: ID of plugin to remove
           """
           if plugin_id not in self.plugins:
               return

           plugin = self.plugins[plugin_id]

           # Call plugin shutdown hook
           try:
               plugin.on_shutdown()
           except Exception as e:
               logger.error(f"Error in plugin {plugin_id} shutdown: {e}")

           del self.plugins[plugin_id]

       def dispatch_event(self, event: Event) -> None:
           """Dispatch event to all registered plugins.

           Args:
               event: Event to dispatch (immutable copy sent to plugins)

           Note:
               Plugin exceptions are caught and logged.
               Failures never affect engine execution.
           """
           # Create immutable copy of event
           event_copy = self._freeze_event(event)

           for plugin_id, plugin in self.plugins.items():
               try:
                   plugin.on_event(event_copy)
               except Exception as e:
                   logger.error(f"Error in plugin {plugin_id}.on_event: {e}", exc_info=True)

       def _freeze_event(self, event: Event) -> Event:
           """Create immutable copy of event for plugin consumption.

           Args:
               event: Original event

           Returns:
               Deep copy of event (prevents mutations)
           """
           return deepcopy(event)

       def get_plugin(self, plugin_id: str) -> PluginBase | None:
           """Get plugin by ID.

           Args:
               plugin_id: Plugin ID

           Returns:
               Plugin instance or None if not found
           """
           return self.plugins.get(plugin_id)

       def list_plugins(self) -> List[str]:
           """List all registered plugin IDs.

           Returns:
               List of plugin IDs
           """
           return list(self.plugins.keys())

       def clear(self) -> None:
           """Unregister all plugins."""
           for plugin_id in list(self.plugins.keys()):
               self.unregister(plugin_id)
   ```

---

### Step 4: Integrate PluginRegistry with TelemetryBus

**File**: `src/agent_engine/telemetry.py`

**Modify TelemetryBus** to dispatch events to plugins:

1. Add plugin registry parameter to __init__:
   ```python
   def __init__(self, plugin_registry: PluginRegistry = None):
       self.events: List[Event] = []
       self.plugin_registry = plugin_registry
   ```

2. Modify emit method to dispatch to plugins:
   ```python
   def emit(self, event: Event) -> None:
       """Emit event to bus and dispatch to plugins.

       Args:
           event: Event to emit
       """
       self.events.append(event)

       # Dispatch to plugins if registry available
       if self.plugin_registry:
           self.plugin_registry.dispatch_event(event)
   ```

---

### Step 5: Update Engine to Initialize Plugin System

**File**: `src/agent_engine/engine.py`

**Modify Engine.__init__** to:

1. Initialize plugin registry:
   ```python
   from agent_engine.runtime.plugin_registry import PluginRegistry

   def __init__(self, dag, config_dir):
       # ... existing init ...

       # Initialize plugin system
       self.plugin_registry = PluginRegistry()
       self.telemetry = TelemetryBus(plugin_registry=self.plugin_registry)

       # Load plugins if plugins.yaml exists
       self._load_plugins(config_dir)

   def _load_plugins(self, config_dir: Path) -> None:
       """Load plugins from config directory.

       Args:
           config_dir: Configuration directory path
       """
       from agent_engine.config.plugin_loader import PluginLoader

       plugins_yaml = config_dir / "plugins.yaml"
       if not plugins_yaml.exists():
           return

       try:
           loader = PluginLoader()
           plugins = loader.load_plugins_from_yaml(plugins_yaml)

           for plugin in plugins:
               self.plugin_registry.register(plugin)

       except Exception as e:
           raise ValueError(f"Failed to load plugins: {e}")
   ```

2. Add method to access plugin registry:
   ```python
   def get_plugin_registry(self) -> PluginRegistry:
       """Get plugin registry for direct plugin management.

       Returns:
           PluginRegistry instance
       """
       return self.plugin_registry
   ```

---

### Step 6: Create Plugin Example/Template

**File**: `src/agent_engine/plugins/example_plugin.py`

**Create example plugin** showing best practices:

```python
"""Example plugin demonstrating read-only event observation."""

import logging
from agent_engine.schemas import Event, PluginBase

logger = logging.getLogger(__name__)


class ExampleLoggingPlugin(PluginBase):
    """Example plugin that logs all events."""

    def __init__(self, plugin_id: str, config: dict = None):
        super().__init__(plugin_id, config)
        self.event_count = 0

    def on_startup(self) -> None:
        """Called when plugin is registered."""
        logger.info(f"Plugin {self.plugin_id} started")

    def on_event(self, event: Event) -> None:
        """Handle engine event (read-only).

        Args:
            event: Engine event (immutable)

        Note:
            This plugin NEVER modifies the event or engine state.
        """
        self.event_count += 1
        logger.debug(f"Event {self.event_count}: {event.type} - {event.payload.get('event', 'unknown')}")

    def on_shutdown(self) -> None:
        """Called when plugin is unregistered."""
        logger.info(f"Plugin {self.plugin_id} shutdown. Processed {self.event_count} events")
```

---

### Step 7: Add Plugin Tests

**Create**: `tests/test_phase9_plugins.py`

**Test Coverage** (minimum 25 tests):

1. **Plugin Schema** (4 tests):
   - Test PluginConfig creation
   - Test PluginConfig validation (invalid id)
   - Test PluginConfig validation (invalid module)
   - Test PluginConfig serialization

2. **Plugin Loader** (6 tests):
   - Test load_plugins_from_yaml (valid plugins)
   - Test load_plugins_from_yaml (file not found - returns empty)
   - Test load_plugins_from_yaml (invalid config - raises ValueError)
   - Test load_plugins_from_yaml (module not found - raises ValueError)
   - Test load_plugins_from_yaml (class not found - raises ValueError)
   - Test load_plugins_from_yaml (class doesn't inherit PluginBase - raises ValueError)

3. **Plugin Registry** (8 tests):
   - Test register plugin
   - Test unregister plugin
   - Test register multiple plugins
   - Test dispatch_event calls all plugins
   - Test plugin exception handling (plugin error doesn't break dispatch)
   - Test dispatch_event passes immutable copy
   - Test get_plugin
   - Test list_plugins

4. **Plugin Isolation** (4 tests):
   - Test plugin cannot mutate event object
   - Test plugin exception doesn't affect other plugins
   - Test plugin cannot access engine internals
   - Test plugin shutdown called on unregister

5. **Engine Integration** (3 tests):
   - Test Engine loads plugins from plugins.yaml
   - Test Engine dispatch events to plugins
   - Test Engine.get_plugin_registry()

---

### Step 8: Create plugins.yaml Validation

**File**: `src/agent_engine/config/schemas/plugins_schema.yaml`

**Schema definition**:
```yaml
$schema: http://json-schema.org/draft-07/schema#
type: object
properties:
  plugins:
    type: array
    items:
      type: object
      properties:
        id:
          type: string
          description: "Plugin unique identifier"
        module:
          type: string
          description: "Python module path to plugin class (e.g., 'my_app.plugins.LoggingPlugin')"
        enabled:
          type: boolean
          default: true
          description: "Whether plugin is enabled"
        config:
          type: object
          description: "Plugin-specific configuration"
      required: [id, module]
```

---

### Step 9: Update ConfigLoader

**File**: `src/agent_engine/config/config_loader.py`

**Modify ConfigLoader.from_config_dir()** to load plugins:

Already handled in Step 5 (Engine._load_plugins), but ensure ConfigLoader is aware:

```python
def load_plugins_yaml(self, config_dir: Path) -> dict:
    """Load plugins.yaml if exists.

    Args:
        config_dir: Configuration directory

    Returns:
        Plugins config dict or empty dict
    """
    plugins_path = config_dir / "plugins.yaml"
    if not plugins_path.exists():
        return {}

    with open(plugins_path, 'r') as f:
        return yaml.safe_load(f) or {}
```

---

### Step 10: Update Documentation

**File**: `README.md`

**Add Phase 9 section**:

1. Plugin system overview
2. Creating custom plugins
3. Plugin interface (PluginBase)
4. Plugin configuration (plugins.yaml)
5. Example plugin code
6. Plugin isolation guarantees
7. Accessing plugin registry from Engine

**File**: `docs/operational/PLAN_BUILD_AGENT_ENGINE.md`

**Update Phase 9 status**:
- Mark as "✅ COMPLETE"
- Add summary of changes
- Add acceptance criteria checklist

---

## SECTION 4 — Acceptance Criteria

Phase 9 is complete when ALL of the following are verified:

### 4.1 Plugin Schema
- [ ] PluginConfig dataclass created
- [ ] PluginConfig validation implemented
- [ ] PluginBase ABC created with on_event, on_startup, on_shutdown
- [ ] Plugin schema exported and registered

### 4.2 Plugin Loader
- [ ] PluginLoader class created
- [ ] load_plugins_from_yaml loads valid plugins
- [ ] Handles missing plugins.yaml (returns empty list)
- [ ] Validates all plugin configs
- [ ] Dynamic module import working
- [ ] Error messages clear and actionable

### 4.3 Plugin Registry
- [ ] PluginRegistry class created
- [ ] register() method works
- [ ] unregister() method works
- [ ] dispatch_event() calls all plugins
- [ ] Plugin exceptions caught and logged
- [ ] Event copies are immutable (deep copy)
- [ ] get_plugin() and list_plugins() working

### 4.4 TelemetryBus Integration
- [ ] TelemetryBus accepts plugin_registry parameter
- [ ] TelemetryBus.emit() dispatches to registry
- [ ] Backward compatible (optional plugin_registry parameter)

### 4.5 Engine Integration
- [ ] Engine initializes PluginRegistry
- [ ] Engine loads plugins.yaml on initialization
- [ ] Engine.get_plugin_registry() accessible
- [ ] Plugins receive all emitted events
- [ ] Plugin loading errors handled gracefully

### 4.6 Plugin Isolation
- [ ] Plugins cannot mutate Event objects
- [ ] Plugins cannot access engine internals (Router, NodeExecutor, etc.)
- [ ] Plugin exceptions never affect task execution
- [ ] Plugin exceptions never affect other plugins
- [ ] Plugin loading failures don't prevent engine startup

### 4.7 Test Coverage
- [ ] At least 25 new Phase 9 tests added
- [ ] All plugin loader scenarios covered
- [ ] Plugin registry dispatch tested
- [ ] Plugin isolation tested
- [ ] Engine integration tested
- [ ] All tests passing (665+ existing + 25 new = 690 minimum)

### 4.8 Documentation
- [ ] README.md updated with plugin system section
- [ ] Plugin interface documented
- [ ] plugins.yaml format documented
- [ ] Example plugin code provided
- [ ] Plugin isolation guarantees documented

### 4.9 No Regressions
- [ ] All Phase 1-8 tests still passing
- [ ] No breaking changes to existing APIs
- [ ] Event emission unchanged
- [ ] Telemetry interface unchanged (except optional parameter)
- [ ] Deterministic execution preserved

---

## SECTION 5 — Implementation Notes

### Immutability Guarantee

To ensure plugin isolation, all events passed to plugins must be deep copies. Use `copy.deepcopy(event)` in PluginRegistry.dispatch_event().

### Error Handling

Plugin errors MUST NOT propagate to engine. All plugin calls must be wrapped in try-except blocks that log but don't raise.

### Dynamic Loading

Use Python's `importlib` to dynamically load plugin classes. Validate that loaded class inherits from PluginBase.

### Plugin Lifecycle

- on_startup() called after plugin registered
- on_event() called for each event (synchronous)
- on_shutdown() called before plugin unregistered

### Configuration

Plugin-specific config passed to plugin constructor as dict. Plugin responsible for parsing and validating.

---

## SECTION 6 — Clarifying Questions

None. All required information is present in canonical specifications and Phase 8 telemetry implementation.
