"""Future investment plan projections (contributions + expected return)."""

from __future__ import annotations

import math
from typing import Any


def _monthly_rate(annual_pct: float) -> float:
    return max(0.0, float(annual_pct or 0)) / 100.0 / 12.0


def months_to_reach_target(
    current: float,
    monthly: float,
    annual_rate_pct: float,
    target: float,
    max_months: int = 600,
) -> int | None:
    """Months until balance (with growth + contributions) reaches target."""
    current = float(current or 0)
    target = float(target or 0)
    monthly = float(monthly or 0)
    if target <= 0 or current >= target - 0.01:
        return 0 if target > 0 else None
    if monthly <= 0 and annual_rate_pct <= 0:
        return None
    r = _monthly_rate(annual_rate_pct)
    balance = current
    for month in range(1, max_months + 1):
        balance *= 1.0 + r
        balance += monthly
        if balance >= target - 0.01:
            return month
    return None


def projected_value(
    current: float,
    monthly: float,
    annual_rate_pct: float,
    months: int,
) -> float:
    """Future value after N months of contributions with monthly compounding."""
    current = float(current or 0)
    monthly = float(monthly or 0)
    months = max(0, int(months))
    r = _monthly_rate(annual_rate_pct)
    balance = current
    for _ in range(months):
        balance *= 1.0 + r
        balance += monthly
    return round(balance, 2)


def enrich_future_investment(row: dict[str, Any], budget_year: int) -> dict[str, Any]:
    """Attach computed fields for API / UI."""
    current = float(row.get("current_amount") or 0)
    target = float(row.get("target_amount") or 0)
    monthly = float(row.get("monthly_contribution") or 0)
    rate = float(row.get("expected_return_annual") or 0)
    target_year = row.get("target_year")
    months_horizon: int | None = None
    if target_year is not None and str(target_year).strip() != "":
        try:
            ty = int(target_year)
            months_horizon = max(0, (ty - int(budget_year)) * 12)
        except (TypeError, ValueError):
            months_horizon = None

    months_to_target = months_to_reach_target(current, monthly, rate, target)
    gap = round(max(0.0, target - current), 2) if target > 0 else 0.0
    progress_pct = round(100.0 * current / target, 1) if target > 0 else None

    projected = None
    if months_horizon is not None and months_horizon > 0:
        projected = projected_value(current, monthly, rate, months_horizon)
    elif months_to_target is not None and months_to_target > 0:
        projected = projected_value(current, monthly, rate, months_to_target)

    return {
        **row,
        "gap": gap,
        "progress_pct": progress_pct,
        "months_to_target": months_to_target,
        "projected_value": projected,
        "months_horizon": months_horizon,
    }


def compute_future_invest_plan(
    items: list[dict[str, Any]],
    budget_year: int,
) -> dict[str, Any]:
    enriched = [enrich_future_investment(dict(i), budget_year) for i in items]
    total_current = round(sum(float(i.get("current_amount") or 0) for i in enriched), 2)
    total_target = round(sum(float(i.get("target_amount") or 0) for i in enriched), 2)
    total_monthly = round(sum(float(i.get("monthly_contribution") or 0) for i in enriched), 2)
    overall_progress = (
        round(100.0 * total_current / total_target, 1) if total_target > 0 else None
    )
    return {
        "items": enriched,
        "total_current": total_current,
        "total_target": total_target,
        "total_monthly_contribution": total_monthly,
        "overall_progress_pct": overall_progress,
        "budget_year": budget_year,
    }
