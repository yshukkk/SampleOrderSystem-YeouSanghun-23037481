"""Generic JSON-file-backed CRUD repository for dict records.

See PRD.md / PLAN.md in this directory for the full design. This module has
no knowledge of any specific entity's field shape (no Sample/Order classes
here) — it only stores and retrieves plain ``dict`` records, keyed by an
auto-assigned integer ``id``.

File schema on disk::

    {"next_id": N, "records": [...]}

Every CRUD call rewrites the file immediately so external readers (e.g. a
separate monitoring process) always observe the latest state on reload.
"""

from __future__ import annotations

import json
from pathlib import Path


class JsonRepository:
    """CRUD repository backed by a single JSON file at ``path``."""

    def __init__(self, path: Path) -> None:
        self.path = Path(path)

    def _load(self) -> dict:
        if not self.path.exists():
            return {"next_id": 1, "records": []}
        with self.path.open("r", encoding="utf-8") as f:
            return json.load(f)

    def _save(self, data: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

    def create(self, record: dict) -> dict:
        data = self._load()
        new_id = data["next_id"]
        new_record = dict(record)
        new_record["id"] = new_id
        data["records"].append(new_record)
        data["next_id"] = new_id + 1
        self._save(data)
        return new_record

    def create_with_id(self, record: dict, record_id: int) -> dict | None:
        """Insert `record` under a caller-supplied `record_id` (primary key).

        Returns ``None`` without modifying anything if `record_id` is already
        in use (duplicate id -- caller decides how to report this). On
        success, advances `next_id` past `record_id` so future auto-increment
        `create()` calls on the same file never collide with it.
        """
        data = self._load()
        for record_row in data["records"]:
            if record_row.get("id") == record_id:
                return None
        new_record = dict(record)
        new_record["id"] = record_id
        data["records"].append(new_record)
        data["next_id"] = max(data["next_id"], record_id + 1)
        self._save(data)
        return new_record

    def list_all(self) -> list[dict]:
        data = self._load()
        return data["records"]

    def find(self, record_id: int) -> dict | None:
        data = self._load()
        for record in data["records"]:
            if record.get("id") == record_id:
                return record
        return None

    def update(self, record_id: int, **fields) -> bool:
        data = self._load()
        for record in data["records"]:
            if record.get("id") == record_id:
                record.update(fields)
                self._save(data)
                return True
        return False

    def delete(self, record_id: int) -> bool:
        data = self._load()
        records = data["records"]
        for i, record in enumerate(records):
            if record.get("id") == record_id:
                del records[i]
                self._save(data)
                return True
        return False
