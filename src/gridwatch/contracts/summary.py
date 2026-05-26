"""RegionSummary — the computed insight value object returned by analytics."""

from __future__ import annotations

from dataclasses import dataclass, field

from gridwatch.contracts.fueltech import FuelCategory


@dataclass(frozen=True)
class RegionSummary:
    region: str
    total_generation_mwh: float
    renewable_generation_mwh: float
    renewable_share: float  # 0..1; 0.0 when there is no generation
    total_emissions_tco2e: float
    emissions_intensity: float  # tCO2e per MWh; 0.0 when there is no generation
    avg_price: float | None
    peak_price: float | None
    by_category_mwh: dict[FuelCategory, float] = field(default_factory=dict)
    reading_count: int = 0

    def as_dict(self) -> dict:
        return {
            "region": self.region,
            "total_generation_mwh": round(self.total_generation_mwh, 3),
            "renewable_generation_mwh": round(self.renewable_generation_mwh, 3),
            "renewable_share_pct": round(self.renewable_share * 100, 2),
            "total_emissions_tco2e": round(self.total_emissions_tco2e, 3),
            "emissions_intensity_tco2e_per_mwh": round(self.emissions_intensity, 4),
            "avg_price_aud_mwh": None if self.avg_price is None else round(self.avg_price, 2),
            "peak_price_aud_mwh": None if self.peak_price is None else round(self.peak_price, 2),
            "by_category_mwh": {c.name: round(v, 3) for c, v in self.by_category_mwh.items()},
            "reading_count": self.reading_count,
        }
