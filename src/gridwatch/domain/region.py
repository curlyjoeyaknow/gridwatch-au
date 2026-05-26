"""Region — the aggregate that owns and guards a set of readings.

Encapsulation: `_readings` is private; callers add/remove through methods and
only ever see a read-only tuple snapshot via `.readings`.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import datetime

from gridwatch.contracts.readings import Reading
from gridwatch.contracts.regions import region_name, validate_region
from gridwatch.exceptions import ValidationError


@dataclass
class Region:
    code: str
    name: str = ""
    _readings: list[Reading] = field(default_factory=list, repr=False)

    def __post_init__(self) -> None:
        self.code = validate_region(self.code)
        if not self.name:
            self.name = region_name(self.code)

    # --- read-only view ---------------------------------------------------
    @property
    def readings(self) -> tuple[Reading, ...]:
        return tuple(self._readings)

    def __len__(self) -> int:
        return len(self._readings)

    # --- mutation (the only way in) --------------------------------------
    def add_reading(self, reading: Reading) -> None:
        if reading.region != self.code:
            raise ValidationError(
                f"reading region {reading.region!r} does not match region {self.code!r}"
            )
        self._readings.append(reading)

    def add_readings(self, readings: Iterable[Reading]) -> None:
        for reading in readings:
            self.add_reading(reading)

    def remove_where(self, predicate: Callable[[Reading], bool]) -> int:
        """Remove readings matching `predicate`; return how many were removed."""
        before = len(self._readings)
        self._readings = [r for r in self._readings if not predicate(r)]
        return before - len(self._readings)

    def clear(self) -> None:
        self._readings.clear()

    # --- search -----------------------------------------------------------
    def filter(
        self,
        *,
        metric: str | None = None,
        fuel_tech: str | None = None,
        renewable_only: bool = False,
        min_value: float | None = None,
        max_value: float | None = None,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[Reading]:
        """Return readings matching every supplied criterion (logical AND)."""
        results = []
        for r in self._readings:
            if metric is not None and r.metric != metric:
                continue
            if fuel_tech is not None and r.fuel_tech != fuel_tech:
                continue
            if renewable_only:
                fuel = getattr(r, "fuel", None)
                if fuel is None or not fuel.is_renewable:
                    continue
            if min_value is not None and r.value < min_value:
                continue
            if max_value is not None and r.value > max_value:
                continue
            if start is not None and r.timestamp < start:
                continue
            if end is not None and r.timestamp > end:
                continue
            results.append(r)
        return results
