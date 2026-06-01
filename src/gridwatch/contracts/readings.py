"""The `Reading` hierarchy — the canonical record shape.

An abstract `Reading` holds the common fields (region, timestamp, value,
interval); each concrete subclass knows its own metric and unit. `unit`,
`metric`, `to_row()` and `label()` are polymorphic, so every consumer treats a
list of mixed readings uniformly.
"""

from __future__ import annotations

import math
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import ClassVar

from gridwatch.contracts.fueltech import FuelTech, classify
from gridwatch.exceptions import ValidationError


@dataclass(frozen=True)
class Reading(ABC):
    region: str
    timestamp: datetime
    value: float
    interval_minutes: int

    def __post_init__(self) -> None:
        if not isinstance(self.region, str) or not self.region.strip():
            raise ValidationError("reading.region must be a non-empty string")
        if not isinstance(self.timestamp, datetime):
            raise ValidationError("reading.timestamp must be a datetime")
        if (
            isinstance(self.value, bool)
            or not isinstance(self.value, int | float)
            or math.isnan(self.value)
            or math.isinf(self.value)
        ):
            raise ValidationError(f"reading.value must be a finite number, got {self.value!r}")
        if not isinstance(self.interval_minutes, int) or self.interval_minutes <= 0:
            raise ValidationError("reading.interval_minutes must be a positive integer")

    @property
    @abstractmethod
    def metric(self) -> str:
        """Short metric name, e.g. 'power'."""

    @property
    @abstractmethod
    def unit(self) -> str:
        """Unit of `value`, e.g. 'MW'."""

    @property
    def fuel_tech(self) -> str | None:
        fuel = getattr(self, "fuel", None)
        return fuel.raw if fuel is not None else None

    @property
    def energy_mwh(self) -> float:
        """`value` (a rate, MW) integrated over the interval, in MWh."""
        return self.value * self.interval_minutes / 60.0

    def label(self) -> str:
        base = f"{self.region} · {self.metric}"
        return f"{base} · {self.fuel_tech}" if self.fuel_tech else base

    def to_row(self) -> dict:
        return {
            "region": self.region,
            "metric": self.metric,
            "fuel_tech": self.fuel_tech,
            "timestamp": self.timestamp.isoformat(),
            "value": self.value,
            "unit": self.unit,
            "interval_minutes": self.interval_minutes,
        }


@dataclass(frozen=True)
class PowerReading(Reading):
    fuel: FuelTech
    metric: ClassVar[str] = "power"
    unit: ClassVar[str] = "MW"


@dataclass(frozen=True)
class EmissionReading(Reading):
    fuel: FuelTech
    metric: ClassVar[str] = "emissions"
    unit: ClassVar[str] = "tCO2e"


@dataclass(frozen=True)
class PriceReading(Reading):
    metric: ClassVar[str] = "price"
    unit: ClassVar[str] = "AUD/MWh"


@dataclass(frozen=True)
class DemandReading(Reading):
    metric: ClassVar[str] = "demand"
    unit: ClassVar[str] = "MW"


_READING_CLASSES = (PowerReading, EmissionReading, PriceReading, DemandReading)
_BY_METRIC = {cls.metric: cls for cls in _READING_CLASSES}


def reading_from_row(row: dict) -> Reading:
    """Rebuild the correct Reading subclass from a serialised row (dispatch on metric).

    Accepts JSON dicts and CSV string-dicts; raises ValidationError on a corrupt row.
    """
    try:
        metric = row["metric"]
        region = row["region"]
        timestamp = datetime.fromisoformat(row["timestamp"])
        value = float(row["value"])
        interval = int(float(row["interval_minutes"]))
        fuel_tech = row.get("fuel_tech") or None
    except (KeyError, TypeError, ValueError) as exc:
        raise ValidationError(f"corrupt reading row {row!r}: {exc}") from exc

    cls = _BY_METRIC.get(metric)
    if cls is None:
        raise ValidationError(f"unknown metric {metric!r} in row")
    if cls in (PowerReading, EmissionReading):
        return cls(region, timestamp, value, interval, fuel=classify(fuel_tech or ""))
    return cls(region, timestamp, value, interval)
