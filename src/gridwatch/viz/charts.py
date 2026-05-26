"""Visualisations (Track 4) — matplotlib renderers over readings & summaries.

The Agg backend is selected up front so charts render headlessly (CI, servers).
Each renderer raises `ValidationError` when there is nothing to plot, so the CLI
can report it cleanly rather than emit a blank image.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import datetime
from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless; must precede pyplot import

import matplotlib.pyplot as plt  # noqa: E402

from gridwatch.contracts.fueltech import RENEWABLE_CATEGORIES, FuelCategory  # noqa: E402
from gridwatch.contracts.readings import (  # noqa: E402
    DemandReading,
    EmissionReading,
    PowerReading,
)
from gridwatch.contracts.summary import RegionSummary  # noqa: E402
from gridwatch.domain.region import Region  # noqa: E402
from gridwatch.exceptions import ValidationError  # noqa: E402


def _floor(ts: datetime, minutes: int) -> datetime:
    return ts.replace(minute=(ts.minute // minutes) * minutes, second=0, microsecond=0)


def _bucketed_generation(region: Region, minutes: int = 30):
    """Return (axis, categories, ys): generation MW averaged into time buckets per fuel."""
    power = [
        r for r in region.readings if isinstance(r, PowerReading) and r.fuel.counts_as_generation
    ]
    if not power:
        return [], [], []
    buckets: dict[FuelCategory, dict[datetime, list[float]]] = defaultdict(
        lambda: defaultdict(list)
    )
    axis_set: set[datetime] = set()
    for r in power:
        bucket = _floor(r.timestamp, minutes)
        buckets[r.fuel.category][bucket].append(r.value)
        axis_set.add(bucket)
    axis = sorted(axis_set)
    categories = sorted(buckets, key=lambda c: c.name)
    ys = []
    for category in categories:
        per_bucket = buckets[category]
        ys.append(
            [sum(per_bucket[b]) / len(per_bucket[b]) if b in per_bucket else 0.0 for b in axis]
        )
    return axis, categories, ys


def _save(fig, path: str | Path) -> Path:
    out = Path(path)
    out.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out, dpi=110, bbox_inches="tight")
    plt.close(fig)
    return out


def fuel_mix_chart(summary: RegionSummary, path: str | Path) -> Path:
    """Pie of generation by fuel category for one region."""
    data = summary.by_category_mwh
    if not data:
        raise ValidationError(f"no generation to plot for {summary.region}")
    labels = [c.name.title() for c in data]
    values = list(data.values())
    fig, ax = plt.subplots(figsize=(7, 5))
    ax.pie(values, labels=labels, autopct="%1.1f%%", startangle=90)
    ax.axis("equal")
    ax.set_title(f"{summary.region} — generation mix by fuel (MWh, last 7d)")
    return _save(fig, path)


def renewable_share_chart(summaries: list[RegionSummary], path: str | Path) -> Path:
    """Bar of renewable share (%) across regions."""
    rows = [s for s in summaries if s.total_generation_mwh > 0]
    if not rows:
        raise ValidationError("no regions with generation to plot")
    regions = [s.region for s in rows]
    shares = [s.renewable_share * 100 for s in rows]
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(regions, shares, color="#2e8b57")
    ax.bar_label(bars, fmt="%.1f%%")
    ax.set_ylabel("Renewable share (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Renewable share by region (last 7d)")
    return _save(fig, path)


def emissions_chart(summaries: list[RegionSummary], path: str | Path) -> Path:
    """Bar of emissions intensity (tCO2e/MWh) across regions."""
    rows = [s for s in summaries if s.reading_count > 0]
    if not rows:
        raise ValidationError("no regions to plot")
    regions = [s.region for s in rows]
    intensity = [s.emissions_intensity for s in rows]
    fig, ax = plt.subplots(figsize=(7, 5))
    bars = ax.bar(regions, intensity, color="#a0522d")
    ax.bar_label(bars, fmt="%.3f")
    ax.set_ylabel("Emissions intensity (tCO₂e/MWh)")
    ax.set_title("Grid emissions intensity by region (last 7d)")
    return _save(fig, path)


def price_trend_chart(region: Region, path: str | Path) -> Path:
    """Line of spot price (AUD/MWh) over time for one region."""
    prices = sorted(region.filter(metric="price"), key=lambda r: r.timestamp)
    if not prices:
        raise ValidationError(f"no price readings to plot for {region.code}")
    xs = [r.timestamp for r in prices]
    ys = [r.value for r in prices]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(xs, ys, color="#1f77b4", linewidth=0.9)
    ax.set_ylabel("Price (AUD/MWh)")
    ax.set_title(f"{region.code} — spot price (last 7d)")
    fig.autofmt_xdate()
    return _save(fig, path)


def generation_stack_chart(region: Region, path: str | Path) -> Path:
    """Stacked area of generation by fuel category over time (the classic NEM chart)."""
    axis, categories, ys = _bucketed_generation(region)
    if not axis:
        raise ValidationError(f"no generation to plot for {region.code}")
    fig, ax = plt.subplots(figsize=(9, 5))
    ax.stackplot(axis, *ys, labels=[c.name.title() for c in categories])
    ax.legend(loc="upper left", fontsize=8, ncol=2)
    ax.set_ylabel("Generation (MW)")
    ax.set_title(f"{region.code} — generation by fuel over time (last 7d)")
    fig.autofmt_xdate()
    return _save(fig, path)


def renewable_share_over_time(region: Region, path: str | Path) -> Path:
    """Line of the renewable share (%) of generation over time."""
    axis, categories, ys = _bucketed_generation(region)
    if not axis:
        raise ValidationError(f"no generation to plot for {region.code}")
    share = []
    for j in range(len(axis)):
        total = sum(ys[i][j] for i in range(len(categories)))
        renewable = sum(ys[i][j] for i, c in enumerate(categories) if c in RENEWABLE_CATEGORIES)
        share.append((renewable / total * 100) if total > 0 else 0.0)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(axis, share, color="#2e8b57", linewidth=1.1)
    ax.set_ylim(0, 100)
    ax.set_ylabel("Renewable share (%)")
    ax.set_title(f"{region.code} — renewable share over time (last 7d)")
    fig.autofmt_xdate()
    return _save(fig, path)


def demand_vs_generation_chart(region: Region, path: str | Path) -> Path:
    """Lines of total generation and demand over time."""
    axis, categories, ys = _bucketed_generation(region)
    demand_raw = [r for r in region.readings if isinstance(r, DemandReading)]
    if not axis and not demand_raw:
        raise ValidationError(f"nothing to plot for {region.code}")
    fig, ax = plt.subplots(figsize=(9, 4))
    if axis:
        total_gen = [sum(ys[i][j] for i in range(len(categories))) for j in range(len(axis))]
        ax.plot(axis, total_gen, label="Total generation", color="#1f77b4", linewidth=1.0)
    if demand_raw:
        demand_buckets: dict[datetime, list[float]] = defaultdict(list)
        for r in demand_raw:
            demand_buckets[_floor(r.timestamp, 30)].append(r.value)
        dx = sorted(demand_buckets)
        dy = [sum(demand_buckets[b]) / len(demand_buckets[b]) for b in dx]
        ax.plot(dx, dy, label="Demand", color="#d62728", linewidth=1.0)
    ax.legend(loc="upper left", fontsize=8)
    ax.set_ylabel("MW")
    ax.set_title(f"{region.code} — demand vs generation (last 7d)")
    fig.autofmt_xdate()
    return _save(fig, path)


def emissions_over_time(region: Region, path: str | Path) -> Path:
    """Line of total emissions (tCO2e) per time bucket."""
    emissions = [r for r in region.readings if isinstance(r, EmissionReading)]
    if not emissions:
        raise ValidationError(f"no emissions to plot for {region.code}")
    buckets: dict[datetime, float] = defaultdict(float)
    for r in emissions:
        buckets[_floor(r.timestamp, 30)] += r.value
    axis = sorted(buckets)
    fig, ax = plt.subplots(figsize=(9, 4))
    ax.plot(axis, [buckets[b] for b in axis], color="#a0522d", linewidth=1.0)
    ax.set_ylabel("Emissions (tCO₂e / 30 min)")
    ax.set_title(f"{region.code} — emissions over time (last 7d)")
    fig.autofmt_xdate()
    return _save(fig, path)


def price_duration_curve(region: Region, path: str | Path) -> Path:
    """Price duration curve: spot prices sorted high→low vs % of intervals."""
    prices = sorted((r.value for r in region.filter(metric="price")), reverse=True)
    if not prices:
        raise ValidationError(f"no price readings to plot for {region.code}")
    xs = [i / len(prices) * 100 for i in range(len(prices))]
    fig, ax = plt.subplots(figsize=(8, 4))
    ax.plot(xs, prices, color="#1f77b4", linewidth=1.1)
    ax.axhline(0, color="grey", linewidth=0.5)
    ax.set_xlabel("% of intervals at or above price")
    ax.set_ylabel("Price (AUD/MWh)")
    ax.set_title(f"{region.code} — price duration curve (last 7d)")
    return _save(fig, path)
