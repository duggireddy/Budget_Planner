"""PDF export endpoint."""

from app.export_pdf import build_budget_pdf


def test_pdf_export_bytes(api_client):
    c = api_client.post("/api/clients", json={"name": "PDF Client"}).json()["client"]
    cid = c["id"]
    api_client.get(f"/api/clients/{cid}/budget/2026")
    r = api_client.get(f"/api/clients/{cid}/export/pdf?year=2026")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert r.content[:4] == b"%PDF"


def test_build_pdf_summary():
    entries = {"rent": [100.0] * 12}
    data = build_budget_pdf(
        {"name": "Test", "company_name": ""},
        2026,
        entries,
        "div12",
        {},
        {"total_assets": 1000, "total_debts": 200, "net_worth": 800},
    )
    assert data.startswith(b"%PDF")
