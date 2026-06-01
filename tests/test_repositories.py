"""Persistence round-trips against REAL files (tmp_path), never mocks."""

from datetime import UTC, datetime

import pytest

from gridwatch.adapters.csv_repo import CsvRepository
from gridwatch.adapters.json_repo import JsonRepository
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


@pytest.mark.parametrize("repo_cls", [JsonRepository, CsvRepository])
def test_round_trip_preserves_readings(tmp_path, repo_cls):
    repo = repo_cls()
    ext = "json" if repo_cls is JsonRepository else "csv"
    path = tmp_path / f"dataset.{ext}"
    repo.save(_sample_regions(), path)
    assert path.exists()

    loaded = {r.code: r for r in repo.load(path)}
    assert set(loaded) == {"SA1", "VIC1"}
    assert len(loaded["SA1"]) == 4
    # the wind power reading rehydrates to the right type/fuel/value
    wind = [r for r in loaded["SA1"].readings if r.fuel_tech == "wind"]
    assert len(wind) == 1
    assert isinstance(wind[0], PowerReading)
    assert wind[0].value == pytest.approx(100.0)
    assert wind[0].metric == "power"


def test_json_preserves_reading_subtypes(tmp_path):
    path = tmp_path / "d.json"
    JsonRepository().save(_sample_regions(), path)
    loaded = {r.code: r for r in JsonRepository().load(path)}
    metrics = {type(r).__name__ for r in loaded["SA1"].readings}
    assert metrics == {"PowerReading", "EmissionReading", "PriceReading", "DemandReading"}


def test_corrupt_json_raises_persistence_error(tmp_path):
    path = tmp_path / "broken.json"
    path.write_text("{ this is not valid json ")
    with pytest.raises(PersistenceError):
        JsonRepository().load(path)


def test_missing_file_raises_persistence_error(tmp_path):
    with pytest.raises(PersistenceError):
        JsonRepository().load(tmp_path / "does-not-exist.json")


def test_csv_round_trip_is_flat_and_reloadable(tmp_path):
    path = tmp_path / "d.csv"
    CsvRepository().save(_sample_regions(), path)
    text = path.read_text()
    assert "region,metric,fuel_tech,timestamp,value,unit,interval_minutes" in text
    loaded = {r.code: r for r in CsvRepository().load(path)}
    assert len(loaded["SA1"]) == 4
