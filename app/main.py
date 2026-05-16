"""FastAPI application entry point."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import FileResponse, JSONResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from app.calculations import chart_payload, compute_full_summary, drilldown_slices
from app.categories import SECTIONS, TABS
from app.database import (
    bulk_upsert,
    create_client,
    db_label,
    delete_client,
    get_client,
    get_import_log,
    get_mappings,
    get_or_create_budget,
    get_settings,
    init_db,
    list_clients,
    load_entries,
    log_import,
    save_mapping,
    set_monatlich_mode,
    update_client,
    upsert_entry,
)
from app.import_excel import all_category_options, apply_import, parse_workbook
from app.import_csv import parse_csv
from app.seed import ensure_sample_client

STATIC_DIR = Path(__file__).resolve().parent.parent / "static"

app = FastAPI(title="Annual Budget", version="2.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.on_event("startup")
def startup() -> None:
    init_db()
    ensure_sample_client()


class ClientBody(BaseModel):
    name: str
    company_name: str = ""
    contact_person: str = ""
    email: str = ""
    phone: str = ""
    street: str = ""
    postal_code: str = ""
    city: str = ""
    country: str = "Germany"
    tax_id: str = ""
    vat_id: str = ""
    iban: str = ""
    notes: str = ""


class EntryBody(BaseModel):
    line_key: str
    month: int
    amount: float


class BulkBody(BaseModel):
    line_key: str
    amount: float
    start_month: int = 1
    end_month: int = 12


class MappingBody(BaseModel):
    file_label: str
    line_key: str


class SettingsBody(BaseModel):
    monatlich_mode: str


class ImportConfirmBody(BaseModel):
    rows: list[dict]


def _client_or_404(client_id: int) -> dict:
    c = get_client(client_id)
    if not c:
        raise HTTPException(404, "Client not found")
    return c


def _budget_id(client_id: int, year: int) -> int:
    _client_or_404(client_id)
    return get_or_create_budget(client_id, year)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
def health() -> dict:
    return {"ok": True, "database": db_label()}


@app.get("/api/clients")
def api_list_clients() -> dict:
    return {"clients": [_serialize_client(c) for c in list_clients()]}


def _serialize_client(c: dict) -> dict:
    if c.get("created_at") and hasattr(c["created_at"], "isoformat"):
        c["created_at"] = c["created_at"].isoformat()
    return c


@app.post("/api/clients")
def api_create_client(body: ClientBody) -> dict:
    try:
        client = create_client(body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        if "UNIQUE" in str(e).upper() or "duplicate" in str(e).lower():
            raise HTTPException(409, "A client with this name already exists") from e
        raise
    return {"client": _serialize_client(client)}


@app.put("/api/clients/{client_id}")
def api_update_client(client_id: int, body: ClientBody) -> dict:
    try:
        client = update_client(client_id, body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    except Exception as e:
        if "UNIQUE" in str(e).upper() or "duplicate" in str(e).lower():
            raise HTTPException(409, "A client with this name already exists") from e
        raise
    if not client:
        raise HTTPException(404, "Client not found")
    return {"client": _serialize_client(client)}


@app.get("/api/clients/{client_id}")
def api_get_client(client_id: int) -> dict:
    c = _client_or_404(client_id)
    return {"client": _serialize_client(c)}


@app.delete("/api/clients/{client_id}")
def api_delete_client(client_id: int) -> dict:
    if not delete_client(client_id):
        raise HTTPException(404, "Client not found")
    return {"ok": True}


@app.get("/api/meta")
def meta() -> dict:
    sections = []
    for s in SECTIONS:
        sections.append({
            "id": s.id,
            "tab": s.tab,
            "title_de": s.title_de,
            "title_en": s.title_en,
            "summary_key": s.summary_key,
            "lines": [
                {
                    "key": ln.key,
                    "label_de": ln.label_de,
                    "label_en": ln.label_en,
                    "line_type": ln.line_type,
                }
                for ln in s.lines
            ],
        })
    return {"tabs": TABS, "sections": sections, "categories": all_category_options()}


@app.get("/api/clients/{client_id}/budget/{year}")
def get_budget(client_id: int, year: int) -> dict:
    client = _client_or_404(client_id)
    bid = _budget_id(client_id, year)
    entries = load_entries(bid)
    settings = get_settings(bid)
    summary = compute_full_summary(entries, settings["monatlich_mode"])
    return {
        "budget_id": bid,
        "client_id": client_id,
        "client_name": client["name"],
        "year": year,
        "entries": entries,
        "summary": summary,
        "settings": settings,
    }


@app.get("/api/clients/{client_id}/budget/{year}/summary")
def get_summary(client_id: int, year: int, month: int = 8) -> dict:
    bid = _budget_id(client_id, year)
    entries = load_entries(bid)
    settings = get_settings(bid)
    return {
        "summary": compute_full_summary(entries, settings["monatlich_mode"]),
        "charts": chart_payload(entries, month, settings["monatlich_mode"]),
    }


@app.get("/api/clients/{client_id}/budget/{year}/drilldown")
def get_drilldown(client_id: int, year: int, section: str, month: int = 8) -> dict:
    bid = _budget_id(client_id, year)
    entries = load_entries(bid)
    return {"slices": drilldown_slices(entries, section, month)}


@app.post("/api/clients/{client_id}/budget/{year}/entry")
def post_entry(client_id: int, year: int, body: EntryBody) -> dict:
    bid = _budget_id(client_id, year)
    upsert_entry(bid, body.line_key, body.month, body.amount)
    entries = load_entries(bid)
    settings = get_settings(bid)
    return {"ok": True, "summary": compute_full_summary(entries, settings["monatlich_mode"])}


@app.post("/api/clients/{client_id}/budget/{year}/bulk")
def post_bulk(client_id: int, year: int, body: BulkBody) -> dict:
    bid = _budget_id(client_id, year)
    bulk_upsert(bid, body.line_key, body.start_month, body.end_month, body.amount)
    entries = load_entries(bid)
    settings = get_settings(bid)
    return {"ok": True, "summary": compute_full_summary(entries, settings["monatlich_mode"])}


@app.post("/api/clients/{client_id}/budget/{year}/settings")
def post_settings(client_id: int, year: int, body: SettingsBody) -> dict:
    bid = _budget_id(client_id, year)
    if body.monatlich_mode not in ("div12", "filled"):
        return JSONResponse({"error": "Invalid mode"}, status_code=400)
    set_monatlich_mode(bid, body.monatlich_mode)
    return {"ok": True, "monatlich_mode": body.monatlich_mode}


@app.post("/api/clients/{client_id}/import/excel")
async def import_excel(client_id: int, year: int = 2026, file: UploadFile = File(...)) -> dict:
    _client_or_404(client_id)
    content = await file.read()
    rows, warnings = parse_workbook(content)
    return {"preview": rows, "warnings": warnings, "count": len(rows)}


@app.post("/api/clients/{client_id}/import/csv")
async def import_csv_endpoint(client_id: int, year: int = 2026, file: UploadFile = File(...)) -> dict:
    _client_or_404(client_id)
    content = await file.read()
    rows, warnings = parse_csv(content)
    return {"preview": rows, "warnings": warnings, "count": len(rows)}


@app.post("/api/clients/{client_id}/import/confirm")
def import_confirm(client_id: int, year: int, body: ImportConfirmBody) -> dict:
    client = _client_or_404(client_id)
    bid = _budget_id(client_id, year)
    n = apply_import(bid, body.rows)
    log_import(f"Imported {n} cells for {client['name']} / {year}", client_id)
    entries = load_entries(bid)
    settings = get_settings(bid)
    return {"ok": True, "imported": n, "summary": compute_full_summary(entries, settings["monatlich_mode"])}


@app.get("/api/mappings")
def list_mappings() -> dict:
    return {"mappings": get_mappings()}


@app.post("/api/mappings")
def post_mapping(body: MappingBody) -> dict:
    save_mapping(body.file_label, body.line_key)
    return {"ok": True}


@app.get("/api/import/log")
def import_log() -> dict:
    return {"log": get_import_log()}


@app.get("/api/clients/{client_id}/export/excel")
def export_excel(client_id: int, year: int = 2026):
    from io import BytesIO
    from openpyxl import Workbook

    from app.calculations import monatlich, summe
    from app.categories import MONTH_NAMES_DE

    client = _client_or_404(client_id)
    bid = _budget_id(client_id, year)
    entries = load_entries(bid)
    settings = get_settings(bid)
    summary = compute_full_summary(entries, settings["monatlich_mode"])

    wb = Workbook()
    ws = wb.active
    ws.title = f"{client['name']} {year}"
    ws.append(["Category"] + MONTH_NAMES_DE + ["Summe", "Monatlich"])

    for section in SECTIONS:
        ws.append([f"{section.title_de} / {section.title_en}"])
        for line in section.lines:
            vals = entries.get(line.key, [0.0] * 12)
            ws.append(
                [line.label_en]
                + vals
                + [summe(vals), monatlich(vals, settings["monatlich_mode"])]
            )

    buf = BytesIO()
    wb.save(buf)
    buf.seek(0)
    safe = "".join(c if c.isalnum() else "_" for c in client["name"])
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="budget_{safe}_{year}.xlsx"'},
    )
