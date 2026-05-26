"""Row <-> Reading (de)serialisation shared by the file repositories.

A reading's `to_row()` is its serialised form; `reading_from_row()` rehydrates the
correct `Reading` subclass from a row, dispatching on `metric` (ADR-003/004).
"""

from __future__ import annotations

from datetime import datetime

from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import (
    DemandReading,
    EmissionReading,
    PowerReading,
    PriceReading,
    Reading,
)
from gridwatch.exceptions import PersistenceError


def reading_from_row(row: dict) -> Reading:
    """Rebuild a Reading from a serialised row (JSON dict or CSV string dict)."""
    try:
        metric = row["metric"]
        region = row["region"]
        timestamp = datetime.fromisoformat(row["timestamp"])
        value = float(row["value"])
        interval = int(float(row["interval_minutes"]))
        fuel_tech = row.get("fuel_tech") or None
    except (KeyError, TypeError, ValueError) as exc:
        raise PersistenceError(f"corrupt reading row {row!r}: {exc}") from exc

    if metric == "power":
        return PowerReading(region, timestamp, value, interval, fuel=classify(fuel_tech or ""))
    if metric == "emissions":
        return EmissionReading(region, timestamp, value, interval, fuel=classify(fuel_tech or ""))
    if metric == "price":
        return PriceReading(region, timestamp, value, interval)
    if metric == "demand":
        return DemandReading(region, timestamp, value, interval)
    raise PersistenceError(f"unknown metric {metric!r} in saved data")
