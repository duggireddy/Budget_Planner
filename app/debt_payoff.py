"""Debt payoff projections from budget surplus, repayments, and interest."""

from __future__ import annotations

import math
from datetime import date
from typing import Any


def _add_months(start: date, months: int) -> tuple[int, int]:
    y = start.year + (start.month - 1 + months) // 12
    m = (start.month - 1 + months) % 12 + 1
    return y, m


def _monthly_rate(annual_rate_pct: float) -> float:
    return max(0.0, float(annual_rate_pct or 0)) / 100.0 / 12.0


def monthly_interest_on_balance(principal: float, annual_rate_pct: float) -> float:
    """First-month interest: outstanding × (annual % / 100) / 12."""
    principal = float(principal or 0)
    if principal <= 0:
        return 0.0
    return round(principal * _monthly_rate(annual_rate_pct), 2)


def months_to_clear_amortizing(
    principal: float,
    payment: float,
    annual_rate_pct: float = 0.0,
) -> int | None:
    """Months to pay off one loan with fixed payment (amortization). None if never."""
    principal = float(principal or 0)
    payment = float(payment or 0)
    if principal <= 0:
        return 0
    if payment <= 0:
        return None
    r = _monthly_rate(annual_rate_pct)
    if r <= 0:
        return int(math.ceil(principal / payment))
    interest = monthly_interest_on_balance(principal, annual_rate_pct)
    if payment <= interest + 1e-9:
        return None
    ratio = 1.0 - interest / payment
    if ratio <= 0:
        return 0
    n = -math.log(ratio) / math.log(1.0 + r)
    return max(1, int(math.ceil(n)))


def _simulate_portfolio_months(
    items: list[dict[str, float]],
    max_months: int = 600,
) -> int | None:
    """Simulate balances with interest until all cleared or impossible."""
    balances = [float(i["balance"]) for i in items]
    rates = [float(i["rate"]) for i in items]
    payments = [float(i["payment"]) for i in items]
    if not balances or sum(balances) <= 0:
        return 0
    if sum(payments) <= 0:
        return None
    for month in range(1, max_months + 1):
        active = False
        for i in range(len(balances)):
            if balances[i] <= 0.005:
                balances[i] = 0.0
                continue
            active = True
            balances[i] *= 1.0 + rates[i]
            pay = min(payments[i], balances[i])
            balances[i] -= pay
        if not active:
            return month - 1 if month > 1 else 0
        if all(b <= 0.005 for b in balances):
            return month
    return None


def compute_debt_payoff(
    debts: list[dict[str, Any]],
    summary: dict[str, Any] | None,
) -> dict[str, Any]:
    """
    Combine budget cashflow (income − expenses) with debt balances,
    monthly repayments, and annual interest rates (%).
    """
    total_debt = round(sum(float(d.get("amount") or 0) for d in debts), 2)
    total_scheduled = round(sum(float(d.get("monthly_payment") or 0) for d in debts), 2)

    monthly_income = 0.0
    monthly_expenses = 0.0
    monthly_surplus = 0.0
    annual_income = 0.0
    annual_expenses = 0.0
    annual_surplus = 0.0

    if summary:
        monthly_income = float(summary["total_revenue"]["monatlich"])
        monthly_expenses = float(summary["total_expenses"]["monatlich"])
        monthly_surplus = float(summary["difference"]["monatlich"])
        annual_income = float(summary["total_revenue"]["summe"])
        annual_expenses = float(summary["total_expenses"]["summe"])
        annual_surplus = float(summary["difference"]["summe"])

    effective_payment = total_scheduled if total_scheduled > 0 else max(0.0, monthly_surplus)

    per_debt: list[dict[str, Any]] = []
    sim_items: list[dict[str, float]] = []

    for d in debts:
        amt = float(d.get("amount") or 0)
        pay = float(d.get("monthly_payment") or 0)
        rate_pct = float(d.get("interest_rate_annual") or 0)
        if pay <= 0 and effective_payment > 0 and total_debt > 0 and amt > 0:
            pay = round(effective_payment * (amt / total_debt), 2)
        months_one = months_to_clear_amortizing(amt, pay, rate_pct)
        free_label: str | None = None
        if months_one is not None and months_one > 0:
            y, m = _add_months(date.today(), months_one)
            free_label = f"{y}-{m:02d}"
        monthly_interest = monthly_interest_on_balance(amt, rate_pct)
        covers_interest = (
            pay > monthly_interest + 1e-9 if amt > 0 and rate_pct > 0 else True
        )
        per_debt.append(
            {
                "id": d.get("id"),
                "name": d.get("name"),
                "amount": amt,
                "interest_rate_annual": round(rate_pct, 4),
                "monthly_payment": float(d.get("monthly_payment") or 0),
                "planned_payment": pay,
                "monthly_interest": monthly_interest,
                "payment_covers_interest": covers_interest,
                "months_to_clear": months_one,
                "debt_free_label": free_label,
            }
        )
        if amt > 0:
            sim_items.append(
                {
                    "balance": amt,
                    "rate": _monthly_rate(rate_pct),
                    "payment": pay,
                }
            )

    months_to_clear: int | None = None
    if sim_items:
        months_to_clear = _simulate_portfolio_months(sim_items)
    debt_free_label: str | None = None
    if months_to_clear is not None and months_to_clear > 0:
        y, m = _add_months(date.today(), months_to_clear)
        debt_free_label = f"{y}-{m:02d}"
    elif total_debt > 0 and effective_payment > 0 and not any(
        p.get("interest_rate_annual", 0) > 0 for p in per_debt
    ):
        months_to_clear = int(math.ceil(total_debt / effective_payment))
        y, m = _add_months(date.today(), months_to_clear)
        debt_free_label = f"{y}-{m:02d}"

    any_interest_blocked = any(
        p["amount"] > 0
        and p["interest_rate_annual"] > 0
        and not p["payment_covers_interest"]
        for p in per_debt
    )
    total_monthly_interest = round(
        sum(float(p.get("monthly_interest") or 0) for p in per_debt), 2
    )

    return {
        "monthly_income": round(monthly_income, 2),
        "monthly_expenses": round(monthly_expenses, 2),
        "monthly_surplus": round(monthly_surplus, 2),
        "annual_income": round(annual_income, 2),
        "annual_expenses": round(annual_expenses, 2),
        "annual_surplus": round(annual_surplus, 2),
        "total_debt": total_debt,
        "total_monthly_payment": total_scheduled,
        "effective_monthly_payment": round(effective_payment, 2),
        "months_to_clear_debts": months_to_clear,
        "debt_free_label": debt_free_label,
        "using_budget_surplus": total_scheduled <= 0 and effective_payment > 0,
        "any_interest_blocked": any_interest_blocked,
        "total_monthly_interest": total_monthly_interest,
        "per_debt": per_debt,
    }
