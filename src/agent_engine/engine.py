from pathlib import Path
from typing import Optional
from agent_engine.config_loader import load_engine_config, EngineConfig
from agent_engine.runtime.task_manager import TaskManager
from agent_engine.runtime.router import Router
from agent_engine.runtime.context import ContextAssembler
from agent_engine.runtime.agent_runtime import AgentRuntime
from agent_engine.runtime.tool_runtime import ToolRuntime
from agent_engine.runtime.pipeline_executor import PipelineExecutor
from agent_engine.runtime.llm_client import LLMClient
from agent_engine.schemas import Task, TaskSpec, TaskMode
from agent_engine.telemetry import TelemetryBus
from agent_engine.plugins import PluginManager

class Engine:
    """Agent Engine orchestrator façade.
    
    The Engine is the single public entry point for running manifest-driven
    multi-agent workflows. It loads configurations, manages task lifecycle,
    and executes workflows through a pipeline of agents and tools.
    
    Example apps should ONLY use Engine and public schemas; do not import
    runtime.* modules directly.
    
    Attributes:
        config (EngineConfig): Loaded configuration (agents, tools, workflow, etc.)
        llm_client (LLMClient): LLM backend adapter
        telemetry (TelemetryBus): Event telemetry bus
        plugins (PluginManager): Optional plugin system
    """

    @classmethod
    def from_config_dir(
        cls,
        config_dir: str,
        llm_client: LLMClient,
        *,
        telemetry: Optional[TelemetryBus] = None,
        plugins: Optional[PluginManager] = None
    ) -> Engine:
        """Create Engine from a configuration directory.
        
        The config_dir must contain YAML/JSON manifests:
        - agents.yaml: Agent definitions
        - tools.yaml: Tool definitions
        - stages.yaml: Stage definitions
        - workflow.yaml: Workflow graph (DAG)
        - pipelines.yaml: Pipeline definitions
        - memory.yaml: Memory configuration (optional)
        
        Args:
            config_dir: Path to directory containing manifests
            llm_client: LLM backend client implementing LLMClient interface
            telemetry: Optional telemetry bus for events/logging
            plugins: Optional plugin manager for hooks
            
        Returns:
            Configured Engine instance
            
        Raises:
            SystemExit or Exception: If config loading fails
            
        Example:
            >>> from agent_engine import Engine
            >>> engine = Engine.from_config_dir(
            ...     "configs/my_app",
            ...     llm_client=MyLLMClient()
            ... )
        """
        manifest_dict = cls._build_manifest_dict(config_dir)
        config = load_engine_config(manifest_dict)
        
        return cls(
            config=config,
            llm_client=llm_client,
            telemetry=telemetry or TelemetryBus(),
            plugins=plugins
        )

    def __init__(
        self,
        config: EngineConfig,
        llm_client: LLMClient,
        telemetry: Optional[TelemetryBus] = None,
        plugins: Optional[PluginManager] = None
    ):
        # Store config and clients
        self.config = config
        self.llm_client = llm_client
        self.telemetry = telemetry or TelemetryBus()
        self.plugins = plugins
        
        # Initialize runtime components:
        self.task_manager = TaskManager(config=self.config)
        self.router = Router(workflow=self.config.workflow, pipelines=self.config.pipelines, stages=self.config.stages)
        self.context_assembler = ContextAssembler(memory_config=self.config.memory)
        self.agent_runtime = AgentRuntime(llm_client=self.llm_client)
        self.tool_runtime = ToolRuntime(tools=self.config.tools, tool_handlers={})
        self.pipeline_executor = PipelineExecutor(telemetry=self.telemetry, plugins=self.plugins)

    def create_task(
        self,
        input: str | TaskSpec,
        *,
        mode: str | TaskMode = "default"
    ) -> Task:
        """Create a new Task from user input.
        
        Args:
            input: Either a raw string request or a fully-formed TaskSpec
            mode: Execution mode (analysis_only, implement, review, dry_run)
                  Defaults to "analysis_only" if "default" is passed
                  
        Returns:
            Task object ready to execute
            
        Example:
            >>> task = engine.create_task("List all Python files", mode="implement")
        """
        if isinstance(input, str):
            task_spec_id = self.config.auto_generate_task_spec_id()
            request = input
        else:
            task_spec_id = input.task_spec_id
            request = input.request
        
        if isinstance(mode, str):
            mode_enum = TaskMode[mode.upper()]
        else:
            mode_enum = mode

        pipeline_id = self.router.choose_pipeline(task_spec=task_spec_id)
        
        task = self.task_manager.create_task(
            spec=task_spec_id,
            request=request,
            mode=mode_enum,
            pipeline_id=pipeline_id
        )
        
        return task

    def run_task(self, task: Task) -> Task:
        """Execute a Task through its configured pipeline.
        
        Args:
            task: Task object (from create_task)
            
        Returns:
            Updated Task with results, status, and routing trace
            
        Example:
            >>> task = engine.create_task("Analyze README.md")
            >>> result = engine.run_task(task)
            >>> print(result.status)
        """
        return self.pipeline_executor.run(task=task, pipeline_id=task.pipeline_id)

    def run_one(
        self,
        input: str | TaskSpec,
        mode: str | TaskMode = "default"
    ) -> Task:
        """Convenience method: create and run a task in one call.
        
        Equivalent to:
            task = engine.create_task(input, mode=mode)
            return engine.run_task(task)
            
        Args:
            input: Either a raw string request or TaskSpec
            mode: Execution mode
            
        Returns:
            Completed Task with results
            
        Example:
            >>> result = engine.run_one("Fix the broken test")
        """
        task = self.create_task(input, mode=mode)
        return self.run_task(task)

    @classmethod
    def _build_manifest_dict(cls, config_dir: str) -> dict:
        """Build manifest dictionary from config directory."""
        manifest_dict = {}
        
        for path in Path(config_dir).glob("**/*.yaml"):
            with open(path, 'r') as f:
                content = f.read()
                manifest_dict[path.stem] = yaml.safe_load(content)
        
        return manifest_dict
