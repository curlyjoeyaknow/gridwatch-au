"""GridWatch AU — menu-driven CLI (Track 5, the driving adapter).

Thin: it parses input, calls the `EnergyGridManager`, and prints results. Every
action catches `GridWatchError` and reports it, so the app never crashes on bad
input, a network failure, or a corrupt file.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from gridwatch.adapters.csv_repo import CsvRepository
from gridwatch.adapters.json_repo import JsonRepository
from gridwatch.adapters.openelectricity import OpenElectricityClient
from gridwatch.application.manager import EnergyGridManager
from gridwatch.contracts.fueltech import classify
from gridwatch.contracts.readings import (
    DemandReading,
    EmissionReading,
    PowerReading,
    PriceReading,
)
from gridwatch.contracts.regions import NEM_REGIONS, validate_region
from gridwatch.exceptions import GridWatchError, ValidationError
from gridwatch.viz import charts

MENU = """
=== GridWatch AU — NEM generation & emissions ===
 1) Fetch live data for a region (API)
 2) List loaded regions
 3) Summarise a region
 4) Compare all loaded regions
 5) Search readings
 6) Visualise (chart)
 7) Save dataset
 8) Load dataset
 9) Add a manual reading
10) Delete readings
 0) Exit
"""

_REPOS = {"json": JsonRepository, "csv": CsvRepository}


class GridWatchCLI:
    def __init__(
        self, manager: EnergyGridManager, *, out=print, input_fn=input, chart_dir="outputs"
    ):
        self.manager = manager
        self.out = out
        self.input_fn = input_fn
        self.chart_dir = Path(chart_dir)

    # --- actions (each self-contained, returns success) -------------------
    def fetch(self, region: str) -> bool:
        try:
            reg = self.manager.import_region(region)
            self.out(f"Imported {len(reg)} readings for {reg.name} ({reg.code}).")
            return True
        except GridWatchError as exc:
            self.out(f"Error: {exc}")
            return False

    def list_regions(self) -> bool:
        regions = self.manager.regions()
        if not regions:
            self.out("No regions loaded. Use 'Fetch' or 'Load' first.")
            return True
        for reg in regions:
            self.out(f"  {reg.code} — {reg.name}: {len(reg)} readings")
        return True

    def summary(self, region: str) -> bool:
        try:
            data = self.manager.summarise(region).as_dict()
        except GridWatchError as exc:
            self.out(f"Error: {exc}")
            return False
        self.out(f"--- {data['region']} (last 7d) ---")
        self.out(f"  Total generation:    {data['total_generation_mwh']:.1f} MWh")
        self.out(f"  Renewable share:     {data['renewable_share_pct']:.1f} %")
        self.out(f"  Total emissions:     {data['total_emissions_tco2e']:.1f} tCO2e")
        intensity = data["emissions_intensity_tco2e_per_mwh"]
        self.out(f"  Emissions intensity: {intensity:.3f} tCO2e/MWh")
        avg, peak = data["avg_price_aud_mwh"], data["peak_price_aud_mwh"]
        self.out(f"  Avg / peak price:    {avg} / {peak} AUD/MWh")
        self.out(f"  Generation by fuel:  {data['by_category_mwh']}")
        return True

    def compare(self) -> bool:
        summaries = self.manager.compare()
        if not summaries:
            self.out("No regions loaded to compare.")
            return True
        self.out(f"{'Region':<8}{'Renewable %':>13}{'Intensity':>12}{'Gen MWh':>12}")
        for s in sorted(summaries, key=lambda x: x.renewable_share, reverse=True):
            self.out(
                f"{s.region:<8}{s.renewable_share * 100:>12.1f}%"
                f"{s.emissions_intensity:>12.3f}{s.total_generation_mwh:>12.0f}"
            )
        return True

    def search(self, *, region=None, metric=None, renewable_only=False, fuel_tech=None) -> bool:
        try:
            criteria = {"renewable_only": renewable_only}
            if metric:
                criteria["metric"] = metric
            if fuel_tech:
                criteria["fuel_tech"] = fuel_tech
            results = self.manager.search(region=region, **criteria)
        except GridWatchError as exc:
            self.out(f"Error: {exc}")
            return False
        self.out(f"{len(results)} reading(s) matched.")
        for r in results[:20]:
            self.out(f"  {r.timestamp.isoformat()}  {r.label()} = {r.value} {r.unit}")
        if len(results) > 20:
            self.out(f"  … and {len(results) - 20} more")
        return True

    def visualise(self, kind: str, region: str | None = None) -> bool:
        try:
            self.chart_dir.mkdir(parents=True, exist_ok=True)
            tag = (region or "all").upper()
            path = self.chart_dir / f"{kind}_{tag}.png"
            if kind == "fuelmix":
                charts.fuel_mix_chart(self.manager.summarise(region), path)
            elif kind == "price":
                charts.price_trend_chart(self.manager.get_region(region), path)
            elif kind == "share":
                charts.renewable_share_chart(self.manager.compare(), path)
            elif kind == "emissions":
                charts.emissions_chart(self.manager.compare(), path)
            else:
                raise ValidationError(f"unknown chart kind {kind!r}")
        except GridWatchError as exc:
            self.out(f"Error: {exc}")
            return False
        self.out(f"Chart written to {path}")
        return True

    def save(self, fmt: str, path: str | Path) -> bool:
        repo_cls = _REPOS.get(fmt.lower())
        if repo_cls is None:
            self.out(f"Error: unknown format {fmt!r} (use json or csv)")
            return False
        try:
            self.manager.save(repo_cls(), path)
        except GridWatchError as exc:
            self.out(f"Error: {exc}")
            return False
        self.out(f"Saved {len(self.manager.regions())} region(s) to {path}")
        return True

    def load(self, fmt: str, path: str | Path) -> bool:
        repo_cls = _REPOS.get(fmt.lower())
        if repo_cls is None:
            self.out(f"Error: unknown format {fmt!r} (use json or csv)")
            return False
        try:
            self.manager.load(repo_cls(), path)
        except GridWatchError as exc:
            self.out(f"Error: {exc}")
            return False
        self.out(f"Loaded {len(self.manager.regions())} region(s) from {path}")
        return True

    def add_reading(self, region, metric, value, interval, fuel_tech=None, timestamp=None) -> bool:
        try:
            code = validate_region(region)
            ts = timestamp or datetime.now(UTC)
            val = float(value)
            iv = int(interval)
            m = metric.strip().lower()
            if m == "power":
                reading = PowerReading(code, ts, val, iv, fuel=classify(fuel_tech or ""))
            elif m == "emissions":
                reading = EmissionReading(code, ts, val, iv, fuel=classify(fuel_tech or ""))
            elif m == "price":
                reading = PriceReading(code, ts, val, iv)
            elif m == "demand":
                reading = DemandReading(code, ts, val, iv)
            else:
                raise ValidationError(f"unknown metric {metric!r} (power/emissions/price/demand)")
            self.manager.add_reading(reading)
        except (GridWatchError, ValueError) as exc:
            self.out(f"Error: {exc}")
            return False
        self.out(f"Added {reading.label()} = {val} {reading.unit}")
        return True

    def delete(self, region, metric) -> bool:
        wanted = metric.strip().lower()
        try:
            removed = self.manager.delete_readings(region, lambda r: r.metric == wanted)
        except GridWatchError as exc:
            self.out(f"Error: {exc}")
            return False
        self.out(f"Removed {removed} reading(s) from {region.upper()}.")
        return True

    # --- interactive loop -------------------------------------------------
    def _ask(self, prompt: str) -> str:
        try:
            return self.input_fn(prompt).strip()
        except (EOFError, KeyboardInterrupt):
            return "0"

    def run(self) -> None:
        self.out(f"Valid NEM regions: {', '.join(NEM_REGIONS)}")
        while True:
            self.out(MENU)
            choice = self._ask("Choose: ")
            if choice == "0":
                self.out("Goodbye.")
                return
            elif choice == "1":
                self.fetch(self._ask("Region (e.g. SA1): "))
            elif choice == "2":
                self.list_regions()
            elif choice == "3":
                self.summary(self._ask("Region: "))
            elif choice == "4":
                self.compare()
            elif choice == "5":
                self.search(
                    region=self._ask("Region (blank = all): ") or None,
                    metric=self._ask("Metric (blank = any): ") or None,
                    renewable_only=self._ask("Renewable only? (y/N): ").lower().startswith("y"),
                )
            elif choice == "6":
                self.visualise(
                    self._ask("Chart (fuelmix/share/emissions/price): ").lower(),
                    self._ask("Region (blank for share/emissions): ") or None,
                )
            elif choice == "7":
                self.save(self._ask("Format (json/csv): "), self._ask("Path: "))
            elif choice == "8":
                self.load(self._ask("Format (json/csv): "), self._ask("Path: "))
            elif choice == "9":
                self.add_reading(
                    self._ask("Region: "),
                    self._ask("Metric (power/emissions/price/demand): "),
                    self._ask("Value: "),
                    self._ask("Interval minutes: "),
                    self._ask("Fuel tech (for power/emissions, else blank): ") or None,
                )
            elif choice == "10":
                self.delete(self._ask("Region: "), self._ask("Metric: "))
            else:
                self.out("Unknown choice.")


def main() -> None:
    manager = EnergyGridManager(source=OpenElectricityClient())
    GridWatchCLI(manager).run()


if __name__ == "__main__":
    main()
