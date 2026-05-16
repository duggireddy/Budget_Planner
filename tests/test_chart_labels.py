"""Donut chart slices must expose both EN and DE labels."""
from app.calculations import chart_payload


def test_donut_sections_have_label_en_and_label_de():
    charts = chart_payload({}, month=8)
    living = next(s for s in charts["donut_sections"] if s["id"] == "living")
    assert living["label_en"] == "Living"
    assert living["label_de"] == "Lebenshaltung"
    assert living["label"] == "Living"
