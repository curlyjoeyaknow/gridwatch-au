"""CsvRepository — flat export/interop format (ADR-004).

One row per reading. JSON is authoritative; CSV is the spreadsheet-friendly view.
"""

from __future__ import annotations

import csv
from pathlib import Path

from gridwatch.adapters.serde import reading_from_row
from gridwatch.domain.region import Region
from gridwatch.exceptions import PersistenceError, ValidationError
from gridwatch.ports.repository import Repository

FIELDS = ["region", "metric", "fuel_tech", "timestamp", "value", "unit", "interval_minutes"]


class CsvRepository(Repository):
    def save(self, regions: list[Region], path: str | Path) -> None:
        try:
            with open(path, "w", newline="", encoding="utf-8") as handle:
                writer = csv.DictWriter(handle, fieldnames=FIELDS)
                writer.writeheader()
                for region in regions:
                    for reading in region.readings:
                        writer.writerow(reading.to_row())
        except OSError as exc:
            raise PersistenceError(f"could not write {path}: {exc}") from exc

    def load(self, path: str | Path) -> list[Region]:
        try:
            with open(path, newline="", encoding="utf-8") as handle:
                rows = list(csv.DictReader(handle))
        except OSError as exc:
            raise PersistenceError(f"could not read {path}: {exc}") from exc

        regions: dict[str, Region] = {}
        try:
            for row in rows:
                if not row.get("fuel_tech"):
                    row["fuel_tech"] = None
                reading = reading_from_row(row)
                region = regions.get(reading.region)
                if region is None:
                    region = Region(reading.region)
                    regions[reading.region] = region
                region.add_reading(reading)
        except (ValidationError, ValueError) as exc:
            raise PersistenceError(f"corrupt CSV in {path}: {exc}") from exc
        return list(regions.values())
