"""Fuel-tech taxonomy and renewable-classification policy.

This is the single place that decides what a raw vendor `fuel_tech` string *means*:
its category, a human label, whether it is renewable, and whether it counts as
generation for share/intensity maths. Consumers never branch on the raw string.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class FuelCategory(Enum):
    SOLAR = "solar"
    WIND = "wind"
    HYDRO = "hydro"
    BIOENERGY = "bioenergy"
    COAL = "coal"
    GAS = "gas"
    DISTILLATE = "distillate"
    BATTERY = "battery"
    PUMPS = "pumps"
    IMPORT = "import"
    EXPORT = "export"
    CURTAILMENT = "curtailment"
    OTHER = "other"


# Renewable sources: stored/interconnect/curtailment flows are NOT here.
RENEWABLE_CATEGORIES = frozenset(
    {FuelCategory.SOLAR, FuelCategory.WIND, FuelCategory.HYDRO, FuelCategory.BIOENERGY}
)

# Categories that count as generation-by-source for renewable share & emissions
# intensity. Battery/pumps/import/export/curtailment/other are excluded so they
# distort neither numerator nor denominator.
GENERATION_CATEGORIES = RENEWABLE_CATEGORIES | {
    FuelCategory.COAL,
    FuelCategory.GAS,
    FuelCategory.DISTILLATE,
}


@dataclass(frozen=True)
class FuelTech:
    """A classified fuel tech: the meaning attached to a raw vendor string."""

    raw: str
    category: FuelCategory
    display_name: str

    @property
    def is_renewable(self) -> bool:
        return self.category in RENEWABLE_CATEGORIES

    @property
    def counts_as_generation(self) -> bool:
        return self.category in GENERATION_CATEGORIES


# raw vendor fuel_tech -> (category, human label)
_TAXONOMY: dict[str, tuple[FuelCategory, str]] = {
    "solar_utility": (FuelCategory.SOLAR, "Solar (utility)"),
    "solar_rooftop": (FuelCategory.SOLAR, "Solar (rooftop)"),
    "wind": (FuelCategory.WIND, "Wind"),
    "hydro": (FuelCategory.HYDRO, "Hydro"),
    "bioenergy_biomass": (FuelCategory.BIOENERGY, "Bioenergy (biomass)"),
    "bioenergy_biogas": (FuelCategory.BIOENERGY, "Bioenergy (biogas)"),
    "coal_black": (FuelCategory.COAL, "Black coal"),
    "coal_brown": (FuelCategory.COAL, "Brown coal"),
    "gas_ccgt": (FuelCategory.GAS, "Gas (CCGT)"),
    "gas_ocgt": (FuelCategory.GAS, "Gas (OCGT)"),
    "gas_recip": (FuelCategory.GAS, "Gas (reciprocating)"),
    "gas_steam": (FuelCategory.GAS, "Gas (steam)"),
    "gas_wcmg": (FuelCategory.GAS, "Gas (waste coal mine gas)"),
    "distillate": (FuelCategory.DISTILLATE, "Distillate"),
    "battery_charging": (FuelCategory.BATTERY, "Battery (charging)"),
    "battery_discharging": (FuelCategory.BATTERY, "Battery (discharging)"),
    "pumps": (FuelCategory.PUMPS, "Pumps"),
    "imports": (FuelCategory.IMPORT, "Imports"),
    "exports": (FuelCategory.EXPORT, "Exports"),
    "curtailment_solar_utility": (FuelCategory.CURTAILMENT, "Curtailment (solar)"),
    "curtailment_wind": (FuelCategory.CURTAILMENT, "Curtailment (wind)"),
}


def classify(raw: str) -> FuelTech:
    """Map a raw vendor fuel_tech to a FuelTech; unknowns become OTHER, never crash."""
    key = (raw or "").strip().lower()
    if key in _TAXONOMY:
        category, label = _TAXONOMY[key]
        return FuelTech(raw=key, category=category, display_name=label)
    return FuelTech(raw=key, category=FuelCategory.OTHER, display_name=key or "unknown")
