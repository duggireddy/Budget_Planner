"""Client-ready multi-sheet Excel export (overview, monthly, yearly, charts, children, details)."""

from __future__ import annotations

from datetime import date
from io import BytesIO

from openpyxl import Workbook
from openpyxl.chart import BarChart, PieChart, Reference
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from app.calculations import (
    chart_payload,
    children_total,
    compute_full_summary,
    monatlich,
    section_total,
    summe,
    total_1,
    total_2,
    total_3,
    total_4,
    total_5,
    total_revenue,
)
from app.categories import MONTH_NAMES_DE, MONTH_NAMES_EN, SECTIONS, sections_for_tab

# Styles
_FILL_HEADER = PatternFill("solid", fgColor="2563EB")
_FILL_SECTION = PatternFill("solid", fgColor="DBEAFE")
_FILL_SUBHEADER = PatternFill("solid", fgColor="E2E8F0")
_FILL_POSITIVE = PatternFill("solid", fgColor="D1FAE5")
_FILL_NEGATIVE = PatternFill("solid", fgColor="FEE2E2")
_FONT_HEADER = Font(bold=True, color="FFFFFF", size=11)
_FONT_TITLE = Font(bold=True, size=14)
_FONT_BOLD = Font(bold=True)
_FONT_SECTION = Font(bold=True, size=11)
_ALIGN_WRAP = Alignment(wrap_text=True, vertical="top")
_THIN = Side(style="thin", color="CBD5E1")
_BORDER = Border(left=_THIN, right=_THIN, top=_THIN, bottom=_THIN)
_NUM_FMT = '#,##0.00'


def _style_header_row(ws, row: int, ncol: int) -> None:
    for c in range(1, ncol + 1):
        cell = ws.cell(row=row, column=c)
        cell.fill = _FILL_HEADER
        cell.font = _FONT_HEADER
        cell.border = _BORDER
        cell.alignment = Alignment(horizontal="center", vertical="center")


def _write_row(ws, row: int, values: list, bold: bool = False, fmt_money: bool = False) -> None:
    for col, val in enumerate(values, start=1):
        cell = ws.cell(row=row, column=col, value=val)
        cell.border = _BORDER
        if bold:
            cell.font = _FONT_BOLD
        if fmt_money and isinstance(val, (int, float)) and col > 1:
            cell.number_format = _NUM_FMT


def _autosize(ws, max_col: int, min_width: int = 10, max_width: int = 42) -> None:
    for col in range(1, max_col + 1):
        letter = get_column_letter(col)
        best = min_width
        for row in ws.iter_rows(min_col=col, max_col=col):
            for cell in row:
                if cell.value is not None:
                    best = max(best, min(len(str(cell.value)) + 2, max_width))
        ws.column_dimensions[letter].width = best


def _sheet_overview(wb: Workbook, client: dict, year: int, summary: dict, charts: dict) -> None:
    ws = wb.create_sheet("Overview", 0)
    ws["A1"] = "Annual Budget Report"
    ws["A1"].font = _FONT_TITLE
    ws.merge_cells("A1:D1")

    info = [
        ("Client", client.get("name", "")),
        ("Company", client.get("company_name") or "—"),
        ("Year", year),
        ("Report date", date.today().isoformat()),
    ]
    r = 3
    for label, val in info:
        ws.cell(row=r, column=1, value=label).font = _FONT_BOLD
        ws.cell(row=r, column=2, value=val)
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Annual key figures (full year)").font = _FONT_SECTION
    r += 1
    _write_row(ws, r, ["Metric", "Amount", "Description"], bold=True)
    _style_header_row(ws, r, 3)
    r += 1

    rev = summary["total_revenue"]["summe"]
    exp = summary["total_expenses"]["summe"]
    diff = summary["difference"]["summe"]
    ch = summary.get("total_children", {}).get("summe", 0)

    bs = charts.get("balance_sheet") or {}
    net = bs.get("net_worth")
    kpis = [
        ("Total revenue", rev, "All income sources combined"),
        ("Total expenses", exp, "Living + housing + insurance + savings + children"),
        ("Balance (surplus / deficit)", diff, "Revenue minus expenses"),
        ("Children (school & fees)", ch, "Child 1 + Child 2 education costs"),
    ]
    if net is not None:
        kpis.extend([
            ("Total assets", bs.get("total_assets", 0), "Savings, gold, property, investments"),
            ("Total debts", bs.get("total_debts", 0), "Loans and liabilities outstanding"),
            ("Net worth", net, "Total assets minus total debts"),
        ])
    for label, amount, desc in kpis:
        _write_row(ws, r, [label, amount, desc], fmt_money=True)
        if amount < 0 and "Balance" in label:
            ws.cell(row=r, column=2).fill = _FILL_NEGATIVE
        elif "revenue" in label.lower() or (amount > 0 and "Balance" in label):
            if "Balance" in label and amount > 0:
                ws.cell(row=r, column=2).fill = _FILL_POSITIVE
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="Expense breakdown (selected month average)").font = _FONT_SECTION
    r += 1
    _write_row(ws, r, ["Category", "Share %", "Amount"], bold=True)
    _style_header_row(ws, r, 3)
    r += 1
    for sl in charts.get("donut_sections", []):
        _write_row(
            ws,
            r,
            [f"{sl.get('label_de', sl.get('label', ''))} / {sl.get('label', '')}", sl.get("pct", 0), sl.get("amount", 0)],
            fmt_money=True,
        )
        r += 1

    r += 1
    ws.cell(row=r, column=1, value="How to read this workbook").font = _FONT_SECTION
    r += 1
    notes = [
        "• Monthly — month-by-month revenue, expenses, and balance.",
        "• Yearly — annual summary rows (same as app Summary tab).",
        "• Charts — spending split and revenue vs expenses (tables + Excel charts).",
        "• Children — school fees, bus, books, semester fees for Child 1 & Child 2.",
        "• Assets & Debts — savings, gold, property, loans; net worth.",
        "• Details — every budget line (including custom rows) with monthly amounts.",
    ]
    for note in notes:
        ws.cell(row=r, column=1, value=note)
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=4)
        r += 1

    _autosize(ws, 4)


def _sheet_monthly(
    wb: Workbook,
    entries: dict,
    monatlich_mode: str,
    custom_keys_by_section: dict[str, list[str]] | None = None,
) -> None:
    ck = custom_keys_by_section
    ws = wb.create_sheet("Monthly")
    headers = ["Row"] + MONTH_NAMES_EN + ["Summe", "Avg/month"]
    _write_row(ws, 1, headers, bold=True)
    _style_header_row(ws, 1, len(headers))

    rows_def = [
        ("Total revenue", lambda m: total_revenue(entries, m, ck)),
        ("Total expenses", lambda m: total_5(entries, m, ck)),
        ("Children (school & fees)", lambda m: children_total(entries, m, ck)),
        ("Living", lambda m: total_1(entries, m, ck)),
        ("Housing", lambda m: total_2(entries, m, ck)),
        ("Insurance & health", lambda m: total_3(entries, m, ck)),
        ("Savings, pension & loans", lambda m: total_4(entries, m, ck)),
        (
            "Balance (revenue − expenses)",
            lambda m: total_revenue(entries, m, ck) - total_5(entries, m, ck),
        ),
    ]

    r = 2
    for label, fn in rows_def:
        months = [round(fn(m), 2) for m in range(1, 13)]
        _write_row(ws, r, [label] + months + [summe(months), monatlich(months, monatlich_mode)], fmt_money=True)
        if "Balance" in label:
            for c in range(2, 16):
                v = ws.cell(row=r, column=c).value
                if isinstance(v, (int, float)) and v < 0:
                    ws.cell(row=r, column=c).fill = _FILL_NEGATIVE
                elif isinstance(v, (int, float)) and v > 0:
                    ws.cell(row=r, column=c).fill = _FILL_POSITIVE
        r += 1

    _autosize(ws, len(headers))


def _sheet_yearly(wb: Workbook, summary: dict) -> None:
    ws = wb.create_sheet("Yearly")
    headers = ["Summary row", "Description (DE)"] + MONTH_NAMES_EN + ["Summe", "Monatlich"]
    _write_row(ws, 1, headers, bold=True)
    _style_header_row(ws, 1, len(headers))

    row_defs = [
        ("Total revenue", "Gesamteinnahmen", summary["total_revenue"]),
        ("Total - 1 Living", "Lebenshaltung", summary["total_1"]),
        ("Total - 2 Housing", "Wohnen", summary["total_2"]),
        ("Total - 3 Insurance", "Versicherung & Gesundheit", summary["total_3"]),
        ("Total - 4 Savings/Loans", "Rente, Vermögen, Kredite", summary["total_4"]),
        ("Children (school & fees)", "Kinder — Schule & Gebühren", summary.get("total_children", {})),
        ("Total expenses", "Gesamtausgaben", summary["total_expenses"]),
        ("Difference (balance)", "Saldo / Differenz", summary["difference"]),
    ]

    r = 2
    for en, de, data in row_defs:
        if not data:
            data = {"months": [0] * 12, "summe": 0, "monatlich": 0}
        _write_row(
            ws,
            r,
            [en, de] + data.get("months", [0] * 12) + [data.get("summe", 0), data.get("monatlich", 0)],
            fmt_money=True,
        )
        if "Difference" in en:
            for c in range(3, 17):
                v = ws.cell(row=r, column=c).value
                if isinstance(v, (int, float)) and v < 0:
                    ws.cell(row=r, column=c).fill = _FILL_NEGATIVE
                elif isinstance(v, (int, float)) and v > 0:
                    ws.cell(row=r, column=c).fill = _FILL_POSITIVE
        r += 1

    _autosize(ws, len(headers))


def _sheet_charts(wb: Workbook, charts: dict) -> None:
    ws = wb.create_sheet("Charts")
    ws["A1"] = "Spending by category (full year total)"
    ws["A1"].font = _FONT_SECTION

    _write_row(ws, 2, ["Category (EN)", "Category (DE)", "Annual amount", "Share %"], bold=True)
    _style_header_row(ws, 2, 4)

    slices = charts.get("donut_sections", [])
    r = 3
    for sl in slices:
        _write_row(
            ws,
            r,
            [sl.get("label", ""), sl.get("label_de", ""), sl.get("amount", 0), sl.get("pct", 0)],
            fmt_money=True,
        )
        r += 1

    if slices:
        pie = PieChart()
        pie.title = "Where spending goes"
        pie.height = 10
        pie.width = 14
        data_ref = Reference(ws, min_col=3, min_row=2, max_row=2 + len(slices))
        cats_ref = Reference(ws, min_col=1, min_row=3, max_row=2 + len(slices))
        pie.add_data(data_ref, titles_from_data=True)
        pie.set_categories(cats_ref)
        ws.add_chart(pie, "F2")

    bar_start = r + 3
    ws.cell(row=bar_start, column=1, value="Revenue vs expenses by month").font = _FONT_SECTION
    bar_start += 1
    _write_row(ws, bar_start, ["Month", "Revenue", "Expenses", "Balance"], bold=True)
    _style_header_row(ws, bar_start, 4)
    bar_start += 1
    bars = charts.get("monthly_bars", [])
    first_data_row = bar_start
    for b in bars:
        mo = int(b.get("month", 1))
        name = MONTH_NAMES_EN[mo - 1] if 1 <= mo <= 12 else str(mo)
        _write_row(
            ws,
            bar_start,
            [name, b.get("revenue", 0), b.get("expenses", 0), b.get("difference", 0)],
            fmt_money=True,
        )
        bar_start += 1

    if bars:
        chart = BarChart()
        chart.type = "col"
        chart.title = "Revenue vs expenses"
        chart.y_axis.title = "Amount"
        chart.height = 12
        chart.width = 18
        data_ref = Reference(ws, min_col=2, min_row=first_data_row - 1, max_row=first_data_row - 1 + len(bars), max_col=3)
        cats_ref = Reference(ws, min_col=1, min_row=first_data_row, max_row=first_data_row - 1 + len(bars))
        chart.add_data(data_ref, titles_from_data=True)
        chart.set_categories(cats_ref)
        ws.add_chart(chart, f"F{bar_start + 2}")

    _autosize(ws, 4)


def _sheet_children(
    wb: Workbook,
    entries: dict,
    monatlich_mode: str,
    custom_keys_by_section: dict[str, list[str]] | None = None,
) -> None:
    ck = custom_keys_by_section
    ws = wb.create_sheet("Children")
    ws["A1"] = "Children — school fees, books, bus, semester & yearly fees"
    ws["A1"].font = _FONT_TITLE
    ws.merge_cells("A1:O1")

    sections = sections_for_tab("children")
    r = 3
    headers = ["Expense item (DE)", "Expense item (EN)"] + MONTH_NAMES_EN + ["Summe", "Monatlich"]
    for section in sections:
        ws.cell(row=r, column=1, value=f"{section.title_de} / {section.title_en}").font = _FONT_SECTION
        ws.cell(row=r, column=1).fill = _FILL_SECTION
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(headers))
        r += 1
        _write_row(ws, r, headers, bold=True)
        _style_header_row(ws, r, len(headers))
        r += 1
        for line in section.lines:
            vals = entries.get(line.key, [0.0] * 12)
            _write_row(
                ws,
                r,
                [line.label_de, line.label_en] + vals + [summe(vals), monatlich(vals, monatlich_mode)],
                fmt_money=True,
            )
            r += 1
        if section.summary_key:
            months = [
                round(section_total(entries, section.id, m, ck.get(section.id) if ck else None), 2)
                for m in range(1, 13)
            ]
            ws.cell(row=r, column=1, value=section.summary_label_de or "Total").font = _FONT_BOLD
            ws.cell(row=r, column=2, value=section.summary_label_en or "Total").font = _FONT_BOLD
            for i, v in enumerate(months, start=3):
                c = ws.cell(row=r, column=i, value=v)
                c.number_format = _NUM_FMT
                c.font = _FONT_BOLD
            ws.cell(row=r, column=15, value=summe(months)).number_format = _NUM_FMT
            ws.cell(row=r, column=16, value=monatlich(months, monatlich_mode)).number_format = _NUM_FMT
            for c in range(1, 17):
                ws.cell(row=r, column=c).fill = _FILL_SUBHEADER
            r += 2

    _autosize(ws, len(headers))


def _sheet_details(
    wb: Workbook,
    entries: dict,
    monatlich_mode: str,
    custom_lines_by_section: dict[str, list[dict]] | None = None,
) -> None:
    ws = wb.create_sheet("Details")
    headers = ["Section", "Item (DE)", "Item (EN)"] + MONTH_NAMES_EN + ["Summe", "Monatlich"]
    _write_row(ws, 1, headers, bold=True)
    _style_header_row(ws, 1, len(headers))
    cl_map = custom_lines_by_section or {}
    r = 2
    for section in SECTIONS:
        ws.cell(row=r, column=1, value=f"{section.title_de} / {section.title_en}")
        ws.cell(row=r, column=1).fill = _FILL_SECTION
        ws.merge_cells(start_row=r, start_column=1, end_row=r, end_column=len(headers))
        r += 1
        for line in section.lines:
            vals = entries.get(line.key, [0.0] * 12)
            _write_row(
                ws,
                r,
                [section.title_en, line.label_de, line.label_en]
                + vals
                + [summe(vals), monatlich(vals, monatlich_mode)],
                fmt_money=True,
            )
            r += 1
        for cl in cl_map.get(section.id, []):
            key = cl["line_key"]
            vals = entries.get(key, [0.0] * 12)
            _write_row(
                ws,
                r,
                [
                    section.title_en,
                    f"{cl['label_de']} (custom)",
                    f"{cl.get('label_en', cl['label_de'])} (custom)",
                ]
                + vals
                + [summe(vals), monatlich(vals, monatlich_mode)],
                fmt_money=True,
            )
            r += 1
        r += 1
    _autosize(ws, len(headers))


def export_sheet_names() -> list[str]:
    """Expected workbook tabs for tests and documentation."""
    return [
        "Overview",
        "Assets & Debts",
        "Monthly",
        "Yearly",
        "Charts",
        "Children",
        "Details",
    ]


def _sheet_balance_sheet(wb: Workbook, balance: dict) -> None:
    ws = wb.create_sheet("Assets & Debts")
    ws["A1"] = "Assets & debts (current values)"
    ws["A1"].font = _FONT_TITLE
    r = 3
    ws.cell(row=r, column=1, value="Assets").font = _FONT_SECTION
    r += 1
    _write_row(ws, r, ["Name", "Type", "Current value", "Notes"], bold=True)
    _style_header_row(ws, r, 4)
    r += 1
    for a in balance.get("assets", []):
        _write_row(
            ws,
            r,
            [a.get("name", ""), a.get("asset_type", ""), a.get("amount", 0), a.get("notes", "")],
            fmt_money=True,
        )
        r += 1
    _write_row(ws, r, ["Total assets", "", balance.get("total_assets", 0), ""], bold=True, fmt_money=True)
    r += 2
    ws.cell(row=r, column=1, value="Debts").font = _FONT_SECTION
    r += 1
    _write_row(ws, r, ["Name", "Outstanding", "Notes"], bold=True)
    _style_header_row(ws, r, 3)
    r += 1
    for d in balance.get("debts", []):
        _write_row(ws, r, [d.get("name", ""), d.get("amount", 0), d.get("notes", "")], fmt_money=True)
        r += 1
    _write_row(ws, r, ["Total debts", balance.get("total_debts", 0), ""], bold=True, fmt_money=True)
    r += 2
    _write_row(ws, r, ["Net worth (assets − debts)", balance.get("net_worth", 0)], bold=True, fmt_money=True)
    _autosize(ws, 4)


def _annual_donut_slices(entries: dict, summary: dict) -> list[dict]:
    from app.calculations import baufinanzierung_total, build_monthly_series

    slices = [
        {"label": "Living", "label_de": "Lebenshaltung", "amount": summary["total_1"]["summe"]},
        {"label": "Housing", "label_de": "Wohnen", "amount": summary["total_2"]["summe"]},
        {"label": "Insurance", "label_de": "Versicherung", "amount": summary["total_3"]["summe"]},
        {"label": "Savings & Loans", "label_de": "Sparen & Kredite", "amount": summary["total_4"]["summe"]},
    ]
    bau = summe(build_monthly_series(entries, baufinanzierung_total))
    if bau > 0:
        slices.append({"label": "Financing", "label_de": "Baufinanzierung", "amount": bau})
    ch = summary.get("total_children", {}).get("summe", 0)
    if ch > 0:
        slices.append({"label": "Children", "label_de": "Kinder", "amount": ch})
    total = sum(s["amount"] for s in slices) or 1
    for s in slices:
        s["pct"] = round(100 * s["amount"] / total, 1)
    return slices


def build_client_workbook(
    client: dict,
    year: int,
    entries: dict[str, list[float]],
    monatlich_mode: str,
    custom_keys_by_section: dict[str, list[str]] | None = None,
    balance_sheet: dict | None = None,
    custom_lines_by_section: dict[str, list[dict]] | None = None,
) -> BytesIO:
    ck = custom_keys_by_section
    summary = compute_full_summary(entries, monatlich_mode, ck)
    charts = chart_payload(entries, 8, monatlich_mode, ck)
    charts["donut_sections"] = _annual_donut_slices(entries, summary)
    if balance_sheet:
        charts["balance_sheet"] = balance_sheet

    wb = Workbook()
    default = wb.active
    wb.remove(default)

    _sheet_overview(wb, client, year, summary, charts)
    if balance_sheet:
        _sheet_balance_sheet(wb, balance_sheet)
    _sheet_monthly(wb, entries, monatlich_mode, ck)
    _sheet_yearly(wb, summary)
    _sheet_charts(wb, charts)
    _sheet_children(wb, entries, monatlich_mode, ck)
    _sheet_details(wb, entries, monatlich_mode, custom_lines_by_section)

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    return buf
