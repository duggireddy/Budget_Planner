"""Sample investment plans and end-to-end add flow (matches UI form)."""

from __future__ import annotations

import math

from app.future_invest import compute_future_invest_plan


def test_sample_plan_eee_etfs():
    """User-like row: current 222, target 2222, 120/mo, 6% return, target year 2032."""
    plan = compute_future_invest_plan(
        [
            {
                "id": 1,
                "name": "eee",
                "current_amount": 222,
                "target_amount": 2222,
                "monthly_contribution": 120,
                "expected_return_annual": 6,
                "target_year": 2032,
            }
        ],
        2026,
    )
    assert plan["total_current"] == 222
    assert plan["total_target"] == 2222
    assert plan["total_monthly_contribution"] == 120
    item = plan["items"][0]
    assert item["gap"] == 2000
    assert item["progress_pct"] == round(100 * 222 / 2222, 1)
    assert item["months_to_target"] is not None
    assert item["months_to_target"] < math.ceil(2000 / 120)
    assert item["projected_value"] is not None
    assert item["projected_value"] > 222


def test_api_add_sample_plan(api_client):
    c = api_client.post("/api/clients", json={"name": "Future Plan Client"}).json()["client"]
    cid = c["id"]
    year = 2026
    r = api_client.post(
        f"/api/clients/{cid}/future-investments?year={year}",
        json={
            "name": "eee",
            "investment_type": "other",
            "current_amount": 222,
            "target_amount": 2222,
            "monthly_contribution": 120,
            "expected_return_annual": 6,
            "target_year": 2032,
            "notes": "",
        },
    )
    assert r.status_code == 200, r.text
    body = r.json()
    plan = body["balance_sheet"]["future_invest_plan"]
    assert len(plan["items"]) == 1
    assert plan["items"][0]["name"] == "eee"
    assert plan["total_current"] == 222
    assert plan["total_target"] == 2222

    budget = api_client.get(f"/api/clients/{cid}/budget/{year}").json()
    assert budget["balance_sheet"]["future_invest_plan"]["total_current"] == 222

    sheet = api_client.get(f"/api/clients/{cid}/balance-sheet?year={year}").json()
    assert sheet["future_invest_plan"]["items"][0]["monthly_contribution"] == 120


def test_api_multiple_goals(api_client):
    c = api_client.post("/api/clients", json={"name": "Multi Goal"}).json()["client"]
    cid = c["id"]
    for payload in (
        {
            "name": "ETF",
            "current_amount": 5000,
            "target_amount": 50000,
            "monthly_contribution": 300,
            "expected_return_annual": 7,
            "target_year": 2035,
        },
        {
            "name": "Pension",
            "current_amount": 12000,
            "target_amount": 200000,
            "monthly_contribution": 400,
            "expected_return_annual": 5,
            "target_year": 2040,
        },
    ):
        r = api_client.post(
            f"/api/clients/{cid}/future-investments?year=2026",
            json={**payload, "investment_type": "other", "notes": ""},
        )
        assert r.status_code == 200, r.text
    plan = api_client.get(f"/api/clients/{cid}/balance-sheet?year=2026").json()[
        "future_invest_plan"
    ]
    assert len(plan["items"]) == 2
    assert plan["total_current"] == 17000
    assert plan["total_target"] == 250000
