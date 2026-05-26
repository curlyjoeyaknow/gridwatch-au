from datetime import UTC, datetime, timedelta

import pytest

from gridwatch.adapters.jsonl_ledger import JsonlEventLedger
from gridwatch.adapters.parquet_ledger import ParquetEventLedger
from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.ingest import IngestEvent
from gridwatch.contracts.readings import PowerReading
from gridwatch.domain.replay import replay_to_regions

TS = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


def _events(value, fuel, ingested_at, batch):
    reading = PowerReading("SA1", TS, value, 30, fuel=classify(fuel))
    return [
        IngestEvent.from_reading(
            reading, source="openelectricity", batch_id=batch, ingested_at=ingested_at
        )
    ]


def _ledger(repo_cls, tmp_path):
    target = tmp_path / ("ledger.jsonl" if repo_cls is JsonlEventLedger else "ledger_dir")
    return repo_cls(target)


@pytest.mark.parametrize("repo_cls", [JsonlEventLedger, ParquetEventLedger])
def test_append_then_read_all_round_trip(tmp_path, repo_cls):
    ledger = _ledger(repo_cls, tmp_path)
    ledger.append(_events(100.0, "wind", TS, "b1"))
    out = ledger.read_all()
    assert len(out) == 1
    assert isinstance(out[0], IngestEvent)
    assert out[0].to_reading() == PowerReading("SA1", TS, 100.0, 30, fuel=classify("wind"))


@pytest.mark.parametrize("repo_cls", [JsonlEventLedger, ParquetEventLedger])
def test_append_is_additive_not_overwrite(tmp_path, repo_cls):
    ledger = _ledger(repo_cls, tmp_path)
    ledger.append(_events(100.0, "wind", TS, "b1"))
    ledger.append(_events(50.0, "coal_black", TS, "b2"))
    assert len(ledger.read_all()) == 2


@pytest.mark.parametrize("repo_cls", [JsonlEventLedger, ParquetEventLedger])
def test_empty_ledger_reads_empty(tmp_path, repo_cls):
    assert _ledger(repo_cls, tmp_path).read_all() == []


def test_replay_dedups_keeping_latest_ingest(tmp_path):
    # same (region, metric, fuel, timestamp), two ingests: latest value should win
    early = _events(100.0, "wind", TS, "b1")
    late = _events(120.0, "wind", TS + timedelta(seconds=0), "b2")
    # bump the ingested_at on the late batch
    late = [
        IngestEvent.from_reading(
            PowerReading("SA1", TS, 120.0, 30, fuel=classify("wind")),
            source="openelectricity",
            batch_id="b2",
            ingested_at=datetime(2026, 5, 26, 14, 0, tzinfo=UTC),
        )
    ]
    regions = replay_to_regions(early + late)
    assert len(regions) == 1
    readings = regions[0].readings
    assert len(readings) == 1
    assert readings[0].value == pytest.approx(120.0)  # latest ingest wins
