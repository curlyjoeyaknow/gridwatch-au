"""GridWatch AU web dashboard — a Flask driving adapter (ADR-008).

Thin: routes call the EnergyGridManager facade, the query engine, and the chart
renderers. No domain logic lives here. `create_app()` is a factory so it can be
tested with Flask's test client and a FakeDataSource-backed manager.
"""

from __future__ import annotations

import csv
import io
import os
import tempfile
from pathlib import Path

from flask import (
    Flask,
    Response,
    abort,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)

from gridwatch.adapters.jsonl_ledger import JsonlEventLedger
from gridwatch.adapters.openelectricity import OpenElectricityClient
from gridwatch.application.manager import EnergyGridManager
from gridwatch.application.query import COLUMNS
from gridwatch.contracts.regions import NEM_REGIONS
from gridwatch.domain.aggregate import PERIODS, TREND_METRICS
from gridwatch.exceptions import GridWatchError
from gridwatch.viz import charts

# chart kind -> renderer
_ALL_CHARTS = {
    "share": charts.renewable_share_chart,
    "emissions": charts.emissions_chart,
}
_REGION_CHARTS = {
    "fuelmix": lambda m, code, p: charts.fuel_mix_chart(m.summarise(code), p),
    "price": lambda m, code, p: charts.price_trend_chart(m.get_region(code), p),
    "stack": lambda m, code, p: charts.generation_stack_chart(m.get_region(code), p),
    "sharetime": lambda m, code, p: charts.renewable_share_over_time(m.get_region(code), p),
    "demandgen": lambda m, code, p: charts.demand_vs_generation_chart(m.get_region(code), p),
    "emissionstime": lambda m, code, p: charts.emissions_over_time(m.get_region(code), p),
    "duration": lambda m, code, p: charts.price_duration_curve(m.get_region(code), p),
}
PAGE_SIZE = 50
SORT_OPTIONS = ["timestamp", "value", "region", "metric", "fuel_tech"]
TREND_COLUMNS = [
    "period",
    "region",
    "generation_mwh",
    "renewable_share_pct",
    "emissions_tco2e",
    "emissions_intensity",
    "avg_price",
    "peak_price",
    "avg_demand_mw",
    "peak_demand_mw",
]


def _parse_filters(args) -> dict:
    filters: dict = {}
    for key in ("region", "metric", "fuel_tech"):
        value = (args.get(key) or "").strip()
        if value:
            filters[key] = value
    if args.get("renewable_only"):
        filters["renewable_only"] = True
    sort_by = (args.get("sort_by") or "").strip()
    if sort_by:
        filters["sort_by"] = sort_by
    if args.get("descending"):
        filters["descending"] = True
    return filters


def create_app(*, manager=None, source=None, ledger=None, chart_dir=None) -> Flask:
    app = Flask(__name__)
    app.config["manager"] = manager or EnergyGridManager(source=source or OpenElectricityClient())
    if ledger is None:
        env_path = os.environ.get("GRIDWATCH_LEDGER")
        ledger = JsonlEventLedger(env_path) if env_path else None
    app.config["ledger"] = ledger
    app.config["chart_dir"] = Path(chart_dir or tempfile.mkdtemp(prefix="gridwatch-charts-"))

    mgr = app.config["manager"]
    if ledger is not None and not mgr.regions():
        try:
            mgr.load_from_ledger(ledger)
        except GridWatchError:
            pass

    @app.get("/")
    def dashboard():
        summaries = sorted(mgr.compare(), key=lambda s: s.renewable_share, reverse=True)
        return render_template(
            "dashboard.html",
            summaries=[s.as_dict() for s in summaries],
            regions=[r.code for r in mgr.regions()],
            all_regions=NEM_REGIONS,
        )

    @app.get("/region/<code>")
    def region_view(code):
        try:
            summary = mgr.summarise(code).as_dict()
        except GridWatchError:
            abort(404)
        return render_template(
            "region.html",
            s=summary,
            code=code.upper(),
            region_charts=list(_REGION_CHARTS),
        )

    @app.get("/table")
    def table():
        filters = _parse_filters(request.args)
        page = max(int(request.args.get("page") or 1), 1)
        error = None
        result = None
        try:
            result = mgr.query(limit=PAGE_SIZE, offset=(page - 1) * PAGE_SIZE, **filters)
        except GridWatchError as exc:
            error = str(exc)
        return render_template(
            "table.html",
            result=result,
            error=error,
            columns=COLUMNS,
            args=request.args,
            page=page,
            page_size=PAGE_SIZE,
            sort_options=SORT_OPTIONS,
        )

    @app.get("/table.csv")
    def table_csv():
        filters = _parse_filters(request.args)
        try:
            result = mgr.query(limit=None, **filters)
        except GridWatchError as exc:
            abort(400, str(exc))
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for row in result.rows:
            writer.writerow({col: row.get(col) for col in COLUMNS})
        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=gridwatch.csv"},
        )

    @app.get("/trends")
    def trends():
        period = (request.args.get("period") or "day").strip()
        region = (request.args.get("region") or "").strip() or None
        metric = (request.args.get("metric") or "renewable_share").strip()
        error = None
        points = []
        try:
            points = mgr.trends(period, region=region)
        except GridWatchError as exc:
            error = str(exc)
        return render_template(
            "trends.html",
            points=[p.as_dict() for p in points],
            columns=TREND_COLUMNS,
            error=error,
            period=period,
            region=region or "",
            metric=metric,
            periods=PERIODS,
            metrics=TREND_METRICS,
            args=request.args,
        )

    @app.get("/trends.csv")
    def trends_csv():
        period = (request.args.get("period") or "day").strip()
        region = (request.args.get("region") or "").strip() or None
        try:
            points = mgr.trends(period, region=region)
        except GridWatchError as exc:
            abort(400, str(exc))
        buffer = io.StringIO()
        writer = csv.DictWriter(buffer, fieldnames=TREND_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        for point in points:
            writer.writerow(point.as_dict())
        return Response(
            buffer.getvalue(),
            mimetype="text/csv",
            headers={"Content-Disposition": "attachment; filename=gridwatch-trends.csv"},
        )

    @app.get("/charts/trend.png")
    def chart_trend():
        period = (request.args.get("period") or "day").strip()
        region = (request.args.get("region") or "").strip() or None
        metric = (request.args.get("metric") or "renewable_share").strip()
        path = app.config["chart_dir"] / f"trend_{metric}_{region or 'all'}_{period}.png"
        try:
            points = mgr.trends(period, region=region)
            charts.period_trend_chart(points, metric, path, period=period)
        except GridWatchError:
            abort(404)
        return send_file(path, mimetype="image/png")

    @app.get("/charts/<kind>.png")
    def chart_all(kind):
        renderer = _ALL_CHARTS.get(kind)
        if renderer is None:
            abort(404)
        path = app.config["chart_dir"] / f"{kind}_all.png"
        try:
            renderer(mgr.compare(), path)
        except GridWatchError:
            abort(404)
        return send_file(path, mimetype="image/png")

    @app.get("/charts/<kind>/<code>.png")
    def chart_region(kind, code):
        renderer = _REGION_CHARTS.get(kind)
        if renderer is None:
            abort(404)
        path = app.config["chart_dir"] / f"{kind}_{code.upper()}.png"
        try:
            renderer(mgr, code.upper(), path)
        except GridWatchError:
            abort(404)
        return send_file(path, mimetype="image/png")

    @app.post("/refresh")
    def refresh():
        led = app.config["ledger"]
        try:
            if led is not None:
                mgr.bulk_fetch(led)
                mgr.load_from_ledger(led)
            else:
                for code in NEM_REGIONS:
                    mgr.import_region(code)
        except GridWatchError:
            pass
        return redirect(url_for("dashboard"))

    return app


def main() -> None:
    app = create_app()
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", 8000)))
