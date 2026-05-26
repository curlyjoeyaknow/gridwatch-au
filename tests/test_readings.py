from dataclasses import FrozenInstanceError
from datetime import UTC, datetime

import pytest

from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import (
    DemandReading,
    EmissionReading,
    PowerReading,
    PriceReading,
    Reading,
)
from gridwatch.exceptions import ValidationError

TS = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


def test_reading_base_is_abstract():
    with pytest.raises(TypeError):
        Reading("SA1", TS, 1.0, 5)


def test_subclasses_carry_their_own_metric_and_unit():
    cases = [
        (PowerReading("SA1", TS, 100.0, 5, fuel=classify("wind")), "power", "MW"),
        (EmissionReading("SA1", TS, 2.5, 5, fuel=classify("coal_black")), "emissions", "tCO2e"),
        (PriceReading("SA1", TS, 84.2, 5), "price", "AUD/MWh"),
        (DemandReading("SA1", TS, 1500.0, 5), "demand", "MW"),
    ]
    for reading, metric, unit in cases:
        assert (reading.metric, reading.unit) == (metric, unit)


def test_to_row_is_polymorphic():
    power_row = PowerReading("SA1", TS, 100.0, 30, fuel=classify("wind")).to_row()
    price_row = PriceReading("SA1", TS, 84.2, 5).to_row()
    assert power_row["fuel_tech"] == "wind" and power_row["unit"] == "MW"
    assert power_row["interval_minutes"] == 30
    assert price_row["fuel_tech"] is None and price_row["metric"] == "price"


def test_energy_integration_uses_interval():
    # 120 MW sustained over a 30-minute interval = 60 MWh
    reading = PowerReading("SA1", TS, 120.0, 30, fuel=classify("wind"))
    assert reading.energy_mwh == pytest.approx(60.0)


def test_label_includes_fuel_when_present():
    assert "wind" in PowerReading("SA1", TS, 1.0, 5, fuel=classify("wind")).label()
    assert "wind" not in PriceReading("SA1", TS, 1.0, 5).label()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"region": "", "timestamp": TS, "value": 1.0, "interval_minutes": 5},
        {"region": "SA1", "timestamp": "not-a-date", "value": 1.0, "interval_minutes": 5},
        {"region": "SA1", "timestamp": TS, "value": float("nan"), "interval_minutes": 5},
        {"region": "SA1", "timestamp": TS, "value": float("inf"), "interval_minutes": 5},
        {"region": "SA1", "timestamp": TS, "value": 1.0, "interval_minutes": 0},
        {"region": "SA1", "timestamp": TS, "value": 1.0, "interval_minutes": -5},
    ],
)
def test_validation_rejects_bad_inputs(kwargs):
    with pytest.raises(ValidationError):
        PriceReading(**kwargs)


def test_readings_are_frozen_and_value_comparable():
    a = PriceReading("SA1", TS, 1.0, 5)
    b = PriceReading("SA1", TS, 1.0, 5)
    assert a == b
    with pytest.raises(FrozenInstanceError):
        a.value = 2.0
