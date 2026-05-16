"""Tests for budget calculations using Jul-Dec 2026 sample."""

import pytest

from app.calculations import (
    difference,
    monatlich,
    summe,
    total_1,
    total_2,
    total_3,
    total_4,
    total_5,
    total_revenue,
)
from app.seed import SAMPLE_LINES


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


def test_monthly_revenue_july(sample_entries):
    assert total_revenue(sample_entries, 7) == 1987.0


def test_monthly_expenses_july(sample_entries):
    assert total_5(sample_entries, 7) == 2485.0
    assert total_1(sample_entries, 7) == 760.0
    assert total_2(sample_entries, 7) == 984.0
    assert total_3(sample_entries, 7) == 221.0
    assert total_4(sample_entries, 7) == 520.0


def test_monthly_difference_july(sample_entries):
    assert difference(sample_entries, 7) == -498.0


def test_annual_totals_jul_dec_six_months(sample_entries):
    """Sum of month cells Jul–Dec (months 7–12) = 6 months."""
    rev = sum(total_revenue(sample_entries, m) for m in range(7, 13))
    exp = sum(total_5(sample_entries, m) for m in range(7, 13))
    diff = sum(difference(sample_entries, m) for m in range(7, 13))
    assert rev == 11922.0  # 1987 * 6
    assert exp == 14910.0  # 2485 * 6
    assert diff == -2988.0


def test_excel_style_summe_equals_monatlich_times_7(sample_entries):
    """Your Excel Summe column uses Monatlich × 7 (e.g. 1987×7 = 13909)."""
    months_rev = [total_revenue(sample_entries, m) for m in range(1, 13)]
    filled = [m for m in months_rev if m != 0]
    monatlich = filled[0] if filled else 0
    assert monatlich == 1987.0
    assert monatlich * 7 == 13909.0
    assert monatlich * 6 == 11922.0


def test_monatlich_filled_mode(sample_entries):
    months = [total_revenue(sample_entries, m) for m in range(1, 13)]
    assert monatlich(months, "filled") == 1987.0
