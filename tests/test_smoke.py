"""Scaffolding smoke tests (PR #1).

These guard the two things PR #1 ships: an importable package tree, and a captured
real API fixture that the later adapter tests will map against. Both can genuinely
fail (broken __init__, corrupt/empty fixture), so they earn their place.
"""
import json
from pathlib import Path

import pytest

FIXTURE = Path(__file__).parent / "fixtures" / "nem_sa1_power_7d.json"


@pytest.mark.parametrize(
    "module",
    [
        "gridwatch",
        "gridwatch.contracts",
        "gridwatch.ports",
        "gridwatch.domain",
        "gridwatch.adapters",
        "gridwatch.viz",
    ],
)
def test_package_imports(module):
    __import__(module)


def test_fixture_is_wellformed():
    data = json.loads(FIXTURE.read_text())
    assert data["region"] == "SA1"
    series = data["data"]
    assert len(series) > 0
    power = [s for s in series if s.get("type") == "power"]
    assert power, "fixture should contain at least one power series"
    sample = power[0]["history"]
    assert sample["interval"] and sample["start"]
    assert len(sample["data"]) > 0
