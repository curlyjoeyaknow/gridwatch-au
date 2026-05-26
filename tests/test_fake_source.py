from datetime import UTC, datetime

import pytest

from gridwatch.adapters.fake_source import FakeDataSource
from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import PowerReading, Reading
from gridwatch.exceptions import ValidationError

TS = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


def test_returns_configured_readings():
    src = FakeDataSource({"SA1": [PowerReading("SA1", TS, 100.0, 5, fuel=classify("wind"))]})
    out = src.fetch_readings("SA1")
    assert len(out) == 1 and isinstance(out[0], Reading)


def test_unconfigured_region_returns_empty_list():
    assert FakeDataSource().fetch_readings("NSW1") == []


def test_respects_region_scope():
    with pytest.raises(ValidationError):
        FakeDataSource().fetch_readings("WA1")


def test_set_region_readings():
    src = FakeDataSource()
    src.set("VIC1", [PowerReading("VIC1", TS, 50.0, 5, fuel=classify("hydro"))])
    assert len(src.fetch_readings("VIC1")) == 1
