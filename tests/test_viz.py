from datetime import UTC, datetime, timedelta

import pytest

from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import EmissionReading, PowerReading, PriceReading
from gridwatch.domain import analytics
from gridwatch.domain.region import Region
from gridwatch.exceptions import ValidationError
from gridwatch.viz import charts

TS = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


def _region():
    reg = Region("SA1")
    reg.add_readings(
        [
            PowerReading("SA1", TS, 100.0, 60, fuel=classify("wind")),
            PowerReading("SA1", TS, 50.0, 60, fuel=classify("coal_black")),
            EmissionReading("SA1", TS, 45.0, 60, fuel=classify("coal_black")),
            PriceReading("SA1", TS, 80.0, 5),
            PriceReading("SA1", TS + timedelta(minutes=5), 120.0, 5),
        ]
    )
    return reg


def test_fuel_mix_chart_writes_a_png(tmp_path):
    path = charts.fuel_mix_chart(analytics.summarise(_region()), tmp_path / "mix.png")
    assert path.exists() and path.stat().st_size > 0


def test_renewable_share_chart_writes_a_png(tmp_path):
    summaries = [analytics.summarise(_region())]
    path = charts.renewable_share_chart(summaries, tmp_path / "share.png")
    assert path.exists() and path.stat().st_size > 0


def test_emissions_chart_writes_a_png(tmp_path):
    summaries = [analytics.summarise(_region())]
    path = charts.emissions_chart(summaries, tmp_path / "emissions.png")
    assert path.exists() and path.stat().st_size > 0


def test_price_trend_chart_writes_a_png(tmp_path):
    path = charts.price_trend_chart(_region(), tmp_path / "price.png")
    assert path.exists() and path.stat().st_size > 0


def test_charts_raise_on_nothing_to_plot(tmp_path):
    empty_summary = analytics.summarise(Region("NSW1"))
    with pytest.raises(ValidationError):
        charts.fuel_mix_chart(empty_summary, tmp_path / "a.png")
    with pytest.raises(ValidationError):
        charts.price_trend_chart(Region("NSW1"), tmp_path / "b.png")
    with pytest.raises(ValidationError):
        charts.renewable_share_chart([], tmp_path / "c.png")
