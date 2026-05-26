from datetime import UTC, datetime

import pytest

from gridwatch.application.query import QueryResult, query_readings
from gridwatch.contracts.fueltech import FuelCategory, classify
from gridwatch.contracts.readings import PowerReading, PriceReading
from gridwatch.exceptions import ValidationError

TS = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


def _p(value, fuel, region="SA1"):
    return PowerReading(region, TS, value, 30, fuel=classify(fuel))


READINGS = [
    _p(100.0, "wind"),
    _p(50.0, "coal_black"),
    _p(30.0, "solar_utility"),
    _p(200.0, "hydro", region="TAS1"),
    PriceReading("SA1", TS, 80.0, 5),
]


def test_returns_query_result():
    assert isinstance(query_readings(READINGS), QueryResult)


def test_filter_by_region():
    result = query_readings(READINGS, region="TAS1")
    assert result.total == 1 and result.rows[0]["region"] == "TAS1"


def test_filter_by_metric_and_renewable_only():
    result = query_readings(READINGS, metric="power", renewable_only=True)
    assert result.total == 3  # wind, solar, hydro


def test_filter_by_category_enum_and_name():
    assert query_readings(READINGS, category=FuelCategory.COAL).total == 1
    assert query_readings(READINGS, category="wind").total == 1


def test_value_range():
    result = query_readings(READINGS, metric="power", min_value=60.0)
    assert sorted(r["value"] for r in result.rows) == [100.0, 200.0]


def test_sort_descending_by_value():
    result = query_readings(READINGS, metric="power", sort_by="value", descending=True)
    assert [r["value"] for r in result.rows][0] == 200.0


def test_pagination_keeps_total():
    result = query_readings(READINGS, sort_by="value", limit=2, offset=0)
    assert result.total == 5
    assert len(result.rows) == 2
    assert result.limit == 2 and result.offset == 0


def test_invalid_sort_key_raises():
    with pytest.raises(ValidationError):
        query_readings(READINGS, sort_by="nope")


def test_unknown_category_name_raises():
    with pytest.raises(ValidationError):
        query_readings(READINGS, category="unobtanium")


def test_empty_input():
    result = query_readings([])
    assert result.total == 0 and result.rows == []
