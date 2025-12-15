"""Credential provider runtime component.

Phase 20: Secrets & Provider Credential Management

Loads and manages provider credentials from environment variables and files.
Never logs or emits actual secret values in telemetry.
"""

import json
import os
from pathlib import Path
from typing import Dict, Optional, Any
from dataclasses import dataclass

from agent_engine.schemas import (
    ProviderCredentialsManifest, ProviderCredential, AuthConfig, CredentialSource
)


class CredentialNotFoundError(Exception):
    """Raised when a requested credential cannot be found or loaded."""
    pass


class CredentialLoadError(Exception):
    """Raised when credential loading fails."""
    pass


@dataclass
class CredentialMetadata:
    """Metadata about a loaded credential (without the secret value).

    Attributes:
        credential_id: Unique identifier
        provider: Provider name
        source: Where credential was loaded from (env or file)
        loaded: Whether credential was successfully loaded
        error: Error message if loading failed
    """
    credential_id: str
    provider: str
    source: str
    loaded: bool
    error: Optional[str] = None


class CredentialProvider:
    """Runtime provider for loading and managing credentials.

    Supports:
    - Loading credentials from environment variables
    - Loading credentials from plain files (text, JSON, YAML)
    - Extracting nested keys from structured files

    v1 design: No encryption. Rely on OS-level file permissions.
    """

    def __init__(self, manifest: Optional[ProviderCredentialsManifest] = None):
        """Initialize credential provider.

        Args:
            manifest: Parsed credentials manifest (or None for empty)
        """
        self.manifest = manifest or ProviderCredentialsManifest(provider_credentials=[])
        self._credentials: Dict[str, str] = {}  # id -> actual credential value
        self._metadata: Dict[str, CredentialMetadata] = {}  # id -> metadata
        self._errors: Dict[str, str] = {}  # id -> error message

        # Load all credentials from manifest
        for credential in self.manifest.provider_credentials:
            self._load_credential(credential)

    def _load_credential(self, credential: ProviderCredential) -> None:
        """Load a single credential from manifest.

        Args:
            credential: ProviderCredential to load
        """
        credential_id = credential.id
        try:
            value = self._resolve_credential_value(credential.auth)
            self._credentials[credential_id] = value
            self._metadata[credential_id] = CredentialMetadata(
                credential_id=credential_id,
                provider=credential.provider,
                source=credential.auth.source.value,
                loaded=True
            )
        except Exception as e:
            error_msg = str(e)
            self._errors[credential_id] = error_msg
            self._metadata[credential_id] = CredentialMetadata(
                credential_id=credential_id,
                provider=credential.provider,
                source=credential.auth.source.value,
                loaded=False,
                error=error_msg
            )

    def _resolve_credential_value(self, auth: AuthConfig) -> str:
        """Resolve credential value from source.

        Args:
            auth: AuthConfig specifying source and location

        Returns:
            The credential value

        Raises:
            CredentialLoadError: If credential cannot be loaded
        """
        if auth.source == CredentialSource.ENV:
            return self._load_from_env(auth.env_var)
        elif auth.source == CredentialSource.FILE:
            return self._load_from_file(auth.file_path, auth.file_key)
        else:
            raise CredentialLoadError(f"Unknown credential source: {auth.source}")

    def _load_from_env(self, env_var: str) -> str:
        """Load credential from environment variable.

        Args:
            env_var: Environment variable name

        Returns:
            The credential value

        Raises:
            CredentialLoadError: If env var not found or empty
        """
        if not env_var:
            raise CredentialLoadError("env_var name not provided")

        value = os.environ.get(env_var)
        if value is None:
            raise CredentialLoadError(f"Environment variable not found: {env_var}")

        if not value.strip():
            raise CredentialLoadError(f"Environment variable is empty: {env_var}")

        return value

    def _load_from_file(self, file_path: str, file_key: Optional[str] = None) -> str:
        """Load credential from file.

        Supports:
        - Plain text files (returns entire content)
        - JSON files with optional key extraction
        - YAML files with optional key extraction

        Args:
            file_path: Path to file
            file_key: Optional key path for structured files (e.g., "api_key" or "credentials.key")

        Returns:
            The credential value

        Raises:
            CredentialLoadError: If file not found, unreadable, or parsing fails
        """
        if not file_path:
            raise CredentialLoadError("file_path not provided")

        path_obj = Path(file_path)
        if not path_obj.exists():
            raise CredentialLoadError(f"File not found: {file_path}")

        if not path_obj.is_file():
            raise CredentialLoadError(f"Not a file: {file_path}")

        try:
            with open(file_path, 'r') as f:
                content = f.read()
        except Exception as e:
            raise CredentialLoadError(f"Cannot read file {file_path}: {e}")

        if not content.strip():
            raise CredentialLoadError(f"File is empty: {file_path}")

        # If no key specified, return entire content
        if not file_key:
            return content.strip()

        # Try to parse as JSON or YAML
        try:
            data = json.loads(content)
            return self._extract_nested_key(data, file_key)
        except json.JSONDecodeError:
            # Try YAML
            try:
                import yaml
                data = yaml.safe_load(content)
                return self._extract_nested_key(data, file_key)
            except Exception as yaml_err:
                raise CredentialLoadError(
                    f"Cannot parse {file_path} as JSON or YAML: {yaml_err}"
                )

    def _extract_nested_key(self, data: Any, key_path: str) -> str:
        """Extract value from nested dict using dot notation.

        Examples:
        - "api_key" -> data["api_key"]
        - "credentials.key" -> data["credentials"]["key"]

        Args:
            data: Parsed data structure
            key_path: Dot-separated key path

        Returns:
            The extracted value as string

        Raises:
            CredentialLoadError: If key not found or value not string-convertible
        """
        keys = key_path.split(".")
        current = data

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                raise CredentialLoadError(
                    f"Key not found in file: {key_path}"
                )

        if current is None:
            raise CredentialLoadError(f"Key {key_path} has null value")

        return str(current)

    def get_credential(self, credential_id: str) -> str:
        """Get credential value by ID.

        Args:
            credential_id: Unique credential identifier

        Returns:
            The credential value

        Raises:
            CredentialNotFoundError: If credential not found or failed to load
        """
        if credential_id in self._credentials:
            return self._credentials[credential_id]

        if credential_id in self._errors:
            raise CredentialNotFoundError(
                f"Credential '{credential_id}' failed to load: {self._errors[credential_id]}"
            )

        raise CredentialNotFoundError(f"Credential not found: {credential_id}")

    def get_credential_metadata(self, credential_id: str) -> Optional[CredentialMetadata]:
        """Get metadata about a credential (without its value).

        Safe for logging and telemetry - contains no secret values.

        Args:
            credential_id: Unique credential identifier

        Returns:
            CredentialMetadata or None if not found
        """
        return self._metadata.get(credential_id)

    def get_all_metadata(self) -> Dict[str, CredentialMetadata]:
        """Get metadata for all credentials.

        Safe for logging and telemetry - contains no secret values.

        Returns:
            Dict mapping credential_id -> CredentialMetadata
        """
        return dict(self._metadata)

    def has_credential(self, credential_id: str) -> bool:
        """Check if credential exists and was successfully loaded.

        Args:
            credential_id: Unique credential identifier

        Returns:
            True if credential exists and is loaded
        """
        return credential_id in self._credentials

    def list_credential_ids(self) -> list[str]:
        """List all credential IDs in manifest.

        Returns:
            List of credential IDs
        """
        return [cred.id for cred in self.manifest.provider_credentials]

    def list_loaded_credential_ids(self) -> list[str]:
        """List successfully loaded credential IDs.

        Returns:
            List of credential IDs that were successfully loaded
        """
        return list(self._credentials.keys())

    def list_failed_credential_ids(self) -> list[str]:
        """List credential IDs that failed to load.

        Returns:
            List of credential IDs with load errors
        """
        return list(self._errors.keys())
