"""FakeDataSource — the only fake in the system, living at the DataSource port.

Lets the core be tested end-to-end with no network.
"""

from __future__ import annotations

from gridwatch.contracts.readings import Reading
from gridwatch.contracts.regions import validate_region
from gridwatch.ports.datasource import DataSource


class FakeDataSource(DataSource):
    name = "fake"

    def __init__(self, readings_by_region: dict[str, list[Reading]] | None = None):
        self._data: dict[str, list[Reading]] = dict(readings_by_region or {})

    def set(self, region: str, readings: list[Reading]) -> None:
        self._data[validate_region(region)] = list(readings)

    def fetch_readings(self, region: str) -> list[Reading]:
        code = validate_region(region)
        return list(self._data.get(code, []))
