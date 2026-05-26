from datetime import UTC, datetime

import pytest

from gridwatch.adapters.fake_source import FakeDataSource
from gridwatch.adapters.json_repo import JsonRepository
from gridwatch.application.manager import EnergyGridManager
from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import EmissionReading, PowerReading, PriceReading
from gridwatch.contracts.summary import RegionSummary
from gridwatch.exceptions import DataSourceError, RegionNotFoundError

TS = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


def _sa1_readings():
    return [
        PowerReading("SA1", TS, 100.0, 60, fuel=classify("wind")),
        PowerReading("SA1", TS, 100.0, 60, fuel=classify("coal_black")),
        EmissionReading("SA1", TS, 90.0, 60, fuel=classify("coal_black")),
        PriceReading("SA1", TS, 100.0, 5),
    ]


def _manager_with_sa1():
    src = FakeDataSource({"SA1": _sa1_readings()})
    mgr = EnergyGridManager(source=src)
    mgr.import_region("SA1")
    return mgr


def test_import_region_populates_from_source():
    mgr = _manager_with_sa1()
    region = mgr.get_region("SA1")
    assert len(region) == 4


def test_import_replaces_on_refetch():
    mgr = _manager_with_sa1()
    mgr.import_region("SA1")  # second import should not duplicate
    assert len(mgr.get_region("SA1")) == 4


def test_get_unknown_region_raises():
    with pytest.raises(RegionNotFoundError):
        EnergyGridManager().get_region("NSW1")


def test_import_without_source_raises():
    with pytest.raises(DataSourceError):
        EnergyGridManager().import_region("SA1")


def test_search_across_and_within_regions():
    mgr = _manager_with_sa1()
    renewables = mgr.search(region="SA1", metric="power", renewable_only=True)
    assert [r.fuel.raw for r in renewables] == ["wind"]
    all_power = mgr.search(metric="power")
    assert len(all_power) == 2


def test_manual_add_and_delete_reading():
    mgr = EnergyGridManager()
    mgr.add_reading(PriceReading("NSW1", TS, 70.0, 5))
    assert len(mgr.get_region("NSW1")) == 1
    removed = mgr.delete_readings("NSW1", lambda r: r.metric == "price")
    assert removed == 1 and len(mgr.get_region("NSW1")) == 0


def test_summarise_and_compare():
    mgr = _manager_with_sa1()
    summary = mgr.summarise("SA1")
    assert isinstance(summary, RegionSummary)
    assert summary.renewable_share == pytest.approx(0.5)
    comparison = mgr.compare()
    assert len(comparison) == 1 and comparison[0].region == "SA1"


def test_save_and_load_round_trip(tmp_path):
    mgr = _manager_with_sa1()
    path = tmp_path / "state.json"
    mgr.save(JsonRepository(), path)

    restored = EnergyGridManager()
    restored.load(JsonRepository(), path)
    assert len(restored.get_region("SA1")) == 4
    assert restored.summarise("SA1").renewable_share == pytest.approx(0.5)
