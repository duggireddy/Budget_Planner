"""CSV export."""

from app.export_csv import build_budget_csv


def test_csv_has_header_and_section_row():
    entries = {"rent": [100.0] * 12}
    data = build_budget_csv(entries, {}, "div12").decode("utf-8-sig")
    lines = data.strip().split("\n")
    assert lines[0].startswith("Section;")
    assert "Living" in data or "rent" in data
