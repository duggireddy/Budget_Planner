"""Custom budget rows: API, grid, and totals across tabs."""

from app.calculations import compute_full_summary, difference, section_total, total_1, total_revenue
from app.database import create_custom_line, custom_line_keys_by_section, get_or_create_budget, upsert_entry


def test_custom_line_in_living_expenses(api_client):
    c = api_client.post("/api/clients", json={"name": "Custom Living"}).json()["client"]
    cid = c["id"]
    r = api_client.post(
        f"/api/clients/{cid}/budget/2026/custom-lines",
        json={
            "section_id": "living",
            "label_de": "Gym",
            "label_en": "Gym",
            "line_type": "expense",
        },
    )
    assert r.status_code == 200
    key = r.json()["line"]["line_key"]
    api_client.post(
        f"/api/clients/{cid}/budget/2026/entry",
        json={"line_key": key, "month": 3, "amount": 80.0},
    )
    b = api_client.get(f"/api/clients/{cid}/budget/2026").json()
    assert key in b["entries"]
    assert b["entries"][key][2] == 80.0
    assert b["summary"]["total_1"]["months"][2] >= 80.0


def test_custom_line_in_self_employed_b_income(api_client):
    c = api_client.post("/api/clients", json={"name": "Custom SE B"}).json()["client"]
    cid = c["id"]
    r = api_client.post(
        f"/api/clients/{cid}/budget/2026/custom-lines",
        json={
            "section_id": "self_employed_b",
            "label_de": "Extra project",
            "label_en": "Extra project",
            "line_type": "income",
        },
    )
    assert r.status_code == 200
    key = r.json()["line"]["line_key"]
    api_client.post(
        f"/api/clients/{cid}/budget/2026/entry",
        json={"line_key": key, "month": 1, "amount": 500.0},
    )
    summary = api_client.get(f"/api/clients/{cid}/budget/2026/summary?month=1").json()["summary"]
    charts = api_client.get(f"/api/clients/{cid}/budget/2026/summary?month=1").json()["charts"]
    assert summary["total_revenue"]["months"][0] >= 500.0
    assert charts["hero"]["revenue"] >= 500.0


def test_custom_line_alt_url(api_client):
    c = api_client.post("/api/clients", json={"name": "Alt URL"}).json()["client"]
    cid = c["id"]
    r = api_client.post(
        f"/api/clients/{cid}/custom-lines?year=2026",
        json={
            "section_id": "housing",
            "label_de": "Extra",
            "label_en": "Extra",
            "line_type": "expense",
        },
    )
    assert r.status_code == 200
    assert "line" in r.json()


def test_calculations_custom_expense_and_income():
    from app.seed import ensure_sample_client

    cid = ensure_sample_client()
    bid = get_or_create_budget(cid, 2026)
    line = create_custom_line(bid, "living", "Club", "Club", "expense")
    upsert_entry(bid, line["line_key"], 1, 40.0)
    ck = custom_line_keys_by_section(bid)
    entries = {line["line_key"]: [40.0] + [0.0] * 11}
    assert total_1(entries, 1, ck) >= 40.0

    inc = create_custom_line(bid, "self_employed_b", "Bonus", "Bonus", "income")
    entries[inc["line_key"]] = [100.0] + [0.0] * 11
    ck = custom_line_keys_by_section(bid)
    assert total_revenue(entries, 1, ck) >= 100.0
    summary = compute_full_summary(entries, "div12", ck)
    assert summary["difference"]["months"][0] == difference(entries, 1, ck)
