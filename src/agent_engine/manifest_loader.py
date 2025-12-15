import yaml
from pathlib import Path
from typing import Dict, List, Optional
from .exceptions import ManifestLoadError


def load_workflow_manifest(config_dir: str) -> Dict:
    """Load workflow.yaml (required)."""
    path = Path(config_dir) / "workflow.yaml"
    if not path.exists():
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
    path = Path(config_dir) / "agents.yaml"
    if not path.exists():
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
    path = Path(config_dir) / "tools.yaml"
    if not path.exists():
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
    path = Path(config_dir) / "memory.yaml"
    if not path.exists():
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
    path = Path(config_dir) / "plugins.yaml"
    if not path.exists():
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
    schemas_dir = Path(config_dir) / "schemas"
    schemas = {}

    if not schemas_dir.exists():
        return schemas

    if not schemas_dir.is_dir():
        return schemas

    for filename in schemas_dir.iterdir():
        if filename.suffix == '.json':
            schema_id = filename.stem  # Get filename without extension
            path = filename
            try:
                with open(path, 'r') as f:
                    schemas[schema_id] = json.load(f)
            except json.JSONDecodeError as e:
                raise ManifestLoadError(f"schemas/{filename}", f"Invalid JSON: {e}")
            except Exception as e:
                raise ManifestLoadError(f"schemas/{filename}", str(e))

    return schemas
