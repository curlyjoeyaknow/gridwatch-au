"""Repository port — where datasets are saved/loaded (ADR-001, ADR-004).

Speaks in domain terms (`Region`). Concrete adapters (`JsonRepository`,
`CsvRepository`) live in `adapters/` and raise `PersistenceError` on I/O failure.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # avoid a runtime ports -> domain import; annotations are strings
    from gridwatch.domain.region import Region


class Repository(ABC):
    @abstractmethod
    def save(self, regions: list[Region], path: str | Path) -> None:
        """Persist regions (and their readings) to `path`."""

    @abstractmethod
    def load(self, path: str | Path) -> list[Region]:
        """Load regions (and their readings) from `path`."""
