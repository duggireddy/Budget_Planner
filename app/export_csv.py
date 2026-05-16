"""Flat CSV export of all budget lines for a client/year."""

from __future__ import annotations

import csv
from io import StringIO

from app.calculations import monatlich, summe
from app.categories import MONTH_NAMES_EN, SECTIONS


def build_budget_csv(
    entries: dict[str, list[float]],
    custom_lines_by_section: dict[str, list[dict]] | None = None,
    monatlich_mode: str = "div12",
) -> bytes:
    cl_map = custom_lines_by_section or {}
    buf = StringIO()
    writer = csv.writer(buf, delimiter=";", lineterminator="\n")
    writer.writerow(
        ["Section", "Category (DE)", "Category (EN)", "Key", *MONTH_NAMES_EN, "Summe", "Monatlich"]
    )

    def write_line(section_title: str, key: str, label_de: str, label_en: str) -> None:
        vals = entries.get(key) or [0.0] * 12
        s = summe(vals)
        m = monatlich(vals, monatlich_mode)
        writer.writerow(
            [section_title, label_de, label_en, key, *[f"{v:.2f}" for v in vals], f"{s:.2f}", f"{m:.2f}"]
        )

    for section in SECTIONS:
        title = section.title_en or section.id
        for line in section.lines:
            write_line(title, line.key, line.label_de, line.label_en)
        for cl in cl_map.get(section.id, []):
            key = cl["line_key"]
            write_line(title, key, cl["label_de"], cl["label_en"])

    return buf.getvalue().encode("utf-8-sig")
