"""REST API for assets, debts, and custom budget lines."""


def test_assets_debts_crud(api_client):
    c = api_client.post("/api/clients", json={"name": "Balance Test Co"}).json()["client"]
    cid = c["id"]
    a = api_client.post(
        f"/api/clients/{cid}/assets",
        json={"name": "ETF", "asset_type": "etf", "amount": 8000},
    )
    assert a.status_code == 200
    d = api_client.post(
        f"/api/clients/{cid}/debts",
        json={"name": "Mortgage", "amount": 2000},
    )
    assert d.status_code == 200
    bs = api_client.get(f"/api/clients/{cid}/balance-sheet").json()
    assert bs["total_assets"] == 8000.0
    assert bs["net_worth"] == 6000.0
    aid = a.json()["asset"]["id"]
    api_client.delete(f"/api/clients/{cid}/assets/{aid}")
    assert api_client.get(f"/api/clients/{cid}/balance-sheet").json()["total_assets"] == 0.0


def test_custom_line_in_budget(api_client):
    c = api_client.post("/api/clients", json={"name": "Custom Line Co"}).json()["client"]
    cid = c["id"]
    r = api_client.post(
        f"/api/clients/{cid}/budget/2026/custom-lines",
        json={
            "section_id": "living",
            "label_de": "Club",
            "label_en": "Club",
            "line_type": "expense",
        },
    )
    assert r.status_code == 200
    key = r.json()["line"]["line_key"]
    api_client.post(
        f"/api/clients/{cid}/budget/2026/entry",
        json={"line_key": key, "month": 1, "amount": 42.0},
    )
    b2 = api_client.get(f"/api/clients/{cid}/budget/2026").json()
    assert b2["entries"].get(key, [0])[0] == 42.0
    api_client.delete(f"/api/clients/{cid}/budget/2026/custom-lines/{key}")


def test_excel_download(api_client):
    from app.seed import ensure_sample_client

    cid = ensure_sample_client()
    r = api_client.get(f"/api/clients/{cid}/export/excel", params={"year": 2026})
    assert r.status_code == 200
    assert "spreadsheet" in r.headers.get("content-type", "")
    assert len(r.content) > 5000
