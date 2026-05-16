"""FastAPI application entry point."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, Response, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from starlette.middleware.base import BaseHTTPMiddleware

from app.auth import (
    SESSION_COOKIE,
    change_password,
    create_session,
    ensure_auth_config,
    revoke_session,
    verify_login,
    verify_session,
)

from app.calculations import chart_payload, compute_full_summary, drilldown_slices
from app.categories import SECTIONS, TABS
from app.database import (
    ASSET_TYPES,
    INVESTMENT_TYPES,
    bulk_upsert,
    compute_balance_sheet,
    create_asset,
    create_client,
    create_custom_line,
    create_debt,
    create_future_investment,
    custom_lines_by_section,
    custom_line_keys_by_section,
    db_label,
    delete_asset,
    delete_client,
    delete_custom_line,
    delete_debt,
    delete_future_investment,
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
    update_asset,
    update_client,
    update_debt,
    update_future_investment,
    upsert_entry,
)
from app.import_excel import all_category_options, apply_import, parse_workbook
from app.import_csv import parse_csv
from app.paths import bundle_dir
from app.seed import ensure_sample_client

STATIC_DIR = bundle_dir() / "static"

app = FastAPI(title="Annual Budget", version="2.0.0")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


def _is_public_path(path: str) -> bool:
    if path in ("/", "/api/health", "/api/auth/login", "/api/auth/status"):
        return True
    if path.startswith("/static/"):
        return True
    return path == "/api/auth/reset-password"


class AuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if _is_public_path(request.url.path):
            return await call_next(request)
        token = request.cookies.get(SESSION_COOKIE)
        if not verify_session(token):
            return JSONResponse(
                status_code=401,
                content={"detail": "Not authenticated"},
            )
        return await call_next(request)


app.add_middleware(AuthMiddleware)


@app.on_event("startup")
def startup() -> None:
    init_db()
    ensure_sample_client()
    ensure_auth_config()


class LoginBody(BaseModel):
    username: str
    password: str


class ResetPasswordBody(BaseModel):
    reset_code: str
    new_password: str
    new_username: str = ""


@app.post("/api/auth/login")
def auth_login(body: LoginBody) -> JSONResponse:
    username = body.username.strip()
    if not verify_login(username, body.password):
        raise HTTPException(status_code=401, detail="Invalid username or password")
    token = create_session(username)
    payload = JSONResponse({"ok": True, "username": username})
    payload.set_cookie(
        SESSION_COOKIE,
        token,
        httponly=True,
        samesite="lax",
        secure=False,
    )
    return payload


@app.get("/api/auth/status")
def auth_status(request: Request) -> dict:
    sess = verify_session(request.cookies.get(SESSION_COOKIE))
    if not sess:
        return {"authenticated": False}
    return {"authenticated": True, "username": sess["username"]}


@app.post("/api/auth/logout")
def auth_logout(request: Request) -> JSONResponse:
    revoke_session(request.cookies.get(SESSION_COOKIE))
    payload = JSONResponse({"ok": True})
    payload.delete_cookie(SESSION_COOKIE)
    return payload


@app.post("/api/auth/reset-password")
def auth_reset_password(body: ResetPasswordBody) -> dict:
    try:
        change_password(
            body.reset_code,
            body.new_password,
            body.new_username.strip() or None,
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e)) from e
    return {"ok": True}


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


class AssetBody(BaseModel):
    name: str
    asset_type: str = "other"
    amount: float = 0
    notes: str = ""


class DebtBody(BaseModel):
    name: str
    amount: float = 0
    monthly_payment: float = 0
    interest_rate_annual: float = 0
    notes: str = ""


class FutureInvestBody(BaseModel):
    name: str
    investment_type: str = "other"
    current_amount: float = 0
    target_amount: float = 0
    monthly_contribution: float = 0
    expected_return_annual: float = 0
    target_year: int | None = None
    notes: str = ""


class CustomLineBody(BaseModel):
    section_id: str
    label_de: str
    label_en: str = ""
    line_type: str = "expense"


def _client_or_404(client_id: int) -> dict:
    c = get_client(client_id)
    if not c:
        raise HTTPException(404, "Client not found")
    return c


def _budget_id(client_id: int, year: int) -> int:
    _client_or_404(client_id)
    return get_or_create_budget(client_id, year)


def _budget_bundle(budget_id: int) -> tuple[dict, dict, dict[str, list[str]], dict]:
    entries = load_entries(budget_id)
    settings = get_settings(budget_id)
    ck = custom_line_keys_by_section(budget_id)
    summary = compute_full_summary(entries, settings["monatlich_mode"], ck)
    return entries, settings, ck, summary


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
    return {
        "tabs": TABS,
        "sections": sections,
        "categories": all_category_options(),
        "asset_types": list(ASSET_TYPES),
        "investment_types": list(INVESTMENT_TYPES),
    }


@app.get("/api/clients/{client_id}/budget/{year}")
def get_budget(client_id: int, year: int) -> dict:
    client = _client_or_404(client_id)
    bid = _budget_id(client_id, year)
    entries, settings, ck, summary = _budget_bundle(bid)
    return {
        "budget_id": bid,
        "client_id": client_id,
        "client_name": client["name"],
        "year": year,
        "entries": entries,
        "summary": summary,
        "settings": settings,
        "custom_lines": custom_lines_by_section(bid),
        "balance_sheet": compute_balance_sheet(client_id, year),
    }


@app.get("/api/clients/{client_id}/budget/{year}/summary")
def get_summary(client_id: int, year: int, month: int = 8) -> dict:
    bid = _budget_id(client_id, year)
    entries, settings, ck, summary = _budget_bundle(bid)
    return {
        "summary": summary,
        "charts": chart_payload(entries, month, settings["monatlich_mode"], ck),
        "balance_sheet": compute_balance_sheet(client_id, year),
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
    entries, settings, ck, summary = _budget_bundle(bid)
    return {"ok": True, "summary": summary}


@app.post("/api/clients/{client_id}/budget/{year}/bulk")
def post_bulk(client_id: int, year: int, body: BulkBody) -> dict:
    bid = _budget_id(client_id, year)
    bulk_upsert(bid, body.line_key, body.start_month, body.end_month, body.amount)
    entries, settings, ck, summary = _budget_bundle(bid)
    return {"ok": True, "summary": summary}


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
    entries, settings, ck, summary = _budget_bundle(bid)
    return {"ok": True, "imported": n, "summary": summary}


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


def _balance_for_client(client_id: int, year: int) -> dict:
    try:
        return compute_balance_sheet(client_id, year)
    except Exception as exc:
        import logging

        logging.getLogger(__name__).warning(
            "balance_sheet year=%s failed (%s), using snapshot without payoff",
            year,
            exc,
        )
        base = compute_balance_sheet(client_id, year=None)
        base.setdefault("payoff", None)
        base["budget_year"] = year
        return base


@app.get("/api/clients/{client_id}/balance-sheet")
def get_balance_sheet(client_id: int, year: int = 2026) -> dict:
    _client_or_404(client_id)
    return _balance_for_client(client_id, year)


@app.post("/api/clients/{client_id}/assets")
def post_asset(client_id: int, body: AssetBody, year: int = 2026) -> dict:
    _client_or_404(client_id)
    try:
        asset = create_asset(client_id, body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"asset": asset, "balance_sheet": _balance_for_client(client_id, year)}


@app.put("/api/clients/{client_id}/assets/{asset_id}")
def put_asset(client_id: int, asset_id: int, body: AssetBody, year: int = 2026) -> dict:
    _client_or_404(client_id)
    asset = update_asset(asset_id, body.model_dump())
    if not asset or asset["client_id"] != client_id:
        raise HTTPException(404, "Asset not found")
    return {"asset": asset, "balance_sheet": _balance_for_client(client_id, year)}


@app.delete("/api/clients/{client_id}/assets/{asset_id}")
def remove_asset(client_id: int, asset_id: int, year: int = 2026) -> dict:
    _client_or_404(client_id)
    from app.database import _get_asset

    a = _get_asset(asset_id)
    if not a or a["client_id"] != client_id:
        raise HTTPException(404, "Asset not found")
    if not delete_asset(asset_id):
        raise HTTPException(404, "Asset not found")
    return {"ok": True, "balance_sheet": _balance_for_client(client_id, year)}


@app.post("/api/clients/{client_id}/debts")
def post_debt(client_id: int, body: DebtBody, year: int = 2026) -> dict:
    _client_or_404(client_id)
    try:
        debt = create_debt(client_id, body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {"debt": debt, "balance_sheet": _balance_for_client(client_id, year)}


@app.put("/api/clients/{client_id}/debts/{debt_id}")
def put_debt(client_id: int, debt_id: int, body: DebtBody, year: int = 2026) -> dict:
    _client_or_404(client_id)
    debt = update_debt(debt_id, body.model_dump())
    if not debt or debt["client_id"] != client_id:
        raise HTTPException(404, "Debt not found")
    return {"debt": debt, "balance_sheet": _balance_for_client(client_id, year)}


@app.delete("/api/clients/{client_id}/debts/{debt_id}")
def remove_debt(client_id: int, debt_id: int, year: int = 2026) -> dict:
    _client_or_404(client_id)
    from app.database import _get_debt

    d = _get_debt(debt_id)
    if not d or d["client_id"] != client_id:
        raise HTTPException(404, "Debt not found")
    if not delete_debt(debt_id):
        raise HTTPException(404, "Debt not found")
    return {"ok": True, "balance_sheet": _balance_for_client(client_id, year)}


@app.post("/api/clients/{client_id}/future-investments")
def post_future_investment(client_id: int, body: FutureInvestBody, year: int = 2026) -> dict:
    _client_or_404(client_id)
    try:
        item = create_future_investment(client_id, body.model_dump())
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    return {
        "investment": item,
        "balance_sheet": _balance_for_client(client_id, year),
    }


@app.put("/api/clients/{client_id}/future-investments/{investment_id}")
def put_future_investment(
    client_id: int, investment_id: int, body: FutureInvestBody, year: int = 2026
) -> dict:
    _client_or_404(client_id)
    item = update_future_investment(investment_id, body.model_dump())
    if not item or item["client_id"] != client_id:
        raise HTTPException(404, "Investment not found")
    return {
        "investment": item,
        "balance_sheet": _balance_for_client(client_id, year),
    }


@app.delete("/api/clients/{client_id}/future-investments/{investment_id}")
def remove_future_investment(
    client_id: int, investment_id: int, year: int = 2026
) -> dict:
    _client_or_404(client_id)
    from app.database import _get_future_investment

    row = _get_future_investment(investment_id)
    if not row or row["client_id"] != client_id:
        raise HTTPException(404, "Investment not found")
    if not delete_future_investment(investment_id):
        raise HTTPException(404, "Investment not found")
    return {"ok": True, "balance_sheet": _balance_for_client(client_id, year)}


@app.post("/api/clients/{client_id}/custom-lines")
def post_custom_line_query(client_id: int, body: CustomLineBody, year: int = 2026) -> dict:
    """Alternate URL (year as query param) for older frontends."""
    return post_custom_line(client_id, year, body)


@app.post("/api/clients/{client_id}/budget/{year}/custom-lines")
def post_custom_line(client_id: int, year: int, body: CustomLineBody) -> dict:
    bid = _budget_id(client_id, year)
    try:
        line = create_custom_line(
            bid, body.section_id, body.label_de, body.label_en, body.line_type
        )
    except ValueError as e:
        raise HTTPException(400, str(e)) from e
    entries, settings, ck, summary = _budget_bundle(bid)
    return {
        "line": line,
        "custom_lines": custom_lines_by_section(bid),
        "entries": entries,
        "summary": summary,
    }


@app.delete("/api/clients/{client_id}/budget/{year}/custom-lines/{line_key}")
def remove_custom_line(client_id: int, year: int, line_key: str) -> dict:
    bid = _budget_id(client_id, year)
    if not delete_custom_line(bid, line_key):
        raise HTTPException(404, "Line not found")
    entries, settings, ck, summary = _budget_bundle(bid)
    return {
        "ok": True,
        "custom_lines": custom_lines_by_section(bid),
        "entries": entries,
        "summary": summary,
    }


@app.get("/api/clients/{client_id}/export/excel")
def export_excel(client_id: int, year: int = 2026):
    from app.export_excel import build_client_workbook

    client = _client_or_404(client_id)
    bid = _budget_id(client_id, year)
    entries = load_entries(bid)
    settings = get_settings(bid)
    ck = custom_line_keys_by_section(bid)
    balance = compute_balance_sheet(client_id, year)
    buf = build_client_workbook(
        client,
        year,
        entries,
        settings["monatlich_mode"],
        ck,
        balance,
        custom_lines_by_section(bid),
    )
    safe = "".join(c if c.isalnum() else "_" for c in client["name"])
    return StreamingResponse(
        buf,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={
            "Content-Disposition": (
                f'attachment; filename="budget_report_{safe}_{year}.xlsx"'
            )
        },
    )


@app.get("/api/clients/{client_id}/export/csv")
def export_csv(client_id: int, year: int = 2026):
    from app.export_csv import build_budget_csv

    client = _client_or_404(client_id)
    bid = _budget_id(client_id, year)
    entries = load_entries(bid)
    settings = get_settings(bid)
    data = build_budget_csv(
        entries,
        custom_lines_by_section(bid),
        settings["monatlich_mode"],
    )
    safe = "".join(c if c.isalnum() else "_" for c in client["name"])
    return Response(
        content=data,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="budget_{safe}_{year}.csv"'
        },
    )


@app.get("/api/clients/{client_id}/export/pdf")
def export_pdf(client_id: int, year: int = 2026, month: int = 8):
    from app.export_pdf import build_budget_pdf

    client = _client_or_404(client_id)
    bid = _budget_id(client_id, year)
    entries = load_entries(bid)
    settings = get_settings(bid)
    ck = custom_line_keys_by_section(bid)
    balance = compute_balance_sheet(client_id, year)
    data = build_budget_pdf(
        client,
        year,
        entries,
        settings["monatlich_mode"],
        ck,
        balance,
        month=max(1, min(12, month)),
    )
    safe = "".join(c if c.isalnum() else "_" for c in client["name"])
    return Response(
        content=data,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="budget_{safe}_{year}.pdf"'
        },
    )


@app.get("/api/clients/{client_id}/export/report")
def export_report(client_id: int, year: int = 2026):
    from app.export_report import build_print_report_html

    client = _client_or_404(client_id)
    bid = _budget_id(client_id, year)
    entries = load_entries(bid)
    settings = get_settings(bid)
    html = build_print_report_html(
        client,
        year,
        entries,
        settings["monatlich_mode"],
        custom_lines_by_section(bid),
    )
    return HTMLResponse(html)
