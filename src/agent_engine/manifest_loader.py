import os
import yaml
from typing import Dict, List, Optional
from .exceptions import ManifestLoadError


def load_workflow_manifest(config_dir: str) -> Dict:
    """Load workflow.yaml (required)."""
    path = os.path.join(config_dir, "workflow.yaml")
    if not os.path.exists(path):
        raise ManifestLoadError("workflow.yaml", "File not found")
    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        if data is None:
            raise ManifestLoadError("workflow.yaml", "Empty file")
        return data
    except yaml.YAMLError as e:
        raise ManifestLoadError("workflow.yaml", f"Invalid YAML: {e}")
    except Exception as e:
        raise ManifestLoadError("workflow.yaml", str(e))


def load_agents_manifest(config_dir: str) -> Dict:
    """Load agents.yaml (required)."""
    path = os.path.join(config_dir, "agents.yaml")
    if not os.path.exists(path):
        raise ManifestLoadError("agents.yaml", "File not found")
    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        if data is None:
            raise ManifestLoadError("agents.yaml", "Empty file")
        return data
    except yaml.YAMLError as e:
        raise ManifestLoadError("agents.yaml", f"Invalid YAML: {e}")
    except Exception as e:
        raise ManifestLoadError("agents.yaml", str(e))


def load_tools_manifest(config_dir: str) -> Dict:
    """Load tools.yaml (required)."""
    path = os.path.join(config_dir, "tools.yaml")
    if not os.path.exists(path):
        raise ManifestLoadError("tools.yaml", "File not found")
    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        if data is None:
            raise ManifestLoadError("tools.yaml", "Empty file")
        return data
    except yaml.YAMLError as e:
        raise ManifestLoadError("tools.yaml", f"Invalid YAML: {e}")
    except Exception as e:
        raise ManifestLoadError("tools.yaml", str(e))


def load_memory_manifest(config_dir: str) -> Optional[Dict]:
    """Load memory.yaml (optional)."""
    path = os.path.join(config_dir, "memory.yaml")
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return data
    except yaml.YAMLError as e:
        raise ManifestLoadError("memory.yaml", f"Invalid YAML: {e}")
    except Exception as e:
        raise ManifestLoadError("memory.yaml", str(e))


def load_plugins_manifest(config_dir: str) -> Optional[Dict]:
    """Load plugins.yaml (optional)."""
    path = os.path.join(config_dir, "plugins.yaml")
    if not os.path.exists(path):
        return None
    try:
        with open(path, 'r') as f:
            data = yaml.safe_load(f)
        return data
    except yaml.YAMLError as e:
        raise ManifestLoadError("plugins.yaml", f"Invalid YAML: {e}")
    except Exception as e:
        raise ManifestLoadError("plugins.yaml", str(e))


def load_schemas(config_dir: str) -> Dict[str, Dict]:
    """Load all JSON schemas from schemas/ directory."""
    import json
    schemas_dir = os.path.join(config_dir, "schemas")
    schemas = {}

    if not os.path.exists(schemas_dir):
        return schemas

    if not os.path.isdir(schemas_dir):
        return schemas

    for filename in os.listdir(schemas_dir):
        if filename.endswith('.json'):
            schema_id = filename[:-5]  # Remove .json extension
            path = os.path.join(schemas_dir, filename)
            try:
                with open(path, 'r') as f:
                    schemas[schema_id] = json.load(f)
            except json.JSONDecodeError as e:
                raise ManifestLoadError(f"schemas/{filename}", f"Invalid JSON: {e}")
            except Exception as e:
                raise ManifestLoadError(f"schemas/{filename}", str(e))

    return schemas
