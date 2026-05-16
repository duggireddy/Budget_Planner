"""Tests for children tab and totals."""

from app.calculations import children_total, difference, total_5
from app.categories import SECTION_BY_ID


def test_child_sections_exist():
    assert "child_1" in SECTION_BY_ID
    assert "child_2" in SECTION_BY_ID
    assert len(SECTION_BY_ID["child_1"].lines) >= 10


def test_children_included_in_total_expenses():
    entries: dict[str, list[float]] = {}
    for key in ("ch1_school_fee", "ch2_bus_fee"):
        entries[key] = [0.0] * 12
        entries[key][0] = 100.0
    assert children_total(entries, 1) == 200.0
    base = total_5(entries, 1) - children_total(entries, 1)
    assert total_5(entries, 1) == base + 200.0


def test_children_affect_balance():
    entries = {"ch1_school_fee": [50.0] + [0.0] * 11}
    assert children_total(entries, 1) == 50.0
    assert difference(entries, 1) == -50.0
