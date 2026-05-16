"""Tests for client assets/debts and custom budget lines."""

from app.calculations import compute_full_summary, total_5
from app.database import (
    compute_balance_sheet,
    create_asset,
    create_custom_line,
    create_debt,
    custom_line_keys_by_section,
    get_or_create_budget,
    upsert_entry,
)
from app.seed import ensure_sample_client


def test_balance_sheet_net_worth():
    ensure_sample_client()
    from app.database import list_clients

    cid = list_clients()[0]["id"]
    create_asset(cid, {"name": "Savings", "asset_type": "savings", "amount": 10000})
    create_asset(cid, {"name": "Gold", "asset_type": "gold", "amount": 5000})
    create_debt(cid, {"name": "Car loan", "amount": 3000})
    bs = compute_balance_sheet(cid)
    assert bs["total_assets"] == 15000.0
    assert bs["total_debts"] == 3000.0
    assert bs["net_worth"] == 12000.0


def test_custom_line_included_in_expenses():
    ensure_sample_client()
    from app.database import list_clients

    cid = list_clients()[0]["id"]
    bid = get_or_create_budget(cid, 2026)
    line = create_custom_line(bid, "living", "Extra hobby", "Extra hobby", "expense")
    upsert_entry(bid, line["line_key"], 1, 100.0)
    entries = {line["line_key"]: [100.0] + [0.0] * 11}
    ck = custom_line_keys_by_section(bid)
    assert total_5(entries, 1, ck) >= 100.0
    summary = compute_full_summary(entries, "div12", ck)
    assert summary["total_1"]["months"][0] >= 100.0
