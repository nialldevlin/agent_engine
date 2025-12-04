"""
Track user-specified overrides with scope awareness.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
import json


OVERRIDE_SCOPES = {"task", "session", "project", "global"}


@dataclass
class OverrideEntry:
    parameter: str
    value: Any
    scope: str
    source: str
    reason: str
    timestamp: str
    task_id: Optional[str] = None

    def serialize(self) -> Dict[str, Any]:
        return asdict(self)


class OverrideManager:
    """Stores overrides by scope and persists project/global entries."""

    def __init__(self, base_path: Path):
        self.base_path = Path(base_path).expanduser()
        self.project_path = self.base_path / ".arthur" / "project_overrides.json"
        self.global_path = Path.home() / ".king_arthur_overrides.json"
        self.task_overrides: Dict[str, List[OverrideEntry]] = {}
        self.session_overrides: List[OverrideEntry] = []
        self.project_overrides: List[OverrideEntry] = self._load_json(self.project_path)
        self.global_overrides: List[OverrideEntry] = self._load_json(self.global_path)

    def record_override(
        self,
        parameter: str,
        value: Any,
        scope: str,
        source: str,
        reason: str,
        task_id: Optional[str] = None,
    ) -> OverrideEntry:
        entry = OverrideEntry(
            parameter=parameter,
            value=value,
            scope=scope if scope in OVERRIDE_SCOPES else "session",
            source=source,
            reason=reason,
            timestamp=datetime.utcnow().isoformat() + "Z",
            task_id=task_id,
        )

        if entry.scope == "task" and task_id:
            self.task_overrides.setdefault(task_id, []).append(entry)
        elif entry.scope == "session":
            self.session_overrides.append(entry)
        elif entry.scope == "project":
            self.project_overrides.append(entry)
            self._save_json(self.project_path, self.project_overrides)
        elif entry.scope == "global":
            self.global_overrides.append(entry)
            self._save_json(self.global_path, self.global_overrides)
        else:
            self.session_overrides.append(entry)

        return entry

    def get_active_overrides(self) -> Dict[str, List[Dict[str, Any]]]:
        data: Dict[str, List[Dict[str, Any]]] = {
            "task": [],
            "session": [entry.serialize() for entry in self.session_overrides],
            "project": [entry.serialize() for entry in self.project_overrides],
            "global": [entry.serialize() for entry in self.global_overrides],
        }
        for task_entries in self.task_overrides.values():
            data["task"].extend(entry.serialize() for entry in task_entries)
        return data

    def _load_json(self, path: Path) -> List[OverrideEntry]:
        try:
            if path.exists():
                data = json.loads(path.read_text(encoding="utf-8"))
                return [OverrideEntry(**item) for item in data if isinstance(item, dict)]
        except Exception:
            pass
        return []

    def _save_json(self, path: Path, entries: List[OverrideEntry]) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as handle:
            json.dump([entry.serialize() for entry in entries], handle, indent=2)
