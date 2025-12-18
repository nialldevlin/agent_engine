"""Credentials and provider credential management schemas.

Phase 20: Secrets & Provider Credential Management

Defines schemas for storing and loading provider credentials from environment
variables and plain files. No encryption in v1 (use OS-level file permissions).
"""

from __future__ import annotations

from enum import Enum
from typing import Optional, Dict, Any

from pydantic import field_validator

from .base import SchemaBase


class AuthType(str, Enum):
    """Credential authentication type (v1 only supports api_key)."""

    API_KEY = "api_key"  # API key authentication


class CredentialSource(str, Enum):
    """Where to load credential from."""

    ENV = "env"      # Environment variable
    FILE = "file"    # Plain file on disk


class AuthConfig(SchemaBase):
    """Authentication configuration for a credential.

    Attributes:
        type: Type of authentication (currently only "api_key")
        source: Where to load from ("env" or "file")
        env_var: Environment variable name (required if source="env")
        file_path: Path to credential file (required if source="file")
        file_key: Optional JSON/YAML key within file (e.g., "api_key", "credentials.key")
    """

    type: AuthType
    source: CredentialSource
    env_var: Optional[str] = None
    file_path: Optional[str] = None
    file_key: Optional[str] = None

    @field_validator('env_var', 'file_path', mode='after')
    @classmethod
    def validate_source_compatibility(cls, v, info):
        """Validate that source and target are compatible."""
        if info.field_name == 'env_var':
            if info.data.get('source') == CredentialSource.ENV and v is None:
                raise ValueError("env_var required when source='env'")
        elif info.field_name == 'file_path':
            if info.data.get('source') == CredentialSource.FILE and v is None:
                raise ValueError("file_path required when source='file'")
        return v


class ProviderCredential(SchemaBase):
    """Provider credential with authentication config.

    Attributes:
        id: Unique identifier for this credential (e.g., "anthropic_sonnet")
        provider: Provider name (e.g., "anthropic", "openai")
        auth: Authentication configuration
        config: Optional provider-specific configuration
                (e.g., base_url, default_model)
    """

    id: str
    provider: str
    auth: AuthConfig
    config: Dict[str, Any] = {}


class ProviderCredentialsManifest(SchemaBase):
    """Root manifest for provider credentials.

    Attributes:
        provider_credentials: List of provider credential definitions
    """

    provider_credentials: list[ProviderCredential] = []
