from pathlib import Path
from typing import Dict, List, Any, Optional
from .dag import DAG
from .manifest_loader import (
    load_workflow_manifest,
    load_agents_manifest,
    load_tools_manifest,
    load_memory_manifest,
    load_plugins_manifest,
    load_schemas
)
from .schema_validator import (
    validate_nodes,
    validate_edges,
    validate_agents,
    validate_tools,
    validate_memory_config,
    validate_exit_nodes
)
from .memory_stores import MemoryStore, initialize_memory_stores, initialize_context_profiles
from .adapters import AdapterRegistry, initialize_adapters
from .schemas.memory import ContextProfile
from .schemas import Event, EventType
from .runtime.task_manager import TaskManager
from .runtime.node_executor import NodeExecutor
from .runtime.router import Router
from .runtime.agent_runtime import AgentRuntime
from .runtime.tool_runtime import ToolRuntime
from .runtime.context import ContextAssembler
from .runtime.deterministic_registry import DeterministicRegistry
from .runtime.artifact_store import ArtifactStore
from .telemetry import TelemetryBus
from .plugin_registry import PluginRegistry
from .plugin_loader import PluginLoader


class Engine:
    """Agent Engine - orchestrates workflow execution.

    Per AGENT_ENGINE_SPEC §8 and PROJECT_INTEGRATION_SPEC §6.
    """

    def __init__(
        self,
        config_dir: str,
        workflow: DAG,
        agents: List[Dict],
        tools: List[Dict],
        schemas: Dict[str, Dict],
        memory_stores: Dict[str, MemoryStore],
        context_profiles: Dict[str, ContextProfile],
        adapters: AdapterRegistry,
        plugins: List[Dict]
    ):
        """Initialize Engine with all components."""
        self.config_dir = config_dir
        self.workflow = workflow
        self.agents = agents
        self.tools = tools
        self.schemas = schemas
        self.memory_stores = memory_stores
        self.context_profiles = context_profiles
        self.adapters = adapters
        self.plugins = plugins

        # Initialize runtime components (Phase 4-5)
        self.task_manager = TaskManager()

        # Initialize artifact store (Phase 10)
        self.artifact_store = ArtifactStore()

        # Initialize plugin registry (Phase 9)
        self.plugin_registry = PluginRegistry()

        # Initialize telemetry (Phase 8) with plugin support
        self.telemetry = TelemetryBus(plugin_registry=self.plugin_registry)

        # Load plugins from config directory (Phase 9)
        self._load_plugins(config_dir)

        # AgentRuntime expects llm_client and template_version
        self.agent_runtime = AgentRuntime(llm_client=None, template_version="v1")

        # ToolRuntime expects tools dict and tool_handlers
        tools_dict = {t['id']: t for t in tools} if tools else {}
        self.tool_runtime = ToolRuntime(
            tools=tools_dict,
            tool_handlers=None,
            llm_client=None,
            telemetry=self.telemetry,
            artifact_store=self.artifact_store
        )

        # ContextAssembler - use a stub for now
        self.context_assembler = None  # TODO: Initialize proper ContextAssembler

        self.deterministic_registry = DeterministicRegistry()

        # JSON engine stub (for schema validation)
        self.json_engine = None  # TODO: Initialize proper JSON validator

        self.node_executor = NodeExecutor(
            agent_runtime=self.agent_runtime,
            tool_runtime=self.tool_runtime,
            context_assembler=self.context_assembler,
            json_engine=self.json_engine,
            deterministic_registry=self.deterministic_registry,
            telemetry=self.telemetry,
            artifact_store=self.artifact_store
        )

        # Initialize router (Phase 5)
        self.router = Router(
            dag=self.workflow,
            task_manager=self.task_manager,
            node_executor=self.node_executor,
            telemetry=self.telemetry
        )

    @classmethod
    def from_config_dir(cls, path: str) -> 'Engine':
        """Load and initialize engine from config directory.

        Per AGENT_ENGINE_SPEC §8 initialization sequence:
        1. Load all manifests
        2. Validate schemas and references
        3. Construct nodes, edges, and DAG
        4. Validate DAG invariants
        5. Initialize memory stores
        6. Register tools and adapters
        7. Load plugins
        8. Return constructed engine

        Args:
            path: Path to config directory containing manifests

        Returns:
            Initialized Engine instance

        Raises:
            ManifestLoadError: If required manifest missing or invalid
            SchemaValidationError: If manifest data invalid
            DAGValidationError: If DAG structure invalid
        """
        # Step 1: Load all manifests
        workflow_data = load_workflow_manifest(path)
        agents_data = load_agents_manifest(path)
        tools_data = load_tools_manifest(path)
        memory_data = load_memory_manifest(path)  # Optional
        plugins_data = load_plugins_manifest(path)  # Optional
        schemas = load_schemas(path)

        # Step 2: Validate manifest data
        nodes = validate_nodes(workflow_data.get('nodes', []), 'workflow.yaml')
        edges = validate_edges(workflow_data.get('edges', []), 'workflow.yaml')
        agents = validate_agents(agents_data.get('agents', []), 'agents.yaml')
        tools = validate_tools(tools_data.get('tools', []), 'tools.yaml')

        if memory_data:
            memory_config = validate_memory_config(
                memory_data.get('memory', {}),
                'memory.yaml'
            )
        else:
            memory_config = None

        # Step 3: Construct DAG
        dag = DAG(nodes, edges)

        # Step 4: Validate DAG
        dag.validate()

        # Step 4a: Validate exit nodes (Phase 7)
        validate_exit_nodes(dag)

        # Step 5: Initialize memory stores
        memory_stores = initialize_memory_stores(memory_config)
        context_profiles = initialize_context_profiles(memory_config)

        # Step 6: Register tools and adapters
        adapters = initialize_adapters(agents, tools)

        # Step 7: Load plugins
        plugins = plugins_data.get('plugins', []) if plugins_data else []

        # Step 8: Return engine
        return cls(
            config_dir=path,
            workflow=dag,
            agents=agents,
            tools=tools,
            schemas=schemas,
            memory_stores=memory_stores,
            context_profiles=context_profiles,
            adapters=adapters,
            plugins=plugins
        )

    def run(self, input: Any, start_node_id: Optional[str] = None) -> Dict[str, Any]:
        """Execute workflow using Phase 5 Router.

        Per AGENT_ENGINE_SPEC §3.1, executes the full workflow from start
        to exit following DAG routing semantics.

        Args:
            input: JSON-serializable input data
            start_node_id: Optional explicit start node ID (uses default if None)

        Returns:
            Dict with task_id, status, output, and history

        Raises:
            EngineError: If routing fails or execution stalls
            ValueError: If input is not JSON-serializable
        """
        import json

        # Validate input is JSON-serializable
        try:
            json.dumps(input)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Input must be JSON-serializable: {e}")

        # Execute via router (Phase 5 Step 12)
        completed_task = self.router.execute_task(input, start_node_id)

        # Format return value
        return {
            "task_id": completed_task.id,
            "status": completed_task.status.value,
            "output": completed_task.current_output,
            "history": [record.dict() for record in completed_task.history]
        }

    def get_events(self) -> List[Event]:
        """Get all telemetry events.

        Returns:
            List of Event objects in emission order
        """
        return self.telemetry.events.copy()

    def get_events_by_type(self, event_type: EventType) -> List[Event]:
        """Get events filtered by type.

        Args:
            event_type: EventType to filter by

        Returns:
            List of matching Event objects
        """
        return [e for e in self.telemetry.events if e.type == event_type]

    def get_events_by_task(self, task_id: str) -> List[Event]:
        """Get events for a specific task.

        Args:
            task_id: Task ID to filter by

        Returns:
            List of Event objects for this task
        """
        return [e for e in self.telemetry.events if e.task_id == task_id]

    def clear_events(self) -> None:
        """Clear all telemetry events."""
        self.telemetry.events.clear()

    def get_plugin_registry(self) -> PluginRegistry:
        """Get plugin registry for direct plugin management.

        Returns:
            PluginRegistry instance
        """
        return self.plugin_registry

    def get_artifact_store(self) -> ArtifactStore:
        """Access the artifact store.

        Returns:
            ArtifactStore instance
        """
        return self.artifact_store

    def _load_plugins(self, config_dir: str) -> None:
        """Load plugins from config directory.

        Args:
            config_dir: Configuration directory path

        Raises:
            ValueError: If plugin loading fails
        """
        plugins_yaml = Path(config_dir) / "plugins.yaml"
        if not plugins_yaml.exists():
            return

        try:
            loader = PluginLoader()
            plugins = loader.load_plugins_from_yaml(plugins_yaml)

            for plugin in plugins:
                self.plugin_registry.register(plugin)

        except ValueError as e:
            raise ValueError(f"Failed to load plugins: {e}")
