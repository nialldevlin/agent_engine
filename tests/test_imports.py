"""Ensure public API surface is limited to Engine and schemas."""


def test_engine_importable():
    from agent_engine import Engine

    assert Engine is not None


def test_public_schema_exports():
    import agent_engine

    required = [
        "Engine",
        "Task",
        "TaskSpec",
        "TaskMode",
        "AgentDefinition",
        "ToolDefinition",
        "WorkflowGraph",
        "Edge",
        "EdgeType",
        "__version__",
    ]
    for name in required:
        assert hasattr(agent_engine, name), f"Missing public export: {name}"


def test_runtime_internals_not_exported():
    import agent_engine

    forbidden = [
        "TaskManager",
        "Router",
        "PipelineExecutor",
        "DAGExecutor",
        "Pipeline",
        "AgentRuntime",
        "ToolRuntime",
        "ContextAssembler",
    ]
    for name in forbidden:
        assert not hasattr(agent_engine, name), f"Internal {name} should not be exported"
