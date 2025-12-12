"""Phase 20: Secrets & Provider Credential Management tests.

Comprehensive test suite for credential loading, management, and engine integration.
Tests cover environment variables, file loading, credential provider API, telemetry,
and security (no secrets in logs/telemetry).
"""

import pytest
import tempfile
import json
import os
from pathlib import Path

from agent_engine.schemas import (
    AuthType, CredentialSource, AuthConfig, ProviderCredential, ProviderCredentialsManifest
)
from agent_engine.credential_loader import load_credentials_manifest, parse_credentials
from agent_engine.runtime.credential_provider import (
    CredentialProvider, CredentialNotFoundError, CredentialLoadError, CredentialMetadata
)
from agent_engine.adapters import AdapterRegistry, initialize_adapters
from agent_engine.exceptions import ManifestLoadError


# ============================================================================
# SCHEMA TESTS (5 tests)
# ============================================================================
class TestCredentialSchemas:
    """Test credential schema definitions."""

    def test_auth_type_enum(self):
        """Test AuthType enum has correct values."""
        assert AuthType.API_KEY.value == "api_key"
        assert len(AuthType) == 1

    def test_credential_source_enum(self):
        """Test CredentialSource enum has correct values."""
        assert CredentialSource.ENV.value == "env"
        assert CredentialSource.FILE.value == "file"
        assert len(CredentialSource) == 2

    def test_auth_config_env_source(self):
        """Test AuthConfig with env source."""
        auth = AuthConfig(
            type=AuthType.API_KEY,
            source=CredentialSource.ENV,
            env_var="MY_API_KEY"
        )
        assert auth.type == AuthType.API_KEY
        assert auth.source == CredentialSource.ENV
        assert auth.env_var == "MY_API_KEY"
        assert auth.file_path is None

    def test_auth_config_file_source(self):
        """Test AuthConfig with file source."""
        auth = AuthConfig(
            type=AuthType.API_KEY,
            source=CredentialSource.FILE,
            file_path="/path/to/key.txt"
        )
        assert auth.source == CredentialSource.FILE
        assert auth.file_path == "/path/to/key.txt"
        assert auth.env_var is None

    def test_auth_config_validation_env_missing_var(self):
        """Test AuthConfig validation fails when env source missing env_var."""
        with pytest.raises(ValueError, match="env_var required"):
            AuthConfig(
                type=AuthType.API_KEY,
                source=CredentialSource.ENV,
                env_var=None
            )

    def test_auth_config_validation_file_missing_path(self):
        """Test AuthConfig validation fails when file source missing file_path."""
        with pytest.raises(ValueError, match="file_path required"):
            AuthConfig(
                type=AuthType.API_KEY,
                source=CredentialSource.FILE,
                file_path=None
            )

    def test_provider_credential_creation(self):
        """Test ProviderCredential creation."""
        auth = AuthConfig(
            type=AuthType.API_KEY,
            source=CredentialSource.ENV,
            env_var="ANTHROPIC_API_KEY"
        )
        cred = ProviderCredential(
            id="anthropic_sonnet",
            provider="anthropic",
            auth=auth,
            config={"base_url": "https://api.anthropic.com", "default_model": "claude-sonnet-4"}
        )
        assert cred.id == "anthropic_sonnet"
        assert cred.provider == "anthropic"
        assert cred.auth == auth
        assert cred.config["base_url"] == "https://api.anthropic.com"

    def test_provider_credentials_manifest_creation(self):
        """Test ProviderCredentialsManifest creation."""
        auth1 = AuthConfig(type=AuthType.API_KEY, source=CredentialSource.ENV, env_var="KEY1")
        cred1 = ProviderCredential(id="id1", provider="provider1", auth=auth1)

        auth2 = AuthConfig(type=AuthType.API_KEY, source=CredentialSource.FILE, file_path="/path/key2")
        cred2 = ProviderCredential(id="id2", provider="provider2", auth=auth2)

        manifest = ProviderCredentialsManifest(provider_credentials=[cred1, cred2])
        assert len(manifest.provider_credentials) == 2
        assert manifest.provider_credentials[0].id == "id1"
        assert manifest.provider_credentials[1].id == "id2"


# ============================================================================
# LOADER TESTS (4 tests)
# ============================================================================
class TestCredentialLoader:
    """Test credential manifest loading."""

    def test_load_credentials_manifest_missing_file(self):
        """Test load_credentials_manifest returns None when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            result = load_credentials_manifest(tmpdir)
            assert result is None

    def test_load_credentials_manifest_valid_yaml(self):
        """Test load_credentials_manifest with valid YAML file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "provider_credentials.yaml"
            manifest_file.write_text("""
provider_credentials:
  - id: test_cred
    provider: test_provider
    auth:
      type: api_key
      source: env
      env_var: TEST_KEY
""")
            result = load_credentials_manifest(tmpdir)
            assert result is not None
            assert "provider_credentials" in result
            assert len(result["provider_credentials"]) == 1

    def test_load_credentials_manifest_invalid_yaml(self):
        """Test load_credentials_manifest raises error on invalid YAML."""
        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_file = Path(tmpdir) / "provider_credentials.yaml"
            manifest_file.write_text("invalid: yaml: content: [")

            with pytest.raises(ManifestLoadError):
                load_credentials_manifest(tmpdir)

    def test_parse_credentials_none(self):
        """Test parse_credentials with None returns empty manifest."""
        result = parse_credentials(None)
        assert isinstance(result, ProviderCredentialsManifest)
        assert len(result.provider_credentials) == 0

    def test_parse_credentials_empty(self):
        """Test parse_credentials with empty list."""
        result = parse_credentials({"provider_credentials": []})
        assert isinstance(result, ProviderCredentialsManifest)
        assert len(result.provider_credentials) == 0

    def test_parse_credentials_single_env(self):
        """Test parse_credentials with single env-based credential."""
        data = {
            "provider_credentials": [
                {
                    "id": "anthropic_sonnet",
                    "provider": "anthropic",
                    "auth": {
                        "type": "api_key",
                        "source": "env",
                        "env_var": "ANTHROPIC_API_KEY"
                    },
                    "config": {"default_model": "claude-sonnet-4"}
                }
            ]
        }
        result = parse_credentials(data)
        assert len(result.provider_credentials) == 1
        cred = result.provider_credentials[0]
        assert cred.id == "anthropic_sonnet"
        assert cred.auth.source == CredentialSource.ENV
        assert cred.auth.env_var == "ANTHROPIC_API_KEY"

    def test_parse_credentials_single_file(self):
        """Test parse_credentials with single file-based credential."""
        data = {
            "provider_credentials": [
                {
                    "id": "openai_gpt4",
                    "provider": "openai",
                    "auth": {
                        "type": "api_key",
                        "source": "file",
                        "file_path": "/etc/secrets/openai.txt"
                    }
                }
            ]
        }
        result = parse_credentials(data)
        cred = result.provider_credentials[0]
        assert cred.auth.source == CredentialSource.FILE
        assert cred.auth.file_path == "/etc/secrets/openai.txt"

    def test_parse_credentials_with_file_key(self):
        """Test parse_credentials with file_key for nested extraction."""
        data = {
            "provider_credentials": [
                {
                    "id": "test_cred",
                    "provider": "test",
                    "auth": {
                        "type": "api_key",
                        "source": "file",
                        "file_path": "/path/secrets.json",
                        "file_key": "credentials.api_key"
                    }
                }
            ]
        }
        result = parse_credentials(data)
        cred = result.provider_credentials[0]
        assert cred.auth.file_key == "credentials.api_key"

    def test_parse_credentials_multiple(self):
        """Test parse_credentials with multiple credentials."""
        data = {
            "provider_credentials": [
                {
                    "id": "cred1",
                    "provider": "provider1",
                    "auth": {"type": "api_key", "source": "env", "env_var": "KEY1"}
                },
                {
                    "id": "cred2",
                    "provider": "provider2",
                    "auth": {"type": "api_key", "source": "env", "env_var": "KEY2"}
                },
                {
                    "id": "cred3",
                    "provider": "provider3",
                    "auth": {"type": "api_key", "source": "file", "file_path": "/path"}
                }
            ]
        }
        result = parse_credentials(data)
        assert len(result.provider_credentials) == 3

    def test_parse_credentials_invalid_auth_type(self):
        """Test parse_credentials rejects unsupported auth type."""
        data = {
            "provider_credentials": [
                {
                    "id": "bad_cred",
                    "provider": "test",
                    "auth": {
                        "type": "oauth2",  # Not supported in v1
                        "source": "env",
                        "env_var": "KEY"
                    }
                }
            ]
        }
        with pytest.raises(ManifestLoadError):
            parse_credentials(data)

    def test_parse_credentials_missing_auth(self):
        """Test parse_credentials requires auth config."""
        data = {
            "provider_credentials": [
                {
                    "id": "bad_cred",
                    "provider": "test"
                }
            ]
        }
        with pytest.raises(ManifestLoadError):
            parse_credentials(data)

    def test_parse_credentials_missing_source(self):
        """Test parse_credentials requires auth.source."""
        data = {
            "provider_credentials": [
                {
                    "id": "bad_cred",
                    "provider": "test",
                    "auth": {"type": "api_key"}
                }
            ]
        }
        with pytest.raises(ManifestLoadError):
            parse_credentials(data)


# ============================================================================
# CREDENTIAL PROVIDER API TESTS (10 tests)
# ============================================================================
class TestCredentialProvider:
    """Test CredentialProvider runtime component."""

    def test_credential_provider_init_empty(self):
        """Test CredentialProvider with empty manifest."""
        provider = CredentialProvider(None)
        assert provider.list_credential_ids() == []
        assert provider.list_loaded_credential_ids() == []

    def test_credential_provider_env_loading(self):
        """Test loading credential from environment variable."""
        os.environ["TEST_API_KEY"] = "secret-key-123"
        try:
            manifest = ProviderCredentialsManifest(
                provider_credentials=[
                    ProviderCredential(
                        id="test_cred",
                        provider="test",
                        auth=AuthConfig(
                            type=AuthType.API_KEY,
                            source=CredentialSource.ENV,
                            env_var="TEST_API_KEY"
                        )
                    )
                ]
            )
            provider = CredentialProvider(manifest)

            assert provider.has_credential("test_cred")
            assert provider.get_credential("test_cred") == "secret-key-123"
            assert len(provider.list_loaded_credential_ids()) == 1
        finally:
            del os.environ["TEST_API_KEY"]

    def test_credential_provider_env_missing(self):
        """Test loading fails when env var not found."""
        manifest = ProviderCredentialsManifest(
            provider_credentials=[
                ProviderCredential(
                    id="missing_cred",
                    provider="test",
                    auth=AuthConfig(
                        type=AuthType.API_KEY,
                        source=CredentialSource.ENV,
                        env_var="NONEXISTENT_VAR"
                    )
                )
            ]
        )
        provider = CredentialProvider(manifest)

        assert not provider.has_credential("missing_cred")
        assert "missing_cred" in provider.list_failed_credential_ids()

        with pytest.raises(CredentialNotFoundError):
            provider.get_credential("missing_cred")

    def test_credential_provider_env_empty(self):
        """Test loading fails when env var is empty."""
        os.environ["EMPTY_KEY"] = ""
        try:
            manifest = ProviderCredentialsManifest(
                provider_credentials=[
                    ProviderCredential(
                        id="empty_cred",
                        provider="test",
                        auth=AuthConfig(
                            type=AuthType.API_KEY,
                            source=CredentialSource.ENV,
                            env_var="EMPTY_KEY"
                        )
                    )
                ]
            )
            provider = CredentialProvider(manifest)

            assert not provider.has_credential("empty_cred")
            with pytest.raises(CredentialNotFoundError):
                provider.get_credential("empty_cred")
        finally:
            del os.environ["EMPTY_KEY"]

    def test_credential_provider_file_plain_text(self):
        """Test loading credential from plain text file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("my-secret-key")
            f.flush()

            try:
                manifest = ProviderCredentialsManifest(
                    provider_credentials=[
                        ProviderCredential(
                            id="file_cred",
                            provider="test",
                            auth=AuthConfig(
                                type=AuthType.API_KEY,
                                source=CredentialSource.FILE,
                                file_path=f.name
                            )
                        )
                    ]
                )
                provider = CredentialProvider(manifest)

                assert provider.has_credential("file_cred")
                assert provider.get_credential("file_cred") == "my-secret-key"
            finally:
                os.unlink(f.name)

    def test_credential_provider_file_missing(self):
        """Test loading fails when file doesn't exist."""
        manifest = ProviderCredentialsManifest(
            provider_credentials=[
                ProviderCredential(
                    id="missing_file",
                    provider="test",
                    auth=AuthConfig(
                        type=AuthType.API_KEY,
                        source=CredentialSource.FILE,
                        file_path="/nonexistent/path/key.txt"
                    )
                )
            ]
        )
        provider = CredentialProvider(manifest)

        assert not provider.has_credential("missing_file")
        with pytest.raises(CredentialNotFoundError):
            provider.get_credential("missing_file")

    def test_credential_provider_file_json_no_key(self):
        """Test loading entire JSON file without key extraction."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump({"api_key": "secret"}, f)
            f.flush()

            try:
                manifest = ProviderCredentialsManifest(
                    provider_credentials=[
                        ProviderCredential(
                            id="json_cred",
                            provider="test",
                            auth=AuthConfig(
                                type=AuthType.API_KEY,
                                source=CredentialSource.FILE,
                                file_path=f.name
                            )
                        )
                    ]
                )
                provider = CredentialProvider(manifest)

                # Should return the entire JSON as string
                value = provider.get_credential("json_cred")
                assert "api_key" in value
            finally:
                os.unlink(f.name)

    def test_credential_provider_file_json_with_key(self):
        """Test extracting value from JSON file with key."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump({"api_key": "secret-123", "other": "data"}, f)
            f.flush()

            try:
                manifest = ProviderCredentialsManifest(
                    provider_credentials=[
                        ProviderCredential(
                            id="json_keyed",
                            provider="test",
                            auth=AuthConfig(
                                type=AuthType.API_KEY,
                                source=CredentialSource.FILE,
                                file_path=f.name,
                                file_key="api_key"
                            )
                        )
                    ]
                )
                provider = CredentialProvider(manifest)

                assert provider.get_credential("json_keyed") == "secret-123"
            finally:
                os.unlink(f.name)

    def test_credential_provider_file_json_nested_key(self):
        """Test extracting nested value from JSON file."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump({
                "credentials": {
                    "api": {
                        "key": "nested-secret"
                    }
                }
            }, f)
            f.flush()

            try:
                manifest = ProviderCredentialsManifest(
                    provider_credentials=[
                        ProviderCredential(
                            id="nested",
                            provider="test",
                            auth=AuthConfig(
                                type=AuthType.API_KEY,
                                source=CredentialSource.FILE,
                                file_path=f.name,
                                file_key="credentials.api.key"
                            )
                        )
                    ]
                )
                provider = CredentialProvider(manifest)

                assert provider.get_credential("nested") == "nested-secret"
            finally:
                os.unlink(f.name)

    def test_credential_provider_file_json_key_not_found(self):
        """Test extracting nonexistent key from JSON fails."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.json') as f:
            json.dump({"other": "data"}, f)
            f.flush()

            try:
                manifest = ProviderCredentialsManifest(
                    provider_credentials=[
                        ProviderCredential(
                            id="bad_key",
                            provider="test",
                            auth=AuthConfig(
                                type=AuthType.API_KEY,
                                source=CredentialSource.FILE,
                                file_path=f.name,
                                file_key="nonexistent"
                            )
                        )
                    ]
                )
                provider = CredentialProvider(manifest)

                assert not provider.has_credential("bad_key")
                with pytest.raises(CredentialNotFoundError):
                    provider.get_credential("bad_key")
            finally:
                os.unlink(f.name)

    def test_credential_provider_metadata_no_secrets(self):
        """Test credential metadata doesn't expose secret values."""
        os.environ["SECRET_KEY"] = "super-secret"
        try:
            manifest = ProviderCredentialsManifest(
                provider_credentials=[
                    ProviderCredential(
                        id="test_cred",
                        provider="test_provider",
                        auth=AuthConfig(
                            type=AuthType.API_KEY,
                            source=CredentialSource.ENV,
                            env_var="SECRET_KEY"
                        )
                    )
                ]
            )
            provider = CredentialProvider(manifest)

            metadata = provider.get_credential_metadata("test_cred")
            assert metadata is not None
            assert metadata.credential_id == "test_cred"
            assert metadata.provider == "test_provider"
            assert metadata.source == "env"
            assert metadata.loaded is True
            assert metadata.error is None
            # Most importantly: no secret in metadata
            assert "super-secret" not in str(metadata)
        finally:
            del os.environ["SECRET_KEY"]

    def test_credential_provider_list_methods(self):
        """Test credential provider list methods."""
        os.environ["GOOD_KEY"] = "value"
        try:
            manifest = ProviderCredentialsManifest(
                provider_credentials=[
                    ProviderCredential(
                        id="good",
                        provider="p1",
                        auth=AuthConfig(type=AuthType.API_KEY, source=CredentialSource.ENV, env_var="GOOD_KEY")
                    ),
                    ProviderCredential(
                        id="bad",
                        provider="p2",
                        auth=AuthConfig(type=AuthType.API_KEY, source=CredentialSource.ENV, env_var="MISSING_KEY")
                    )
                ]
            )
            provider = CredentialProvider(manifest)

            assert set(provider.list_credential_ids()) == {"good", "bad"}
            assert provider.list_loaded_credential_ids() == ["good"]
            assert provider.list_failed_credential_ids() == ["bad"]
        finally:
            del os.environ["GOOD_KEY"]

    def test_credential_provider_get_all_metadata(self):
        """Test getting all credential metadata."""
        os.environ["KEY1"] = "val1"
        try:
            manifest = ProviderCredentialsManifest(
                provider_credentials=[
                    ProviderCredential(
                        id="cred1",
                        provider="p1",
                        auth=AuthConfig(type=AuthType.API_KEY, source=CredentialSource.ENV, env_var="KEY1")
                    ),
                    ProviderCredential(
                        id="cred2",
                        provider="p2",
                        auth=AuthConfig(type=AuthType.API_KEY, source=CredentialSource.ENV, env_var="MISSING")
                    )
                ]
            )
            provider = CredentialProvider(manifest)

            all_metadata = provider.get_all_metadata()
            assert len(all_metadata) == 2
            assert all_metadata["cred1"].loaded is True
            assert all_metadata["cred2"].loaded is False
        finally:
            del os.environ["KEY1"]


# ============================================================================
# ADAPTER INTEGRATION TESTS (3 tests)
# ============================================================================
class TestAdapterIntegration:
    """Test credential injection into adapter registry."""

    def test_adapter_registry_with_credential_provider(self):
        """Test AdapterRegistry accepts credential provider."""
        os.environ["TEST_KEY"] = "test-value"
        try:
            manifest = ProviderCredentialsManifest(
                provider_credentials=[
                    ProviderCredential(
                        id="test",
                        provider="test",
                        auth=AuthConfig(
                            type=AuthType.API_KEY,
                            source=CredentialSource.ENV,
                            env_var="TEST_KEY"
                        )
                    )
                ]
            )
            credential_provider = CredentialProvider(manifest)

            registry = AdapterRegistry(credential_provider=credential_provider)
            assert registry.credential_provider is not None
            assert registry.credential_provider.has_credential("test")
        finally:
            del os.environ["TEST_KEY"]

    def test_initialize_adapters_with_credentials(self):
        """Test initialize_adapters function passes credential provider."""
        os.environ["KEY"] = "value"
        try:
            manifest = ProviderCredentialsManifest(
                provider_credentials=[
                    ProviderCredential(
                        id="cred1",
                        provider="test",
                        auth=AuthConfig(type=AuthType.API_KEY, source=CredentialSource.ENV, env_var="KEY")
                    )
                ]
            )
            credential_provider = CredentialProvider(manifest)

            agents = [{"id": "a1", "llm": "llm1"}]
            tools = [{"id": "t1"}]

            registry = initialize_adapters(agents, tools, credential_provider)
            assert registry.credential_provider is credential_provider
        finally:
            del os.environ["KEY"]

    def test_adapter_registry_none_credential_provider(self):
        """Test AdapterRegistry works with None credential provider."""
        registry = AdapterRegistry(credential_provider=None)
        assert registry.credential_provider is None

        agents = [{"id": "a1", "llm": "llm1"}]
        tools = []
        registry = initialize_adapters(agents, tools, None)
        assert registry.credential_provider is None


# ============================================================================
# TELEMETRY TESTS (2 tests)
# ============================================================================
class TestCredentialTelemetry:
    """Test that credentials don't leak into telemetry."""

    def test_credential_metadata_safe_for_telemetry(self):
        """Test credential metadata is safe to emit in telemetry."""
        os.environ["SECRET"] = "very-secret-value"
        try:
            manifest = ProviderCredentialsManifest(
                provider_credentials=[
                    ProviderCredential(
                        id="cred1",
                        provider="anthropic",
                        auth=AuthConfig(type=AuthType.API_KEY, source=CredentialSource.ENV, env_var="SECRET")
                    )
                ]
            )
            provider = CredentialProvider(manifest)

            # Get metadata which would be safe to emit
            metadata = provider.get_credential_metadata("cred1")
            metadata_dict = {
                "id": metadata.credential_id,
                "provider": metadata.provider,
                "source": metadata.source,
                "loaded": metadata.loaded
            }

            # Should be JSON serializable and contain no secrets
            import json
            json_str = json.dumps(metadata_dict)
            assert "very-secret-value" not in json_str
            assert "SECRET" not in json_str
            assert "anthropic" in json_str
        finally:
            del os.environ["SECRET"]

    def test_all_metadata_safe_for_telemetry(self):
        """Test all credentials metadata is safe for telemetry."""
        os.environ["K1"] = "secret1"
        os.environ["K2"] = "secret2"
        try:
            manifest = ProviderCredentialsManifest(
                provider_credentials=[
                    ProviderCredential(
                        id="c1",
                        provider="p1",
                        auth=AuthConfig(type=AuthType.API_KEY, source=CredentialSource.ENV, env_var="K1")
                    ),
                    ProviderCredential(
                        id="c2",
                        provider="p2",
                        auth=AuthConfig(type=AuthType.API_KEY, source=CredentialSource.ENV, env_var="K2")
                    )
                ]
            )
            provider = CredentialProvider(manifest)

            all_meta = provider.get_all_metadata()
            meta_dict = {
                cid: {"provider": m.provider, "source": m.source, "loaded": m.loaded}
                for cid, m in all_meta.items()
            }

            import json
            json_str = json.dumps(meta_dict)
            assert "secret1" not in json_str
            assert "secret2" not in json_str
        finally:
            del os.environ["K1"]
            del os.environ["K2"]


# ============================================================================
# ERROR HANDLING TESTS (3 tests)
# ============================================================================
class TestErrorHandling:
    """Test error handling in credential loading."""

    def test_load_error_message_access(self):
        """Test accessing error messages for failed credentials."""
        manifest = ProviderCredentialsManifest(
            provider_credentials=[
                ProviderCredential(
                    id="missing",
                    provider="test",
                    auth=AuthConfig(type=AuthType.API_KEY, source=CredentialSource.ENV, env_var="NONEXISTENT")
                )
            ]
        )
        provider = CredentialProvider(manifest)

        with pytest.raises(CredentialNotFoundError) as exc_info:
            provider.get_credential("missing")

        assert "missing" in str(exc_info.value)

    def test_partial_load_some_succeed_some_fail(self):
        """Test provider handles mix of successful and failed loads."""
        os.environ["GOOD"] = "good-value"
        try:
            manifest = ProviderCredentialsManifest(
                provider_credentials=[
                    ProviderCredential(
                        id="good_cred",
                        provider="p1",
                        auth=AuthConfig(type=AuthType.API_KEY, source=CredentialSource.ENV, env_var="GOOD")
                    ),
                    ProviderCredential(
                        id="bad_cred",
                        provider="p2",
                        auth=AuthConfig(type=AuthType.API_KEY, source=CredentialSource.ENV, env_var="BAD")
                    ),
                    ProviderCredential(
                        id="also_good",
                        provider="p3",
                        auth=AuthConfig(type=AuthType.API_KEY, source=CredentialSource.ENV, env_var="GOOD")
                    )
                ]
            )
            provider = CredentialProvider(manifest)

            # Two should load, one should fail
            assert len(provider.list_loaded_credential_ids()) == 2
            assert len(provider.list_failed_credential_ids()) == 1
            assert "bad_cred" in provider.list_failed_credential_ids()
        finally:
            del os.environ["GOOD"]

    def test_yaml_file_with_key_extraction(self):
        """Test YAML file parsing with key extraction."""
        import yaml
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.yaml') as f:
            yaml.dump({
                "services": {
                    "anthropic": {
                        "api_key": "yaml-secret-123"
                    }
                }
            }, f)
            f.flush()

            try:
                manifest = ProviderCredentialsManifest(
                    provider_credentials=[
                        ProviderCredential(
                            id="yaml_cred",
                            provider="test",
                            auth=AuthConfig(
                                type=AuthType.API_KEY,
                                source=CredentialSource.FILE,
                                file_path=f.name,
                                file_key="services.anthropic.api_key"
                            )
                        )
                    ]
                )
                provider = CredentialProvider(manifest)

                assert provider.get_credential("yaml_cred") == "yaml-secret-123"
            finally:
                os.unlink(f.name)


# ============================================================================
# EDGE CASE TESTS (2 tests)
# ============================================================================
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_credential_with_whitespace_in_file(self):
        """Test credential file with leading/trailing whitespace."""
        with tempfile.NamedTemporaryFile(mode='w', delete=False, suffix='.txt') as f:
            f.write("  \n  secret-key-with-spaces  \n  ")
            f.flush()

            try:
                manifest = ProviderCredentialsManifest(
                    provider_credentials=[
                        ProviderCredential(
                            id="spaces",
                            provider="test",
                            auth=AuthConfig(
                                type=AuthType.API_KEY,
                                source=CredentialSource.FILE,
                                file_path=f.name
                            )
                        )
                    ]
                )
                provider = CredentialProvider(manifest)

                # Should be stripped
                assert provider.get_credential("spaces") == "secret-key-with-spaces"
            finally:
                os.unlink(f.name)

    def test_credential_with_special_characters(self):
        """Test credential values with special characters."""
        special_value = "key+=!@#$%^&*()[]{}|\\:;\"'<>,.?/"
        os.environ["SPECIAL_KEY"] = special_value
        try:
            manifest = ProviderCredentialsManifest(
                provider_credentials=[
                    ProviderCredential(
                        id="special",
                        provider="test",
                        auth=AuthConfig(type=AuthType.API_KEY, source=CredentialSource.ENV, env_var="SPECIAL_KEY")
                    )
                ]
            )
            provider = CredentialProvider(manifest)

            assert provider.get_credential("special") == special_value
        finally:
            del os.environ["SPECIAL_KEY"]
