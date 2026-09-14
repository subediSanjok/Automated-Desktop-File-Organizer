"""History tracking manager for recording and reverting file moves."""

from __future__ import annotations

import json
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional


@dataclass
class MoveRecord:
    """Represents an individual file move event."""
    source_path: str
    dest_path: str
    category: str
    timestamp: float
    batch_id: str
    reverted: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> MoveRecord:
        return cls(
            source_path=str(data["source_path"]),
            dest_path=str(data["dest_path"]),
            category=str(data.get("category", "")),
            timestamp=float(data.get("timestamp", time.time())),
            batch_id=str(data.get("batch_id", "default")),
            reverted=bool(data.get("reverted", False)),
        )


class MoveHistoryManager:
    """Manages persistent move records to support undo / revert operations."""

    def __init__(self, history_file: Optional[Path | str]=None) -> None:
        self.history_file = (
            Path(history_file) if history_file else Path("logs") / "move_history.json"
        )
        self.records: List[MoveRecord] = []
        self._load()

    def _load(self) -> None:
        """Load history records from disk if file exists."""
        if not self.history_file.exists():
            return
        try:
            with open(self.history_file, "r", encoding="utf-8") as f:
                raw_list = json.load(f)
                self.records = [MoveRecord.from_dict(item) for item in raw_list]
        except Exception:
            self.records = []

    def save(self) -> None:
        """Persist history records to disk."""
        try:
            self.history_file.parent.mkdir(parents=True, exist_ok=True)
            with open(self.history_file, "w", encoding="utf-8") as f:
                json.dump([r.to_dict() for r in self.records], f, indent=2)
        except Exception:
            pass

    def add_record(
        self,
        source_path: Path | str,
        dest_path: Path | str,
        category: str,
        batch_id: str,
    ) -> MoveRecord:
        """Record a file move."""
        record = MoveRecord(
            source_path=str(source_path),
            dest_path=str(dest_path),
            category=category,
            timestamp=time.time(),
            batch_id=batch_id,
            reverted=False,
        )
        self.records.append(record)
        self.save()
        return record

    def get_batches(self) -> List[str]:
        """Get unique batch IDs in chronological order (most recent first)."""
        batches: List[str] = []
        for r in reversed(self.records):
            if r.batch_id not in batches:
                batches.append(r.batch_id)
        return batches

    def get_records_for_batch(self, batch_id: str) -> List[MoveRecord]:
        """Get all move records for a specific batch ID."""
        return [r for r in self.records if r.batch_id == batch_id and not r.reverted]

    def get_all_active_records(self) -> List[MoveRecord]:
        """Get all un-reverted records."""
        return [r for r in self.records if not r.reverted]

    def mark_reverted(self, records: List[MoveRecord]) -> None:
        """Mark a list of records as reverted and persist."""
        reverted_dest_paths = {r.dest_path for r in records}
        for r in self.records:
            if r.dest_path in reverted_dest_paths:
                r.reverted = True
        self.save()
