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
    validate_memory_config
)
from .memory_stores import MemoryStore, initialize_memory_stores, initialize_context_profiles
from .adapters import AdapterRegistry, initialize_adapters
from .schemas.memory import ContextProfile
from .runtime.task_manager import TaskManager
from .runtime.node_executor import NodeExecutor
from .runtime.router import Router
from .runtime.agent_runtime import AgentRuntime
from .runtime.tool_runtime import ToolRuntime
from .runtime.context import ContextAssembler
from .runtime.deterministic_registry import DeterministicRegistry


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

        # AgentRuntime expects llm_client and template_version
        self.agent_runtime = AgentRuntime(llm_client=None, template_version="v1")

        # ToolRuntime expects tools dict and tool_handlers
        tools_dict = {t['id']: t for t in tools} if tools else {}
        self.tool_runtime = ToolRuntime(tools=tools_dict, tool_handlers=None, llm_client=None)

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
            deterministic_registry=self.deterministic_registry
        )

        # Initialize router (Phase 5)
        self.router = Router(
            dag=self.workflow,
            task_manager=self.task_manager,
            node_executor=self.node_executor
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
