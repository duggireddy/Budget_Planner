"""Use-case tests: assets, debts, net worth (API level)."""


def test_uc_add_asset_updates_totals(api_client):
  c = api_client.post("/api/clients", json={"name": "UC Asset Client"}).json()["client"]
  cid = c["id"]
  bs0 = api_client.get(f"/api/clients/{cid}/balance-sheet").json()
  assert bs0["total_assets"] == 0
  assert bs0["net_worth"] == 0

  api_client.post(
      f"/api/clients/{cid}/assets",
      json={"name": "Savings", "amount": 1000, "asset_type": "other"},
  )
  bs1 = api_client.get(f"/api/clients/{cid}/balance-sheet").json()
  assert bs1["total_assets"] == 1000.0
  assert bs1["net_worth"] == 1000.0
  assert len(bs1["assets"]) == 1


def test_uc_assets_minus_debts_net_worth(api_client):
  c = api_client.post("/api/clients", json={"name": "UC Net Worth Client"}).json()["client"]
  cid = c["id"]
  api_client.post(f"/api/clients/{cid}/assets", json={"name": "Gold", "amount": 5000})
  api_client.post(f"/api/clients/{cid}/debts", json={"name": "Loan", "amount": 1200})
  bs = api_client.get(f"/api/clients/{cid}/balance-sheet").json()
  assert bs["total_assets"] == 5000.0
  assert bs["total_debts"] == 1200.0
  assert bs["net_worth"] == 3800.0


def test_balance_sheet_includes_payoff(api_client):
    c = api_client.post("/api/clients", json={"name": "Payoff Client"}).json()["client"]
    cid = c["id"]
    api_client.post(f"/api/clients/{cid}/debts", json={"name": "Loan", "amount": 1200, "monthly_payment": 100})
    bs = api_client.get(f"/api/clients/{cid}/balance-sheet?year=2026").json()
    assert "payoff" in bs
    assert bs["payoff"]["total_debt"] == 1200
    assert bs["payoff"]["months_to_clear_debts"] == 12


def test_uc_budget_includes_balance_sheet(api_client):
  from app.seed import ensure_sample_client

  cid = ensure_sample_client()
  b = api_client.get(f"/api/clients/{cid}/budget/2026").json()
  assert "balance_sheet" in b
  assert "total_assets" in b["balance_sheet"]
  assert "net_worth" in b["balance_sheet"]
