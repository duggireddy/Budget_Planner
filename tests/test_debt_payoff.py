"""Debt payoff projections from budget and monthly repayments."""

import math

from app.debt_payoff import compute_debt_payoff


def _summary(rev, exp):
    diff = rev - exp
    return {
        "total_revenue": {"monatlich": rev, "summe": rev * 12},
        "total_expenses": {"monatlich": exp, "summe": exp * 12},
        "difference": {"monatlich": diff, "summe": diff * 12},
    }


def test_payoff_uses_monthly_repayments():
    debts = [{"id": 1, "name": "Loan", "amount": 1200, "monthly_payment": 100}]
    p = compute_debt_payoff(debts, _summary(3000, 2500))
    assert p["months_to_clear_debts"] == 12
    assert p["per_debt"][0]["months_to_clear"] == 12


def test_payoff_uses_budget_surplus_when_no_repayments():
    debts = [{"id": 1, "name": "Card", "amount": 600, "monthly_payment": 0}]
    p = compute_debt_payoff(debts, _summary(4000, 3500))
    assert p["effective_monthly_payment"] == 500
    assert p["months_to_clear_debts"] == math.ceil(600 / 500)
    assert p["using_budget_surplus"] is True


def test_payoff_income_from_budget():
    debts = []
    p = compute_debt_payoff(debts, _summary(5000, 4000))
    assert p["monthly_income"] == 5000
    assert p["monthly_surplus"] == 1000
    assert p["months_to_clear_debts"] is None


def test_payoff_with_interest_takes_longer():
    debts = [
        {
            "id": 1,
            "name": "Loan",
            "amount": 1200,
            "monthly_payment": 100,
            "interest_rate_annual": 12,
        }
    ]
    p = compute_debt_payoff(debts, _summary(3000, 2500))
    assert p["per_debt"][0]["months_to_clear"] > 12
    assert p["months_to_clear_debts"] > 12


def test_monthly_interest_formula():
    from app.debt_payoff import monthly_interest_on_balance

    assert monthly_interest_on_balance(10000, 5.5) == 45.83
    assert monthly_interest_on_balance(0, 10) == 0.0


def test_car_loan_example_months_with_interest():
    """Car 19k @ 5.5% p.a., 220/month — months must exceed simple 19000/220."""
    debts = [
        {
            "id": 1,
            "name": "Car",
            "amount": 19000,
            "monthly_payment": 220,
            "interest_rate_annual": 5.5,
        }
    ]
    p = compute_debt_payoff(debts, _summary(3000, 2500))
    per = p["per_debt"][0]
    assert per["monthly_interest"] == round(19000 * 5.5 / 100 / 12, 2)
    assert per["months_to_clear"] > math.ceil(19000 / 220)
    assert per["months_to_clear"] == 111


def test_higher_interest_increases_months():
    base = {
        "id": 1,
        "name": "Loan",
        "amount": 10000,
        "monthly_payment": 200,
    }
    p0 = compute_debt_payoff([{**base, "interest_rate_annual": 0}], _summary(3000, 2500))
    p1 = compute_debt_payoff([{**base, "interest_rate_annual": 5.5}], _summary(3000, 2500))
    assert p1["per_debt"][0]["months_to_clear"] > p0["per_debt"][0]["months_to_clear"]
    assert p1["per_debt"][0]["monthly_interest"] == 45.83


def test_payoff_payment_below_interest_never_clears():
    debts = [
        {
            "id": 1,
            "name": "Card",
            "amount": 1200,
            "monthly_payment": 10,
            "interest_rate_annual": 12,
        }
    ]
    p = compute_debt_payoff(debts, _summary(5000, 4000))
    assert p["per_debt"][0]["months_to_clear"] is None
    assert p["per_debt"][0]["payment_covers_interest"] is False
    assert p["any_interest_blocked"] is True
