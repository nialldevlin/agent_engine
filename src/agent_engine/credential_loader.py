"""Credential manifest loader.

Phase 20: Secrets & Provider Credential Management

Loads provider_credentials.yaml manifest and parses credential definitions.
"""

import os
import json
import yaml
from typing import Dict, List, Optional

from .exceptions import ManifestLoadError
from .schemas import (
    AuthType, CredentialSource, AuthConfig, ProviderCredential, ProviderCredentialsManifest
)


def load_credentials_manifest(config_dir: str) -> Optional[Dict]:
    """Load provider_credentials.yaml (optional file).

    Args:
        config_dir: Path to configuration directory

    Returns:
        Parsed YAML dict or None if file doesn't exist

    Raises:
        ManifestLoadError: If file exists but is invalid YAML
    """
    path = os.path.join(config_dir, "provider_credentials.yaml")
    if not os.path.exists(path):
        return None

    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return data
    except yaml.YAMLError as e:
        raise ManifestLoadError("provider_credentials.yaml", f"Invalid YAML: {e}")
    except Exception as e:
        raise ManifestLoadError("provider_credentials.yaml", str(e))


def parse_credentials(data: Optional[Dict]) -> ProviderCredentialsManifest:
    """Parse raw credential manifest data into schema objects.

    Args:
        data: Raw YAML data (or None for empty manifest)

    Returns:
        ProviderCredentialsManifest with parsed credentials

    Raises:
        ValueError: If credential definition is invalid
        ManifestLoadError: If parsing fails
    """
    if data is None:
        return ProviderCredentialsManifest(provider_credentials=[])

    if not isinstance(data, dict):
        raise ManifestLoadError("provider_credentials.yaml", "Root must be a dict")

    credentials_data = data.get("provider_credentials", [])
    if not isinstance(credentials_data, list):
        raise ManifestLoadError("provider_credentials.yaml", "provider_credentials must be a list")

    credentials: List[ProviderCredential] = []

    for i, cred_data in enumerate(credentials_data):
        try:
            # Parse auth config
            auth_data = cred_data.get("auth", {})
            if not auth_data:
                raise ValueError("auth config required")

            auth_type_str = auth_data.get("type")
            if not auth_type_str:
                raise ValueError("auth.type required")

            # v1 only supports api_key
            if auth_type_str != "api_key":
                raise ValueError(f"Unsupported auth type: {auth_type_str} (v1 only supports 'api_key')")

            source_str = auth_data.get("source")
            if not source_str:
                raise ValueError("auth.source required")

            try:
                auth_type = AuthType(auth_type_str)
                source = CredentialSource(source_str)
            except ValueError as e:
                raise ValueError(f"Invalid auth config: {e}")

            # Create AuthConfig
            auth_config = AuthConfig(
                type=auth_type,
                source=source,
                env_var=auth_data.get("env_var"),
                file_path=auth_data.get("file_path"),
                file_key=auth_data.get("file_key")
            )

            # Create ProviderCredential
            credential = ProviderCredential(
                id=cred_data.get("id"),
                provider=cred_data.get("provider"),
                auth=auth_config,
                config=cred_data.get("config", {})
            )

            credentials.append(credential)

        except Exception as e:
            raise ManifestLoadError(
                "provider_credentials.yaml",
                f"Invalid credential at index {i}: {str(e)}"
            )

    return ProviderCredentialsManifest(provider_credentials=credentials)
