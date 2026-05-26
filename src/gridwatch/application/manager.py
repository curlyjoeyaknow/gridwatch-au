"""EnergyGridManager — the facade the CLI talks to.

Orchestrates region/reading CRUD, search, live import, summaries, and persistence
through the ports (ADR-001). Holds the loaded regions; everything below it is pure
or behind a port.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from gridwatch.contracts.ingest import IngestEvent
from gridwatch.contracts.readings import Reading
from gridwatch.contracts.regions import NEM_REGIONS, validate_region
from gridwatch.contracts.summary import RegionSummary
from gridwatch.domain import analytics
from gridwatch.domain.region import Region
from gridwatch.domain.replay import replay_to_regions
from gridwatch.exceptions import DataSourceError, RegionNotFoundError
from gridwatch.ports.datasource import DataSource
from gridwatch.ports.ledger import EventLedger
from gridwatch.ports.repository import Repository


class EnergyGridManager:
    def __init__(self, source: DataSource | None = None):
        self._source = source
        self._regions: dict[str, Region] = {}

    # --- regions ----------------------------------------------------------
    def add_region(self, code: str) -> Region:
        region = Region(code)
        self._regions[region.code] = region
        return region

    def get_region(self, code: str) -> Region:
        key = validate_region(code)
        if key not in self._regions:
            raise RegionNotFoundError(f"region {key} is not loaded")
        return self._regions[key]

    def regions(self) -> list[Region]:
        return list(self._regions.values())

    def remove_region(self, code: str) -> None:
        self._regions.pop(validate_region(code), None)

    # --- live import ------------------------------------------------------
    def import_region(self, code: str, source: DataSource | None = None) -> Region:
        src = source or self._source
        if src is None:
            raise DataSourceError("no data source configured for import")
        key = validate_region(code)
        readings = src.fetch_readings(key)
        region = Region(key)  # replace on (re)import to reflect the latest fetch
        region.add_readings(readings)
        self._regions[key] = region
        return region

    # --- bulk fetch + append-only ledger (ADR-007) -----------------------
    def bulk_fetch(
        self,
        ledger: EventLedger,
        source: DataSource | None = None,
        regions: list[str] | None = None,
    ) -> dict[str, int]:
        """Fetch regions and append every reading to the ledger as IngestEvents.

        Returns the per-region event count. Does not mutate in-memory state — call
        `load_from_ledger` to derive it.
        """
        src = source or self._source
        if src is None:
            raise DataSourceError("no data source configured for bulk fetch")
        codes = [validate_region(c) for c in (regions or NEM_REGIONS)]
        batch_id = uuid4().hex
        ingested_at = datetime.now(UTC)
        source_name = getattr(src, "name", "unknown")
        counts: dict[str, int] = {}
        for code in codes:
            readings = src.fetch_readings(code)
            events = [
                IngestEvent.from_reading(
                    r, source=source_name, batch_id=batch_id, ingested_at=ingested_at
                )
                for r in readings
            ]
            ledger.append(events)
            counts[code] = len(events)
        return counts

    def load_from_ledger(self, ledger: EventLedger) -> None:
        """Replace in-memory state with the ledger's replayed (deduplicated) state."""
        self._regions = {r.code: r for r in replay_to_regions(ledger.read_all())}

    # --- manual reading CRUD ---------------------------------------------
    def add_reading(self, reading: Reading) -> None:
        key = validate_region(reading.region)
        region = self._regions.get(key)
        if region is None:
            region = Region(key)
            self._regions[key] = region
        region.add_reading(reading)

    def delete_readings(self, code: str, predicate: Callable[[Reading], bool]) -> int:
        return self.get_region(code).remove_where(predicate)

    # --- search -----------------------------------------------------------
    def search(self, *, region: str | None = None, **criteria) -> list[Reading]:
        regions = [self.get_region(region)] if region else self._regions.values()
        results: list[Reading] = []
        for reg in regions:
            results.extend(reg.filter(**criteria))
        return results

    # --- insight ----------------------------------------------------------
    def summarise(self, code: str) -> RegionSummary:
        return analytics.summarise(self.get_region(code))

    def compare(self) -> list[RegionSummary]:
        return [analytics.summarise(reg) for reg in self._regions.values()]

    # --- persistence ------------------------------------------------------
    def save(self, repo: Repository, path: str | Path) -> None:
        repo.save(self.regions(), path)

    def load(self, repo: Repository, path: str | Path) -> None:
        self._regions = {region.code: region for region in repo.load(path)}
