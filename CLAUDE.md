# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Bot Omie is a Python RPA bot that automates extraction of financial reports from Omie ERP, processes Excel files, persists data to PostgreSQL (schema `omie`), and archives files to a network drive. It has a Tkinter GUI (`app/gui.py`) and a CLI entry point (`app/main.py`).

## Commands

```bash
# Install dependencies
pip install -r requirements.txt
playwright install firefox

# Run via GUI (recommended)
python app/gui.py

# Run extraction directly (headless, requires auth.json)
python app/main.py

# Discover selectors when Omie UI changes
python app/tools/get_selectors.py
```

There is no test suite, linter, or build system configured.

## Architecture

The app follows a modular ETL (Extract, Transform, Load) pattern:

```
GUI (gui.py) → Orchestrator (main.py) → Auth (auth.py) + Playwright (Firefox)
                                        ↓
                              Excel Processing (process_excel.py)
                                        ↓
                              Database Upsert (upsert_*.py) → PostgreSQL (db/db.py)
                                        ↓
                              File Archive (utils.py) → Network Drive (Z:\...)
```

### Key Modules

- **`app/main.py`** — Core orchestrator. Manages the Playwright browser session, navigates Omie, extracts reports by `data-slug`, processes them, and saves to DB. Contains retry logic (MAX_RETRIES=3) and a fixed 5-minute wait after report execution.
- **`app/gui.py`** — Tkinter GUI with auth status, report selection checkboxes, log viewer, progress bar, and a 10-second inactivity timer that auto-starts extraction.
- **`app/auth.py`** — Hybrid authentication: first run requires manual login + 2FA (saves cookies to `auth.json`); subsequent runs restore cookies. Falls back to auto-login with credentials from `.env` if cookies expire.
- **`app/actions/process_excel/process_excel.py`** — Reads Excel files with dynamic header detection, normalizes columns, removes empty rows/columns via Pandas + OpenPyXL.
- **`app/actions/upsert_data/upsert_*.py`** — Three handlers (a_pagar, nf_faturadas, notas_debito) in schema `omie`. Use `psycopg2.extras.execute_values()` for bulk insert and dynamic table creation with PostgreSQL types (SERIAL, NUMERIC, TIMESTAMPTZ).
- **`app/db/db.py`** — PostgreSQL connection pool (`ThreadedConnectionPool`), auto-creates schema `omie` and trigger function `set_updated_at()`.
- **`app/utils.py`** — File archiving (move to network path) and local cleanup.

### Report Configuration

Reports are defined in `RELATORIOS` list in `main.py`. Each entry has:
- `nome_menu` — Display name
- `data_slug` — Omie's `data-slug` attribute used for reliable element selection
- `arquivo` — Expected Excel filename in `app/downloads/`
- `tabela` — PostgreSQL table name (in schema `omie`)
- `upsert_handler` — Function reference for DB persistence

### Authentication Flow

1. First run: User clicks "Primeira Configuração" → visible browser opens → manual login + 2FA → cookies saved to `auth.json`
2. Subsequent runs: cookies loaded from `auth.json` → headless Firefox
3. If cookies expired: `realizar_login()` auto-fills email/password from `.env` vars `OMIE_USER`/`OMIE_PASSWORD`

## Environment Variables (.env)

- `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` — PostgreSQL connection
- `DB_POOL_MIN`, `DB_POOL_MAX` — Connection pool sizing
- `OMIE_URL`, `OMIE_USER`, `OMIE_PASSWORD` — Omie ERP credentials
- `REDE_DESTINO` — Windows network path for file archiving
- `AUTO_CLOSE` — Whether GUI closes after extraction completes

## Language & Conventions

- All UI text, logs, comments, and documentation are in **Brazilian Portuguese**
- Commit messages follow conventional commits in Portuguese (e.g., `fix: ajustar seletor de acesso`)
- The project uses Playwright's **synchronous API** (not async)
- Browser engine is **Firefox** (not Chromium)
- No type hints are used in the current codebase
