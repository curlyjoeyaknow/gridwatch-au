import pytest

from gridwatch.contracts.fueltech import FuelCategory, FuelTech, classify


@pytest.mark.parametrize(
    "raw",
    ["solar_utility", "solar_rooftop", "wind", "hydro", "bioenergy_biomass", "bioenergy_biogas"],
)
def test_known_renewables_count_as_renewable_generation(raw):
    ft = classify(raw)
    assert isinstance(ft, FuelTech)
    assert ft.is_renewable
    assert ft.counts_as_generation


@pytest.mark.parametrize("raw", ["coal_black", "coal_brown", "gas_ccgt", "gas_ocgt", "distillate"])
def test_known_fossil_count_as_generation_but_not_renewable(raw):
    ft = classify(raw)
    assert not ft.is_renewable
    assert ft.counts_as_generation


@pytest.mark.parametrize(
    "raw",
    [
        "battery_charging",
        "battery_discharging",
        "pumps",
        "imports",
        "exports",
        "curtailment_wind",
        "curtailment_solar_utility",
    ],
)
def test_storage_and_interconnect_flows_excluded_from_generation(raw):
    ft = classify(raw)
    assert not ft.counts_as_generation
    assert not ft.is_renewable


def test_unknown_fuel_maps_to_other_safely():
    ft = classify("fusion_reactor_9000")
    assert ft.category is FuelCategory.OTHER
    assert not ft.is_renewable
    assert not ft.counts_as_generation
    assert ft.raw == "fusion_reactor_9000"


def test_display_name_is_human_readable():
    assert classify("solar_rooftop").display_name != "solar_rooftop"
    assert classify("gas_ccgt").display_name


def test_classify_is_case_and_whitespace_tolerant():
    assert classify("  WIND ").category is FuelCategory.WIND
