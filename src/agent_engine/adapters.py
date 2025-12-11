from typing import Dict, List, Optional
from agent_engine.schemas import AdapterMetadata, AdapterType


class AdapterRegistry:
    """Registry for tools and LLM providers (stub for Phase 2)."""

    def __init__(self):
        self.tools: Dict[str, Dict] = {}
        self.llm_providers: Dict[str, Dict] = {}

    def register_tool(self, tool_config: Dict) -> None:
        """Register a tool by its ID."""
        tool_id = tool_config['id']
        self.tools[tool_id] = tool_config

    def register_llm_provider(self, provider_id: str, config: Dict) -> None:
        """Register an LLM provider by its ID."""
        self.llm_providers[provider_id] = config

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


def initialize_adapters(agents: List[Dict], tools: List[Dict]) -> AdapterRegistry:
    """Initialize adapter registry from agents and tools manifests."""
    registry = AdapterRegistry()

    # Register LLM providers from agents
    for agent in agents:
        provider_id = agent['llm']
        config = agent.get('config', {})
        registry.register_llm_provider(provider_id, config)

    # Register tools
    for tool in tools:
        registry.register_tool(tool)

    return registry
