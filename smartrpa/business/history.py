"""History Store — JSON-based persistent storage for task execution records.

Append-only JSON file stored at data_dir("history.json").
"""
import os
import json
import datetime
from typing import Any, Dict, List, Optional

from smartrpa.ui.theme import data_dir


class HistoryStore:
    """Append-only JSON storage for task execution history."""

    def __init__(self):
        """Initialize the history store. Creates the backing file if needed."""
        self._path = os.path.join(data_dir(), "history.json")
        self._ensure_file()

    def _ensure_file(self) -> None:
        """Create the history file if it doesn't exist."""
        if os.path.isdir(self._path):
            # A directory exists where the file should be — remove it first.
            import shutil
            shutil.rmtree(self._path)
        if not os.path.isfile(self._path):
            with open(self._path, "w", encoding="utf-8") as f:
                json.dump([], f)

    def _read_all(self) -> list:
        """Read all records from the JSON file.

        Returns:
            List of record dicts.
        """
        try:
            with open(self._path, "r", encoding="utf-8") as f:
                data = json.load(f)
            if not isinstance(data, list):
                return []
            return data
        except (json.JSONDecodeError, IOError):
            return []

    def _write_all(self, records: list) -> None:
        """Write all records to the JSON file.

        Args:
            records: List of record dicts to persist.
        """
        with open(self._path, "w", encoding="utf-8") as f:
            json.dump(records, f, ensure_ascii=False, indent=2)

    # ═══════════════════════════════════════════════
    #  Public API
    # ═══════════════════════════════════════════════

    def add_record(
        self,
        task_name: str,
        steps: int = 0,
        errors: int = 0,
        duration: float = 0.0,
        timestamp: Optional[str] = None,
    ) -> None:
        """Append a new execution record.

        Args:
            task_name: Display name of the executed task.
            steps: Number of steps executed.
            errors: Number of errors encountered.
            duration: Total execution duration in seconds.
            timestamp: ISO-format timestamp string. Defaults to now.
        """
        if timestamp is None:
            timestamp = datetime.datetime.now().isoformat()

        record: Dict[str, Any] = {
            "task_name": task_name,
            "steps": steps,
            "errors": errors,
            "duration": duration,
            "timestamp": timestamp,
        }

        records = self._read_all()
        records.append(record)
        self._write_all(records)

    def get_records(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get the most recent execution records.

        Args:
            limit: Maximum number of records to return.

        Returns:
            List of record dicts, newest first.
        """
        records = self._read_all()
        # Return most recent first
        return records[-limit:][::-1]

    def clear(self) -> None:
        """Delete all history records."""
        self._write_all([])

    def count(self) -> int:
        """Get the total number of records.

        Returns:
            Number of records.
        """
        return len(self._read_all())
