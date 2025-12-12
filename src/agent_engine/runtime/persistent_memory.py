"""Persistent memory backends for Phase 19 Artifact Storage Subsystem.

Provides file-backed (JSONL) and database-backed (SQLite) storage for
memory items and artifacts with automatic persistence and retention policies.
"""

from __future__ import annotations

import json
import sqlite3
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Protocol
from datetime import datetime
from zoneinfo import ZoneInfo
import threading

from agent_engine.schemas.memory import ContextItem


class PersistentBackend(Protocol):
    """Abstract interface for persistent storage backends."""

    def add(self, item: ContextItem) -> None:
        """Add a context item and persist to storage.

        Args:
            item: ContextItem to store and persist

        Raises:
            IOError: If persistence fails
        """
        ...

    def query(
        self,
        filters: Dict[str, Any],
        limit: int = 100,
        order_by: str = "timestamp"
    ) -> List[ContextItem]:
        """Query items matching filters.

        Args:
            filters: Dict of field->value filters
            limit: Maximum items to return
            order_by: Field to sort by

        Returns:
            List of matching ContextItems
        """
        ...

    def get(self, item_id: str) -> Optional[ContextItem]:
        """Get item by ID.

        Args:
            item_id: Context item ID

        Returns:
            ContextItem if found, None otherwise
        """
        ...

    def delete(self, item_id: str) -> bool:
        """Delete item by ID.

        Args:
            item_id: Context item ID

        Returns:
            True if deleted, False if not found
        """
        ...

    def list_all(self) -> List[ContextItem]:
        """List all items in store.

        Returns:
            All ContextItems
        """
        ...

    def clear(self) -> None:
        """Clear all items from store."""
        ...

    def count(self) -> int:
        """Count items in store.

        Returns:
            Number of items
        """
        ...

    def enforce_retention(self, max_items: Optional[int]) -> None:
        """Enforce retention policy by deleting oldest items if needed.

        Args:
            max_items: Maximum number of items to keep (None = no limit)
        """
        ...


class JsonLinesBackend:
    """JSONL file-backed storage for context items.

    Each line in the file is a complete JSON record. Provides:
    - Automatic flushing on every write
    - Efficient append-on-write semantics
    - Automatic retention enforcement
    """

    def __init__(self, file_path: str):
        """Initialize JSONL backend.

        Args:
            file_path: Path to JSONL file (created if doesn't exist)

        Raises:
            OSError: If directory cannot be created
        """
        self.file_path = Path(file_path)
        self.file_path.parent.mkdir(parents=True, exist_ok=True)

        # In-memory cache for faster queries
        self._items: Dict[str, ContextItem] = {}
        self._lock = threading.Lock()

        # Load existing items from file
        self._load_from_file()

    def _load_from_file(self) -> None:
        """Load all items from JSONL file into memory."""
        if not self.file_path.exists():
            return

        with open(self.file_path, 'r') as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    data = json.loads(line)
                    item = self._deserialize_context_item(data)
                    self._items[item.context_item_id] = item
                except (json.JSONDecodeError, ValueError, KeyError):
                    # Skip malformed lines
                    pass

    def _serialize_context_item(self, item: ContextItem) -> Dict[str, Any]:
        """Serialize ContextItem to dict for JSON storage."""
        return {
            "context_item_id": item.context_item_id,
            "kind": item.kind,
            "source": item.source,
            "timestamp": item.timestamp,
            "tags": item.tags,
            "importance": item.importance,
            "token_cost": item.token_cost,
            "payload": item.payload,
            "metadata": item.metadata
        }

    def _deserialize_context_item(self, data: Dict[str, Any]) -> ContextItem:
        """Deserialize dict from JSON into ContextItem."""
        return ContextItem(
            context_item_id=data["context_item_id"],
            kind=data["kind"],
            source=data["source"],
            timestamp=data.get("timestamp"),
            tags=data.get("tags", []),
            importance=data.get("importance"),
            token_cost=data.get("token_cost"),
            payload=data.get("payload"),
            metadata=data.get("metadata", {})
        )

    def _flush_to_file(self) -> None:
        """Flush all items to file."""
        with open(self.file_path, 'w') as f:
            for item in self._items.values():
                data = self._serialize_context_item(item)
                f.write(json.dumps(data) + '\n')

    def add(self, item: ContextItem) -> None:
        """Add item and flush to file.

        Args:
            item: ContextItem to add
        """
        with self._lock:
            self._items[item.context_item_id] = item
            self._flush_to_file()

    def query(
        self,
        filters: Dict[str, Any],
        limit: int = 100,
        order_by: str = "timestamp"
    ) -> List[ContextItem]:
        """Query items matching filters.

        Args:
            filters: Field->value filter dict
            limit: Max items to return
            order_by: Field to sort by

        Returns:
            List of matching items
        """
        with self._lock:
            results = []
            for item in self._items.values():
                if self._matches_filters(item, filters):
                    results.append(item)

            # Sort
            reverse = True
            if order_by.startswith("-"):
                order_by = order_by[1:]
                reverse = False

            results.sort(
                key=lambda i: getattr(i, order_by, None) or "",
                reverse=reverse
            )

            return results[:limit]

    def _matches_filters(self, item: ContextItem, filters: Dict[str, Any]) -> bool:
        """Check if item matches all filters."""
        for field, value in filters.items():
            item_value = getattr(item, field, None)

            if isinstance(value, dict):
                for op, op_value in value.items():
                    if not self._apply_operator(item_value, op, op_value):
                        return False
            elif isinstance(value, list):
                if not isinstance(item_value, list):
                    return False
                if not any(v in item_value for v in value):
                    return False
            else:
                if item_value != value:
                    return False

        return True

    def _apply_operator(self, value: Any, op: str, target: Any) -> bool:
        """Apply comparison operator."""
        if value is None:
            if op == "$eq":
                return target is None
            elif op == "$ne":
                return target is not None
            else:
                return False

        ops = {
            "$eq": lambda a, b: a == b,
            "$ne": lambda a, b: a != b,
            "$gt": lambda a, b: a > b,
            "$gte": lambda a, b: a >= b,
            "$lt": lambda a, b: a < b,
            "$lte": lambda a, b: a <= b,
        }
        if op in ops:
            try:
                return ops[op](value, target)
            except (TypeError, AttributeError):
                return False
        return False

    def get(self, item_id: str) -> Optional[ContextItem]:
        """Get item by ID."""
        with self._lock:
            return self._items.get(item_id)

    def delete(self, item_id: str) -> bool:
        """Delete item by ID and flush."""
        with self._lock:
            if item_id in self._items:
                del self._items[item_id]
                self._flush_to_file()
                return True
            return False

    def list_all(self) -> List[ContextItem]:
        """List all items."""
        with self._lock:
            return list(self._items.values())

    def clear(self) -> None:
        """Clear all items and flush."""
        with self._lock:
            self._items.clear()
            self._flush_to_file()

    def count(self) -> int:
        """Count items."""
        with self._lock:
            return len(self._items)

    def enforce_retention(self, max_items: Optional[int]) -> None:
        """Enforce retention by deleting oldest items.

        Args:
            max_items: Max items to keep (None = no limit)
        """
        if max_items is None:
            return

        with self._lock:
            if len(self._items) > max_items:
                # Sort by timestamp, delete oldest
                sorted_items = sorted(
                    self._items.values(),
                    key=lambda i: i.timestamp or ""
                )
                to_delete = sorted_items[:len(self._items) - max_items]
                for item in to_delete:
                    del self._items[item.context_item_id]
                self._flush_to_file()


class SQLiteBackend:
    """SQLite database-backed storage for context items and artifacts.

    Provides:
    - Persistent storage with atomic writes
    - Automatic commit on every write
    - Efficient querying via SQL
    - Automatic retention enforcement
    - Support for artifacts with metadata
    """

    def __init__(self, db_path: str):
        """Initialize SQLite backend.

        Args:
            db_path: Path to SQLite database (created if doesn't exist)

        Raises:
            sqlite3.Error: If database operations fail
        """
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

        self._init_database()

    def _init_database(self) -> None:
        """Initialize database schema if needed."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    CREATE TABLE IF NOT EXISTS memory_items (
                        id TEXT PRIMARY KEY,
                        context_item_id TEXT UNIQUE NOT NULL,
                        kind TEXT NOT NULL,
                        source TEXT NOT NULL,
                        timestamp TEXT,
                        tags TEXT,
                        importance REAL,
                        token_cost REAL,
                        payload TEXT NOT NULL,
                        metadata TEXT,
                        created_at TEXT NOT NULL
                    )
                ''')

                conn.execute('''
                    CREATE TABLE IF NOT EXISTS artifacts (
                        id TEXT PRIMARY KEY,
                        artifact_id TEXT UNIQUE NOT NULL,
                        task_id TEXT NOT NULL,
                        node_id TEXT,
                        artifact_type TEXT NOT NULL,
                        timestamp TEXT NOT NULL,
                        schema_ref TEXT,
                        payload TEXT NOT NULL,
                        additional_metadata TEXT,
                        created_at TEXT NOT NULL
                    )
                ''')

                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_task_id ON artifacts(task_id)
                ''')
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_node_id ON artifacts(node_id)
                ''')
                conn.execute('''
                    CREATE INDEX IF NOT EXISTS idx_artifact_type ON artifacts(artifact_type)
                ''')

                conn.commit()

    def add(self, item: ContextItem) -> None:
        """Add item to database.

        Args:
            item: ContextItem to add
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO memory_items
                    (id, context_item_id, kind, source, timestamp, tags,
                     importance, token_cost, payload, metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    item.context_item_id,  # Use item ID as row ID
                    item.context_item_id,
                    item.kind,
                    item.source,
                    item.timestamp,
                    json.dumps(item.tags or []),
                    item.importance,
                    item.token_cost,
                    json.dumps(item.payload),
                    json.dumps(item.metadata or {}),
                    datetime.now(ZoneInfo("UTC")).isoformat()
                ))
                conn.commit()

    def query(
        self,
        filters: Dict[str, Any],
        limit: int = 100,
        order_by: str = "timestamp"
    ) -> List[ContextItem]:
        """Query items with SQL filtering.

        Args:
            filters: Field->value filter dict
            limit: Max items
            order_by: Field to sort by

        Returns:
            List of matching items
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                query = "SELECT * FROM memory_items WHERE 1=1"
                params = []

                for field, value in filters.items():
                    if field in ["kind", "source", "importance", "token_cost"]:
                        query += f" AND {field} = ?"
                        params.append(value)

                # Handle timestamp ordering
                reverse = True
                if order_by.startswith("-"):
                    order_by = order_by[1:]
                    reverse = False

                query += f" ORDER BY {order_by} {'DESC' if reverse else 'ASC'}"
                query += f" LIMIT {limit}"

                rows = conn.execute(query, params).fetchall()

                items = []
                for row in rows:
                    item = self._deserialize_row(row)
                    items.append(item)

                return items

    def _deserialize_row(self, row: tuple) -> ContextItem:
        """Deserialize database row to ContextItem."""
        (_, context_item_id, kind, source, timestamp, tags_json,
         importance, token_cost, payload_json, metadata_json, _) = row

        return ContextItem(
            context_item_id=context_item_id,
            kind=kind,
            source=source,
            timestamp=timestamp,
            tags=json.loads(tags_json or "[]"),
            importance=importance,
            token_cost=token_cost,
            payload=json.loads(payload_json),
            metadata=json.loads(metadata_json or "{}")
        )

    def get(self, item_id: str) -> Optional[ContextItem]:
        """Get item by ID."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT * FROM memory_items WHERE context_item_id = ?",
                    (item_id,)
                ).fetchone()

                if row:
                    return self._deserialize_row(row)
                return None

    def delete(self, item_id: str) -> bool:
        """Delete item by ID."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.execute(
                    "DELETE FROM memory_items WHERE context_item_id = ?",
                    (item_id,)
                )
                conn.commit()
                return cursor.rowcount > 0

    def list_all(self) -> List[ContextItem]:
        """List all items."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute("SELECT * FROM memory_items").fetchall()
                return [self._deserialize_row(row) for row in rows]

    def clear(self) -> None:
        """Clear all items."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute("DELETE FROM memory_items")
                conn.commit()

    def count(self) -> int:
        """Count items."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                result = conn.execute(
                    "SELECT COUNT(*) FROM memory_items"
                ).fetchone()
                return result[0] if result else 0

    def enforce_retention(self, max_items: Optional[int]) -> None:
        """Enforce retention policy.

        Args:
            max_items: Max items to keep (None = no limit)
        """
        if max_items is None:
            return

        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM memory_items"
                ).fetchone()[0]

                if count > max_items:
                    # Delete oldest items
                    to_delete = count - max_items
                    conn.execute(f'''
                        DELETE FROM memory_items
                        WHERE context_item_id IN (
                            SELECT context_item_id FROM memory_items
                            ORDER BY timestamp ASC
                            LIMIT {to_delete}
                        )
                    ''')
                    conn.commit()

    def add_artifact(
        self,
        artifact_id: str,
        task_id: str,
        node_id: Optional[str],
        artifact_type: str,
        timestamp: str,
        schema_ref: Optional[str],
        payload: Any,
        additional_metadata: Optional[Dict[str, Any]] = None
    ) -> None:
        """Store artifact in database.

        Args:
            artifact_id: Unique artifact ID
            task_id: Task that produced artifact
            node_id: Node that produced artifact (optional)
            artifact_type: Type of artifact
            timestamp: ISO-8601 timestamp
            schema_ref: Schema reference (optional)
            payload: Artifact data
            additional_metadata: Additional metadata dict
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                conn.execute('''
                    INSERT OR REPLACE INTO artifacts
                    (id, artifact_id, task_id, node_id, artifact_type,
                     timestamp, schema_ref, payload, additional_metadata, created_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    artifact_id,
                    artifact_id,
                    task_id,
                    node_id,
                    artifact_type,
                    timestamp,
                    schema_ref,
                    json.dumps(payload),
                    json.dumps(additional_metadata or {}),
                    datetime.now(ZoneInfo("UTC")).isoformat()
                ))
                conn.commit()

    def get_artifact(self, artifact_id: str) -> Optional[Dict[str, Any]]:
        """Get artifact by ID.

        Args:
            artifact_id: Artifact ID

        Returns:
            Artifact dict or None
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                row = conn.execute(
                    "SELECT * FROM artifacts WHERE artifact_id = ?",
                    (artifact_id,)
                ).fetchone()

                if row:
                    return self._deserialize_artifact_row(row)
                return None

    def get_artifacts_by_task(self, task_id: str) -> List[Dict[str, Any]]:
        """Get all artifacts for a task.

        Args:
            task_id: Task ID

        Returns:
            List of artifact dicts
        """
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                rows = conn.execute(
                    "SELECT * FROM artifacts WHERE task_id = ? ORDER BY timestamp DESC",
                    (task_id,)
                ).fetchall()
                return [self._deserialize_artifact_row(row) for row in rows]

    def _deserialize_artifact_row(self, row: tuple) -> Dict[str, Any]:
        """Deserialize artifact row."""
        (_, artifact_id, task_id, node_id, artifact_type, timestamp,
         schema_ref, payload_json, additional_metadata_json, _) = row

        return {
            "artifact_id": artifact_id,
            "task_id": task_id,
            "node_id": node_id,
            "artifact_type": artifact_type,
            "timestamp": timestamp,
            "schema_ref": schema_ref,
            "payload": json.loads(payload_json),
            "additional_metadata": json.loads(additional_metadata_json or "{}")
        }

    def artifact_count(self) -> int:
        """Count artifacts."""
        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                result = conn.execute(
                    "SELECT COUNT(*) FROM artifacts"
                ).fetchone()
                return result[0] if result else 0

    def enforce_artifact_retention(self, max_items: Optional[int]) -> None:
        """Enforce artifact retention policy.

        Args:
            max_items: Max artifacts to keep (None = no limit)
        """
        if max_items is None:
            return

        with self._lock:
            with sqlite3.connect(self.db_path) as conn:
                count = conn.execute(
                    "SELECT COUNT(*) FROM artifacts"
                ).fetchone()[0]

                if count > max_items:
                    to_delete = count - max_items
                    conn.execute(f'''
                        DELETE FROM artifacts
                        WHERE artifact_id IN (
                            SELECT artifact_id FROM artifacts
                            ORDER BY timestamp ASC
                            LIMIT {to_delete}
                        )
                    ''')
                    conn.commit()


class PersistentMemoryStore:
    """Wrapper around persistent backend for unified interface.

    Supports both JSONL and SQLite backends with automatic selection
    based on configuration.
    """

    def __init__(
        self,
        backend_type: str = "in_memory",
        file_path: Optional[str] = None,
        db_path: Optional[str] = None,
        max_items: Optional[int] = None
    ):
        """Initialize persistent memory store.

        Args:
            backend_type: "jsonl", "sqlite", or "in_memory"
            file_path: Path for JSONL backend
            db_path: Path for SQLite backend
            max_items: Retention policy - max items to keep

        Raises:
            ValueError: If backend type invalid or required paths missing
        """
        self.backend_type = backend_type
        self.max_items = max_items

        if backend_type == "jsonl":
            if not file_path:
                raise ValueError("file_path required for jsonl backend")
            self.backend = JsonLinesBackend(file_path)
        elif backend_type == "sqlite":
            if not db_path:
                raise ValueError("db_path required for sqlite backend")
            self.backend = SQLiteBackend(db_path)
        elif backend_type == "in_memory":
            # Use a simple dict-based in-memory store
            self.backend = None
            self._memory_items: Dict[str, ContextItem] = {}
        else:
            raise ValueError(f"Unknown backend type: {backend_type}")

    def add(self, item: ContextItem) -> None:
        """Add item with automatic persistence and retention.

        Args:
            item: ContextItem to add
        """
        if self.backend:
            self.backend.add(item)
            self.backend.enforce_retention(self.max_items)
        else:
            self._memory_items[item.context_item_id] = item
            self._enforce_retention()

    def query(
        self,
        filters: Dict[str, Any],
        limit: int = 100,
        order_by: str = "timestamp"
    ) -> List[ContextItem]:
        """Query items."""
        if self.backend:
            return self.backend.query(filters, limit, order_by)
        else:
            # In-memory query
            results = []
            for item in self._memory_items.values():
                if self._matches_filters(item, filters):
                    results.append(item)

            reverse = True
            if order_by.startswith("-"):
                order_by = order_by[1:]
                reverse = False

            results.sort(
                key=lambda i: getattr(i, order_by, None) or "",
                reverse=reverse
            )
            return results[:limit]

    def _matches_filters(self, item: ContextItem, filters: Dict[str, Any]) -> bool:
        """Check if item matches filters."""
        for field, value in filters.items():
            item_value = getattr(item, field, None)
            if isinstance(value, dict):
                for op, op_value in value.items():
                    if not self._apply_operator(item_value, op, op_value):
                        return False
            elif isinstance(value, list):
                if not isinstance(item_value, list):
                    return False
                if not any(v in item_value for v in value):
                    return False
            else:
                if item_value != value:
                    return False
        return True

    def _apply_operator(self, value: Any, op: str, target: Any) -> bool:
        """Apply operator."""
        if value is None:
            return (op == "$eq" and target is None) or (op == "$ne" and target is not None)
        ops = {
            "$eq": lambda a, b: a == b,
            "$ne": lambda a, b: a != b,
            "$gt": lambda a, b: a > b,
            "$gte": lambda a, b: a >= b,
            "$lt": lambda a, b: a < b,
            "$lte": lambda a, b: a <= b,
        }
        if op in ops:
            try:
                return ops[op](value, target)
            except (TypeError, AttributeError):
                return False
        return False

    def get(self, item_id: str) -> Optional[ContextItem]:
        """Get item by ID."""
        if self.backend:
            return self.backend.get(item_id)
        else:
            return self._memory_items.get(item_id)

    def delete(self, item_id: str) -> bool:
        """Delete item by ID."""
        if self.backend:
            return self.backend.delete(item_id)
        else:
            if item_id in self._memory_items:
                del self._memory_items[item_id]
                return True
            return False

    def list_all(self) -> List[ContextItem]:
        """List all items."""
        if self.backend:
            return self.backend.list_all()
        else:
            return list(self._memory_items.values())

    def clear(self) -> None:
        """Clear all items."""
        if self.backend:
            self.backend.clear()
        else:
            self._memory_items.clear()

    def count(self) -> int:
        """Count items."""
        if self.backend:
            return self.backend.count()
        else:
            return len(self._memory_items)

    def _enforce_retention(self) -> None:
        """Enforce retention for in-memory store."""
        if self.max_items is not None and len(self._memory_items) > self.max_items:
            sorted_items = sorted(
                self._memory_items.values(),
                key=lambda i: i.timestamp or ""
            )
            to_delete = sorted_items[:len(self._memory_items) - self.max_items]
            for item in to_delete:
                del self._memory_items[item.context_item_id]
