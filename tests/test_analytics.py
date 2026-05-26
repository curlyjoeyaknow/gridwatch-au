from datetime import UTC, datetime

import pytest

from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import EmissionReading, PowerReading, PriceReading
from gridwatch.contracts.summary import RegionSummary
from gridwatch.domain import analytics
from gridwatch.domain.region import Region

TS = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


def _p(value, fuel, interval=60):
    # interval=60 -> 1 hour -> value MW == value MWh, keeps the arithmetic obvious
    return PowerReading("SA1", TS, value, interval, fuel=classify(fuel))


def test_total_and_renewable_generation():
    rs = [_p(100.0, "wind"), _p(100.0, "coal_black")]
    assert analytics.total_generation_mwh(rs) == pytest.approx(200.0)
    assert analytics.renewable_generation_mwh(rs) == pytest.approx(100.0)
    assert analytics.renewable_share(rs) == pytest.approx(0.5)


def test_non_generation_flows_excluded_from_share():
    rs = [_p(100.0, "wind"), _p(999.0, "imports"), _p(50.0, "battery_discharging")]
    assert analytics.total_generation_mwh(rs) == pytest.approx(100.0)
    assert analytics.renewable_share(rs) == pytest.approx(1.0)


def test_emissions_and_intensity():
    coal = classify("coal_black")
    rs = [_p(100.0, "coal_black"), EmissionReading("SA1", TS, 90.0, 60, fuel=coal)]
    assert analytics.total_emissions(rs) == pytest.approx(90.0)
    assert analytics.emissions_intensity(rs) == pytest.approx(0.9)


def test_price_stats():
    rs = [PriceReading("SA1", TS, 80.0, 5), PriceReading("SA1", TS, 120.0, 5)]
    avg, peak = analytics.price_stats(rs)
    assert avg == pytest.approx(100.0) and peak == pytest.approx(120.0)


def test_empty_inputs_are_safe():
    assert analytics.total_generation_mwh([]) == 0.0
    assert analytics.renewable_share([]) == 0.0
    assert analytics.emissions_intensity([]) == 0.0
    assert analytics.price_stats([]) == (None, None)


def test_summarise_returns_region_summary():
    reg = Region("SA1")
    reg.add_readings(
        [
            _p(100.0, "wind"),
            _p(100.0, "coal_black"),
            EmissionReading("SA1", TS, 90.0, 60, fuel=classify("coal_black")),
            PriceReading("SA1", TS, 100.0, 5),
        ]
    )
    s = analytics.summarise(reg)
    assert isinstance(s, RegionSummary)
    assert s.region == "SA1"
    assert s.total_generation_mwh == pytest.approx(200.0)
    assert s.renewable_share == pytest.approx(0.5)
    assert s.emissions_intensity == pytest.approx(0.45)  # 90 / 200
    assert s.avg_price == pytest.approx(100.0)
    assert s.as_dict()["renewable_share_pct"] == pytest.approx(50.0)
