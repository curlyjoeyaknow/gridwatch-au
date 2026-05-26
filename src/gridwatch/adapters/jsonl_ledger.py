"""JsonlEventLedger — append-only JSON Lines (ADR-007).

One event per line; append opens the file in append mode and never rewrites it.
Simple and human-readable; for large bulk fetches prefer the Parquet ledger.
"""

from __future__ import annotations

import json
from pathlib import Path

from gridwatch.contracts.ingest import IngestEvent
from gridwatch.exceptions import PersistenceError
from gridwatch.ports.ledger import EventLedger


class JsonlEventLedger(EventLedger):
    def __init__(self, path: str | Path):
        self._path = Path(path)

    def append(self, events: list[IngestEvent]) -> None:
        if not events:
            return
        try:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            with open(self._path, "a", encoding="utf-8") as handle:
                for event in events:
                    handle.write(json.dumps(event.to_row()) + "\n")
        except OSError as exc:
            raise PersistenceError(f"could not append to ledger {self._path}: {exc}") from exc

    def read_all(self) -> list[IngestEvent]:
        if not self._path.exists():
            return []
        try:
            with open(self._path, encoding="utf-8") as handle:
                return [IngestEvent.from_row(json.loads(line)) for line in handle if line.strip()]
        except (OSError, ValueError, KeyError) as exc:
            raise PersistenceError(f"corrupt ledger {self._path}: {exc}") from exc
