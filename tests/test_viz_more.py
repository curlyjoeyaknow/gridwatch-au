"""Additional chart types (PR #8) — render to PNG, guard empty input."""

from datetime import UTC, datetime, timedelta

import pytest

from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import (
    DemandReading,
    EmissionReading,
    PowerReading,
    PriceReading,
)
from gridwatch.domain.region import Region
from gridwatch.exceptions import ValidationError
from gridwatch.viz import charts

TS = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


def _timeseries_region():
    reg = Region("SA1")
    for i in range(8):
        ts = TS + timedelta(minutes=30 * i)
        reg.add_readings(
            [
                PowerReading("SA1", ts, 100.0 + i, 30, fuel=classify("wind")),
                PowerReading("SA1", ts, 60.0, 30, fuel=classify("coal_black")),
                PowerReading("SA1", ts, 20.0, 30, fuel=classify("solar_utility")),
                DemandReading("SA1", ts, 180.0, 30),
                EmissionReading("SA1", ts, 12.0, 30, fuel=classify("coal_black")),
                PriceReading("SA1", ts, 80.0 + i * 4, 5),
            ]
        )
    return reg


@pytest.mark.parametrize(
    "fn",
    [
        charts.generation_stack_chart,
        charts.price_duration_curve,
        charts.renewable_share_over_time,
        charts.demand_vs_generation_chart,
        charts.emissions_over_time,
    ],
)
def test_chart_writes_png(tmp_path, fn):
    path = fn(_timeseries_region(), tmp_path / f"{fn.__name__}.png")
    assert path.exists() and path.stat().st_size > 0


@pytest.mark.parametrize(
    "fn",
    [
        charts.generation_stack_chart,
        charts.price_duration_curve,
        charts.renewable_share_over_time,
        charts.demand_vs_generation_chart,
        charts.emissions_over_time,
    ],
)
def test_chart_raises_on_empty_region(tmp_path, fn):
    with pytest.raises(ValidationError):
        fn(Region("NSW1"), tmp_path / "x.png")
