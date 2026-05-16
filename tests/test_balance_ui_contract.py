"""Contract tests matching the Assets & Debts UI (POST ?year=, balance_sheet in body)."""

import math

import pytest


@pytest.fixture
def client_year(api_client):
    c = api_client.post("/api/clients", json={"name": "UI Contract Client"}).json()["client"]
    cid = c["id"]
    year = 2026
    api_client.get(f"/api/clients/{cid}/budget/{year}")
    return cid, year


def test_post_asset_with_year_query_returns_balance_sheet(api_client, client_year):
    cid, year = client_year
    r = api_client.post(
        f"/api/clients/{cid}/assets?year={year}",
        json={"name": "www", "amount": 77, "asset_type": "other", "notes": ""},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert "balance_sheet" in body
    bs = body["balance_sheet"]
    assert bs["total_assets"] == 77.0
    assert len(bs["assets"]) == 1
    assert bs["assets"][0]["name"] == "www"


def test_post_debt_then_balance_sheet_matches(api_client, client_year):
    cid, year = client_year
    api_client.post(
        f"/api/clients/{cid}/assets?year={year}",
        json={"name": "Cash", "amount": 100, "asset_type": "other"},
    )
    r = api_client.post(
        f"/api/clients/{cid}/debts?year={year}",
        json={"name": "333", "amount": 77, "monthly_payment": 77, "notes": ""},
    )
    assert r.status_code == 200
    bs = r.json()["balance_sheet"]
    assert bs["total_debts"] == 77.0
    assert bs["total_assets"] == 100.0
    assert bs["net_worth"] == 23.0
    assert bs["payoff"] is not None
    assert bs["payoff"]["months_to_clear_debts"] == 1


def test_debt_interest_rate_affects_payoff(api_client, client_year):
    cid, year = client_year
    r = api_client.post(
        f"/api/clients/{cid}/debts?year={year}",
        json={
            "name": "Loan",
            "amount": 10000,
            "monthly_payment": 200,
            "interest_rate_annual": 5.5,
            "notes": "",
        },
    )
    assert r.status_code == 200, r.text
    bs = r.json()["balance_sheet"]
    debt = bs["debts"][0]
    assert debt["interest_rate_annual"] == 5.5
    payoff = bs["payoff"]
    assert payoff["total_monthly_interest"] > 0
    per = payoff["per_debt"][0]
    assert per["monthly_interest"] > 0
    assert per["interest_rate_annual"] == 5.5
    assert per["months_to_clear"] is not None
    assert per["months_to_clear"] > 1
    assert per["months_to_clear"] > math.ceil(10000 / 200)


def test_put_debt_interest_persists(api_client, client_year):
    cid, year = client_year
    created = api_client.post(
        f"/api/clients/{cid}/debts?year={year}",
        json={
            "name": "Car",
            "amount": 19000,
            "monthly_payment": 220,
            "interest_rate_annual": 0,
            "notes": "",
        },
    ).json()
    did = created["debt"]["id"]
    assert created["debt"]["interest_rate_annual"] == 0

    updated = api_client.put(
        f"/api/clients/{cid}/debts/{did}?year={year}",
        json={
            "name": "Car",
            "amount": 19000,
            "monthly_payment": 220,
            "interest_rate_annual": 5.5,
            "notes": "",
        },
    )
    assert updated.status_code == 200, updated.text
    debt = updated.json()["debt"]
    assert debt["interest_rate_annual"] == 5.5
    per = updated.json()["balance_sheet"]["payoff"]["per_debt"][0]
    assert per["monthly_interest"] == round(19000 * 5.5 / 100 / 12, 2)
    assert per["months_to_clear"] > math.ceil(19000 / 220)

    reloaded = api_client.get(f"/api/clients/{cid}/balance-sheet?year={year}").json()
    saved = next(d for d in reloaded["debts"] if d["id"] == did)
    assert saved["interest_rate_annual"] == 5.5


def test_put_debt_interest_sequential_keeps_latest(api_client, client_year):
    cid, year = client_year
    did = api_client.post(
        f"/api/clients/{cid}/debts?year={year}",
        json={
            "name": "Gold",
            "amount": 14000,
            "monthly_payment": 200,
            "interest_rate_annual": 0,
            "notes": "",
        },
    ).json()["debt"]["id"]

    body = {
        "name": "Gold",
        "amount": 14000,
        "monthly_payment": 200,
        "notes": "",
    }
    api_client.put(
        f"/api/clients/{cid}/debts/{did}?year={year}",
        json={**body, "interest_rate_annual": 5},
    )
    final = api_client.put(
        f"/api/clients/{cid}/debts/{did}?year={year}",
        json={**body, "interest_rate_annual": 5.5},
    ).json()

    assert final["debt"]["interest_rate_annual"] == 5.5
    assert final["balance_sheet"]["payoff"]["per_debt"][0]["interest_rate_annual"] == 5.5


def test_budget_load_includes_saved_assets(api_client, client_year):
    cid, year = client_year
    api_client.post(
        f"/api/clients/{cid}/assets?year={year}",
        json={"name": "Saved", "amount": 50, "asset_type": "other"},
    )
    budget = api_client.get(f"/api/clients/{cid}/budget/{year}").json()
    assert budget["balance_sheet"]["total_assets"] == 50.0
    assert any(a["name"] == "Saved" for a in budget["balance_sheet"]["assets"])
