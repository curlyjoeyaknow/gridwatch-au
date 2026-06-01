"""OpenElectricity API adapter.

Fetches the free v4 7-day feed and maps the vendor payload into our `Reading`
objects. The vendor shape stops here — `map_payload` is a pure function so the
mapping is testable against a captured fixture with no network.
"""

from __future__ import annotations

import re
from datetime import datetime, timedelta

import requests

from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import (
    DemandReading,
    EmissionReading,
    PowerReading,
    PriceReading,
    Reading,
)
from gridwatch.contracts.regions import validate_region
from gridwatch.exceptions import DataSourceError
from gridwatch.ports.datasource import DataSource

BASE_URL = "https://data.openelectricity.org.au/v4/stats/au/NEM/{region}/power/7d.json"
USER_AGENT = "gridwatch-au/0.1 (+https://github.com/curlyjoeyaknow/gridwatch-au)"

_INTERVAL_UNITS = {"m": 1, "h": 60, "d": 1440}


def _parse_interval(text) -> int | None:
    """'5m' -> 5, '30m' -> 30, '1h' -> 60. Unknown/missing -> None."""
    if not isinstance(text, str):
        return None
    match = re.fullmatch(r"(\d+)([mhd])", text.strip())
    if not match:
        return None
    return int(match.group(1)) * _INTERVAL_UNITS[match.group(2)]


def _build(stype, fuel_raw, region, ts, value, interval) -> Reading | None:
    if stype == "power":
        if fuel_raw is None:  # the fuel_tech=None power series is regional demand
            return DemandReading(region, ts, value, interval)
        return PowerReading(region, ts, value, interval, fuel=classify(fuel_raw))
    if stype == "emissions":
        return EmissionReading(region, ts, value, interval, fuel=classify(fuel_raw or ""))
    if stype == "price":
        return PriceReading(region, ts, value, interval)
    if stype == "demand":
        return DemandReading(region, ts, value, interval)
    return None  # temperature & unknown series are not grid metrics we manage


def _map_series(series: dict, region: str) -> list[Reading]:
    history = series.get("history") or {}
    interval = _parse_interval(history.get("interval"))
    data = history.get("data") or []
    try:
        start = datetime.fromisoformat(history["start"]) if history.get("start") else None
    except (TypeError, ValueError):
        start = None
    if interval is None or start is None or not data:
        return []  # skip incomplete series rather than crash

    out: list[Reading] = []
    for i, raw_value in enumerate(data):
        if raw_value is None:
            continue  # a gap in the series
        try:
            value = float(raw_value)
        except (TypeError, ValueError):
            continue
        ts = start + timedelta(minutes=interval * i)
        reading = _build(series.get("type"), series.get("fuel_tech"), region, ts, value, interval)
        if reading is not None:
            out.append(reading)
    return out


def map_payload(payload: dict, region: str) -> list[Reading]:
    """Map a v4 power payload into typed Readings (pure; raises DataSourceError)."""
    series_list = payload.get("data") if isinstance(payload, dict) else None
    if not isinstance(series_list, list):
        raise DataSourceError("malformed OpenElectricity payload: 'data' missing or not a list")
    readings: list[Reading] = []
    for series in series_list:
        if isinstance(series, dict):
            readings.extend(_map_series(series, region))
    return readings


class OpenElectricityClient(DataSource):
    name = "openelectricity"

    def __init__(self, *, timeout: float = 20.0, session=None, base_url: str = BASE_URL):
        self._timeout = timeout
        self._session = session or requests.Session()
        self._base_url = base_url

    def fetch_readings(self, region: str) -> list[Reading]:
        code = validate_region(region)  # reject out-of-scope before any request
        url = self._base_url.format(region=code)
        try:
            response = self._session.get(
                url, headers={"User-Agent": USER_AGENT}, timeout=self._timeout
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            raise DataSourceError(f"failed to fetch {code} from OpenElectricity: {exc}") from exc
        except ValueError as exc:  # JSON decode error
            raise DataSourceError(f"OpenElectricity returned non-JSON for {code}: {exc}") from exc
        return map_payload(payload, code)
