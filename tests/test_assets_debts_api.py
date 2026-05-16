"""Asset and debt POST endpoints (multiple URL styles)."""


def test_post_asset_without_year_query(api_client):
    c = api_client.post("/api/clients", json={"name": "Asset URL Test"}).json()["client"]
    cid = c["id"]
    r = api_client.post(
        f"/api/clients/{cid}/assets",
        json={"name": "Cash", "amount": 100, "asset_type": "other"},
    )
    assert r.status_code == 200
    bs = r.json()["balance_sheet"]
    assert bs["total_assets"] >= 100
    assert any(a["name"] == "Cash" for a in bs["assets"])


def test_post_debt_without_year_query(api_client):
    c = api_client.post("/api/clients", json={"name": "Debt URL Test"}).json()["client"]
    cid = c["id"]
    r = api_client.post(
        f"/api/clients/{cid}/debts",
        json={"name": "Loan", "amount": 500, "monthly_payment": 50},
    )
    assert r.status_code == 200
    bs = r.json()["balance_sheet"]
    assert bs["total_debts"] >= 500
    assert bs["payoff"]["months_to_clear_debts"] == 10
