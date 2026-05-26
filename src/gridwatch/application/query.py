"""Query engine — filter, sort, paginate readings for the data-table browse.

Pure: takes an iterable of Readings and query options, returns a `QueryResult` of
serialised rows plus the total match count (for paging). Used by the CLI browse.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable
from dataclasses import dataclass
from datetime import datetime

from gridwatch.contracts.fueltech import FuelCategory
from gridwatch.contracts.readings import Reading
from gridwatch.exceptions import ValidationError

_SORT_KEYS: dict[str, Callable[[Reading], object]] = {
    "timestamp": lambda r: r.timestamp,
    "value": lambda r: r.value,
    "region": lambda r: r.region,
    "metric": lambda r: r.metric,
    "fuel_tech": lambda r: (r.fuel_tech or ""),
}

COLUMNS = ["timestamp", "region", "metric", "fuel_tech", "value", "unit"]


@dataclass(frozen=True)
class QueryResult:
    rows: list[dict]
    total: int
    offset: int
    limit: int | None

    @property
    def shown(self) -> int:
        return len(self.rows)


def _as_category(category) -> FuelCategory | None:
    if category is None or isinstance(category, FuelCategory):
        return category
    try:
        return FuelCategory(str(category).strip().lower())
    except ValueError as exc:
        valid = ", ".join(c.value for c in FuelCategory)
        raise ValidationError(f"unknown fuel category {category!r}; choose from {valid}") from exc


def query_readings(
    readings: Iterable[Reading],
    *,
    region: str | None = None,
    metric: str | None = None,
    fuel_tech: str | None = None,
    category: FuelCategory | str | None = None,
    renewable_only: bool = False,
    min_value: float | None = None,
    max_value: float | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    sort_by: str = "timestamp",
    descending: bool = False,
    limit: int | None = None,
    offset: int = 0,
) -> QueryResult:
    if sort_by not in _SORT_KEYS:
        raise ValidationError(f"cannot sort by {sort_by!r}; choose from {sorted(_SORT_KEYS)}")
    cat = _as_category(category)
    region_code = region.strip().upper() if region else None

    matched: list[Reading] = []
    for r in readings:
        if region_code and r.region != region_code:
            continue
        if metric and r.metric != metric:
            continue
        if fuel_tech and r.fuel_tech != fuel_tech:
            continue
        fuel = getattr(r, "fuel", None)
        if cat is not None and (fuel is None or fuel.category is not cat):
            continue
        if renewable_only and (fuel is None or not fuel.is_renewable):
            continue
        if min_value is not None and r.value < min_value:
            continue
        if max_value is not None and r.value > max_value:
            continue
        if start is not None and r.timestamp < start:
            continue
        if end is not None and r.timestamp > end:
            continue
        matched.append(r)

    matched.sort(key=_SORT_KEYS[sort_by], reverse=descending)
    total = len(matched)
    end_index = (offset + limit) if limit is not None else None
    page = matched[offset:end_index]
    return QueryResult(rows=[r.to_row() for r in page], total=total, offset=offset, limit=limit)
