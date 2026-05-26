from datetime import UTC, datetime

import pytest

from gridwatch.adapters.fake_source import FakeDataSource
from gridwatch.adapters.jsonl_ledger import JsonlEventLedger
from gridwatch.application.manager import EnergyGridManager
from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import PowerReading
from gridwatch.exceptions import DataSourceError

TS = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


def _source():
    return FakeDataSource(
        {
            "SA1": [PowerReading("SA1", TS, 100.0, 30, fuel=classify("wind"))],
            "TAS1": [PowerReading("TAS1", TS, 80.0, 30, fuel=classify("hydro"))],
        }
    )


def test_bulk_fetch_appends_events_to_ledger(tmp_path):
    ledger = JsonlEventLedger(tmp_path / "ledger.jsonl")
    mgr = EnergyGridManager(source=_source())
    counts = mgr.bulk_fetch(ledger, regions=["SA1", "TAS1"])
    assert counts == {"SA1": 1, "TAS1": 1}
    assert len(ledger.read_all()) == 2


def test_load_from_ledger_rebuilds_regions(tmp_path):
    ledger = JsonlEventLedger(tmp_path / "ledger.jsonl")
    mgr = EnergyGridManager(source=_source())
    mgr.bulk_fetch(ledger, regions=["SA1", "TAS1"])

    fresh = EnergyGridManager()
    fresh.load_from_ledger(ledger)
    assert {r.code for r in fresh.regions()} == {"SA1", "TAS1"}
    assert len(fresh.get_region("SA1")) == 1


def test_repeated_bulk_fetch_grows_ledger_but_state_dedups(tmp_path):
    ledger = JsonlEventLedger(tmp_path / "ledger.jsonl")
    mgr = EnergyGridManager(source=_source())
    mgr.bulk_fetch(ledger, regions=["SA1"])
    mgr.bulk_fetch(ledger, regions=["SA1"])
    assert len(ledger.read_all()) == 2  # history grew

    mgr.load_from_ledger(ledger)
    assert len(mgr.get_region("SA1")) == 1  # derived state deduped


def test_bulk_fetch_without_source_raises(tmp_path):
    ledger = JsonlEventLedger(tmp_path / "ledger.jsonl")
    with pytest.raises(DataSourceError):
        EnergyGridManager().bulk_fetch(ledger, regions=["SA1"])
