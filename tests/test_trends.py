from datetime import UTC, datetime

import pytest

from gridwatch.adapters.fake_source import FakeDataSource
from gridwatch.application.manager import EnergyGridManager
from gridwatch.cli import GridWatchCLI
from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import (
    DemandReading,
    EmissionReading,
    PowerReading,
    PriceReading,
)
from gridwatch.domain.aggregate import aggregate
from gridwatch.exceptions import ValidationError
from gridwatch.viz import charts


def _readings(region="SA1"):
    rows = []
    for day in (1, 2):
        ts = datetime(2026, 5, day, 12, 0, tzinfo=UTC)
        rows += [
            PowerReading(region, ts, 100.0, 60, fuel=classify("wind")),
            PowerReading(region, ts, 100.0, 60, fuel=classify("coal_black")),
            EmissionReading(region, ts, 90.0, 60, fuel=classify("coal_black")),
            PriceReading(region, ts, 100.0, 60),
            DemandReading(region, ts, 900.0, 60),
        ]
    return rows


def test_period_trend_chart_writes_png(tmp_path):
    points = aggregate(_readings(), "day")
    path = charts.period_trend_chart(points, "renewable_share", tmp_path / "t.png", period="day")
    assert path.exists() and path.stat().st_size > 0


def test_period_trend_chart_unknown_metric_raises(tmp_path):
    points = aggregate(_readings(), "day")
    with pytest.raises(ValidationError):
        charts.period_trend_chart(points, "nope", tmp_path / "t.png")


def test_period_trend_chart_empty_raises(tmp_path):
    with pytest.raises(ValidationError):
        charts.period_trend_chart([], "renewable_share", tmp_path / "t.png")


def test_manager_trends():
    mgr = EnergyGridManager()
    for r in _readings("SA1"):
        mgr.add_reading(r)
    points = mgr.trends("day")
    assert len(points) == 2 and points[0].region == "SA1"


def test_cli_trends_outputs_table(tmp_path):
    source = FakeDataSource({"SA1": _readings("SA1")})
    mgr = EnergyGridManager(source=source)
    mgr.import_region("SA1")
    out: list[str] = []
    cli = GridWatchCLI(mgr, out=out.append, chart_dir=tmp_path)
    assert cli.trends("day") is True
    joined = "\n".join(out).lower()
    assert "renewable" in joined and "generation" in joined


def test_cli_trends_bad_period_reports_error(tmp_path):
    cli = GridWatchCLI(EnergyGridManager(), out=lambda *_: None, chart_dir=tmp_path)
    out: list[str] = []
    cli.out = out.append
    assert cli.trends("fortnight") is False
    assert any("error" in line.lower() for line in out)
