"""Future investment plan projections and API."""

from __future__ import annotations

from app.future_invest import (
    compute_future_invest_plan,
    months_to_reach_target,
    projected_value,
)


def test_months_to_reach_target_with_contributions():
    # 1000 current, 100/month, 0% return, target 2500 -> 15 months
    assert months_to_reach_target(1000, 100, 0, 2500) == 15


def test_projected_value_compounding():
    v = projected_value(1000, 100, 12, 12)
    assert v > 2200


def test_compute_future_invest_plan_enriches():
    plan = compute_future_invest_plan(
        [
            {
                "id": 1,
                "name": "ETF",
                "current_amount": 5000,
                "target_amount": 10000,
                "monthly_contribution": 200,
                "expected_return_annual": 6,
                "target_year": 2030,
            }
        ],
        2026,
    )
    assert plan["total_current"] == 5000
    assert plan["total_target"] == 10000
    assert len(plan["items"]) == 1
    item = plan["items"][0]
    assert item["gap"] == 5000
    assert item["progress_pct"] == 50.0
    assert item["projected_value"] is not None


def test_future_investment_crud_api(api_client):
    r = api_client.post("/api/clients", json={"name": "Invest Co"})
    assert r.status_code == 200
    cid = r.json()["client"]["id"]
    r = api_client.post(
        f"/api/clients/{cid}/future-investments?year=2026",
        json={
            "name": "Pension",
            "current_amount": 1000,
            "target_amount": 5000,
            "monthly_contribution": 150,
            "expected_return_annual": 5,
            "target_year": 2032,
        },
    )
    assert r.status_code == 200
    body = r.json()
    assert body["investment"]["name"] == "Pension"
    plan = body["balance_sheet"]["future_invest_plan"]
    assert plan["total_current"] == 1000
    assert len(plan["items"]) == 1
    iid = body["investment"]["id"]
    r = api_client.put(
        f"/api/clients/{cid}/future-investments/{iid}?year=2026",
        json={
            "name": "Pension",
            "current_amount": 2000,
            "target_amount": 5000,
            "monthly_contribution": 150,
            "expected_return_annual": 5,
            "target_year": 2032,
        },
    )
    assert r.status_code == 200
    assert r.json()["balance_sheet"]["future_invest_plan"]["total_current"] == 2000
    r = api_client.delete(f"/api/clients/{cid}/future-investments/{iid}?year=2026")
    assert r.status_code == 200
    assert r.json()["balance_sheet"]["future_invest_plan"]["items"] == []
