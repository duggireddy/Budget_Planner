"""CSV import — delegates to excel parser after normalizing rows."""

from __future__ import annotations

import csv
from io import StringIO

from app.import_excel import match_line_key, parse_de_amount
from app.database import get_mappings


def parse_csv(content: bytes) -> tuple[list[dict], list[str]]:
    text = content.decode("utf-8-sig", errors="replace")
    reader = csv.reader(StringIO(text), delimiter=";")
    rows = list(reader)
    if not rows:
        reader = csv.reader(StringIO(text), delimiter=",")
        rows = list(reader)
    if not rows:
        return [], ["Empty CSV"]

    # Reuse excel logic by building pseudo sheet
    from app.import_excel import parse_workbook
    from openpyxl import Workbook

    wb = Workbook()
    ws = wb.active
    for r in rows:
        ws.append(r)
    from io import BytesIO
    buf = BytesIO()
    wb.save(buf)
    return parse_workbook(buf.getvalue())
