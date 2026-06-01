"""SqliteRepository — indexed, SQL-backed snapshot storage.

A third interchangeable `Repository` (alongside JSON/CSV). `save` is a snapshot
replace inside one transaction; the append-only history lives in the ledger.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from gridwatch.adapters.serde import reading_from_row
from gridwatch.domain.region import Region
from gridwatch.exceptions import PersistenceError, ValidationError
from gridwatch.ports.repository import Repository

_SCHEMA = """
CREATE TABLE regions (code TEXT PRIMARY KEY, name TEXT);
CREATE TABLE readings (
    region   TEXT NOT NULL,
    metric   TEXT NOT NULL,
    fuel_tech TEXT,
    timestamp TEXT NOT NULL,
    value    REAL NOT NULL,
    unit     TEXT NOT NULL,
    interval_minutes INTEGER NOT NULL
);
CREATE INDEX idx_readings_query ON readings (region, metric, timestamp);
"""

_COLUMNS = ["region", "metric", "fuel_tech", "timestamp", "value", "unit", "interval_minutes"]


class SqliteRepository(Repository):
    def save(self, regions: list[Region], path: str | Path) -> None:
        try:
            with sqlite3.connect(path) as conn:
                conn.execute("DROP TABLE IF EXISTS regions")
                conn.execute("DROP TABLE IF EXISTS readings")
                conn.executescript(_SCHEMA)
                conn.executemany(
                    "INSERT INTO regions (code, name) VALUES (?, ?)",
                    [(r.code, r.name) for r in regions],
                )
                rows = [
                    tuple(reading.to_row()[col] for col in _COLUMNS)
                    for region in regions
                    for reading in region.readings
                ]
                conn.executemany(
                    f"INSERT INTO readings ({', '.join(_COLUMNS)}) "
                    f"VALUES ({', '.join('?' * len(_COLUMNS))})",
                    rows,
                )
        except (sqlite3.Error, OSError) as exc:
            raise PersistenceError(f"could not write SQLite database {path}: {exc}") from exc

    def load(self, path: str | Path) -> list[Region]:
        if not Path(path).exists():
            raise PersistenceError(f"SQLite database not found: {path}")
        try:
            with sqlite3.connect(path) as conn:
                conn.row_factory = sqlite3.Row
                region_rows = conn.execute("SELECT code, name FROM regions").fetchall()
                names = {row["code"]: row["name"] for row in region_rows}
                select = f"SELECT {', '.join(_COLUMNS)} FROM readings"
                reading_rows = [dict(row) for row in conn.execute(select)]
        except (sqlite3.Error, OSError) as exc:
            raise PersistenceError(f"could not read SQLite database {path}: {exc}") from exc

        regions: dict[str, Region] = {code: Region(code, name) for code, name in names.items()}
        try:
            for row in reading_rows:
                reading = reading_from_row(row)
                region = regions.get(reading.region)
                if region is None:
                    region = Region(reading.region)
                    regions[reading.region] = region
                region.add_reading(reading)
        except (ValidationError, ValueError) as exc:
            raise PersistenceError(f"corrupt reading in {path}: {exc}") from exc
        return list(regions.values())
