from typing import Dict, List, Optional


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
