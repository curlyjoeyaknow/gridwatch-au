"""Analytics — pure functions that fold readings into insight.

No I/O, no mutation. Renewable share and emissions intensity follow the
generation policy in ADR-003 (storage/interconnect/curtailment excluded).
"""

from __future__ import annotations

from collections.abc import Iterable

from gridwatch.contracts.fueltech import FuelCategory
from gridwatch.contracts.readings import (
    DemandReading,
    EmissionReading,
    PowerReading,
    PriceReading,
    Reading,
)
from gridwatch.contracts.summary import RegionSummary


def _generation_power(readings: Iterable[Reading]) -> list[PowerReading]:
    return [r for r in readings if isinstance(r, PowerReading) and r.fuel.counts_as_generation]


def total_generation_mwh(readings: Iterable[Reading]) -> float:
    return sum(r.energy_mwh for r in _generation_power(readings))


def renewable_generation_mwh(readings: Iterable[Reading]) -> float:
    return sum(r.energy_mwh for r in _generation_power(readings) if r.fuel.is_renewable)


def generation_by_category(readings: Iterable[Reading]) -> dict[FuelCategory, float]:
    totals: dict[FuelCategory, float] = {}
    for r in _generation_power(readings):
        totals[r.fuel.category] = totals.get(r.fuel.category, 0.0) + r.energy_mwh
    return totals


def renewable_share(readings: Iterable[Reading]) -> float:
    readings = list(readings)
    total = total_generation_mwh(readings)
    if total <= 0:
        return 0.0
    return renewable_generation_mwh(readings) / total


def total_emissions(readings: Iterable[Reading]) -> float:
    return sum(r.value for r in readings if isinstance(r, EmissionReading))


def emissions_intensity(readings: Iterable[Reading]) -> float:
    readings = list(readings)
    total = total_generation_mwh(readings)
    if total <= 0:
        return 0.0
    return total_emissions(readings) / total


def price_stats(readings: Iterable[Reading]) -> tuple[float | None, float | None]:
    prices = [r.value for r in readings if isinstance(r, PriceReading)]
    if not prices:
        return (None, None)
    return (sum(prices) / len(prices), max(prices))


def demand_stats(readings: Iterable[Reading]) -> tuple[float | None, float | None]:
    """(average, peak) demand in MW, or (None, None) if no demand readings."""
    demand = [r.value for r in readings if isinstance(r, DemandReading)]
    if not demand:
        return (None, None)
    return (sum(demand) / len(demand), max(demand))


def summarise(region) -> RegionSummary:
    """Fold a Region's readings into a RegionSummary."""
    readings = list(region.readings)
    avg_price, peak_price = price_stats(readings)
    return RegionSummary(
        region=region.code,
        total_generation_mwh=total_generation_mwh(readings),
        renewable_generation_mwh=renewable_generation_mwh(readings),
        renewable_share=renewable_share(readings),
        total_emissions_tco2e=total_emissions(readings),
        emissions_intensity=emissions_intensity(readings),
        avg_price=avg_price,
        peak_price=peak_price,
        by_category_mwh=generation_by_category(readings),
        reading_count=len(readings),
    )
