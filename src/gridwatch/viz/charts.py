"""Visualisations (Track 4) — matplotlib renderers over readings & summaries.

The Agg backend is selected up front so charts render headlessly (CI, servers).
Each renderer raises `ValidationError` when there is nothing to plot, so the CLI
can report it cleanly rather than emit a blank image.
"""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")  # headless; must precede pyplot import

import matplotlib.pyplot as plt  # noqa: E402

from gridwatch.contracts.summary import RegionSummary  # noqa: E402
from gridwatch.domain.region import Region  # noqa: E402
from gridwatch.exceptions import ValidationError  # noqa: E402


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
