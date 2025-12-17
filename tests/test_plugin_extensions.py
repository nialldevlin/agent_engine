from types import SimpleNamespace

from agent_engine.adapters import AdapterRegistry
from agent_engine.runtime.agent_runtime import AgentRuntime
from agent_engine.runtime.llm_client import LLMClient
from agent_engine.schemas.plugin import PluginBase
from agent_engine.engine import _convert_tools
from agent_engine.schemas.tool import ToolDefinition, ToolKind, ToolCapability, ToolRiskLevel
from agent_engine.memory_stores import initialize_memory_stores


class DummyLLM(LLMClient):
    def __init__(self, tag: str):
        self.tag = tag

    def generate(self, request):
        return f"dummy:{self.tag}"

    def stream_generate(self, request):
        yield self.generate(request)


class DummyPlugin(PluginBase):
    def register_extensions(self, adapters: AdapterRegistry) -> None:
        adapters.register_llm_factory("dummy", lambda conf: DummyLLM(conf.get("model", "default")))
        adapters.register_tool_factory(
            "dummy_tool",
            lambda conf, workspace_root: (
                ToolDefinition(
                    tool_id=conf["id"],
                    kind=ToolKind.DETERMINISTIC,
                    name=conf.get("name", conf["id"]),
                    description=conf.get("description", ""),
                    inputs_schema_id="",
                    outputs_schema_id="",
                    capabilities=[ToolCapability.DETERMINISTIC_SAFE],
                    risk_level=ToolRiskLevel.LOW,
                    version="1.0.0",
                    metadata={},
                    allow_network=False,
                    allow_shell=False,
                    filesystem_root=str(workspace_root),
                ),
                lambda **kwargs: "ok",
            ),
        )
        adapters.register_memory_store_factory(
            "dummy_store",
            lambda store_id, conf: {"store_id": store_id, "backend": "dummy_store"},
        )

    def on_event(self, event):
        return None


def test_plugin_registers_llm_factory_and_agent_runtime_uses_it():
    registry = AdapterRegistry()
    plugin = DummyPlugin(plugin_id="p1")
    plugin.register_extensions(registry)

    runtime = AgentRuntime(llm_client=None, adapter_registry=registry)
    client = runtime._get_or_create_llm_client(
        agent_id="agent1",
        llm_config={"provider": "dummy", "model": "custom-model"},
        manifest_llm_model="dummy/custom-model",
    )

    assert isinstance(client, DummyLLM)
    assert client.generate({}) == "dummy:custom-model"


def test_unknown_provider_falls_back_to_none_when_no_default_client():
    registry = AdapterRegistry()
    runtime = AgentRuntime(llm_client=None, adapter_registry=registry)
    client = runtime._get_or_create_llm_client(
        agent_id="agent1",
        llm_config={"provider": "missing", "model": "x"},
        manifest_llm_model="missing/x",
    )
    assert client is None


def test_plugin_registers_tool_factory_used_in_convert_tools(tmp_path):
    registry = AdapterRegistry()
    plugin = DummyPlugin(plugin_id="p1")
    plugin.register_extensions(registry)

    tools = [{"id": "dummy", "type": "dummy_tool"}]
    defs, handlers = _convert_tools(tools, tmp_path, adapter_registry=registry)
    assert defs and defs[0].tool_id == "dummy"
    assert "dummy" in handlers
    assert handlers["dummy"]() == "ok"


def test_plugin_memory_store_factory_used_by_initializer():
    registry = AdapterRegistry()
    plugin = DummyPlugin(plugin_id="p1")
    plugin.register_extensions(registry)

    mem = initialize_memory_stores(
        {
            "task_store": {"backend": "dummy_store"},
            "project_store": {"backend": "in_memory"},
            "global_store": {"backend": "in_memory"},
        },
        adapter_registry=registry,
    )
    assert mem["task"] == {"store_id": "task", "backend": "dummy_store"}
