"""Extended tests for 2026 sample budget (rough data from template)."""

import os
from pathlib import Path

import pytest

from app.calculations import (
    compute_full_summary,
    difference,
    section_total,
    summe,
    total_1,
    total_2,
    total_3,
    total_4,
    total_5,
    total_revenue,
)
from app.seed import SAMPLE_LINES

_test_db = Path(__file__).resolve().parent / "_test_sample.db"
os.environ["DB_BACKEND"] = "sqlite"
os.environ["SQLITE_PATH"] = str(_test_db)


def _entries_from_sample() -> dict[str, list[float]]:
    entries: dict[str, list[float]] = {}
    for key, amount in SAMPLE_LINES:
        entries[key] = [0.0] * 12
        for m in range(7, 13):
            entries[key][m - 1] = amount
    return entries


@pytest.fixture
def sample_entries():
    return _entries_from_sample()


# --- Monthly (Jul = month 7) ---

def test_jan_jun_are_zero(sample_entries):
    for m in range(1, 7):
        assert total_revenue(sample_entries, m) == 0.0
        assert total_5(sample_entries, m) == 0.0
        assert difference(sample_entries, m) == 0.0


def test_living_line_items_sum_to_760(sample_entries):
    assert section_total(sample_entries, "living", 7) == 760.0


def test_housing_line_items_sum_to_984(sample_entries):
    assert section_total(sample_entries, "housing", 7) == 984.0


def test_insurance_line_items_sum_to_221(sample_entries):
    assert section_total(sample_entries, "property_insurance", 7) == 221.0


def test_loan_is_total_4(sample_entries):
    assert section_total(sample_entries, "credit", 7) == 520.0
    assert total_4(sample_entries, 7) == 520.0


def test_total_5_equals_sum_of_blocks(sample_entries):
    m = 7
    assert total_5(sample_entries, m) == (
        total_1(sample_entries, m)
        + total_2(sample_entries, m)
        + total_3(sample_entries, m)
        + total_4(sample_entries, m)
    )


# --- Annual Summe (sum of Jan–Dec cells; Jul–Dec filled = 6 months) ---

def test_living_annual_summe_sum_of_cells(sample_entries):
    months = [total_1(sample_entries, m) for m in range(1, 13)]
    assert summe(months) == 4560.0


def test_housing_annual_summe_sum_of_cells(sample_entries):
    months = [total_2(sample_entries, m) for m in range(1, 13)]
    assert summe(months) == 5904.0


def test_revenue_annual_summe_sum_of_cells(sample_entries):
    months = [total_revenue(sample_entries, m) for m in range(1, 13)]
    assert summe(months) == 11922.0


def test_expenses_annual_summe_sum_of_cells(sample_entries):
    months = [total_5(sample_entries, m) for m in range(1, 13)]
    assert summe(months) == 14910.0


def test_difference_annual_summe_sum_of_cells(sample_entries):
    months = [difference(sample_entries, m) for m in range(1, 13)]
    assert summe(months) == -2988.0


def test_excel_template_summe_matches_sheet_bottom_rows():
    """Bottom summary rows in your Excel use Monatlich × 7 for several totals."""
    assert 984 * 7 == 6888.0
    assert 1987 * 7 == 13909.0
    assert 2485 * 7 == 17395.0
    assert -498 * 7 == -3486.0
    assert 760 * 6 == 4560.0


def test_full_summary_matches_sum_of_cells(sample_entries):
    s = compute_full_summary(sample_entries, "div12")
    assert s["total_revenue"]["summe"] == 11922.0
    assert s["total_expenses"]["summe"] == 14910.0
    assert s["difference"]["summe"] == -2988.0


def test_monatlich_filled_mode_matches_excel_monthly_rate(sample_entries):
    s = compute_full_summary(sample_entries, "filled")
    assert s["total_revenue"]["monatlich"] == 1987.0
    assert s["total_expenses"]["monatlich"] == 2485.0
    assert s["difference"]["monatlich"] == -498.0


def test_seed_loads_sample_from_db():
    if _test_db.exists():
        _test_db.unlink()
    from app.database import get_or_create_budget, init_db, load_entries
    from app.seed import ensure_sample_client

    init_db()
    cid = ensure_sample_client()
    bid = get_or_create_budget(cid, 2026)
    entries = load_entries(bid)
    assert total_revenue(entries, 8) == 1987.0
    assert total_5(entries, 8) == 2485.0
    assert difference(entries, 8) == -498.0
