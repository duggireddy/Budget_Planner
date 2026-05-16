"""PDF budget report with dashboard, charts, summary, and assets/debts snapshots."""

from __future__ import annotations

from datetime import date
from io import BytesIO
from typing import Any

from fpdf import FPDF

from app.calculations import chart_payload, compute_full_summary
from app.export_excel import _annual_donut_slices
from app.export_pdf_charts import render_bar_png, render_donut_png


def _txt(s: str) -> str:
    """FPDF core fonts: keep printable Latin-1."""
    if not s:
        return ""
    return s.encode("latin-1", errors="replace").decode("latin-1")


def _money(v: float) -> str:
    return f"{float(v):,.2f}"


class _ReportPDF(FPDF):
    def footer(self) -> None:
        self.set_y(-10)
        self.set_font("Helvetica", size=8)
        self.set_text_color(100, 100, 100)
        self.cell(0, 5, _txt(f"Page {self.page_no()}"), align="C")


def _section_heading(pdf: FPDF, title: str) -> None:
    if pdf.get_y() > 250:
        pdf.add_page()
    pdf.ln(3)
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(26, 35, 50)
    pdf.cell(0, 8, _txt(title), ln=True)
    pdf.set_font("Helvetica", size=10)
    pdf.set_text_color(0, 0, 0)


def _kpi_row(pdf: FPDF, items: list[tuple[str, float | str]], col_w: float = 46) -> None:
    pdf.set_font("Helvetica", "B", size=8)
    y0 = pdf.get_y()
    x = pdf.l_margin
    for label, _ in items:
        pdf.set_xy(x, y0)
        pdf.cell(col_w, 5, _txt(label), align="C")
        x += col_w
    pdf.set_font("Helvetica", size=10)
    y1 = y0 + 6
    x = pdf.l_margin
    for _, val in items:
        pdf.set_xy(x, y1)
        text = _money(val) if isinstance(val, (int, float)) else _txt(str(val))
        pdf.cell(col_w, 7, text, align="C")
        x += col_w
    pdf.set_y(y1 + 10)


def _embed_png(pdf: FPDF, png: bytes, max_w: float = 185) -> None:
    if pdf.get_y() > 160:
        pdf.add_page()
    x = pdf.l_margin
    y = pdf.get_y()
    pdf.image(BytesIO(png), x=x, y=y, w=max_w)
    pdf.ln(2)


def _table_header(pdf: FPDF, cols: list[tuple[str, float]]) -> None:
    pdf.set_font("Helvetica", "B", size=9)
    pdf.set_fill_color(241, 245, 249)
    for label, w in cols:
        pdf.cell(w, 7, _txt(label), border=1, fill=True)
    pdf.ln()


def _table_row(pdf: FPDF, cols: list[tuple[str, float]], bold: bool = False) -> None:
    pdf.set_font("Helvetica", "B" if bold else "", size=9)
    for text, w in cols:
        pdf.cell(w, 6, _txt(text)[:64], border=1)
    pdf.ln()


def _write_dashboard(
    pdf: FPDF,
    charts: dict[str, Any],
    summary: dict[str, Any],
    balance: dict | None,
    month: int,
) -> None:
    _section_heading(pdf, "Dashboard snapshot")
    hero = charts.get("hero") or {}
    yr = charts.get("year") or {}
    m = max(1, min(12, month))
    month_name = [
        "Jan", "Feb", "Mar", "Apr", "May", "Jun",
        "Jul", "Aug", "Sep", "Oct", "Nov", "Dec",
    ][m - 1]

    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 6, _txt(f"Month view: {month_name}  |  Full year totals below"), ln=True)

    kpis = [
        ("Revenue (month)", hero.get("revenue", 0)),
        ("Expenses (month)", hero.get("expenses", 0)),
        ("Balance (month)", hero.get("difference", 0)),
        ("Revenue (year)", yr.get("revenue", 0)),
    ]
    _kpi_row(pdf, kpis[:4], col_w=45)

    kpis2 = [
        ("Expenses (year)", yr.get("expenses", 0)),
        ("Balance (year)", yr.get("difference", 0)),
        ("Annual diff (Summe)", summary["difference"]["summe"]),
    ]
    if balance:
        kpis2.append(("Net worth", balance.get("net_worth", 0)))
    _kpi_row(pdf, kpis2, col_w=45)

    pdf.set_font("Helvetica", "B", size=9)
    pdf.cell(0, 6, _txt(f"Expense sections ({month_name})"), ln=True)
    pdf.set_font("Helvetica", size=9)
    sec_rows = [
        ("Living", summary["total_1"]["months"][m - 1]),
        ("Housing", summary["total_2"]["months"][m - 1]),
        ("Insurance", summary["total_3"]["months"][m - 1]),
        ("Savings & loans", summary["total_4"]["months"][m - 1]),
        ("Children", summary.get("total_children", {}).get("months", [0] * 12)[m - 1]),
    ]
    col_w = (90, 40)
    for label, amt in sec_rows:
        _table_row(pdf, [(label, col_w[0]), (_money(amt), col_w[1])])


def _write_charts(pdf: FPDF, charts: dict[str, Any]) -> None:
    pdf.add_page()
    _section_heading(pdf, "Charts snapshot")
    pdf.set_font("Helvetica", size=9)
    pdf.cell(0, 6, _txt("Spending split (full year) and revenue vs expenses by month"), ln=True)
    pdf.ln(2)

    donut = charts.get("donut_sections") or []
    bars = charts.get("monthly_bars") or []
    _embed_png(pdf, render_donut_png(donut, "Where spending goes (annual)"))
    pdf.ln(4)
    if pdf.get_y() > 140:
        pdf.add_page()
    _embed_png(pdf, render_bar_png(bars, "Revenue vs expenses (monthly)"))


def _write_annual_summary(pdf: FPDF, summary: dict[str, Any]) -> None:
    pdf.add_page()
    _section_heading(pdf, "Annual summary (full year)")
    ch = summary.get("total_children", {}).get("summe", 0)
    rows = [
        ("Total revenue", summary["total_revenue"]["summe"]),
        ("Total - 1 Living", summary["total_1"]["summe"]),
        ("Total - 2 Housing", summary["total_2"]["summe"]),
        ("Total - 3 Insurance", summary["total_3"]["summe"]),
        ("Total - 4 Savings / loans", summary["total_4"]["summe"]),
        ("Children (school & fees)", ch),
        ("Total expenses", summary["total_expenses"]["summe"]),
        ("Balance (surplus / deficit)", summary["difference"]["summe"]),
    ]
    col_w = (110, 50)
    for label, amount in rows:
        _table_row(pdf, [(label, col_w[0]), (_money(amount), col_w[1])])


def _write_balance_sheet(pdf: FPDF, balance: dict[str, Any]) -> None:
    pdf.add_page()
    _section_heading(pdf, "Assets & debts snapshot")

    col_w = (70, 35, 35, 35)
    pdf.set_font("Helvetica", "B", size=9)
    pdf.cell(0, 6, _txt("Summary"), ln=True)
    for label, amount in [
        ("Total assets", balance.get("total_assets", 0)),
        ("Total debts", balance.get("total_debts", 0)),
        ("Net worth", balance.get("net_worth", 0)),
    ]:
        _table_row(pdf, [(label, 90), (_money(float(amount)), 50)])

    payoff = balance.get("payoff") or {}
    if payoff:
        pdf.ln(3)
        pdf.set_font("Helvetica", "B", size=9)
        pdf.cell(0, 6, _txt("Debt payoff plan"), ln=True)
        pdf.set_font("Helvetica", size=9)
        plan_rows = [
            ("Monthly income", payoff.get("monthly_income", 0)),
            ("Monthly expenses", payoff.get("monthly_expenses", 0)),
            ("Monthly surplus", payoff.get("monthly_surplus", 0)),
            ("Repay / month (entered)", payoff.get("total_monthly_payment", 0)),
        ]
        for label, val in plan_rows:
            _table_row(pdf, [(label, 90), (_money(float(val)), 50)])
        months = payoff.get("months_to_clear_debts")
        if months is not None:
            free = payoff.get("debt_free_label") or "—"
            _table_row(pdf, [("Months to clear all debts", 90), (str(months), 25), (free, 25)])

    assets = balance.get("assets") or []
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", size=10)
    pdf.cell(0, 7, _txt("Assets"), ln=True)
    _table_header(pdf, [("Name", col_w[0]), ("Amount", col_w[1])])
    if assets:
        for a in assets:
            _table_row(pdf, [(a.get("name", ""), col_w[0]), (_money(float(a.get("amount") or 0)), col_w[1])])
        _table_row(
            pdf,
            [("Total assets", col_w[0]), (_money(float(balance.get("total_assets", 0))), col_w[1])],
            bold=True,
        )
    else:
        pdf.set_font("Helvetica", "I", size=9)
        pdf.cell(0, 6, _txt("No assets recorded"), ln=True)

    debts = balance.get("debts") or []
    per = {p.get("id"): p for p in (payoff.get("per_debt") or [])}
    pdf.ln(4)
    pdf.set_font("Helvetica", "B", size=10)
    pdf.cell(0, 7, _txt("Debts"), ln=True)
    debt_cols = [("Name", 45), ("Interest %", 22), ("Outstanding", 30), ("Repay/mo", 28), ("Months", 22)]
    _table_header(pdf, debt_cols)
    if debts:
        for d in debts:
            pd = per.get(d.get("id")) or {}
            months = pd.get("months_to_clear")
            months_txt = str(months) if months is not None else ("!" if pd.get("payment_covers_interest") is False else "—")
            _table_row(
                pdf,
                [
                    (d.get("name", ""), 45),
                    (f"{float(d.get('interest_rate_annual') or 0):.2f}", 22),
                    (_money(float(d.get("amount") or 0)), 30),
                    (_money(float(d.get("monthly_payment") or 0)), 28),
                    (months_txt, 22),
                ],
            )
        _table_row(
            pdf,
            [
                ("Total debts", 45),
                ("", 22),
                (_money(float(balance.get("total_debts", 0))), 30),
                (_money(float(payoff.get("total_monthly_payment", 0))), 28),
                ("", 22),
            ],
            bold=True,
        )
    else:
        pdf.set_font("Helvetica", "I", size=9)
        pdf.cell(0, 6, _txt("No debts recorded"), ln=True)


def build_budget_pdf(
    client: dict,
    year: int,
    entries: dict[str, list[float]],
    monatlich_mode: str,
    custom_keys_by_section: dict[str, list[str]] | None,
    balance: dict | None = None,
    month: int = 8,
) -> bytes:
    summary = compute_full_summary(entries, monatlich_mode, custom_keys_by_section)
    charts = chart_payload(entries, month, monatlich_mode, custom_keys_by_section)
    charts["donut_sections"] = _annual_donut_slices(entries, summary)

    pdf = _ReportPDF()
    pdf.set_auto_page_break(auto=True, margin=14)
    pdf.add_page()
    pdf.set_font("Helvetica", "B", 16)
    pdf.cell(0, 10, _txt("Annual Budget Report"), ln=True)
    pdf.set_font("Helvetica", size=11)
    pdf.cell(0, 7, _txt(f"Client: {client.get('name', '')}"), ln=True)
    if client.get("company_name"):
        pdf.cell(0, 6, _txt(f"Company: {client['company_name']}"), ln=True)
    pdf.cell(0, 6, _txt(f"Year: {year}  |  Generated: {date.today().isoformat()}"), ln=True)
    pdf.ln(4)

    _write_dashboard(pdf, charts, summary, balance, month)
    _write_charts(pdf, charts)
    _write_annual_summary(pdf, summary)
    if balance:
        _write_balance_sheet(pdf, balance)

    buf = BytesIO()
    pdf.output(buf)
    return buf.getvalue()
