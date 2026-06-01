"""JsonRepository — canonical, loss-less persistence."""

from __future__ import annotations

import json
from pathlib import Path

from gridwatch.adapters.serde import reading_from_row
from gridwatch.domain.region import Region
from gridwatch.exceptions import PersistenceError, ValidationError
from gridwatch.ports.repository import Repository

SCHEMA_VERSION = 1


class JsonRepository(Repository):
    def save(self, regions: list[Region], path: str | Path) -> None:
        payload = {
            "version": SCHEMA_VERSION,
            "regions": [
                {
                    "code": region.code,
                    "name": region.name,
                    "readings": [r.to_row() for r in region.readings],
                }
                for region in regions
            ],
        }
        try:
            Path(path).write_text(json.dumps(payload, indent=2))
        except OSError as exc:
            raise PersistenceError(f"could not write {path}: {exc}") from exc

    def load(self, path: str | Path) -> list[Region]:
        try:
            payload = json.loads(Path(path).read_text())
        except (OSError, ValueError) as exc:
            raise PersistenceError(f"could not read {path}: {exc}") from exc

        try:
            regions = []
            for entry in payload["regions"]:
                region = Region(entry["code"], entry.get("name", ""))
                region.add_readings(reading_from_row(row) for row in entry["readings"])
                regions.append(region)
            return regions
        except (KeyError, TypeError, ValidationError) as exc:
            raise PersistenceError(f"corrupt dataset in {path}: {exc}") from exc
