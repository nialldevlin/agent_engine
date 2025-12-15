"""
Profile management for Phase 18 CLI Framework.

Handles loading and management of CLI profiles from cli_profiles.yaml.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import yaml
from pathlib import Path

from .exceptions import CliError


@dataclass
class SessionPolicies:
    """Session persistence policies."""

    persist_history: bool = True
    persist_attachments: bool = True
    history_file: Optional[str] = None
    max_history_items: int = 1000

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "SessionPolicies":
        """Create from dictionary, using defaults for missing fields."""
        if data is None:
            return cls()
        return cls(
            persist_history=data.get("persist_history", True),
            persist_attachments=data.get("persist_attachments", True),
            history_file=data.get("history_file"),
            max_history_items=data.get("max_history_items", 1000),
        )


@dataclass
class InputMappingConfig:
    """Input mapping configuration."""

    mode: str = "chat"
    attach_files_as_context: bool = False
    include_profile_id: bool = False
    include_session_id: bool = False

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "InputMappingConfig":
        """Create from dictionary, using defaults for missing fields."""
        if data is None:
            return cls()
        return cls(
            mode=data.get("mode", "chat"),
            attach_files_as_context=data.get("attach_files_as_context", False),
            include_profile_id=data.get("include_profile_id", False),
            include_session_id=data.get("include_session_id", False),
        )


@dataclass
class InputMappings:
    """Input mappings configuration."""

    default: InputMappingConfig = field(default_factory=InputMappingConfig)

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "InputMappings":
        """Create from dictionary, using defaults for missing fields."""
        if data is None:
            return cls()
        default_config = data.get("default", {})
        return cls(
            default=InputMappingConfig.from_dict(default_config),
        )


@dataclass
class PresentationRules:
    """Presentation rules for output formatting."""

    show_system_messages: bool = False
    show_telemetry_inline: bool = True
    truncate_output_lines: Optional[int] = None

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "PresentationRules":
        """Create from dictionary, using defaults for missing fields."""
        if data is None:
            return cls()
        return cls(
            show_system_messages=data.get("show_system_messages", False),
            show_telemetry_inline=data.get("show_telemetry_inline", True),
            truncate_output_lines=data.get("truncate_output_lines"),
        )


@dataclass
class TelemetryOverlays:
    """Telemetry display configuration."""

    enabled: bool = True
    level: str = "summary"  # "summary" or "verbose"

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "TelemetryOverlays":
        """Create from dictionary, using defaults for missing fields."""
        if data is None:
            return cls()
        return cls(
            enabled=data.get("enabled", True),
            level=data.get("level", "summary"),
        )


@dataclass
class CustomCommand:
    """Custom command configuration."""

    name: str
    entrypoint: str
    description: str = ""
    aliases: List[str] = field(default_factory=list)
    help: str = ""

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CustomCommand":
        """Create from dictionary."""
        return cls(
            name=data["name"],
            entrypoint=data["entrypoint"],
            description=data.get("description", ""),
            aliases=data.get("aliases", []),
            help=data.get("help", ""),
        )


@dataclass
class Profile:
    """CLI profile configuration."""

    id: str
    label: Optional[str] = None
    description: Optional[str] = None
    default_config_dir: Optional[str] = None
    default_workflow_id: Optional[str] = None
    session_policies: SessionPolicies = field(default_factory=SessionPolicies)
    input_mappings: InputMappings = field(default_factory=InputMappings)
    custom_commands: List[CustomCommand] = field(default_factory=list)
    presentation_rules: PresentationRules = field(default_factory=PresentationRules)
    telemetry_overlays: TelemetryOverlays = field(default_factory=TelemetryOverlays)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Profile":
        """Create from dictionary, using defaults for missing fields."""
        if "id" not in data:
            raise CliError("Profile missing required field: 'id'")

        custom_cmds = []
        if "custom_commands" in data and data["custom_commands"]:
            custom_cmds = [CustomCommand.from_dict(cmd) for cmd in data["custom_commands"]]

        return cls(
            id=data["id"],
            label=data.get("label"),
            description=data.get("description"),
            default_config_dir=data.get("default_config_dir"),
            default_workflow_id=data.get("default_workflow_id"),
            session_policies=SessionPolicies.from_dict(data.get("session_policies")),
            input_mappings=InputMappings.from_dict(data.get("input_mappings")),
            custom_commands=custom_cmds,
            presentation_rules=PresentationRules.from_dict(data.get("presentation_rules")),
            telemetry_overlays=TelemetryOverlays.from_dict(data.get("telemetry_overlays")),
        )


def load_profiles(config_dir: str) -> List[Profile]:
    """
    Load CLI profiles from cli_profiles.yaml.

    Args:
        config_dir: Directory containing cli_profiles.yaml

    Returns:
        List of Profile objects

    Raises:
        CliError: If YAML is malformed or profiles are invalid
    """
    config_path = Path(config_dir) / "cli_profiles.yaml"

    if not config_path.exists():
        return [get_default_profile()]

    try:
        with open(config_path, "r") as f:
            data = yaml.safe_load(f) or {}
    except yaml.YAMLError as e:
        raise CliError(f"Failed to parse cli_profiles.yaml: {str(e)}")
    except IOError as e:
        raise CliError(f"Failed to read cli_profiles.yaml: {str(e)}")

    profiles_data = data.get("profiles", [])
    if not profiles_data:
        return [get_default_profile()]

    profiles = []
    for profile_data in profiles_data:
        try:
            profile = Profile.from_dict(profile_data)
            profiles.append(profile)
        except CliError as e:
            raise CliError(f"Invalid profile configuration: {str(e)}")

    return profiles if profiles else [get_default_profile()]


def get_default_profile() -> Profile:
    """
    Get the default profile.

    Returns:
        Profile with sensible defaults
    """
    return Profile(
        id="default",
        label="Default Profile",
        description="Default CLI profile",
        session_policies=SessionPolicies(),
        input_mappings=InputMappings(),
        presentation_rules=PresentationRules(),
        telemetry_overlays=TelemetryOverlays(),
    )
