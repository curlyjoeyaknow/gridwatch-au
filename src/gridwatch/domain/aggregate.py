"""Time-bucketed aggregation — summarise readings by hour/day/week/month.

Pure: groups readings into period buckets (per region) and folds each bucket into a
`PeriodPoint` using the same analytics as the per-region summary. This is what turns
raw 5-/30-minute rows into something you can analyse and trend.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from gridwatch.contracts.fueltech import FuelCategory
from gridwatch.contracts.readings import Reading
from gridwatch.domain import analytics
from gridwatch.exceptions import ValidationError

PERIODS = ("hour", "day", "week", "month")

# trend metrics the UI can plot (key -> attribute on PeriodPoint)
TREND_METRICS = (
    "renewable_share",
    "total_generation_mwh",
    "total_emissions_tco2e",
    "emissions_intensity",
    "avg_price",
    "avg_demand_mw",
)


@dataclass(frozen=True)
class PeriodPoint:
    period_start: datetime
    region: str
    total_generation_mwh: float
    renewable_share: float
    total_emissions_tco2e: float
    emissions_intensity: float
    avg_price: float | None
    peak_price: float | None
    avg_demand_mw: float | None
    peak_demand_mw: float | None
    by_category_mwh: dict[FuelCategory, float] = field(default_factory=dict)

    def as_dict(self) -> dict:
        def _r(value, ndigits):
            return None if value is None else round(value, ndigits)

        return {
            "period": self.period_start.isoformat(),
            "region": self.region,
            "generation_mwh": round(self.total_generation_mwh, 3),
            "renewable_share_pct": round(self.renewable_share * 100, 2),
            "emissions_tco2e": round(self.total_emissions_tco2e, 3),
            "emissions_intensity": round(self.emissions_intensity, 4),
            "avg_price": _r(self.avg_price, 2),
            "peak_price": _r(self.peak_price, 2),
            "avg_demand_mw": _r(self.avg_demand_mw, 1),
            "peak_demand_mw": _r(self.peak_demand_mw, 1),
        }


def floor_period(ts: datetime, period: str) -> datetime:
    """Floor a timestamp to the start of its hour/day/ISO-week/month (in its own tz)."""
    if period == "hour":
        return ts.replace(minute=0, second=0, microsecond=0)
    if period == "day":
        return ts.replace(hour=0, minute=0, second=0, microsecond=0)
    if period == "week":
        day = ts.replace(hour=0, minute=0, second=0, microsecond=0)
        return day - timedelta(days=day.weekday())  # back to Monday
    if period == "month":
        return ts.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    raise ValidationError(f"unknown period {period!r}; choose from {', '.join(PERIODS)}")


def aggregate(
    readings: Iterable[Reading], period: str, region: str | None = None
) -> list[PeriodPoint]:
    """Group readings into period buckets per region and fold each into a PeriodPoint."""
    if period not in PERIODS:
        raise ValidationError(f"unknown period {period!r}; choose from {', '.join(PERIODS)}")
    region_code = region.strip().upper() if region else None

    buckets: dict[tuple[str, datetime], list[Reading]] = defaultdict(list)
    for r in readings:
        if region_code and r.region != region_code:
            continue
        buckets[(r.region, floor_period(r.timestamp, period))].append(r)

    points: list[PeriodPoint] = []
    for (reg, start), group in buckets.items():
        avg_price, peak_price = analytics.price_stats(group)
        avg_demand, peak_demand = analytics.demand_stats(group)
        points.append(
            PeriodPoint(
                period_start=start,
                region=reg,
                total_generation_mwh=analytics.total_generation_mwh(group),
                renewable_share=analytics.renewable_share(group),
                total_emissions_tco2e=analytics.total_emissions(group),
                emissions_intensity=analytics.emissions_intensity(group),
                avg_price=avg_price,
                peak_price=peak_price,
                avg_demand_mw=avg_demand,
                peak_demand_mw=peak_demand,
                by_category_mwh=analytics.generation_by_category(group),
            )
        )
    points.sort(key=lambda p: (p.region, p.period_start))
    return points
