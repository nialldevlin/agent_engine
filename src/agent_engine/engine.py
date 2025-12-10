from typing import Dict, List, Any
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

    def run(self, input: Any) -> Dict[str, Any]:
        """Execute workflow (stub for Phase 2).

        In Phase 2, execution is not implemented. This returns a stub
        indicating successful initialization.

        Args:
            input: JSON-serializable input data

        Returns:
            Stub dict with initialization status
        """
        import json

        # Validate input is JSON-serializable
        try:
            json.dumps(input)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Input must be JSON-serializable: {e}")

        # Get default start node
        start_node = self.workflow.get_default_start_node()

        # Return stub (no execution until Phase 4)
        return {
            "status": "initialized",
            "dag_valid": True,
            "start_node": start_node.stage_id,
            "message": "Execution not implemented until Phase 4"
        }
