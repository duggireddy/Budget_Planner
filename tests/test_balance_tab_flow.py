"""Full assets & debts tab flow with rough sample data."""


def test_balance_tab_rough_data_crud(api_client):
    c = api_client.post("/api/clients", json={"name": "Rough Data Client"}).json()["client"]
    cid = c["id"]
    year = 2026

    # Seed budget year so payoff is included
    api_client.get(f"/api/clients/{cid}/budget/{year}")

    assets = [
        ("Savings", 12000),
        ("ETF portfolio", 45000),
        ("Gold", 8000),
    ]
    for name, amount in assets:
        r = api_client.post(
            f"/api/clients/{cid}/assets",
            json={"name": name, "amount": amount, "asset_type": "other"},
        )
        assert r.status_code == 200, r.text

    debts = [
        ("Mortgage", 180000, 1200, 3.5),
        ("Car loan", 8500, 350, 5.5),
    ]
    for name, amount, payment, rate in debts:
        r = api_client.post(
            f"/api/clients/{cid}/debts?year={year}",
            json={
                "name": name,
                "amount": amount,
                "monthly_payment": payment,
                "interest_rate_annual": rate,
                "notes": "",
            },
        )
        assert r.status_code == 200, r.text

    bs = api_client.get(f"/api/clients/{cid}/balance-sheet?year={year}").json()
    assert bs["total_assets"] == 65000.0
    assert bs["total_debts"] == 188500.0
    assert bs["net_worth"] == -123500.0
    assert len(bs["assets"]) == 3
    assert len(bs["debts"]) == 2
    assert bs["payoff"]["total_monthly_payment"] == 1550.0
    assert bs["payoff"]["total_monthly_interest"] > 0
    mortgage = next(d for d in bs["debts"] if d["name"] == "Mortgage")
    assert mortgage["interest_rate_annual"] == 3.5

    # Update first asset
    aid = bs["assets"][0]["id"]
    r = api_client.put(
        f"/api/clients/{cid}/assets/{aid}?year={year}",
        json={"name": "Savings", "amount": 15000, "asset_type": "other", "notes": ""},
    )
    assert r.status_code == 200
    assert r.json()["balance_sheet"]["total_assets"] == 68000.0

    # Delete second debt
    did = bs["debts"][1]["id"]
    r = api_client.delete(f"/api/clients/{cid}/debts/{did}?year={year}")
    assert r.status_code == 200
    bs2 = r.json()["balance_sheet"]
    assert len(bs2["debts"]) == 1
    assert bs2["total_debts"] == 180000.0

    # Raise mortgage interest via PUT (simulates editing interest % in UI)
    mid = bs["debts"][0]["id"]
    r = api_client.put(
        f"/api/clients/{cid}/debts/{mid}?year={year}",
        json={
            "name": "Mortgage",
            "amount": 180000,
            "monthly_payment": 1200,
            "interest_rate_annual": 4.0,
            "notes": "",
        },
    )
    assert r.status_code == 200
    assert r.json()["debt"]["interest_rate_annual"] == 4.0
    per = r.json()["balance_sheet"]["payoff"]["per_debt"][0]
    assert per["months_to_clear"] is not None

    budget = api_client.get(f"/api/clients/{cid}/budget/{year}").json()
    assert "balance_sheet" in budget
    assert budget["balance_sheet"]["total_assets"] == 68000.0
