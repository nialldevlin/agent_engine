from typing import Dict, List, Optional, TYPE_CHECKING, Callable, Any
from agent_engine.schemas import AdapterMetadata, AdapterType
from agent_engine.runtime.llm_client import AnthropicLLMClient, OpenAILLMClient, OllamaLLMClient
from agent_engine.memory_stores import MemoryStore

if TYPE_CHECKING:
    from agent_engine.runtime.llm_client import LLMClient

if TYPE_CHECKING:
    from agent_engine.runtime.credential_provider import CredentialProvider


class AdapterRegistry:
    """Registry for tools and LLM providers (stub for Phase 2).

    Phase 20 addition: Supports credential injection for providers.
    """

    def __init__(self, credential_provider: Optional['CredentialProvider'] = None):
        self.tools: Dict[str, Dict] = {}
        self.llm_providers: Dict[str, Dict] = {}
        self.llm_factories: Dict[str, Callable[[Dict[str, Any]], 'LLMClient']] = {}
        self.tool_factories: Dict[str, Callable[[Dict[str, Any], Any], tuple[Any, Optional[Callable]]]] = {}
        self.memory_store_factories: Dict[str, Callable[[str, Dict[str, Any]], Any]] = {}
        self.credential_provider = credential_provider

    def register_tool(self, tool_config: Dict) -> None:
        """Register a tool by its ID."""
        tool_id = tool_config['id']
        self.tools[tool_id] = tool_config

    def register_llm_provider(self, provider_id: str, config: Dict) -> None:
        """Register an LLM provider by its ID."""
        self.llm_providers[provider_id] = config

    def register_llm_factory(self, provider_id: str, factory: Callable[[Dict[str, Any]], 'LLMClient']) -> None:
        """Register a factory that can create LLM clients for a provider."""
        self.llm_factories[provider_id] = factory

    def create_llm_client(self, provider_id: str, config: Dict[str, Any]) -> Optional['LLMClient']:
        """Create an LLM client using a registered factory."""
        factory = self.llm_factories.get(provider_id)
        if not factory:
            return None
        return factory(config)

    def register_tool_factory(self, tool_type: str, factory: Callable[[Dict[str, Any], Any], tuple[Any, Optional[Callable]]]) -> None:
        """Register a factory for tool definitions/handlers keyed by tool type."""
        self.tool_factories[tool_type] = factory

    def create_tool(self, tool_type: str, config: Dict[str, Any], workspace_root: Any) -> Optional[tuple[Any, Optional[Callable]]]:
        """Create a tool definition/handler via a registered factory."""
        factory = self.tool_factories.get(tool_type)
        if not factory:
            return None
        return factory(config, workspace_root)

    def register_memory_store_factory(self, backend: str, factory: Callable[[str, Dict[str, Any]], Any]) -> None:
        """Register a factory for memory stores keyed by backend name."""
        self.memory_store_factories[backend] = factory

    def create_memory_store(self, backend: str, store_id: str, config: Dict[str, Any]) -> Optional[Any]:
        factory = self.memory_store_factories.get(backend)
        if not factory:
            return None
        return factory(store_id, config)

    def get_tool(self, tool_id: str) -> Optional[Dict]:
        """Get tool config by ID."""
        return self.tools.get(tool_id)

    def get_llm_provider(self, provider_id: str) -> Optional[Dict]:
        """Get LLM provider config by ID."""
        return self.llm_providers.get(provider_id)

    def get_adapter_metadata(self) -> List[AdapterMetadata]:
        """Get metadata for all registered adapters.

        Returns list of AdapterMetadata for both tools and LLM providers.
        For Phase 15, returns stub metadata with empty versions and hashes.

        Returns:
            List of AdapterMetadata instances for all adapters
        """
        metadata_list = []

        # Collect LLM provider adapters
        for provider_id in self.llm_providers.keys():
            metadata_list.append(
                AdapterMetadata(
                    adapter_id=provider_id,
                    adapter_type=AdapterType.LLM,
                    version="",
                    config_hash="",
                    enabled=True
                )
            )

        # Collect tool adapters
        for tool_id in self.tools.keys():
            metadata_list.append(
                AdapterMetadata(
                    adapter_id=tool_id,
                    adapter_type=AdapterType.TOOL,
                    version="",
                    config_hash="",
                    enabled=True
                )
            )

        return metadata_list


def initialize_adapters(
    agents: List[Dict],
    tools: List[Dict],
    credential_provider: Optional['CredentialProvider'] = None,
    registry: Optional[AdapterRegistry] = None,
) -> AdapterRegistry:
    """Initialize adapter registry from agents and tools manifests.

    Phase 20 addition: Accepts credential provider for credential injection.

    Args:
        agents: List of agent definitions
        tools: List of tool definitions
        credential_provider: Optional credential provider for credential injection

    Returns:
        Initialized AdapterRegistry
    """
    registry = registry or AdapterRegistry(credential_provider=credential_provider)

    _register_builtin_llm_factories(registry)
    _register_builtin_memory_store_factories(registry)

    # Register LLM providers from agents
    for agent in agents:
        provider_id = agent['llm']
        config = agent.get('config', {})
        registry.register_llm_provider(provider_id, config)

    # Register tools
    for tool in tools:
        if hasattr(tool, "tool_id"):
            config = {}
            if hasattr(tool, "model_dump"):
                config = tool.model_dump()
            elif hasattr(tool, "dict"):
                config = tool.dict()
            registry.register_tool({"id": tool.tool_id, "config": config})
        else:
            registry.register_tool(tool)

    return registry


def _register_builtin_llm_factories(registry: AdapterRegistry) -> None:
    """Register bundled LLM provider factories."""
    registry.register_llm_factory("anthropic", lambda conf: AnthropicLLMClient(
        api_key=conf.get("api_key") or conf.get("key") or _env("ANTHROPIC_API_KEY"),
        model=conf.get("model") or conf.get("llm_model") or conf.get("name") or "claude-3-5-sonnet-20240620",
        base_url=conf.get("base_url", "https://api.anthropic.com/v1/messages"),
        max_tokens=conf.get("max_tokens", 512),
        timeout=conf.get("timeout", 30),
    ))
    registry.register_llm_factory("openai", lambda conf: OpenAILLMClient(
        api_key=conf.get("api_key") or conf.get("key") or _env("OPENAI_API_KEY"),
        model=conf.get("model") or conf.get("llm_model") or conf.get("name") or "gpt-4o-mini",
        base_url=conf.get("base_url", "https://api.openai.com/v1/chat/completions"),
        organization=conf.get("organization"),
        max_tokens=conf.get("max_tokens", 512),
        timeout=conf.get("timeout", 30),
    ))
    registry.register_llm_factory("ollama", lambda conf: OllamaLLMClient(
        model=conf.get("model") or conf.get("name") or "llama3",
        base_url=conf.get("base_url", "http://localhost:11434"),
        timeout=conf.get("timeout", 30),
        auto_pull=conf.get("auto_pull", True),
        auto_select_llama_size=conf.get("auto_select_llama_size", False),
        llama_size_thresholds_gb=conf.get("llama_size_thresholds_gb"),
        min_llama_size=conf.get("min_llama_size"),
        max_llama_size=conf.get("max_llama_size"),
    ))


def _register_builtin_memory_store_factories(registry: AdapterRegistry) -> None:
    """Register default memory store factory (in-memory/jsonl/sqlite)."""
    registry.register_memory_store_factory(
        "in_memory",
        lambda store_id, conf: MemoryStore(
            store_id,
            store_type="in_memory",
            backend=conf.get("backend", "in_memory"),
            file_path=conf.get("file_path"),
            db_path=conf.get("db_path"),
            max_items=conf.get("max_items"),
        ),
    )
    registry.register_memory_store_factory(
        "jsonl",
        lambda store_id, conf: MemoryStore(
            store_id,
            store_type="jsonl",
            backend="jsonl",
            file_path=conf.get("file_path"),
            db_path=None,
            max_items=conf.get("max_items"),
        ),
    )
    registry.register_memory_store_factory(
        "sqlite",
        lambda store_id, conf: MemoryStore(
            store_id,
            store_type="sqlite",
            backend="sqlite",
            file_path=None,
            db_path=conf.get("db_path"),
            max_items=conf.get("max_items"),
        ),
    )


def _env(name: str) -> Optional[str]:
    import os
    return os.getenv(name)
