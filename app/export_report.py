"""Printable HTML budget report (Save as PDF from browser)."""

from __future__ import annotations

from datetime import date
from html import escape

from app.calculations import compute_full_summary, summe
from app.categories import MONTH_NAMES_EN, SECTIONS


def _money(v: float) -> str:
    return f"{v:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_print_report_html(
    client: dict,
    year: int,
    entries: dict[str, list[float]],
    monatlich_mode: str,
    custom_lines_by_section: dict[str, list[dict]] | None = None,
) -> str:
    cl_map = custom_lines_by_section or {}
    ck = {
        sid: [ln["line_key"] for ln in lines]
        for sid, lines in (custom_lines_by_section or {}).items()
    }
    summary = compute_full_summary(entries, monatlich_mode, ck)
    rev = summary["total_revenue"]["summe"]
    exp = summary["total_expenses"]["summe"]
    diff = summary["difference"]["summe"]
    name = escape(client.get("name") or "Client")
    company = escape(client.get("company_name") or "—")

    rows_html = ""
    for section in SECTIONS:
        title = escape(section.title_en)
        line_items: list[tuple[str, str, str]] = [
            (line.key, line.label_de, line.label_en) for line in section.lines
        ]
        for cl in cl_map.get(section.id, []):
            line_items.append((cl["line_key"], cl["label_de"], cl["label_en"]))
        for key, _de, label_en in line_items:
            vals = entries.get(key) or [0.0] * 12
            s = summe(vals)
            cells = "".join(f"<td class='num'>{_money(v)}</td>" for v in vals)
            rows_html += (
                f"<tr><td>{title}</td><td>{escape(label_en)}</td>"
                f"{cells}<td class='num'><strong>{_money(s)}</strong></td></tr>"
            )

    month_headers = "".join(f"<th>{m}</th>" for m in MONTH_NAMES_EN)
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8" />
  <title>Budget report — {name} {year}</title>
  <style>
    body {{ font-family: "Segoe UI", system-ui, sans-serif; margin: 24px; color: #1a2332; }}
    h1 {{ margin: 0 0 8px; font-size: 1.5rem; }}
    .meta {{ color: #64748b; margin-bottom: 24px; }}
    .kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(160px, 1fr)); gap: 12px; margin-bottom: 24px; }}
    .kpi {{ background: #f8fafc; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px; }}
    .kpi strong {{ display: block; font-size: 1.2rem; margin-top: 4px; }}
    table {{ width: 100%; border-collapse: collapse; font-size: 0.75rem; }}
    th, td {{ border: 1px solid #e2e8f0; padding: 6px 8px; text-align: left; }}
    th {{ background: #f1f5f9; }}
    td.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
    @media print {{
      body {{ margin: 12px; }}
      .no-print {{ display: none; }}
    }}
  </style>
</head>
<body>
  <p class="no-print"><button onclick="window.print()">Print / Save as PDF</button></p>
  <h1>Annual budget report</h1>
  <p class="meta">{name} · {company} · {year} · Generated {date.today().isoformat()}</p>
  <div class="kpis">
    <div class="kpi">Revenue<strong>{_money(rev)}</strong></div>
    <div class="kpi">Expenses<strong>{_money(exp)}</strong></div>
    <div class="kpi">Balance<strong>{_money(diff)}</strong></div>
  </div>
  <table>
    <thead><tr><th>Section</th><th>Category</th>{month_headers}<th>Summe</th></tr></thead>
    <tbody>{rows_html}</tbody>
  </table>
  <script>window.addEventListener("load", () => setTimeout(() => window.print(), 300));</script>
</body>
</html>"""
