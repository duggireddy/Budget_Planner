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


def compute_other_income(
    entries: dict[str, list[float]],
    person: str,
    month: int,
    extra_keys: list[str] | None = None,
) -> float:
    prefix = "oia_" if person == "a" else "oib_"
    keys = [k for k in entries if k.startswith(prefix)]
    if extra_keys:
        keys = keys + [k for k in extra_keys if k not in keys]
    return _sum_lines(entries, keys, month)


def section_total(
    entries: dict[str, list[float]],
    section_id: str,
    month: int,
    extra_keys: list[str] | None = None,
) -> float:
    if section_id == "self_employed_a":
        base = compute_self_employed_net(entries, "a", month)
    elif section_id == "self_employed_b":
        base = compute_self_employed_net(entries, "b", month)
    elif section_id == "net_a":
        base = compute_net_employment(entries, "a", month)
    elif section_id == "net_b":
        base = compute_net_employment(entries, "b", month)
    elif section_id == "other_income_a":
        base = compute_other_income(entries, "a", month, extra_keys)
    elif section_id == "other_income_b":
        base = compute_other_income(entries, "b", month, extra_keys)
    else:
        keys = _section_line_keys(section_id)
        if extra_keys:
            keys = keys + [k for k in extra_keys if k not in keys]
        base = _sum_lines(entries, keys, month)
    if extra_keys and section_id in (
        "self_employed_a",
        "self_employed_b",
        "net_a",
        "net_b",
        "other_income_a",
        "other_income_b",
    ):
        base += _sum_lines(entries, extra_keys, month)
    return base


def total_revenue(
    entries: dict[str, list[float]],
    month: int,
    custom_keys_by_section: dict[str, list[str]] | None = None,
) -> float:
    """All income sections including custom rows per section."""
    ck = custom_keys_by_section
    return (
        section_total(entries, "self_employed_a", month, _ck(ck, "self_employed_a"))
        + section_total(entries, "self_employed_b", month, _ck(ck, "self_employed_b"))
        + section_total(entries, "net_a", month, _ck(ck, "net_a"))
        + section_total(entries, "net_b", month, _ck(ck, "net_b"))
        + section_total(entries, "other_income_a", month, _ck(ck, "other_income_a"))
        + section_total(entries, "other_income_b", month, _ck(ck, "other_income_b"))
    )


def _ck(custom_keys_by_section: dict[str, list[str]] | None, section_id: str) -> list[str] | None:
    if not custom_keys_by_section:
        return None
    return custom_keys_by_section.get(section_id)


def total_1(
    entries: dict[str, list[float]],
    month: int,
    custom_keys_by_section: dict[str, list[str]] | None = None,
) -> float:
    return section_total(entries, "living", month, _ck(custom_keys_by_section, "living"))


def total_2(
    entries: dict[str, list[float]],
    month: int,
    custom_keys_by_section: dict[str, list[str]] | None = None,
) -> float:
    return section_total(entries, "housing", month, _ck(custom_keys_by_section, "housing"))


def total_3(
    entries: dict[str, list[float]],
    month: int,
    custom_keys_by_section: dict[str, list[str]] | None = None,
) -> float:
    return (
        section_total(entries, "health_a", month, _ck(custom_keys_by_section, "health_a"))
        + section_total(entries, "health_b", month, _ck(custom_keys_by_section, "health_b"))
        + section_total(
            entries, "property_insurance", month, _ck(custom_keys_by_section, "property_insurance")
        )
    )


def total_4(
    entries: dict[str, list[float]],
    month: int,
    custom_keys_by_section: dict[str, list[str]] | None = None,
) -> float:
    return (
        section_total(entries, "pension", month, _ck(custom_keys_by_section, "pension"))
        + section_total(entries, "wealth", month, _ck(custom_keys_by_section, "wealth"))
        + section_total(entries, "credit", month, _ck(custom_keys_by_section, "credit"))
    )


def children_total(
    entries: dict[str, list[float]],
    month: int,
    custom_keys_by_section: dict[str, list[str]] | None = None,
) -> float:
    return section_total(entries, "child_1", month, _ck(custom_keys_by_section, "child_1")) + section_total(
        entries, "child_2", month, _ck(custom_keys_by_section, "child_2")
    )


def baufinanzierung_total(
    entries: dict[str, list[float]],
    month: int,
    custom_keys_by_section: dict[str, list[str]] | None = None,
) -> float:
    return section_total(
        entries, "baufinanzierung", month, _ck(custom_keys_by_section, "baufinanzierung")
    )


def total_5(
    entries: dict[str, list[float]],
    month: int,
    custom_keys_by_section: dict[str, list[str]] | None = None,
) -> float:
    return (
        total_1(entries, month, custom_keys_by_section)
        + total_2(entries, month, custom_keys_by_section)
        + baufinanzierung_total(entries, month, custom_keys_by_section)
        + total_3(entries, month, custom_keys_by_section)
        + total_4(entries, month, custom_keys_by_section)
        + children_total(entries, month, custom_keys_by_section)
    )


def difference(
    entries: dict[str, list[float]],
    month: int,
    custom_keys_by_section: dict[str, list[str]] | None = None,
) -> float:
    return total_revenue(entries, month, custom_keys_by_section) - total_5(
        entries, month, custom_keys_by_section
    )


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


def compute_full_summary(
    entries: dict[str, list[float]],
    monatlich_mode: str = "div12",
    custom_keys_by_section: dict[str, list[str]] | None = None,
) -> dict:
    ck = custom_keys_by_section
    revenue = build_monthly_series(entries, lambda e, m: total_revenue(e, m, ck))
    expenses = build_monthly_series(entries, lambda e, m: total_5(e, m, ck))
    diff = build_monthly_series(entries, lambda e, m: difference(e, m, ck))
    t1 = build_monthly_series(entries, lambda e, m: total_1(e, m, ck))
    t2 = build_monthly_series(entries, lambda e, m: total_2(e, m, ck))
    t3 = build_monthly_series(entries, lambda e, m: total_3(e, m, ck))
    t4 = build_monthly_series(entries, lambda e, m: total_4(e, m, ck))
    tch = build_monthly_series(entries, lambda e, m: children_total(e, m, ck))

    section_summaries = {}
    for section in SECTIONS:
        if section.summary_key:
            monthly = build_monthly_series(
                entries,
                lambda e, m, sid=section.id: section_total(e, sid, m, _ck(ck, sid)),
            )
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
        "total_children": {
            "months": tch,
            "summe": summe(tch),
            "monatlich": monatlich(tch, monatlich_mode),
        },
        "total_5": {
            "months": expenses,
            "summe": summe(expenses),
            "monatlich": monatlich(expenses, monatlich_mode),
        },
        "section_summaries": section_summaries,
    }


def chart_payload(
    entries: dict[str, list[float]],
    month: int,
    monatlich_mode: str = "div12",
    custom_keys_by_section: dict[str, list[str]] | None = None,
) -> dict:
    ck = custom_keys_by_section
    m = max(1, min(12, month))
    rev = total_revenue(entries, m, ck)
    exp = total_5(entries, m, ck)
    diff = difference(entries, m, ck)

    slices = [
        {
            "id": "living",
            "label": "Living",
            "label_en": "Living",
            "label_de": "Lebenshaltung",
            "amount": total_1(entries, m, ck),
        },
        {
            "id": "housing",
            "label": "Housing",
            "label_en": "Housing",
            "label_de": "Wohnen",
            "amount": total_2(entries, m, ck),
        },
        {
            "id": "insurance",
            "label": "Insurance",
            "label_en": "Insurance",
            "label_de": "Versicherung",
            "amount": total_3(entries, m, ck),
        },
        {
            "id": "savings_loans",
            "label": "Savings & Loans",
            "label_en": "Savings & Loans",
            "label_de": "Sparen & Kredite",
            "amount": total_4(entries, m, ck),
        },
    ]
    bau = baufinanzierung_total(entries, m, ck)
    if bau > 0:
        slices.append(
            {
                "id": "baufinanzierung",
                "label": "Financing",
                "label_en": "Financing",
                "label_de": "Baufinanzierung",
                "amount": bau,
            }
        )
    ch = children_total(entries, m, ck)
    if ch > 0:
        slices.append(
            {
                "id": "children",
                "label": "Children",
                "label_en": "Children (school & fees)",
                "label_de": "Kinder (Schule & Gebühren)",
                "amount": ch,
            }
        )

    total_slice = sum(s["amount"] for s in slices) or 1
    for s in slices:
        s["pct"] = round(100 * s["amount"] / total_slice, 1)

    monthly_bars = []
    for mo in range(1, 13):
        monthly_bars.append({
            "month": mo,
            "revenue": total_revenue(entries, mo, ck),
            "expenses": total_5(entries, mo, ck),
            "difference": difference(entries, mo, ck),
        })

    return {
        "hero": {"revenue": rev, "expenses": exp, "difference": diff, "month": m},
        "donut_sections": slices,
        "monthly_bars": monthly_bars,
        "year": {
            "revenue": summe([total_revenue(entries, mo, ck) for mo in range(1, 13)]),
            "expenses": summe([total_5(entries, mo, ck) for mo in range(1, 13)]),
            "difference": summe([difference(entries, mo, ck) for mo in range(1, 13)]),
        },
    }


_DRILLDOWN_GROUPS: dict[str, list[str]] = {
    "insurance": ["health_a", "health_b", "property_insurance"],
    "savings_loans": ["pension", "wealth", "credit"],
    "children": ["child_1", "child_2"],
}


def drilldown_slices(entries: dict[str, list[float]], section_id: str, month: int) -> list[dict]:
    from app.categories import SECTION_BY_ID

    if section_id in _DRILLDOWN_GROUPS:
        items = []
        for sid in _DRILLDOWN_GROUPS[section_id]:
            items.extend(drilldown_slices(entries, sid, month))
        items.sort(key=lambda x: -x["amount"])
        total = sum(i["amount"] for i in items) or 1
        for i in items:
            i["pct"] = round(100 * i["amount"] / total, 1)
        return items[:12]

    section = SECTION_BY_ID.get(section_id)
    if not section:
        return []
    items = []
    for line in section.lines:
        amt = _get(entries, line.key, month)
        if amt > 0:
            items.append({"key": line.key, "label": line.label_en, "label_de": line.label_de, "amount": amt})
    prefix = f"cx_{section_id}_"
    for key, vals in entries.items():
        if key.startswith(prefix) and key not in {ln.key for ln in section.lines}:
            amt = _get(entries, key, month)
            if amt > 0:
                items.append({"key": key, "label": key, "label_de": key, "amount": amt})
    items.sort(key=lambda x: -x["amount"])
    if len(items) > 8:
        other = sum(i["amount"] for i in items[8:])
        items = items[:8] + [
            {"key": "other", "label": "Other", "label_en": "Other", "label_de": "Sonstiges", "amount": other}
        ]
    total = sum(i["amount"] for i in items) or 1
    for i in items:
        i["pct"] = round(100 * i["amount"] / total, 1)
    return items
