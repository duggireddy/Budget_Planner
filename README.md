# Annual Budget (local finance app)

Web app for **annual household/business budgets** per **client** and **calendar year**.  
All data stays on your PC in `data/budget.db` (SQLite). No cloud required.

---

## Quick start

```powershell
cd d:\Finance\Automation
.\.venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python -m pytest tests/ -v
python -m uvicorn app.main:app --host 127.0.0.1 --port 8765
```

Or double-click **`start_budget.bat`**.

Open **http://127.0.0.1:8765** and press **Ctrl+F5** after code updates.

---

## Top bar: Client + Year

| Control | What it does |
|--------|----------------|
| **Client** | Switch which customer’s budget you view (2025–2040 data is separate per client). |
| **Year** | Pick calendar year **2025 … 2040**. Each year has its own 12 months of amounts. |

Changing client or year reloads that client’s budget for that year. Empty years start at zero until you enter data.

Use the **Clients** tab to create/edit full profiles (address, tax ID, IBAN, etc.).

---

## How data is saved (year-wise — recommended design)

This is already how the app works. You do **not** need a separate file per year.

```
Client (name, address, tax ID, …)
  └── Budget per year (2025, 2026, … 2040)
        └── 12 months × each budget line (amount per category)
```

| Table | Stores |
|-------|--------|
| `clients` | Name, company, address, email, phone, tax/VAT ID, IBAN, notes |
| `budgets` | One row per **(client_id, year)** — settings like Monatlich mode |
| `entries` | **line_key + month (1–12) + amount** for that budget |

**Why this is a good approach**

- One client, many years — no duplicate client records.
- Switch year in the header — instant load; no manual “save as 2027”.
- Easy backup: copy `data\budget.db`.
- Same structure as your Excel template (rows = categories, columns = months).

**Workflow**

1. Select **Client** + **Year** in the header.
2. **Enter data** → type amounts (auto-saved; totals update on all tabs).
3. Change **Year** to plan 2027; change **Client** for another customer.
4. **Summary** / **Dashboard** show totals for the selected client + year only.

---

## Excel template categories — all included

The app implements the full template in `app/categories.py` (DE + EN labels).

### Income (Einnahmen)

- **Self-employed A & B**: Revenue, taxes, social security, operating expenses, trade tax, other → *Summe Nettoeinnahme selbstst.*
- **Net A & B**: Gross, net, 450€ job → *Summe Netto nichtselbstst.*
- **Other income A & B**: Child benefit, parental allowance, rental, PV, alimony, pensions (statutory + tiers 1–3), interest, dividends, tax refunds, licenses, other → *Summe Sonstige Einnahmen*

### Expenses

- **Living (Total - 1)**: Clothes, household, eating out, cosmetics, hobby, pets, medication, doctors, pocket money, daycare, care, vacation, bank fees, tobacco, gifts, gym, mobile, cable, streaming, music, books, magazines, semester fee, transport, alimony, union, other (×3) → *Summe Lebenshaltung*
- **Housing (Total - 2)**: Warm rent, electricity, heating, GEZ, property tax, internet, cleaning, garage, other → *Summe Wohnen*
- **Real estate financing**: Financing 1/2 + principal, building society loan, repayment replacement 1/2 → *Summe Baufinanzierung*
- **Health A & B**: Supplementary health, care, life, disability, asset component → *Summe Krankenversicherung*
- **Property insurance (Total - 3)**: VSP, animal liability, household, glass, car, accident, travel, building, legal, ADAC, other
- **Pension**: Rürup ×2, Riester ×2, private provision ×2
- **Wealth**: Gold, investment plans, savings, Bauspar; loans 1–3

### Bottom summary (computed automatically)

- **Total revenue** · **Total expenses** · **Difference** (revenue − expenses only)

---

## Features

- Dashboard, Enter data, Summary, Charts, Clients
- EN / DE (top right)
- Import/export Excel & CSV
- Sample client with demo data (Jul–Dec) on first run

---

## Configuration

File: **`.env`**

```ini
DB_BACKEND=sqlite
```

Optional MySQL (requires Docker): `DB_BACKEND=mysql` then `docker compose up -d`.

**Do not** type `MYSQL_USER=budget` in PowerShell — that is bash syntax. Use `.env` only.

---

## Commands

| Action | Command |
|--------|---------|
| Install dependencies | `pip install -r requirements.txt` |
| Run tests (26) | `python -m pytest tests/ -v` |
| Start app | `start_budget.bat` |
| Start app (manual) | `python -m uvicorn app.main:app --host 127.0.0.1 --port 8765` |
| Backup all data | Copy `data\budget.db` |
| Reset database | Delete `data\budget.db` and restart |

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| App won’t start | Ensure `.env` has `DB_BACKEND=sqlite`. Delete `data\budget.db` if corrupted and restart. |
| Old UI / totals not updating | **Ctrl+F5** in browser (use `app.js?v=7`). |
| Port in use | Close other terminal running uvicorn, or run `start_budget.bat` (kills port 8765). |
| Wrong year empty | Normal — each year is separate; enter data or copy from Excel import. |

---

## Project layout

```
app/categories.py   # All budget lines (matches Excel)
app/calculations.py # Totals, Difference, charts
app/database.py     # SQLite storage
app/main.py         # API
static/             # Web UI
data/budget.db      # Your data (created on first run)
```
