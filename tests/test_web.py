from datetime import UTC, datetime

import pytest

from gridwatch.adapters.fake_source import FakeDataSource
from gridwatch.adapters.jsonl_ledger import JsonlEventLedger
from gridwatch.application.manager import EnergyGridManager
from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import (
    DemandReading,
    EmissionReading,
    PowerReading,
    PriceReading,
)
from gridwatch.web import create_app

TS = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


def _readings(region="SA1"):
    return [
        PowerReading(region, TS, 100.0, 30, fuel=classify("wind")),
        PowerReading(region, TS, 100.0, 30, fuel=classify("coal_black")),
        EmissionReading(region, TS, 50.0, 30, fuel=classify("coal_black")),
        PriceReading(region, TS, 90.0, 5),
        DemandReading(region, TS, 1500.0, 5),
    ]


@pytest.fixture
def client(tmp_path):
    mgr = EnergyGridManager()
    for r in _readings("SA1"):
        mgr.add_reading(r)
    app = create_app(manager=mgr, chart_dir=tmp_path)
    app.config.update(TESTING=True)
    return app.test_client()


def test_dashboard_lists_region(client):
    resp = client.get("/")
    assert resp.status_code == 200
    assert b"SA1" in resp.data


def test_region_page_shows_metrics(client):
    resp = client.get("/region/SA1")
    assert resp.status_code == 200
    assert b"enewable" in resp.data  # "Renewable"/"renewable"


def test_unknown_region_page_404(client):
    assert client.get("/region/NSW1").status_code == 404


def test_table_renders_rows(client):
    resp = client.get("/table")
    assert resp.status_code == 200
    assert b"power" in resp.data


def test_table_filter_renewable_only(client):
    resp = client.get("/table?metric=power&renewable_only=on")
    assert resp.status_code == 200
    assert b"wind" in resp.data


def test_table_csv_export(client):
    resp = client.get("/table.csv?metric=power")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert b"timestamp,region,metric,fuel_tech,value,unit" in resp.data


def test_region_chart_png(client):
    resp = client.get("/charts/fuelmix/SA1.png")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"


def test_all_chart_png(client):
    resp = client.get("/charts/share.png")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"


def test_chart_for_empty_region_404(client):
    assert client.get("/charts/fuelmix/NSW1.png").status_code == 404


def test_table_json_returns_filtered_series(client):
    resp = client.get("/table.json?metric=power")
    assert resp.status_code == 200
    assert resp.mimetype == "application/json"
    data = resp.get_json()
    assert data["count"] > 0
    assert data["unit"] == "MW"
    assert data["series"] and data["labels"]
    assert "breakdown" in data


def test_table_json_respects_renewable_filter(client):
    data = client.get("/table.json?metric=power&renewable_only=on").get_json()
    # SA1 fixture has one renewable power fuel: wind
    assert [s["label"] for s in data["series"]] == ["wind"]


def test_table_json_bad_sort_returns_400(client):
    resp = client.get("/table.json?sort_by=nope")
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_chartjs_is_served(client):
    resp = client.get("/static/chart.min.js")
    assert resp.status_code == 200
    assert b"Chart" in resp.data


def test_table_page_wires_charts(client):
    html = client.get("/table").data
    assert b"lineChart" in html and b"barChart" in html
    assert b"chart.min.js" in html and b"table.json" in html


def test_trends_page_renders_summary(client):
    resp = client.get("/trends?period=day")
    assert resp.status_code == 200
    assert b"summary" in resp.data.lower()


def test_trends_bad_period_shows_error(client):
    resp = client.get("/trends?period=fortnight")
    assert resp.status_code == 200
    assert b"rror" in resp.data  # "Error:"


def test_trend_chart_png(client):
    resp = client.get("/charts/trend.png?period=day&metric=renewable_share")
    assert resp.status_code == 200
    assert resp.mimetype == "image/png"


def test_trends_csv_export(client):
    resp = client.get("/trends.csv?period=day")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert b"period,region,generation_mwh,renewable_share_pct" in resp.data


def test_refresh_bulk_fetches_and_loads(tmp_path):
    source = FakeDataSource({"SA1": _readings("SA1"), "TAS1": _readings("TAS1")})
    ledger = JsonlEventLedger(tmp_path / "ledger.jsonl")
    mgr = EnergyGridManager(source=source)
    app = create_app(manager=mgr, ledger=ledger, chart_dir=tmp_path)
    app.config.update(TESTING=True)
    client = app.test_client()

    resp = client.post("/refresh")
    assert resp.status_code in (302, 303)
    assert len(ledger.read_all()) == 10  # 5 readings x 2 regions

    dash = client.get("/")
    assert b"SA1" in dash.data and b"TAS1" in dash.data
