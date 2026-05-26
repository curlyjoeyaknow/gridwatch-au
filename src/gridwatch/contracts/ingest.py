"""IngestEvent — one observed reading, recorded at download time (ADR-007).

Envelope (event_id, ingested_at, source, batch_id) + the reading payload. The
ledger stores these append-only; `to_reading()` rebuilds the typed Reading and
the replay projection folds a stream of events back into Regions.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import uuid4

from gridwatch.contracts.readings import Reading, reading_from_row


@dataclass(frozen=True)
class IngestEvent:
    event_id: str
    ingested_at: datetime
    source: str
    batch_id: str
    region: str
    metric: str
    fuel_tech: str | None
    timestamp: datetime
    value: float
    unit: str
    interval_minutes: int

    @classmethod
    def from_reading(
        cls,
        reading: Reading,
        *,
        source: str,
        batch_id: str,
        ingested_at: datetime,
        event_id: str | None = None,
    ) -> IngestEvent:
        row = reading.to_row()
        return cls(
            event_id=event_id or uuid4().hex,
            ingested_at=ingested_at,
            source=source,
            batch_id=batch_id,
            region=row["region"],
            metric=row["metric"],
            fuel_tech=row["fuel_tech"],
            timestamp=reading.timestamp,
            value=row["value"],
            unit=row["unit"],
            interval_minutes=row["interval_minutes"],
        )

    def to_reading(self) -> Reading:
        return reading_from_row(
            {
                "region": self.region,
                "metric": self.metric,
                "fuel_tech": self.fuel_tech,
                "timestamp": self.timestamp.isoformat(),
                "value": self.value,
                "unit": self.unit,
                "interval_minutes": self.interval_minutes,
            }
        )

    def to_row(self) -> dict:
        return {
            "event_id": self.event_id,
            "ingested_at": self.ingested_at.isoformat(),
            "source": self.source,
            "batch_id": self.batch_id,
            "region": self.region,
            "metric": self.metric,
            "fuel_tech": self.fuel_tech,
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "unit": self.unit,
            "interval_minutes": self.interval_minutes,
        }

    @classmethod
    def from_row(cls, row: dict) -> IngestEvent:
        return cls(
            event_id=row["event_id"],
            ingested_at=datetime.fromisoformat(row["ingested_at"]),
            source=row["source"],
            batch_id=row["batch_id"],
            region=row["region"],
            metric=row["metric"],
            fuel_tech=row["fuel_tech"] if row["fuel_tech"] else None,
            timestamp=datetime.fromisoformat(row["timestamp"]),
            value=float(row["value"]),
            unit=row["unit"],
            interval_minutes=int(row["interval_minutes"]),
        )
