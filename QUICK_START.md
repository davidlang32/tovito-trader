# Tovito Trader - Quick Start Guide

Get up and running in 5 minutes.

---

## Prerequisites

- [ ] Python 3.11+ installed ([Download](https://www.python.org/downloads/))
- [ ] Node.js 18+ installed ([Download](https://nodejs.org/))
- [ ] Git (optional, for cloning)

---

## Step 1: Get the Project

```cmd
cd C:\
git clone <repository-url> tovito-trader
cd tovito-trader
```

Or download and extract the ZIP file to `C:\tovito-trader`

---

## Step 2: Install Python Dependencies

```cmd
cd C:\tovito-trader
pip install -r requirements.txt
```

Required packages: fastapi, uvicorn, python-jose, bcrypt, requests, etc.

---

## Step 3: Configure Environment

Copy the example config:
```cmd
copy config\.env.example config\.env.development
```

Edit `config\.env.development` with your settings:
```env
TRADIER_API_KEY=your_tradier_api_key
TRADIER_ACCOUNT_ID=your_account_id
JWT_SECRET_KEY=generate_a_secure_random_string
```

---

## Step 4: Verify Database

The database should already exist at `data\tovito.db`.

Validate it:
```cmd
python run.py validate
```

Expected: All 8 checks pass ✅

---

## Step 5: Set Up Portal Authentication

Run the migration (first time only):
```cmd
python migrate_add_auth_table.py
```

Set up your login:
```cmd
python verify_investor.py --email dlang32@gmail.com --password "YourSecurePass123!"
```

---

## Step 6: Start the API

```cmd
python -m uvicorn apps.investor_portal.api.main:app --port 8000
```

Verify: Open http://localhost:8000/docs

---

## Step 7: Start the Portal

Open a **new terminal**:

```cmd
cd C:\tovito-trader\apps\investor_portal\frontend\investor_portal
npm install
npm run dev
```

Open: http://localhost:3000

---

## Step 8: Test Everything

Open a **third terminal**:

```cmd
cd C:\tovito-trader
set TEST_PASSWORD=YourSecurePass123!
python test_api_regression.py --report
```

Expected: 18/18 tests pass ✅

---

## Daily Usage

### Calculate Daily NAV (after 4 PM EST)
```cmd
python scripts\nav\daily_nav_enhanced.py
```

### Validate Data
```cmd
python run.py validate
```

### Start Services
```cmd
# Terminal 1: API
python -m uvicorn apps.investor_portal.api.main:app --port 8000

# Terminal 2: Portal
cd apps\investor_portal\frontend\investor_portal
npm run dev
```

---

## Common Tasks

| Task | Command |
|------|---------|
| List investors | `python scripts\investor\list_investors.py` |
| Process contribution | `python scripts\investor\process_contribution.py` |
| Process withdrawal | `python scripts\investor\process_withdrawal_enhanced.py` |
| Generate report | `python scripts\reporting\generate_monthly_report.py --month 2026-01` |
| Backup database | `python scripts\utilities\backup_database.py` |

---

## Troubleshooting

| Problem | Solution |
|---------|----------|
| `pip` not found | Add Python to PATH, restart terminal |
| `npm` not found | Add Node.js to PATH, restart terminal |
| API won't start | Check if port 8000 is in use |
| Portal won't load | Make sure API is running first |
| Login fails | Reset password with `verify_investor.py` |

---

## Next Steps

1. Read [FUND_ADMIN_GUIDE.md](FUND_ADMIN_GUIDE.md) for complete documentation
2. Set up Task Scheduler for automated daily NAV
3. Configure email for investor reports
4. Set up external health monitoring

---

## File Locations

```
C:\tovito-trader\
├── data\tovito.db           # Main database
├── config\.env.development  # Configuration
├── run.py                   # Main CLI
├── test_api_regression.py   # Test suite
└── FUND_ADMIN_GUIDE.md      # Full documentation
```

---

**Need help?** See the full [Fund Admin Guide](FUND_ADMIN_GUIDE.md) or run:
```cmd
python run.py --help
```
