"""Debt interest and amortization formulas (matches static/app.js and app/debt_payoff.py)."""

import math

from app.debt_payoff import compute_debt_payoff, monthly_interest_on_balance, months_to_clear_amortizing


def _summary(rev=5000, exp=4000):
    diff = rev - exp
    return {
        "total_revenue": {"monatlich": rev, "summe": rev * 12},
        "total_expenses": {"monatlich": exp, "summe": exp * 12},
        "difference": {"monatlich": diff, "summe": diff * 12},
    }


def test_interest_formula_matches_outstanding_times_rate():
    assert monthly_interest_on_balance(19000, 5.5) == round(19000 * 5.5 / 100 / 12, 2)
    assert monthly_interest_on_balance(0, 10) == 0.0


def test_months_with_interest_exceeds_simple_division():
    simple = math.ceil(19000 / 220)
    with_interest = months_to_clear_amortizing(19000, 220, 5.5)
    assert with_interest is not None
    assert with_interest > simple
    assert with_interest == 111


def test_portfolio_payoff_sums_interest(api_client):
    c = api_client.post("/api/clients", json={"name": "Multi Debt"}).json()["client"]
    cid = c["id"]
    year = 2026
    api_client.get(f"/api/clients/{cid}/budget/{year}")
    for name, amount, pay, rate in [
        ("Car", 19000, 220, 5.5),
        ("Gold", 14000, 200, 4.0),
    ]:
        api_client.post(
            f"/api/clients/{cid}/debts?year={year}",
            json={
                "name": name,
                "amount": amount,
                "monthly_payment": pay,
                "interest_rate_annual": rate,
                "notes": "",
            },
        )
    bs = api_client.get(f"/api/clients/{cid}/balance-sheet?year={year}").json()
    payoff = bs["payoff"]
    assert payoff["total_monthly_interest"] > 0
    per_sum = sum(p["monthly_interest"] for p in payoff["per_debt"])
    assert abs(per_sum - payoff["total_monthly_interest"]) < 0.02
    assert bs["total_debts"] == 33000.0
