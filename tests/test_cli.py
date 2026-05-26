from datetime import UTC, datetime

from gridwatch.adapters.fake_source import FakeDataSource
from gridwatch.application.manager import EnergyGridManager
from gridwatch.cli import GridWatchCLI
from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import EmissionReading, PowerReading, PriceReading

TS = datetime(2026, 5, 26, 12, 0, tzinfo=UTC)


def _sa1():
    return [
        PowerReading("SA1", TS, 100.0, 60, fuel=classify("wind")),
        PowerReading("SA1", TS, 100.0, 60, fuel=classify("coal_black")),
        EmissionReading("SA1", TS, 90.0, 60, fuel=classify("coal_black")),
        PriceReading("SA1", TS, 100.0, 5),
    ]


def _cli(tmp_path, *, input_fn=None):
    src = FakeDataSource({"SA1": _sa1()})
    mgr = EnergyGridManager(source=src)
    out: list[str] = []
    cli = GridWatchCLI(mgr, out=out.append, input_fn=input_fn, chart_dir=tmp_path)
    return cli, out


def test_fetch_reports_count(tmp_path):
    cli, out = _cli(tmp_path)
    assert cli.fetch("SA1") is True
    assert any("imported" in line.lower() for line in out)


def test_fetch_bad_region_reports_error_without_crashing(tmp_path):
    cli, out = _cli(tmp_path)
    assert cli.fetch("WA1") is False
    assert any("error" in line.lower() for line in out)


def test_summary_outputs_metrics(tmp_path):
    cli, out = _cli(tmp_path)
    cli.fetch("SA1")
    out.clear()
    assert cli.summary("SA1") is True
    joined = "\n".join(out).lower()
    assert "renewable" in joined and "%" in joined


def test_summary_unknown_region_reports_error(tmp_path):
    cli, out = _cli(tmp_path)
    assert cli.summary("NSW1") is False
    assert any("error" in line.lower() for line in out)


def test_visualise_writes_a_chart_file(tmp_path):
    cli, out = _cli(tmp_path)
    cli.fetch("SA1")
    assert cli.visualise("fuelmix", "SA1") is True
    assert list(tmp_path.glob("*.png"))


def test_save_then_load_in_a_fresh_manager(tmp_path):
    cli, _ = _cli(tmp_path)
    cli.fetch("SA1")
    path = tmp_path / "state.json"
    assert cli.save("json", path) is True

    fresh = GridWatchCLI(EnergyGridManager(), out=lambda *_: None, chart_dir=tmp_path)
    assert fresh.load("json", path) is True
    assert fresh.summary("SA1") is True


def test_bulk_fetch_then_load_ledger(tmp_path):
    cli, out = _cli(tmp_path)
    ledger = tmp_path / "ledger.jsonl"
    assert cli.bulk_fetch("jsonl", ledger) is True
    assert any("appended" in line.lower() for line in out)

    fresh = GridWatchCLI(EnergyGridManager(), out=lambda *_: None, chart_dir=tmp_path)
    assert fresh.load_ledger("jsonl", ledger) is True
    assert fresh.summary("SA1") is True


def test_bulk_fetch_unknown_ledger_format_reports_error(tmp_path):
    cli, out = _cli(tmp_path)
    assert cli.bulk_fetch("xml", tmp_path / "x") is False
    assert any("error" in line.lower() for line in out)


def test_run_loop_drives_fetch_then_exit(tmp_path):
    # menu: 1 = fetch -> "SA1" -> 0 = exit
    scripted = iter(["1", "SA1", "0"])
    cli, out = _cli(tmp_path, input_fn=lambda *_: next(scripted))
    cli.run()
    assert any("imported" in line.lower() for line in out)
    assert any("goodbye" in line.lower() for line in out)
