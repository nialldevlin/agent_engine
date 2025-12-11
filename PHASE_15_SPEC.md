# Phase 15: Adapter Management - MINIMAL

Create adapter metadata tracking:

1. **schemas/adapter.py**: AdapterType enum, AdapterMetadata dataclass
2. **Enhance schemas/metadata.py**: Add adapter_metadata: List[AdapterMetadata] field to EngineMetadata
3. **Enhance adapters.py**: Add get_adapter_metadata() returning stub list
4. **Enhance metadata_collector.py**: collect_adapter_metadata() and enhance collect_adapter_versions()
5. **Tests**: 10+ tests covering schema, collection, integration

Minimal: Just metadata tracking, no dynamic loading/health checks.
Files: adapter.py, modify metadata.py/adapters.py/metadata_collector.py, test file.
