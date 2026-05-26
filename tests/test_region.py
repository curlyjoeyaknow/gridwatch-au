from datetime import UTC, datetime, timedelta

import pytest

from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import PowerReading, PriceReading
from gridwatch.domain.region import Region
from gridwatch.exceptions import ValidationError

TS = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


def _power(value, fuel, ts=TS, interval=30):
    return PowerReading("SA1", ts, value, interval, fuel=classify(fuel))


def test_region_resolves_friendly_name():
    assert Region("SA1").name == "South Australia"


def test_readings_view_is_read_only_snapshot():
    reg = Region("SA1")
    reg.add_reading(PriceReading("SA1", TS, 80.0, 5))
    view = reg.readings
    assert isinstance(view, tuple) and len(view) == 1
    # the exposed view cannot mutate internal state
    assert not hasattr(view, "append")


def test_add_reading_rejects_region_mismatch():
    reg = Region("SA1")
    with pytest.raises(ValidationError):
        reg.add_reading(PriceReading("NSW1", TS, 80.0, 5))


def test_filter_by_metric_and_renewable_only():
    reg = Region("SA1")
    reg.add_readings(
        [
            _power(100.0, "wind"),
            _power(50.0, "coal_black"),
            PriceReading("SA1", TS, 80.0, 5),
        ]
    )
    assert len(reg.filter(metric="power")) == 2
    renewables = reg.filter(metric="power", renewable_only=True)
    assert [r.fuel.raw for r in renewables] == ["wind"]


def test_filter_by_time_window_and_value_threshold():
    reg = Region("SA1")
    reg.add_readings(
        [
            _power(100.0, "wind", ts=TS),
            _power(20.0, "wind", ts=TS + timedelta(hours=1)),
            _power(300.0, "wind", ts=TS + timedelta(hours=2)),
        ]
    )
    windowed = reg.filter(start=TS + timedelta(minutes=30), end=TS + timedelta(hours=1, minutes=30))
    assert [r.value for r in windowed] == [20.0]
    big = reg.filter(min_value=50.0)
    assert sorted(r.value for r in big) == [100.0, 300.0]


def test_remove_where_and_clear():
    reg = Region("SA1")
    reg.add_readings([_power(100.0, "wind"), _power(50.0, "coal_black")])
    removed = reg.remove_where(lambda r: not r.fuel.is_renewable)
    assert removed == 1 and len(reg) == 1
    reg.clear()
    assert len(reg) == 0
