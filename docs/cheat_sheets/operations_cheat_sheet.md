# TOVITO TRADER — Operations Cheat Sheet

```
Last Updated: February 2026
All commands run from: C:\tovito-trader
```

---

## DAILY OPERATIONS

### Automated (Windows Task Scheduler)

| Time (EST) | Task | Script |
|---|---|---|
| 4:05 PM | Daily NAV Update | `run_daily.bat` |
| 5:05 PM | Watchdog Verification | `run_watchdog.bat` |
| Weekly (Fri) | Data Integrity Check | `run_weekly_validation.bat` |
| 1st of Month | Monthly Reports + Email | `send_monthly_reports.bat` |

### Manual NAV Update

```powershell
python scripts/daily_nav_enhanced.py
```

---

## INVESTOR MANAGEMENT

### Fund Flow Workflow (Contributions & Withdrawals)

```powershell
# Step 1: Submit contribution or withdrawal request
python scripts/investor/submit_fund_flow.py

# Step 2: Match to brokerage ACH transaction
python scripts/investor/match_fund_flow.py

# Step 3: Execute share accounting
python scripts/investor/process_fund_flow.py
```

> **Tax policy:** Withdrawals disburse the full amount. Realized gains are tracked
> and tax is settled quarterly via `scripts/tax/quarterly_tax_payment.py`.

### Account Management

```powershell
# List all investors (quick ID lookup)
python scripts/investor/list_investors.py

# Assign unallocated deposit to investor
python scripts/investor/assign_pending_contribution.py

# Update investor email addresses
python scripts/investor/update_investor_emails.py

# View investor emails
python scripts/investor/view_investor_emails.py

# Close an investor account (full liquidation + tax settlement)
python scripts/investor/close_investor_account.py --investor 20260101-01A
```

---

## REPORTING

```powershell
# Generate monthly report (PDF)
python scripts/reporting/generate_monthly_report.py --month 1 --year 2026

# Generate + email to all investors
python scripts/reporting/generate_monthly_report.py --month 1 --year 2026 --email

# Generate for one investor only
python scripts/reporting/generate_monthly_report.py --month 1 --year 2026 --investor 20260101-01A --email

# Export transactions to Excel
python scripts/reporting/export_transactions_excel.py
```

---

## TAXATION

```powershell
# Quarterly estimated tax payment (run 4x/year)
python scripts/tax/quarterly_tax_payment.py --quarter 1 --year 2026

# Year-end reconciliation (actual vs. estimated)
python scripts/tax/yearend_tax_reconciliation.py --year 2026
```

---

## APPLICATIONS

> Full launch guide with ports & troubleshooting: `docs/cheat_sheets/APP_LAUNCHER_CHEAT_SHEET.md`

### Operations Health Dashboard (Streamlit — port 8502)

```powershell
python -m streamlit run apps/ops_dashboard/app.py --server.port 8502
# Open: http://localhost:8502
```

### Market Monitor (Streamlit — port 8501)

```powershell
cd apps/market_monitor && streamlit run main.py
# Or use the launcher:
apps\market_monitor\run.bat
```

### Fund Manager Dashboard (Desktop)

```powershell
cd apps/fund_manager && python dashboard.py
```

### Investor Portal (Web)

```powershell
# Backend API (FastAPI — port 8000)
cd apps/investor_portal/api && python -m uvicorn main:app --reload --port 8000
# API docs: http://localhost:8000/docs

# Frontend (React + Vite — port 5173)
cd apps/investor_portal/frontend/investor_portal && npm run dev
# View: http://localhost:5173
```

---

## TRADING & POSITIONS

```powershell
# View trades (interactive)
python scripts/trading/query_trades.py

# Filter by symbol
python scripts/trading/query_trades.py --symbol SGOV

# View ACH deposits/withdrawals
python scripts/trading/query_trades.py --ach

# Trade summary
python scripts/trading/query_trades.py --summary

# View current positions
python scripts/utilities/view_positions.py
```

---

## VALIDATION & HEALTH

```powershell
# Full system integrity check
python scripts/validation/validate_comprehensive.py

# System health check (DB, API, email, disk)
python scripts/validation/system_health_check.py

# Data reconciliation
python scripts/validation/validate_reconciliation.py --verbose

# TastyTrade API connection test
python scripts/validation/test_tastytrade_connection.py
```

---

## DATABASE

```powershell
# BACKUP (always run before any DB changes!)
python scripts/utilities/backup_database.py

# Reverse last transaction (creates offsetting entry)
python scripts/utilities/reverse_transaction.py

# View system logs (PII-safe)
python scripts/utilities/view_logs.py

# Check database schema
python scripts/setup/check_database_schema.py

# Create test database (for development)
python scripts/setup/setup_test_database.py
```

---

## PROSPECTS & OUTREACH

```powershell
# Add a prospect
python scripts/prospects/add_prospect.py

# List all prospects
python scripts/prospects/list_prospects.py

# Bulk import from CSV
python scripts/prospects/import_prospects.py prospects.csv

# Send fund performance report to prospects
python scripts/prospects/send_prospect_report.py --month 1 --year 2026 --prospects prospects.csv

# View communication history
python scripts/prospects/view_communications.py
```

---

## EMAIL

```powershell
# Test email configuration
python scripts/email/test_email.py

# Check email config diagnostics
python scripts/email/check_email_config.py
```

---

## TESTING

```powershell
# Run full test suite
pytest tests/ -v

# Run specific test modules
pytest tests/test_contributions.py -v
pytest tests/test_withdrawals.py -v
pytest tests/test_nav_calculations.py -v
pytest tests/test_combined_brokerage.py -v
pytest tests/test_tastytrade_client.py -v
pytest tests/test_brokerage_factory.py -v
```

---

## QUICK REFERENCE — KEY ENV VARS (.env)

| Variable | Purpose |
|---|---|
| `BROKERAGE_PROVIDERS` | Combined NAV sources (e.g. `tradier,tastytrade`) |
| `TASTYTRADE_CLIENT_SECRET` | TastyTrade OAuth client secret |
| `TASTYTRADE_REFRESH_TOKEN` | TastyTrade OAuth refresh token |
| `TASTYTRADE_ACCOUNT_ID` | TastyTrade account for NAV |
| `TRADIER_API_KEY` | Tradier API key |
| `TRADIER_ACCOUNT_ID` | Tradier account ID |
| `DATABASE_PATH` | Main DB path (default: `data/tovito.db`) |
| `TAX_RATE` | Federal tax rate (default: `0.37`) |

---

## CRITICAL REMINDERS

1. **Always backup before DB changes:** `python scripts/utilities/backup_database.py`
2. **Never delete records** — use reversing entries
3. **Test against test DB** — never develop against production
4. **Run tests before and after changes:** `pytest tests/ -v`
5. **NAV can never be negative** — validate before writing
6. **No PII in logs/code** — use `src/utils/safe_logging.py`
