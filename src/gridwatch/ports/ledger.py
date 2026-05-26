"""EventLedger port — the append-only ingest history (ADR-007).

Adapters (`JsonlEventLedger`, `ParquetEventLedger`) implement append/read; the core
never overwrites — appends only — and derives state by replaying what it reads.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from gridwatch.contracts.ingest import IngestEvent


class EventLedger(ABC):
    @abstractmethod
    def append(self, events: list[IngestEvent]) -> None:
        """Append events; never modify or remove existing ones."""

    @abstractmethod
    def read_all(self) -> list[IngestEvent]:
        """Return every event ever appended (order not guaranteed)."""
