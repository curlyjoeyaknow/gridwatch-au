from datetime import UTC, datetime

import pytest

from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import (
    DemandReading,
    EmissionReading,
    PowerReading,
    PriceReading,
)
from gridwatch.domain.aggregate import PeriodPoint, aggregate
from gridwatch.exceptions import ValidationError


def _readings(region="SA1"):
    rows = []
    for day in (1, 2):  # 2026-05-01 (Fri), 2026-05-02 (Sat)
        for hour in (0, 12):
            ts = datetime(2026, 5, day, hour, 0, tzinfo=UTC)
            rows += [
                PowerReading(region, ts, 100.0, 60, fuel=classify("wind")),
                PowerReading(region, ts, 100.0, 60, fuel=classify("coal_black")),
                EmissionReading(region, ts, 90.0, 60, fuel=classify("coal_black")),
                PriceReading(region, ts, 50.0 if hour == 0 else 150.0, 60),
                DemandReading(region, ts, 1000.0, 60),
            ]
    return rows


def test_bucket_counts_per_period():
    rs = _readings()
    assert len(aggregate(rs, "hour")) == 4
    assert len(aggregate(rs, "day")) == 2
    assert len(aggregate(rs, "week")) == 1  # both days fall in the same ISO week
    assert len(aggregate(rs, "month")) == 1


def test_daily_metrics_are_correct():
    point = aggregate(_readings(), "day")[0]
    assert isinstance(point, PeriodPoint)
    # per day: wind 200 MWh + coal 200 MWh = 400; renewable share 0.5
    assert point.total_generation_mwh == pytest.approx(400.0)
    assert point.renewable_share == pytest.approx(0.5)
    assert point.total_emissions_tco2e == pytest.approx(180.0)
    assert point.emissions_intensity == pytest.approx(0.45)  # 180 / 400
    assert point.avg_price == pytest.approx(100.0) and point.peak_price == pytest.approx(150.0)
    assert point.avg_demand_mw == pytest.approx(1000.0)
    assert point.peak_demand_mw == pytest.approx(1000.0)


def test_weekly_aggregates_both_days():
    point = aggregate(_readings(), "week")[0]
    assert point.total_generation_mwh == pytest.approx(800.0)
    assert point.total_emissions_tco2e == pytest.approx(360.0)


def test_groups_by_region_and_filters():
    rs = _readings("SA1") + _readings("TAS1")
    all_days = aggregate(rs, "day")
    assert {p.region for p in all_days} == {"SA1", "TAS1"}
    assert len(all_days) == 4  # 2 regions x 2 days
    only_sa = aggregate(rs, "day", region="sa1")
    assert {p.region for p in only_sa} == {"SA1"}


def test_sorted_by_region_then_period():
    rs = _readings("SA1") + _readings("TAS1")
    points = aggregate(rs, "day")
    keys = [(p.region, p.period_start) for p in points]
    assert keys == sorted(keys)


def test_invalid_period_raises():
    with pytest.raises(ValidationError):
        aggregate(_readings(), "fortnight")


def test_empty_input():
    assert aggregate([], "day") == []


def test_as_dict_shape():
    d = aggregate(_readings(), "day")[0].as_dict()
    assert d["renewable_share_pct"] == pytest.approx(50.0)
    assert d["region"] == "SA1" and "period" in d
