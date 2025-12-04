def test_import_agent_engine() -> None:
    import agent_engine  # noqa: F401

    assert hasattr(agent_engine, "__version__")
