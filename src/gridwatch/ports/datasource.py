"""DataSource port — where readings come from (ADR-001).

The core depends on this ABC, never on `requests` or a vendor payload. Adapters
(real API client, fake) implement it and return our `Reading` objects.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from gridwatch.contracts.readings import Reading


class DataSource(ABC):
    @abstractmethod
    def fetch_readings(self, region: str) -> list[Reading]:
        """Return all readings for a region's available window, as typed Readings.

        Implementations must map any vendor shape into Reading objects and raise
        `DataSourceError` on failure — no vendor data crosses this boundary.
        """
