# TOVITO TRADER — Application Launcher Cheat Sheet

```
Last Updated: February 2026
All commands run from: C:\tovito-trader
```

---

## QUICK LAUNCH TABLE

| App | Type | Port | How to Launch |
|-----|------|------|---------------|
| **Ops Dashboard** | Streamlit | 8502 | `python -m streamlit run apps/ops_dashboard/app.py --server.port 8502` |
| **Market Monitor** | Streamlit | 8501 | `cd apps/market_monitor && streamlit run main.py` |
| **Fund Manager** | Desktop | — | `cd apps/fund_manager && python dashboard.py` |
| **Investor Portal API** | FastAPI | 8000 | `cd apps/investor_portal/api && python -m uvicorn main:app --reload --port 8000` |
| **Investor Portal UI** | React | 5173 | `cd apps/investor_portal/frontend/investor_portal && npm run dev` |

---

## DASHBOARDS & MONITORING

### Operations Health Dashboard (Streamlit)
System health at a glance — NAV freshness, automation status, reconciliation, logs, email delivery.
Shows actionable fix guidance for every non-green indicator.

```powershell
python -m streamlit run apps/ops_dashboard/app.py --server.port 8502
```
Open: **http://localhost:8502**

### Market Monitor (Streamlit)
Live market data, portfolio streaming, price alerts, and data explorer.

```powershell
cd apps/market_monitor && streamlit run main.py
# Or use the launcher:
apps\market_monitor\run.bat
```
Open: **http://localhost:8501**

### Fund Manager Dashboard (Desktop)
Full-featured desktop app — NAV charts, investor allocations, positions, transactions,
SQL data explorer, trading journal, tax management, alert monitoring.

```powershell
cd apps/fund_manager && python dashboard.py
```

---

## INVESTOR PORTAL (Web App)

The portal has two parts — both must be running for investors to use it.

### Backend API (FastAPI)

```powershell
cd apps/investor_portal/api && python -m uvicorn main:app --reload --port 8000
```
API Docs: **http://localhost:8000/docs**

### Frontend (React + Vite)

```powershell
cd apps/investor_portal/frontend/investor_portal && npm run dev
```
Open: **http://localhost:5173**

Prerequisites: Node.js 18+, run `npm install` first if dependencies are missing.

---

## AUTOMATED TASKS (Windows Task Scheduler)

These run automatically. Use these commands to run them manually if needed.

| Time (EST) | Task | Manual Command | Batch Launcher |
|------------|------|----------------|----------------|
| 4:05 PM daily | Daily NAV Update | `python scripts/daily_nav_enhanced.py` | `run_daily.bat` |
| 5:05 PM daily | Watchdog Health Check | `python apps/market_monitor/watchdog_monitor.py` | `run_watchdog.bat` |
| Weekly (Fri) | Data Validation | `python scripts/validation/validate_reconciliation.py --verbose` | `run_weekly_validation.bat` |
| 1st of month | Monthly Reports | `python scripts/reporting/generate_monthly_report.py --previous-month --email` | `send_monthly_reports.bat` |

---

## EXTERNAL MONITORING (healthchecks.io)

Dashboard: **https://healthchecks.io** (login required)

Two checks configured:
- **Daily NAV** — Pinged on success/fail at end of `daily_nav_enhanced.py`. Alerts if no ping by grace time.
- **Watchdog** — Pinged by `watchdog_monitor.py` when all system checks pass.

If a check shows DOWN:
1. Open the **Ops Dashboard** (http://localhost:8502) for detailed status
2. Check logs: `logs/task_scheduler.log` (NAV) or `logs/watchdog_scheduler.log` (Watchdog)
3. Run the script manually to see the error output

---

## VALIDATION & HEALTH CHECKS

```powershell
# Full system integrity check
python scripts/validation/validate_comprehensive.py

# System health check (DB, API, email, disk)
python scripts/validation/system_health_check.py

# Data reconciliation
python scripts/validation/validate_reconciliation.py --verbose

# TastyTrade API connection test
python scripts/validation/test_tastytrade_connection.py

# Email configuration test
python scripts/email/test_email.py
```

---

## TESTING

```powershell
# Full test suite (~214 tests)
pytest tests/ -v

# Specific test areas
pytest tests/test_nav_calculations.py -v
pytest tests/test_contributions.py -v
pytest tests/test_withdrawals.py -v
pytest tests/test_ops_health_checks.py -v
pytest tests/test_remediation.py -v
```

---

## PORT REFERENCE

| Port | Application | URL |
|------|-------------|-----|
| 5173 | Investor Portal Frontend | http://localhost:5173 |
| 8000 | Investor Portal API | http://localhost:8000/docs |
| 8501 | Market Monitor | http://localhost:8501 |
| 8502 | Ops Dashboard | http://localhost:8502 |

---

## TROUBLESHOOTING

**"Python not found" in batch files:**
Python must be at `C:\Python314\python.exe` or on PATH. Batch files check `C:\Python314` first.

**Streamlit won't start:**
```powershell
pip install streamlit
```

**Investor Portal frontend won't start:**
```powershell
cd apps/investor_portal/frontend/investor_portal
npm install
npm run dev
```

**Port already in use:**
```powershell
# Find what's using a port (e.g., 8502)
netstat -ano | findstr :8502
# Kill the process
taskkill /PID <pid> /F
```

**TastyTrade session expired:**
Delete `.tastytrade_session` in project root — next API call creates a new session (may require 2FA).
