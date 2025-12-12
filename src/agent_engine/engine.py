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
from .credential_loader import load_credentials_manifest, parse_credentials
from .metrics_loader import load_metrics_manifest, parse_metrics
from .policy_loader import load_policy_manifest, parse_policies
from .scheduler_loader import load_scheduler_manifest, parse_scheduler, get_default_config as get_default_scheduler_config
from .runtime import MetricsCollector, CredentialProvider
from .runtime.policy_evaluator import PolicyEvaluator
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
from .schemas import Event, EventType, EngineMetadata, MetricSample
from .runtime.task_manager import TaskManager
from .runtime.node_executor import NodeExecutor
from .runtime.router import Router
from .runtime.scheduler import TaskScheduler
from .runtime.agent_runtime import AgentRuntime
from .runtime.tool_runtime import ToolRuntime
from .runtime.context import ContextAssembler
from .runtime.deterministic_registry import DeterministicRegistry
from .runtime.artifact_store import ArtifactStore
from .runtime.metadata_collector import collect_engine_metadata
from .runtime.inspector import Inspector
from .telemetry import TelemetryBus
from .plugin_registry import PluginRegistry
from .plugin_loader import PluginLoader
from .paths import resolve_state_root, ensure_directory


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
        plugins: List[Dict],
        metadata: Optional[EngineMetadata] = None,
        metrics_collector: Optional[MetricsCollector] = None,
        policy_evaluator: Optional[PolicyEvaluator] = None,
        credential_provider: Optional[CredentialProvider] = None,
        state_root: Optional[Path] = None,
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
        self.metadata = metadata
        self.metrics_collector = metrics_collector
        self.policy_evaluator = policy_evaluator
        self.credential_provider = credential_provider
        self.state_root = ensure_directory(state_root or resolve_state_root(config_dir))

        # Initialize runtime components (Phase 4-5)
        self.task_manager = TaskManager(telemetry=None, state_root=self.state_root)
        # Expose DAG under canonical attribute for tests/apps
        self.dag = self.workflow

        # Initialize scheduler (Phase 21) - uses default config for now
        # Scheduler config can be passed via __init__ parameter in future
        self.scheduler = None  # Will be set in from_config_dir

        # Initialize artifact store (Phase 10)
        self.artifact_store = ArtifactStore()

        # Initialize plugin registry (Phase 9)
        self.plugin_registry = PluginRegistry()

        # Initialize telemetry (Phase 8) with plugin support and metrics
        self.telemetry = TelemetryBus(plugin_registry=self.plugin_registry, metrics_collector=metrics_collector)
        # Attach telemetry to task manager now that bus exists
        self.task_manager.telemetry = self.telemetry

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
            artifact_store=self.artifact_store,
            policy_evaluator=self.policy_evaluator,
        )

        # ContextAssembler uses configured memory stores and context profiles
        self.context_assembler = ContextAssembler(context_profiles=context_profiles)

        self.deterministic_registry = DeterministicRegistry()

        # JSON engine for schema validation
        from agent_engine import json_engine
        self.json_engine = json_engine

        self.node_executor = NodeExecutor(
            agent_runtime=self.agent_runtime,
            tool_runtime=self.tool_runtime,
            context_assembler=self.context_assembler,
            json_engine=self.json_engine,
            deterministic_registry=self.deterministic_registry,
            telemetry=self.telemetry,
            artifact_store=self.artifact_store,
            metadata=self.metadata
        )

        # Initialize router (Phase 5)
        self.router = Router(
            dag=self.workflow,
            task_manager=self.task_manager,
            node_executor=self.node_executor,
            telemetry=self.telemetry,
            metadata=self.metadata
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
        metrics_data = load_metrics_manifest(path)  # Optional (Phase 13)

        # Step 2: Validate manifest data
        nodes = validate_nodes(workflow_data.get('nodes', []), 'workflow.yaml')
        edges = validate_edges(workflow_data.get('edges', []), 'workflow.yaml')
        agents = validate_agents(agents_data.get('agents', []), 'agents.yaml')
        tools = validate_tools(tools_data.get('tools', []), 'tools.yaml')

        # If no EXIT node defined, synthesize a minimal exit to support healthchecks/minimal configs
        from agent_engine.schemas.stage import NodeKind, NodeRole, Node as StageNode
        from agent_engine.schemas.workflow import Edge as WorkflowEdge
        has_exit = any(n.role == NodeRole.EXIT for n in nodes.values())
        if not has_exit:
            exit_node = StageNode(
                stage_id="exit",
                name="exit",
                kind=NodeKind.DETERMINISTIC,
                role=NodeRole.EXIT,
                context="none",
                default_start=False
            )
            nodes[exit_node.stage_id] = exit_node
            # Connect default start to synthetic exit if possible
            default_start = next((n for n in nodes.values() if n.role == NodeRole.START and n.default_start), None)
            if default_start:
                edges.append(WorkflowEdge(from_node_id=default_start.stage_id, to_node_id=exit_node.stage_id))

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

        # Phase 20: Load credentials (optional)
        credentials_data = load_credentials_manifest(path)
        credentials_manifest = parse_credentials(credentials_data)
        credential_provider = CredentialProvider(credentials_manifest)

        # Step 6: Register tools and adapters (with credential support)
        adapters = initialize_adapters(agents, tools, credential_provider)

        # Step 7: Load plugins
        plugins = plugins_data.get('plugins', []) if plugins_data else []

        # Phase 11: Collect engine metadata
        metadata = collect_engine_metadata(path, adapters)

        # Phase 13: Load metrics configuration
        metrics_profiles = parse_metrics(metrics_data)
        # Use first enabled profile or default
        metrics_profile = next((p for p in metrics_profiles if p.enabled), None)
        metrics_collector = MetricsCollector(metrics_profile)

        # Phase 14: Load policies
        policy_data = load_policy_manifest(path)
        policy_sets = parse_policies(policy_data)

        # Phase 21: Load scheduler configuration
        scheduler_data = load_scheduler_manifest(path)
        scheduler_config = parse_scheduler(scheduler_data)

        # Step 8: Return engine
        state_root = ensure_directory(resolve_state_root(path))

        engine = cls(
            config_dir=path,
            workflow=dag,
            agents=agents,
            tools=tools,
            schemas=schemas,
            memory_stores=memory_stores,
            context_profiles=context_profiles,
            adapters=adapters,
            plugins=plugins,
            metadata=metadata,
            metrics_collector=metrics_collector,
            policy_evaluator=None,  # Initialized below
            credential_provider=credential_provider,
            state_root=state_root,
        )

        # Initialize policy evaluator with telemetry after engine creation
        engine.policy_evaluator = PolicyEvaluator(policy_sets, engine.telemetry)
        # Update tool runtime with policy evaluator
        engine.tool_runtime.policy_evaluator = engine.policy_evaluator

        # Initialize scheduler with telemetry (Phase 21)
        engine.scheduler = TaskScheduler(config=scheduler_config, telemetry=engine.telemetry)

        # Determine run mode: execute if CLI profiles present (full app), otherwise stub initialization
        from pathlib import Path
        engine.run_mode = "execute" if Path(path).joinpath("cli_profiles.yaml").exists() else "stub"

        return engine

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

        # Stub initialization mode (Phase 2 style) for minimal configs
        if getattr(self, "run_mode", "execute") == "stub":
            start_node = self.workflow.get_default_start_node()
            return {
                "status": "initialized",
                "dag_valid": True,
                "start_node": getattr(start_node, "stage_id", getattr(start_node, "node_id", None)),
                "message": "Engine initialized (stub run mode)",
            }

        import time
        start_time = time.time()

        # Execute via router (Phase 5 Step 12)
        completed_task = self.router.execute_task(input, start_node_id)

        # Derive execution metadata
        elapsed_ms = int((time.time() - start_time) * 1000)
        node_sequence = [r.node_id for r in getattr(completed_task, "history", []) if hasattr(r, "node_id")]
        status_value = getattr(completed_task.status, "value", str(completed_task.status)) if completed_task else "failed"
        status_map = {
            "completed": "success",
            "failed": "failure",
            "partial": "partial"
        }
        normalized_status = status_map.get(str(status_value), str(status_value))

        # Emit task completed event
        if self.telemetry and completed_task:
            self.telemetry.task_completed(
                task_id=completed_task.task_id,
                status=normalized_status,
                lifecycle=getattr(completed_task.lifecycle, "value", str(completed_task.lifecycle)),
                output=completed_task.current_output
            )

        # Format return value
        return {
            "task_id": getattr(completed_task, "task_id", None),
            "status": normalized_status,
            "output": completed_task.current_output if completed_task else None,
            "history": [record.model_dump(mode="json") for record in getattr(completed_task, "history", [])],
            "node_sequence": node_sequence,
            "execution_time_ms": elapsed_ms,
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

    def get_metadata(self) -> Optional[EngineMetadata]:
        """Get engine metadata collected during initialization.

        Returns:
            EngineMetadata instance or None if not available
        """
        return self.metadata

    def get_metrics(self) -> List[MetricSample]:
        """Get all collected metrics.

        Returns:
            List of MetricSample objects collected during execution
        """
        return self.telemetry.get_metrics()

    def get_metrics_collector(self) -> Optional[MetricsCollector]:
        """Get the metrics collector.

        Returns:
            MetricsCollector instance or None if not available
        """
        return self.metrics_collector

    def get_memory_store(self, scope: str) -> Optional[MemoryStore]:
        """Access memory store by scope ('task', 'project', 'global')."""
        key_map = {
            "task": "task",
            "project": "project",
            "global": "global",
        }
        lookup = key_map.get(scope, scope)
        return self.memory_stores.get(lookup) if self.memory_stores else None

    def get_credential_provider(self) -> Optional[CredentialProvider]:
        """Get the credential provider for accessing loaded credentials.

        Phase 20: Returns the credential provider with loaded provider credentials.
        Safe to emit metadata (no secret values) in telemetry.

        Returns:
            CredentialProvider instance or None if not available
        """
        return self.credential_provider

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

    def load_evaluations(self) -> List['EvaluationSuite']:
        """Load evaluation suites from config directory.

        Returns:
            List of EvaluationSuite objects loaded from evaluations.yaml
        """
        from agent_engine.evaluation_loader import load_evaluations_manifest, parse_evaluations

        eval_data = load_evaluations_manifest(self.config_dir)
        if not eval_data:
            return []

        return parse_evaluations(eval_data)

    def create_evaluator(self) -> 'Evaluator':
        """Create an evaluator for running evaluation suites.

        Returns:
            Evaluator instance configured with this engine
        """
        from agent_engine.runtime import Evaluator
        return Evaluator(
            engine=self,
            artifact_store=self.artifact_store,
            telemetry=self.telemetry
        )

    def create_inspector(self) -> Inspector:
        """Create an inspector for read-only task queries.

        Phase 16: Inspector provides read-only access to task state,
        history, artifacts, and events without mutation capabilities.

        Returns:
            Inspector instance configured with this engine's task manager
        """
        return Inspector(self.task_manager)

    def run_multiple(self, inputs: List[Any], start_node_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Execute multiple inputs sequentially.

        Phase 17: Runs each input through the workflow in sequence,
        collecting results. No concurrent execution (sequential only).

        Args:
            inputs: List of JSON-serializable input data
            start_node_id: Optional explicit start node ID (uses default if None)

        Returns:
            List of result dicts, one per input:
            [
                {"task_id": str, "status": str, "output": Any, "history": List},
                ...
            ]

        Raises:
            ValueError: If any input is not JSON-serializable
        """
        import json

        results = []
        for input_data in inputs:
            # Validate input is JSON-serializable
            try:
                json.dumps(input_data)
            except (TypeError, ValueError) as e:
                raise ValueError(f"Input must be JSON-serializable: {e}")

            # Execute via router (Phase 5)
            completed_task = self.router.execute_task(input_data, start_node_id)

            # Format return value
            results.append({
                "task_id": completed_task.task_id if hasattr(completed_task, 'task_id') else str(completed_task.id),
                "status": completed_task.status.value if hasattr(completed_task.status, 'value') else str(completed_task.status),
                "output": completed_task.current_output if hasattr(completed_task, 'current_output') else None,
                "history": [record.model_dump(mode="json") if hasattr(record, 'model_dump') else record for record in (completed_task.history if hasattr(completed_task, 'history') else [])]
            })

        return results

    def get_all_task_ids(self) -> List[str]:
        """Get all task IDs currently tracked.

        Phase 17: Returns list of task identifiers in memory.

        Returns:
            List of task ID strings
        """
        return list(self.task_manager.tasks.keys())

    def get_task_summary(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get summary of a task.

        Phase 17: Convenience method using Inspector to get task summary.

        Args:
            task_id: Task identifier

        Returns:
            Summary dict or None if task not found
        """
        inspector = self.create_inspector()
        return inspector.get_task_summary(task_id)

    def enqueue(self, input: Any, start_node_id: Optional[str] = None) -> str:
        """Queue a task for later execution (Phase 21).

        Per scheduler design, enqueues task for FIFO execution.
        Use run_queued() to execute queued tasks.

        Args:
            input: JSON-serializable input data
            start_node_id: Optional explicit start node ID

        Returns:
            Task ID for tracking

        Raises:
            RuntimeError: If queue is full
            ValueError: If input is not JSON-serializable
        """
        import json

        # Validate input is JSON-serializable
        try:
            json.dumps(input)
        except (TypeError, ValueError) as e:
            raise ValueError(f"Input must be JSON-serializable: {e}")

        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")

        return self.scheduler.enqueue_task(input, start_node_id)

    def run_queued(self) -> List[Dict[str, Any]]:
        """Execute all queued tasks sequentially (Phase 21).

        Dequeues and runs tasks one at a time (max_concurrency=1 in v1).

        Returns:
            List of result dicts, one per executed task:
            [
                {"task_id": str, "status": str, "output": Any, "history": List},
                ...
            ]

        Raises:
            Exception: If any task execution fails
        """
        if not self.scheduler:
            raise RuntimeError("Scheduler not initialized")

        results = []

        # Execute all queued tasks
        while self.scheduler.get_queue_size() > 0:
            # Dequeue next task
            task_id = self.scheduler.run_next()
            if not task_id:
                break

            # Get queued task info
            queued_task = None
            for task in self.scheduler.running.values():
                if task.task_id == task_id:
                    queued_task = task
                    break

            if not queued_task:
                continue

            try:
                # Execute the task using router
                completed_task = self.router.execute_task(
                    queued_task.input,
                    queued_task.start_node_id
                )

                # Mark as completed
                self.scheduler.mark_task_completed(
                    task_id,
                    completed_task.current_output if hasattr(completed_task, 'current_output') else None
                )

                # Format result
                results.append({
                    "task_id": task_id,
                    "status": "completed",
                    "output": completed_task.current_output if hasattr(completed_task, 'current_output') else None,
                    "history": [record.dict() if hasattr(record, 'dict') else record for record in (completed_task.history if hasattr(completed_task, 'history') else [])]
                })

            except Exception as e:
                # Mark as failed
                self.scheduler.mark_task_failed(task_id, str(e))

                # Format error result
                results.append({
                    "task_id": task_id,
                    "status": "failed",
                    "output": None,
                    "error": str(e),
                    "history": []
                })

        return results

    def get_scheduler(self) -> Optional[TaskScheduler]:
        """Get the task scheduler (Phase 21).

        Returns:
            TaskScheduler instance, or None if not initialized
        """
        return self.scheduler

    def get_queue_status(self) -> Dict[str, Any]:
        """Get current queue status (Phase 21).

        Returns:
            Dict with queue stats and task states
        """
        if not self.scheduler:
            return {
                "scheduler_enabled": False,
                "queue_size": 0,
                "running_count": 0,
                "completed_count": 0,
                "tasks": {}
            }

        return {
            "scheduler_enabled": self.scheduler.config.enabled,
            "max_concurrency": self.scheduler.config.max_concurrency,
            "queue_policy": self.scheduler.config.queue_policy.value,
            "max_queue_size": self.scheduler.config.max_queue_size,
            "queue_size": self.scheduler.get_queue_size(),
            "running_count": self.scheduler.get_running_count(),
            "completed_count": self.scheduler.get_completed_count(),
            "tasks": self.scheduler.get_all_states()
        }

    def create_repl(self, config_dir: Optional[str] = None, profile_id: Optional[str] = None) -> 'REPL':
        """Create a REPL for interactive workflow execution.

        Phase 18: Provides a reusable, extensible REPL framework with:
        - Profile-based configuration
        - Session history management
        - Built-in command set
        - Extensible command registry
        - File operations with workspace safety
        - Telemetry integration

        Args:
            config_dir: Directory containing cli_profiles.yaml (defaults to engine's config_dir)
            profile_id: Optional profile ID to activate (defaults to first profile)

        Returns:
            REPL instance ready to run

        Example:
            engine = Engine.from_config_dir("./config")
            repl = engine.create_repl()
            repl.run()
        """
        from .cli import REPL

        if config_dir is None:
            config_dir = self.config_dir

        return REPL(self, config_dir, profile_id)
