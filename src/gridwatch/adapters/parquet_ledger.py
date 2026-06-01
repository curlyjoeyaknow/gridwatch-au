"""ParquetEventLedger — append-only columnar ledger.

Parquet files are immutable, so each append writes a new file into a directory;
`read_all` reads every file back. Compact for large bulk fetches.
"""

from __future__ import annotations

from pathlib import Path
from uuid import uuid4

import pyarrow as pa
import pyarrow.parquet as pq

from gridwatch.contracts.ingest import IngestEvent
from gridwatch.exceptions import PersistenceError
from gridwatch.ports.ledger import EventLedger


class ParquetEventLedger(EventLedger):
    def __init__(self, directory: str | Path):
        self._dir = Path(directory)

    def append(self, events: list[IngestEvent]) -> None:
        if not events:
            return
        try:
            self._dir.mkdir(parents=True, exist_ok=True)
            table = pa.Table.from_pylist([event.to_row() for event in events])
            filename = f"{events[0].batch_id}-{uuid4().hex[:8]}.parquet"
            pq.write_table(table, self._dir / filename)
        except (OSError, pa.ArrowException) as exc:
            raise PersistenceError(
                f"could not append to parquet ledger {self._dir}: {exc}"
            ) from exc

    def read_all(self) -> list[IngestEvent]:
        if not self._dir.exists() or not any(self._dir.glob("*.parquet")):
            return []
        try:
            table = pq.read_table(self._dir)
            return [IngestEvent.from_row(row) for row in table.to_pylist()]
        except (OSError, pa.ArrowException, ValueError, KeyError) as exc:
            raise PersistenceError(f"corrupt parquet ledger {self._dir}: {exc}") from exc
