"""Adapter tests — mapping correctness against a captured real response, plus
error handling via a fake HTTP session (no network)."""

import json
from pathlib import Path

import pytest
import requests

from gridwatch.adapters.openelectricity import OpenElectricityClient, map_payload
from gridwatch.contracts.readings import (
    DemandReading,
    EmissionReading,
    PowerReading,
    PriceReading,
    Reading,
)
from gridwatch.exceptions import DataSourceError, ValidationError

FIXTURE = Path(__file__).parent / "fixtures" / "nem_sa1_power_7d.json"


@pytest.fixture
def payload():
    return json.loads(FIXTURE.read_text())


# --- mapping (the heart of the adapter) ----------------------------------
def test_maps_fixture_into_typed_readings(payload):
    readings = map_payload(payload, "SA1")
    assert readings, "should produce readings from a real payload"
    assert all(isinstance(r, Reading) for r in readings), "no vendor dict may leak"
    assert all(r.region == "SA1" for r in readings)


def test_all_reading_types_present(payload):
    readings = map_payload(payload, "SA1")
    kinds = {type(r) for r in readings}
    assert PowerReading in kinds
    assert EmissionReading in kinds
    assert PriceReading in kinds
    assert DemandReading in kinds


def test_renewable_share_is_a_sane_fraction(payload):
    from gridwatch.domain import analytics

    readings = map_payload(payload, "SA1")
    share = analytics.renewable_share(readings)
    assert 0.0 <= share <= 1.0


def test_malformed_payload_raises(payload):
    with pytest.raises(DataSourceError):
        map_payload({"data": "not-a-list"}, "SA1")


def test_incomplete_series_skipped_not_crashed():
    bad = {"data": [{"type": "power", "fuel_tech": "wind", "history": {}}]}
    assert map_payload(bad, "SA1") == []


# --- HTTP behaviour via a fake session -----------------------------------
class _FakeResponse:
    def __init__(self, *, json_data=None, status=200):
        self._json = json_data
        self.status_code = status

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.HTTPError(f"HTTP {self.status_code}")

    def json(self):
        if self._json is None:
            raise ValueError("no JSON body")
        return self._json


class _FakeSession:
    def __init__(self, response=None, exc=None):
        self._response = response
        self._exc = exc
        self.calls = []

    def get(self, url, headers=None, timeout=None):
        self.calls.append({"url": url, "headers": headers, "timeout": timeout})
        if self._exc:
            raise self._exc
        return self._response


def test_client_sends_user_agent_and_region_url(payload):
    session = _FakeSession(response=_FakeResponse(json_data=payload))
    client = OpenElectricityClient(session=session)
    readings = client.fetch_readings("SA1")
    assert readings
    assert "SA1" in session.calls[0]["url"]
    assert session.calls[0]["headers"]["User-Agent"]


def test_http_error_becomes_datasource_error():
    session = _FakeSession(response=_FakeResponse(status=503))
    with pytest.raises(DataSourceError):
        OpenElectricityClient(session=session).fetch_readings("SA1")


def test_non_json_becomes_datasource_error():
    session = _FakeSession(response=_FakeResponse(json_data=None))
    with pytest.raises(DataSourceError):
        OpenElectricityClient(session=session).fetch_readings("SA1")


def test_network_error_becomes_datasource_error():
    session = _FakeSession(exc=requests.ConnectionError("down"))
    with pytest.raises(DataSourceError):
        OpenElectricityClient(session=session).fetch_readings("SA1")


def test_bad_region_rejected_before_any_request():
    session = _FakeSession(response=_FakeResponse(json_data={"data": []}))
    with pytest.raises(ValidationError):
        OpenElectricityClient(session=session).fetch_readings("WA1")
    assert session.calls == []
