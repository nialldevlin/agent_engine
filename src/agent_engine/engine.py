from __future__ import annotations

from pathlib import Path
from typing import Any, Callable, Dict, Optional

from agent_engine.config_loader import EngineConfig, load_engine_config
from agent_engine.plugins import PluginManager
from agent_engine.runtime.agent_runtime import AgentRuntime
from agent_engine.runtime.context import ContextAssembler
from agent_engine.runtime.dag_executor import DAGExecutor
from agent_engine.runtime.router import Router
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.runtime.tool_runtime import ToolRuntime
from agent_engine.runtime.llm_client import LLMClient
from agent_engine.schemas import Task, TaskMode, TaskSpec
from agent_engine.telemetry import TelemetryBus


class Engine:
    """Facade that runs manifest-driven Agent Engine workloads.

    Example applications must use Engine and public schemas only; runtime internals (router,
    task manager, dag executor, etc.) must not be imported directly.
    """

    _REQUIRED_MANIFESTS = ("agents", "tools", "workflow")

    @classmethod
    def from_config_dir(
        cls,
        config_dir: str,
        llm_client: LLMClient,
        *,
        telemetry: Optional[TelemetryBus] = None,
        plugins: Optional[PluginManager] = None,
    ) -> Engine:
        """Create an Engine from a directory of YAML/JSON manifests.

        Args:
            config_dir: Directory containing the required manifests.
            llm_client: Concrete LLM client implementation.
            telemetry: Optional telemetry bus.
            plugins: Optional plugin manager for runtime hooks.

        Returns:
            Configured Engine instance.

        Raises:
            FileNotFoundError: If a required manifest cannot be found.
            RuntimeError: If manifest validation fails.
        """
        base_dir = Path(config_dir).expanduser().resolve()
        manifest_paths = cls._collect_manifest_paths(base_dir)
        config, error = load_engine_config(manifest_paths)
        if error:
            raise RuntimeError(f"Failed to load engine config: {error.message}")
        if config is None:
            raise RuntimeError("Engine configuration factory returned no config.")
        return cls(
            config=config,
            llm_client=llm_client,
            telemetry=telemetry,
            plugins=plugins,
        )

    def __init__(
        self,
        config: EngineConfig,
        llm_client: LLMClient,
        telemetry: Optional[TelemetryBus] = None,
        plugins: Optional[PluginManager] = None,
        *,
        task_manager: Optional[TaskManager] = None,
        router: Optional[Router] = None,
        context_assembler: Optional[ContextAssembler] = None,
        agent_runtime: Optional[AgentRuntime] = None,
        tool_runtime: Optional[ToolRuntime] = None,
        dag_executor: Optional[DAGExecutor] = None,
    ):
        """Initialize the Engine with resolved runtime components."""
        self.config = config
        self.llm_client = llm_client
        self.telemetry = telemetry or TelemetryBus()
        self.plugins = plugins

        self.task_manager = task_manager or TaskManager()
        self.router = router or Router(
            workflow=config.workflow, stages=config.stages
        )
        self.context_assembler = context_assembler or ContextAssembler(memory_config=config.memory)
        self.agent_runtime = agent_runtime or AgentRuntime(llm_client=self.llm_client)
        self.tool_runtime = tool_runtime or ToolRuntime(
            tools=config.tools,
            llm_client=self.llm_client,
        )
        self.dag_executor = dag_executor or DAGExecutor(
            task_manager=self.task_manager,
            router=self.router,
            context_assembler=self.context_assembler,
            agent_runtime=self.agent_runtime,
            tool_runtime=self.tool_runtime,
            telemetry=self.telemetry,
            plugins=self.plugins,
        )

    def create_task(self, input: str | TaskSpec, *, mode: str | TaskMode = "default") -> Task:
        """Create a Task from either a string request or a full TaskSpec.

        Args:
            input: User request or pre-built TaskSpec.
            mode: Optional execution mode override; defaults to ``analysis_only``.

        Returns:
            Task instance that is ready for execution.
        """
        mode_enum = self._resolve_mode(mode)
        if isinstance(input, TaskSpec):
            task_spec = input
            if mode_enum != TaskMode.ANALYSIS_ONLY or mode != "default":
                task_spec = task_spec.model_copy(update={"mode": mode_enum})
        else:
            task_spec = TaskSpec(
                task_spec_id=_generate_task_spec_id(),
                request=input,
                mode=mode_enum,
            )
        return self.task_manager.create_task(spec=task_spec)

    def run_task(self, task: Task) -> Task:
        """Run a Task through the workflow DAG."""
        return self.dag_executor.run(task=task)

    def run_one(self, input: str | TaskSpec, mode: str | TaskMode = "default") -> Task:
        """Convenience helper that creates and runs a task in one call."""
        task = self.create_task(input, mode=mode)
        return self.run_task(task)

    def register_tool_handler(self, tool_id: str, handler: Callable[[Dict[str, Any]], Any]) -> None:
        """Register a deterministic tool handler for the given tool_id."""
        if tool_id not in self.config.tools:
            raise ValueError(f"Unknown tool_id: {tool_id}")
        self.tool_runtime.tool_handlers[tool_id] = handler

    @staticmethod
    def _resolve_mode(mode: str | TaskMode) -> TaskMode:
        if isinstance(mode, TaskMode):
            return mode
        normalized = mode.lower()
        if normalized == "default":
            return TaskMode.ANALYSIS_ONLY
        try:
            return TaskMode(normalized)
        except ValueError as exc:
            raise ValueError(f"Unknown TaskMode: {mode}") from exc

    @classmethod
    def _collect_manifest_paths(cls, base_dir: Path) -> Dict[str, Optional[Path]]:
        if not base_dir.is_dir():
            raise FileNotFoundError(f"Config directory does not exist: {base_dir}")
        result: Dict[str, Optional[Path]] = {}
        for name in (*cls._REQUIRED_MANIFESTS, "memory"):
            result[name] = cls._find_manifest(base_dir, name)
            if name in cls._REQUIRED_MANIFESTS and result[name] is None:
                raise FileNotFoundError(f"Required manifest '{name}' missing in {base_dir}")
        return result

    @staticmethod
    def _find_manifest(base_dir: Path, stem: str) -> Optional[Path]:
        for ext in (".yaml", ".yml", ".json"):
            candidate = base_dir / f"{stem}{ext}"
            if candidate.exists():
                return candidate
        return None


def _generate_task_spec_id() -> str:
    from uuid import uuid4

    return f"spec-{uuid4().hex[:8]}"
