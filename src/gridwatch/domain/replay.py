"""Replay projection — fold an ingest-event stream into current Regions (ADR-007).

State is derived, not stored: deduplicate by (region, metric, fuel_tech, timestamp),
keeping the observation with the latest `ingested_at` so revisions supersede.
"""

from __future__ import annotations

from collections.abc import Iterable

from gridwatch.contracts.ingest import IngestEvent
from gridwatch.domain.region import Region


def replay_to_regions(events: Iterable[IngestEvent]) -> list[Region]:
    latest: dict[tuple, IngestEvent] = {}
    for event in events:
        key = (event.region, event.metric, event.fuel_tech, event.timestamp)
        current = latest.get(key)
        if current is None or event.ingested_at >= current.ingested_at:
            latest[key] = event

    regions: dict[str, Region] = {}
    for event in latest.values():
        region = regions.get(event.region)
        if region is None:
            region = Region(event.region)
            regions[event.region] = region
        region.add_reading(event.to_reading())
    return list(regions.values())
