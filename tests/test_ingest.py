from datetime import UTC, datetime

import pytest

from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.ingest import IngestEvent
from gridwatch.contracts.readings import EmissionReading, PowerReading, PriceReading

TS = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)
INGESTED = datetime(2026, 5, 26, 13, 0, tzinfo=UTC)


def test_from_reading_captures_envelope_and_payload():
    reading = PowerReading("SA1", TS, 100.0, 30, fuel=classify("wind"))
    event = IngestEvent.from_reading(
        reading, source="openelectricity", batch_id="b1", ingested_at=INGESTED
    )
    assert event.region == "SA1"
    assert event.metric == "power"
    assert event.fuel_tech == "wind"
    assert event.value == pytest.approx(100.0)
    assert event.source == "openelectricity" and event.batch_id == "b1"
    assert event.event_id  # generated


@pytest.mark.parametrize(
    "reading",
    [
        PowerReading("SA1", TS, 100.0, 30, fuel=classify("wind")),
        EmissionReading("SA1", TS, 5.0, 30, fuel=classify("gas_ccgt")),
        PriceReading("SA1", TS, 84.2, 5),
    ],
)
def test_event_rebuilds_the_same_reading(reading):
    event = IngestEvent.from_reading(reading, source="x", batch_id="b", ingested_at=INGESTED)
    assert event.to_reading() == reading


def test_row_round_trip():
    reading = PowerReading("SA1", TS, 100.0, 30, fuel=classify("wind"))
    event = IngestEvent.from_reading(reading, source="x", batch_id="b", ingested_at=INGESTED)
    assert IngestEvent.from_row(event.to_row()) == event
