"""Budget calculation engine — single source of truth."""

from __future__ import annotations

from app.categories import SECTIONS, SELF_EMPLOYED_KEYS


def _get(entries: dict[str, list[float]], key: str, month: int) -> float:
    vals = entries.get(key)
    if not vals or month < 1 or month > 12:
        return 0.0
    return float(vals[month - 1] or 0)


def _sum_lines(entries: dict[str, list[float]], keys: list[str], month: int) -> float:
    return sum(_get(entries, k, month) for k in keys)


def _section_line_keys(section_id: str) -> list[str]:
    for s in SECTIONS:
        if s.id == section_id:
            return [ln.key for ln in s.lines]
    return []


def compute_self_employed_net(entries: dict[str, list[float]], person: str, month: int) -> float:
    rev, tax, soc, op, trade, other, _ = SELF_EMPLOYED_KEYS[person]
    return (
        _get(entries, rev, month)
        - _get(entries, tax, month)
        - _get(entries, soc, month)
        - _get(entries, op, month)
        - _get(entries, trade, month)
        - _get(entries, other, month)
    )


def compute_net_employment(entries: dict[str, list[float]], person: str, month: int) -> float:
    if person == "a":
        return _get(entries, "na_net", month) + _get(entries, "na_minijob", month)
    return _get(entries, "nb_net", month) + _get(entries, "nb_minijob", month)


def compute_other_income(entries: dict[str, list[float]], person: str, month: int) -> float:
    prefix = "oia_" if person == "a" else "oib_"
    keys = [k for k in entries if k.startswith(prefix)]
    return _sum_lines(entries, keys, month)


def section_total(entries: dict[str, list[float]], section_id: str, month: int) -> float:
    if section_id == "self_employed_a":
        return compute_self_employed_net(entries, "a", month)
    if section_id == "self_employed_b":
        return compute_self_employed_net(entries, "b", month)
    if section_id == "net_a":
        return compute_net_employment(entries, "a", month)
    if section_id == "net_b":
        return compute_net_employment(entries, "b", month)
    if section_id == "other_income_a":
        return compute_other_income(entries, "a", month)
    if section_id == "other_income_b":
        return compute_other_income(entries, "b", month)
    return _sum_lines(entries, _section_line_keys(section_id), month)


def total_revenue(entries: dict[str, list[float]], month: int) -> float:
    return (
        compute_self_employed_net(entries, "a", month)
        + compute_self_employed_net(entries, "b", month)
        + compute_net_employment(entries, "a", month)
        + compute_net_employment(entries, "b", month)
        + compute_other_income(entries, "a", month)
        + compute_other_income(entries, "b", month)
    )


def total_1(entries: dict[str, list[float]], month: int) -> float:
    return section_total(entries, "living", month)


def total_2(entries: dict[str, list[float]], month: int) -> float:
    return section_total(entries, "housing", month)


def total_3(entries: dict[str, list[float]], month: int) -> float:
    return (
        section_total(entries, "health_a", month)
        + section_total(entries, "health_b", month)
        + section_total(entries, "property_insurance", month)
    )


def total_4(entries: dict[str, list[float]], month: int) -> float:
    return (
        section_total(entries, "pension", month)
        + section_total(entries, "wealth", month)
        + section_total(entries, "credit", month)
    )


def baufinanzierung_total(entries: dict[str, list[float]], month: int) -> float:
    return section_total(entries, "baufinanzierung", month)


def total_5(entries: dict[str, list[float]], month: int) -> float:
    return (
        total_1(entries, month)
        + total_2(entries, month)
        + baufinanzierung_total(entries, month)
        + total_3(entries, month)
        + total_4(entries, month)
    )


def difference(entries: dict[str, list[float]], month: int) -> float:
    return total_revenue(entries, month) - total_5(entries, month)


def summe(vals: list[float]) -> float:
    return round(sum(vals), 2)


def monatlich(vals: list[float], mode: str = "div12") -> float:
    total = summe(vals)
    if mode == "filled":
        filled = [v for v in vals if v != 0]
        if filled:
            return round(total / len(filled), 2)
    return round(total / 12, 2)


def build_monthly_series(entries: dict[str, list[float]], fn) -> list[float]:
    return [round(fn(entries, m), 2) for m in range(1, 13)]


def compute_full_summary(entries: dict[str, list[float]], monatlich_mode: str = "div12") -> dict:
    revenue = build_monthly_series(entries, total_revenue)
    expenses = build_monthly_series(entries, total_5)
    diff = build_monthly_series(entries, difference)
    t1 = build_monthly_series(entries, total_1)
    t2 = build_monthly_series(entries, total_2)
    t3 = build_monthly_series(entries, total_3)
    t4 = build_monthly_series(entries, total_4)

    section_summaries = {}
    for section in SECTIONS:
        if section.summary_key:
            monthly = build_monthly_series(entries, lambda e, m, sid=section.id: section_total(e, sid, m))
            section_summaries[section.summary_key] = {
                "months": monthly,
                "summe": summe(monthly),
                "monatlich": monatlich(monthly, monatlich_mode),
            }

    return {
        "total_revenue": {
            "months": revenue,
            "summe": summe(revenue),
            "monatlich": monatlich(revenue, monatlich_mode),
        },
        "total_expenses": {
            "months": expenses,
            "summe": summe(expenses),
            "monatlich": monatlich(expenses, monatlich_mode),
        },
        "difference": {
            "months": diff,
            "summe": summe(diff),
            "monatlich": monatlich(diff, monatlich_mode),
        },
        "total_1": {"months": t1, "summe": summe(t1), "monatlich": monatlich(t1, monatlich_mode)},
        "total_2": {"months": t2, "summe": summe(t2), "monatlich": monatlich(t2, monatlich_mode)},
        "total_3": {"months": t3, "summe": summe(t3), "monatlich": monatlich(t3, monatlich_mode)},
        "total_4": {"months": t4, "summe": summe(t4), "monatlich": monatlich(t4, monatlich_mode)},
        "total_5": {
            "months": expenses,
            "summe": summe(expenses),
            "monatlich": monatlich(expenses, monatlich_mode),
        },
        "section_summaries": section_summaries,
    }


def chart_payload(entries: dict[str, list[float]], month: int, monatlich_mode: str = "div12") -> dict:
    m = max(1, min(12, month))
    rev = total_revenue(entries, m)
    exp = total_5(entries, m)
    diff = difference(entries, m)

    slices = [
        {"id": "living", "label": "Living", "label_de": "Lebenshaltung", "amount": total_1(entries, m)},
        {"id": "housing", "label": "Housing", "label_de": "Wohnen", "amount": total_2(entries, m)},
        {"id": "insurance", "label": "Insurance", "label_de": "Versicherung", "amount": total_3(entries, m)},
        {"id": "savings_loans", "label": "Savings & Loans", "label_de": "Sparen & Kredite", "amount": total_4(entries, m)},
    ]
    bau = baufinanzierung_total(entries, m)
    if bau > 0:
        slices.append({"id": "baufinanzierung", "label": "Financing", "label_de": "Baufinanzierung", "amount": bau})

    total_slice = sum(s["amount"] for s in slices) or 1
    for s in slices:
        s["pct"] = round(100 * s["amount"] / total_slice, 1)

    monthly_bars = []
    for mo in range(1, 13):
        monthly_bars.append({
            "month": mo,
            "revenue": total_revenue(entries, mo),
            "expenses": total_5(entries, mo),
            "difference": difference(entries, mo),
        })

    return {
        "hero": {"revenue": rev, "expenses": exp, "difference": diff, "month": m},
        "donut_sections": slices,
        "monthly_bars": monthly_bars,
        "year": {
            "revenue": summe([total_revenue(entries, mo) for mo in range(1, 13)]),
            "expenses": summe([total_5(entries, mo) for mo in range(1, 13)]),
            "difference": summe([difference(entries, mo) for mo in range(1, 13)]),
        },
    }


def drilldown_slices(entries: dict[str, list[float]], section_id: str, month: int) -> list[dict]:
    from app.categories import SECTION_BY_ID

    section = SECTION_BY_ID.get(section_id)
    if not section:
        return []
    items = []
    for line in section.lines:
        amt = _get(entries, line.key, month)
        if amt > 0:
            items.append({"key": line.key, "label": line.label_en, "label_de": line.label_de, "amount": amt})
    items.sort(key=lambda x: -x["amount"])
    if len(items) > 8:
        other = sum(i["amount"] for i in items[8:])
        items = items[:8] + [{"key": "other", "label": "Other", "label_de": "Sonstiges", "amount": other}]
    total = sum(i["amount"] for i in items) or 1
    for i in items:
        i["pct"] = round(100 * i["amount"] / total, 1)
    return items
