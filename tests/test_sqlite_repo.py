"""SqliteRepository round-trips against a REAL on-disk database (ADR-006)."""

from datetime import UTC, datetime

import pytest

from gridwatch.adapters.sqlite_repo import SqliteRepository
from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import (
    DemandReading,
    EmissionReading,
    PowerReading,
    PriceReading,
)
from gridwatch.domain.region import Region
from gridwatch.exceptions import PersistenceError

TS = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


def _sample_regions():
    sa = Region("SA1")
    sa.add_readings(
        [
            PowerReading("SA1", TS, 100.0, 30, fuel=classify("wind")),
            EmissionReading("SA1", TS, 5.0, 30, fuel=classify("gas_ccgt")),
            PriceReading("SA1", TS, 84.2, 5),
            DemandReading("SA1", TS, 1500.0, 5),
        ]
    )
    vic = Region("VIC1")
    vic.add_reading(PowerReading("VIC1", TS, 200.0, 30, fuel=classify("coal_brown")))
    return [sa, vic]


def test_round_trip_preserves_readings_and_types(tmp_path):
    path = tmp_path / "grid.db"
    SqliteRepository().save(_sample_regions(), path)
    assert path.exists()

    loaded = {r.code: r for r in SqliteRepository().load(path)}
    assert set(loaded) == {"SA1", "VIC1"}
    assert len(loaded["SA1"]) == 4
    types = {type(r).__name__ for r in loaded["SA1"].readings}
    assert types == {"PowerReading", "EmissionReading", "PriceReading", "DemandReading"}
    wind = [r for r in loaded["SA1"].readings if r.fuel_tech == "wind"][0]
    assert isinstance(wind, PowerReading)
    assert wind.value == pytest.approx(100.0)


def test_save_is_a_snapshot_replace(tmp_path):
    path = tmp_path / "grid.db"
    repo = SqliteRepository()
    repo.save(_sample_regions(), path)
    repo.save([Region("NSW1")], path)  # second save replaces, not appends
    loaded = {r.code: r for r in repo.load(path)}
    assert set(loaded) == {"NSW1"}


def test_corrupt_database_raises_persistence_error(tmp_path):
    path = tmp_path / "broken.db"
    path.write_text("this is definitely not a sqlite database")
    with pytest.raises(PersistenceError):
        SqliteRepository().load(path)


def test_missing_database_raises_persistence_error(tmp_path):
    with pytest.raises(PersistenceError):
        SqliteRepository().load(tmp_path / "nope.db")
