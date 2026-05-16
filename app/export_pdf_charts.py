"""Matplotlib chart images for PDF export."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.categories import MONTH_NAMES_EN

CHART_COLORS = ["#4F8EF7", "#7C5CFC", "#F59E0B", "#EF6B6B", "#10B981", "#6366F1"]


def _fig_to_png(fig: plt.Figure) -> bytes:
    buf = BytesIO()
    fig.savefig(buf, format="png", dpi=130, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    return buf.getvalue()


def render_donut_png(slices: list[dict[str, Any]], title: str) -> bytes:
    labels = [s.get("label_en") or s.get("label") or "" for s in slices]
    amounts = [float(s.get("amount") or 0) for s in slices]
    if not slices or sum(amounts) <= 0:
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.text(0.5, 0.5, "No expense data", ha="center", va="center", fontsize=12)
        ax.axis("off")
        fig.suptitle(title, fontsize=11, fontweight="bold")
        return _fig_to_png(fig)

    colors = [CHART_COLORS[i % len(CHART_COLORS)] for i in range(len(slices))]
    fig, ax = plt.subplots(figsize=(7.5, 4.5))
    wedges, _, autotexts = ax.pie(
        amounts,
        labels=None,
        autopct=lambda pct: f"{pct:.0f}%" if pct >= 4 else "",
        colors=colors,
        startangle=90,
        wedgeprops={"width": 0.45, "edgecolor": "white", "linewidth": 1},
        pctdistance=0.78,
    )
    for t in autotexts:
        t.set_fontsize(8)
    ax.legend(
        wedges,
        [f"{lbl} ({s.get('pct', 0)}%)" for lbl, s in zip(labels, slices)],
        loc="center left",
        bbox_to_anchor=(1.02, 0.5),
        fontsize=8,
        frameon=False,
    )
    fig.suptitle(title, fontsize=11, fontweight="bold")
    fig.tight_layout()
    return _fig_to_png(fig)


def render_bar_png(bars: list[dict[str, Any]], title: str) -> bytes:
    if not bars:
        fig, ax = plt.subplots(figsize=(8, 4))
        ax.text(0.5, 0.5, "No monthly data", ha="center", va="center", fontsize=12)
        ax.axis("off")
        fig.suptitle(title, fontsize=11, fontweight="bold")
        return _fig_to_png(fig)

    months = []
    for b in bars:
        mo = int(b.get("month", 1))
        months.append(MONTH_NAMES_EN[mo - 1] if 1 <= mo <= 12 else str(mo))
    rev = [float(b.get("revenue") or 0) for b in bars]
    exp = [float(b.get("expenses") or 0) for b in bars]

    x = range(len(months))
    width = 0.38
    fig, ax = plt.subplots(figsize=(8.5, 4.5))
    ax.bar([i - width / 2 for i in x], rev, width, label="Revenue", color="#059669")
    ax.bar([i + width / 2 for i in x], exp, width, label="Expenses", color="#ea580c")
    ax.set_xticks(list(x))
    ax.set_xticklabels(months, rotation=45, ha="right", fontsize=8)
    ax.yaxis.set_major_formatter(
        matplotlib.ticker.FuncFormatter(lambda v, _: f"{v:,.0f}")
    )
    ax.legend(fontsize=8)
    ax.grid(axis="y", alpha=0.3)
    fig.suptitle(title, fontsize=11, fontweight="bold")
    fig.tight_layout()
    return _fig_to_png(fig)
