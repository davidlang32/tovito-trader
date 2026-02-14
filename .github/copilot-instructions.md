# Tovito Trader - AI Agent Instructions

## Project Overview

**Tovito Trader** is a pooled investment fund management system for tracking investor portfolios, calculating daily NAV (Net Asset Value), handling tax withholding, and providing investor access via web portal.

### Core Purpose
- Calculate daily NAV from broker account data (Single Source of Truth in `daily_nav` table)
- Manage investor contributions/withdrawals with proportional share accounting
- Track realized gains and apply 37% tax withholding
- REST API (FastAPI) + React frontend for investor portal
- Real-time market monitoring and automation

---

## Architecture & Data Flow

### Three-App Design
```
investor_portal/api/     ← FastAPI backend (Port 8000, /docs for swagger)
investor_portal/frontend/← React investor dashboard (Port 5173)
market_monitor/          ← Real-time market alerts (future)
fund_manager/            ← Admin dashboard (future)
```

### Database (Single Database)
- **Location**: `data/tovito.db` (SQLite)
- **Schema**: `src/database/schema_v2.py` (source of truth)
- **Key Tables**:
  - `investors`: investor_id, name, email, current_shares, net_investment
  - `transactions`: date, investor_id, type (Initial/Contribution/Withdrawal/Tax_Payment), amount, shares_transacted, nav_per_share
  - `daily_nav`: date, portfolio_value, total_shares, nav_per_share (SINGLE SOURCE OF TRUTH)
  - `tax_events`: realized_gain, tax_amount, investor_id
  - `audit_log`: all changes for compliance

### Data Flow: Daily NAV (Automated via Task Scheduler)
```
1. scripts/daily_nav_enhanced.py runs after market close
2. Syncs Tradier account positions → updates portfolio_value
3. Calculates: nav_per_share = portfolio_value / total_shares
4. Writes to daily_nav table
5. Writes heartbeat file (logs/daily_nav_heartbeat.txt) for monitoring
6. Pings external monitor, sends email alerts on failure
```

### Financial Data Patterns
- All amounts: decimal precision (USD)
- Tax rate: 37% (configurable in `config/settings.py` as TAX_RATE)
- Shares: tracked per investor with transaction history
- NAV per share: recalculated daily, used for all future transactions

### Tax Withholding Specifics
**When is tax applied?**
- **On Withdrawal**: Tax is calculated and withheld when investor withdraws funds
- Formula: `proportion_withdrawn = withdrawal_amount / current_value` → `realized_gain = total_unrealized_gain × proportion_withdrawn` → `tax = realized_gain × TAX_RATE`
- Tax recorded in `tax_events` table, linked to transaction
- Net proceeds to investor = `withdrawal_amount - tax_withheld`

**Share basis tracking:**
- Each investor's shares represent proportional ownership
- On contribution: `shares_purchased = amount / nav_per_share_at_date`
- On withdrawal: shares are sold proportionally at current NAV, triggering any gains

---

## Configuration & Environment

### Settings Pattern
```python
# UNIVERSAL: Always use settings singleton
from config.settings import settings

# NOT hardcoded values - all go through settings:
# - DATABASE_PATH (default: data/tovito.db)
# - TRADIER_API_KEY, TRADIER_ACCOUNT_ID
# - TAX_RATE (default: 0.37)
# - EMAIL_ENABLED, SMTP settings
# - LOG_LEVEL, LOG_TO_FILE
# - CORS_ORIGINS, JWT_SECRET_KEY

# Environment detection:
settings.is_production   # Check if production
settings.is_development  # Check if development
settings.ENV             # Current environment string
```

### Environment Files
- `.env.development` (for local dev)
- `.env.production` (for production, in config/ folder)
- `.env` fallback (root)
- Loaded automatically by Settings class

---

## Command Patterns (Windows-First)

### Main Entry Point
```cmd
# Use run.py for all operations (adds PROJECT_ROOT to sys.path)
python run.py api              # Test Tradier API connection
python run.py nav              # Run daily NAV update
python run.py validate         # 8-point data validation
python run.py investors        # List all investors
python run.py positions        # View current positions
python run.py contribution     # Process contribution transaction
python run.py withdrawal       # Process withdrawal
python run.py health           # System health check
python run.py test             # Run pytest suite
```

### API Development
```cmd
cd C:\tovito-trader
python -m uvicorn apps.investor_portal.api.main:app --reload --port 8000
# Open http://localhost:8000/docs for Swagger UI
```

### Frontend Development
```cmd
cd apps\investor_portal\frontend\investor_portal
npm install
npm run dev
# Open http://localhost:5173
```

### Testing
```cmd
python -m pytest tests/              # All tests
python -m pytest tests/test_nav.py   # Specific test
pytest --tb=short                    # Shorter output
```

### Windows Scheduled Tasks (Batch Files)
- `run_daily.bat` - Daily NAV update (monitored by watchdog)
- `run_weekly_validation.bat` - Data integrity checks
- `send_monthly_reports.bat` - Investor statements
- All run from PROJECT_ROOT and log to `logs/` folder

---

## Code Patterns & Conventions

### Scripts Directory Structure
```
scripts/
  daily_nav_enhanced.py    ← Main daily update (monitored by watchdog)
  daily_runner.py          ← Coordinated batch runner
  email_adapter.py         ← Email delivery (SMTP, Gmail)
  nav_helper.py            ← NAV calculation utility
  validation/ 
    ├── 8_point_validation.py ← Full data integrity suite
    └── [other validators]
  reporting/
    ├── monthly_statements.py  ← Generate investor statements
    └── [tax reports, etc]
  investor/
    ├── contribution_processor.py
    └── withdrawal_processor.py
```

### Script Conventions
1. **Path Setup** (ALWAYS first):
   ```python
   from pathlib import Path
   PROJECT_DIR = Path("C:/tovito-trader")  # or use __file__
   sys.path.insert(0, str(PROJECT_DIR))
   ```

2. **Logging Pattern**:
   ```python
   LOG_FILE = PROJECT_DIR / "logs" / "scriptname.log"
   def log(message, level="INFO"):
       timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
       print(f"[{timestamp}] [{level}] {message}")
       with open(LOG_FILE, 'a') as f:
           f.write(f"[{timestamp}] [{level}] {message}\n")
   ```

3. **Heartbeat Pattern** (for task monitoring):
   ```python
   HEARTBEAT_FILE = PROJECT_DIR / "logs" / "daily_nav_heartbeat.txt"
   # Write after successful run so watchdog_monitor.py can verify
   with open(HEARTBEAT_FILE, 'w') as f:
       f.write(f"Last run: {datetime.now()}\n")
   ```

4. **Error Handling**:
   ```python
   # Don't crash on edge cases - log and continue
   try:
       # operation
   except Exception as e:
       log(f"Failed: {e}", "ERROR")
       # Send alert email via scripts/email_adapter.py
       # Then continue with next item
   ```

### API Patterns (FastAPI)

**Routers**: In `apps/investor_portal/api/routes/`
```python
# Each router is an independent module
from fastapi import APIRouter
router = APIRouter()

@router.get("/holdings/{investor_id}")
async def get_holdings(investor_id: str):
    # Use sqlalchemy models or database.py helpers
    return {...}
```

**Authentication**: JWT token in header
```python
from fastapi.security import HTTPBearer
security = HTTPBearer()

@router.post("/login")
async def login(credentials: LoginRequest):
    # Verify against database, return JWT token
    return {"access_token": token}
```

**Database Access** (in routes):
```python
from .models import get_investor_holdings, get_daily_nav
# Models in models/ folder handle all SQLAlchemy/SQL queries
```

### Database Queries
- **Schema-based**: Use SQLAlchemy ORM when possible (models.py)
- **Raw SQL**: For complex queries, use sqlite3 directly with proper parameterization
- **NeverString interpolation**: Always use ? placeholders
  ```python
  cursor.execute("SELECT * FROM investors WHERE investor_id = ?", (investor_id,))
  ```

### Testing Conventions
- **Test DB**: `conftest.py` provides `test_db` and `populated_db` fixtures
- **Mocking Tradier**: `conftest.py` includes mock factory
- **Each test**: Uses fresh test database (conftest handles cleanup)

---

## Authentication & Authorization

### JWT-Based Authentication (FastAPI)
```python
# Login flow: /auth/login → verify email+password → return JWT tokens
from apps.investor_portal.api.dependencies import create_access_token, verify_token

# Access tokens expire (short-lived, ~15 mins)
# Refresh tokens allow renewal (long-lived, ~7 days)
# Both stored in secure HTTP-only cookies on frontend

# Protected routes check token in header:
@router.get("/my-holdings")
async def get_holdings(current_user: CurrentUser = Depends(get_current_user)):
    # current_user contains investor_id, email, name
    return {...}
```

### First-Time Setup (Email Verification)
1. Investor receives email link with verification token
2. Token grants access to set password
3. Password stored hashed (using bcrypt via dependencies)
4. Email-based authentication (not username)

---

## Withdrawal & Contribution Processing

### Contribution Transaction Flow
```
scripts/investor/process_contribution.py:
  1. User/admin provides: investor_id, amount, [transaction_date]
  2. Fetch NAV per share from daily_nav table for that date
  3. Calculate shares: shares = amount / nav_per_share
  4. Insert transaction row: type='Contribution', net_investment updated
  5. Update investor.current_shares += shares
  6. Log to audit_log for compliance
  7. Optional: Send confirmation email
```

**Key Code Pattern:**
```python
# From process_contribution.py
nav_per_share, _, _ = get_nav_for_date(conn, transaction_date)  # Allows backdating
new_shares = amount / nav_per_share
cursor.execute("""
    INSERT INTO transactions 
    (date, investor_id, transaction_type, amount, shares_transacted, nav_per_share)
    VALUES (?, ?, 'Contribution', ?, ?, ?)
""", (transaction_date, investor_id, amount, new_shares, nav_per_share))
```

### Withdrawal Transaction Flow (includes tax calculation)
```
scripts/investor/process_withdrawal.py:
  1. User provides: investor_id, withdrawal_amount, [transaction_date]
  2. Fetch current holdings: current_value, unrealized_gain
  3. Calculate proportion being withdrawn: proportion = amount / current_value
  4. Calculate realized_gain = total_unrealized_gain × proportion
  5. Calculate tax = realized_gain × TAX_RATE (from settings.TAX_RATE)
  6. Create transaction: type='Withdrawal', shares_sold = amount / nav_per_share
  7. Create tax_event: realized_gain, tax_amount, investor_id
  8. Update investor.current_shares -= shares_sold
  9. Send investor statement showing tax withheld
```

**Important:** Withdrawals can be backdated (using historical NAV), useful for accounting corrections.

---

## Monitoring, Alerting & Watchdog System

### Heartbeat File Monitoring
```python
# Daily NAV script writes heartbeat AFTER successful completion:
HEARTBEAT_FILE = "logs/daily_nav_heartbeat.txt"
with open(HEARTBEAT_FILE, 'w') as f:
    f.write(f"Last successful run: {datetime.now()}\n")
    f.write(f"Portfolio Value: ${portfolio_value:,.2f}\n")
    f.write(f"NAV per Share: ${nav_per_share:.4f}\n")
```

### Watchdog Monitor Checks (runs separately ~1 hour after daily NAV)
```
apps/market_monitor/watchdog_monitor.py checks:
  1. Was NAV updated today in database? (SELECT MAX(date) FROM daily_nav)
  2. Does heartbeat file exist and is recent? (age < N hours)
  3. Any errors in recent logs? (scan daily_runner.log for ERROR)
  4. Is database accessible? (can open/query)
  5. External monitoring: ping healthchecks.io URLs
```

### Alert Chain on Failure
```
Failure Detected
  ↓
Send Email Alert (to ALERT_EMAIL, e.g., admin)
  ↓
Ping HEALTHCHECK_WATCHDOG_URL (healthchecks.io webhook)
  ↓
Log issue to watchdog.log with timestamp
  ↓
Retry next check (watchdog runs hourly)
```

**Setup:** Create free healthchecks.io account, get webhook URLs, set in `.env`:
```env
HEALTHCHECK_WATCHDOG_URL=https://hc-ping.com/[unique-id]
HEALTHCHECK_DAILY_NAV_URL=https://hc-ping.com/[unique-id-2]
```

---

## Database Schema Upgrades & Migration

### Upgrade Pattern (v2.0)
```python
# scripts/upgrade_v2.py: Migrating database schema
# 1. Backup existing database (pre_upgrade_timestamp.db)
# 2. Inspect current schema (PRAGMA table_info)
# 3. Add missing columns safely (check if exists first)
# 4. Migrate data to new tables if needed
# 5. Validate migration success
# 6. Restore from backup if errors

def add_column_safe(cursor, table_name, col_name, col_type, default=None):
    """Safely add a column if it doesn't exist"""
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = {row[1] for row in cursor.fetchall()}
    if col_name not in columns:
        cursor.execute(f"ALTER TABLE {table_name} ADD COLUMN {col_name} {col_type}")
```

**When to upgrade:**
- Schema changes in `src/database/schema_v2.py`
- New columns needed for features
- Data normalization

**Never:** Drop tables without backup first!

---

## Frontend Architecture (React + Vite)

### Setup & Development
```cmd
cd apps\investor_portal\frontend\investor_portal
npm install                    # Install dependencies once
npm run dev                    # Start dev server (Vite on port 5173)
npm run build                  # Production build to dist/
```

### Tech Stack
- **React 18** - Component library
- **Vite** - Build tool (fast HMR hot module reload)
- **Tailwind CSS** - Styling
- **Lucide React** - Icons

### Component Structure
```
src/
  App.jsx              # Main component (routing, auth check)
  main.jsx             # Entry point
  index.css            # Global styles
  [components/]        # Feature components (not yet structured)
  [hooks/]             # Custom React hooks (auth, API calls)
  [services/]          # API client functions
  [pages/]             # Page components
```

### API Communication Pattern
```javascript
// Typical API call from frontend
async function login(email, password) {
    const response = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
        credentials: 'include'  // Include JWT cookies
    });
    return response.json();
}
```

### Authentication in Frontend
- JWT access token stored in HTTP-only cookie (secure by default)
- Token automatically sent with requests
- On 401 Unauthorized: refresh token or redirect to login
- User info fetched from `/auth/me` after login

---

## Real-World Code Examples

### Example 1: Add New API Endpoint
```python
# apps/investor_portal/api/routes/investor.py
from fastapi import APIRouter, Depends
from ..dependencies import get_current_user, CurrentUser
from ..models.database import get_investor_tax_history

router = APIRouter()

@router.get("/tax-history")
async def get_tax_history(
    year: int,
    current_user: CurrentUser = Depends(get_current_user)
):
    """Get tax events for a specific year"""
    events = get_investor_tax_history(current_user.investor_id, year)
    return {
        "investor_id": current_user.investor_id,
        "year": year,
        "tax_events": events
    }
```

Include in main.py:
```python
from .routes import investor
app.include_router(investor.router, prefix="/investor", tags=["Investor"])
```

### Example 2: Process a Transaction with Tax
```python
# scripts/investor/process_withdrawal.py (simplified)
def process_withdrawal(investor_id: str, amount: float, date: str):
    conn = sqlite3.connect(DATABASE_PATH)
    cursor = conn.cursor()
    
    # Get holdings
    cursor.execute(
        "SELECT current_shares, net_investment FROM investors WHERE investor_id=?",
        (investor_id,)
    )
    current_shares, net_investment = cursor.fetchone()
    
    # Get NAV for date
    nav_per_share = get_nav_for_date(conn, date)
    current_value = current_shares * nav_per_share
    
    # Calculate gain
    unrealized_gain = current_value - net_investment
    proportion = amount / current_value
    realized_gain = unrealized_gain * proportion
    
    # Calculate tax
    tax_withheld = realized_gain * TAX_RATE
    net_proceeds = amount - tax_withheld
    
    # Record transaction
    cursor.execute("""
        INSERT INTO transactions 
        (date, investor_id, transaction_type, amount, shares_transacted, nav_per_share)
        VALUES (?, ?, 'Withdrawal', ?, ?, ?)
    """, (date, investor_id, amount, amount/nav_per_share, nav_per_share))
    
    # Record tax event
    cursor.execute("""
        INSERT INTO tax_events (investor_id, realized_gain, tax_amount, date)
        VALUES (?, ?, ?, ?)
    """, (investor_id, realized_gain, tax_withheld, date))
    
    # Update investor
    cursor.execute(
        "UPDATE investors SET current_shares = current_shares - ? WHERE investor_id = ?",
        (amount / nav_per_share, investor_id)
    )
    
    conn.commit()
    return {"status": "success", "net_proceeds": net_proceeds, "tax": tax_withheld}
```

### Example 3: Daily NAV Update Flow
```python
# scripts/daily_nav_enhanced.py (simplified)
class DailyNAVUpdater:
    def run(self):
        try:
            # 1. Get portfolio data from Tradier
            portfolio_data = self.fetch_tradier_positions()
            portfolio_value = sum(pos['market_value'] for pos in portfolio_data)
            
            # 2. Get total shares
            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute("SELECT SUM(current_shares) FROM investors")
            total_shares = cursor.fetchone()[0]
            
            # 3. Calculate NAV
            nav_per_share = portfolio_value / total_shares
            
            # 4. Write to daily_nav table
            cursor.execute("""
                INSERT INTO daily_nav (date, portfolio_value, total_shares, nav_per_share)
                VALUES (DATE('now'), ?, ?, ?)
            """, (portfolio_value, total_shares, nav_per_share))
            conn.commit()
            
            # 5. Write heartbeat
            self.write_heartbeat()
            
            # 6. Ping external monitoring
            self.ping_healthcheck("success")
            
            self.log("Daily NAV update complete", "SUCCESS")
            
        except Exception as e:
            self.log(f"Update failed: {e}", "ERROR")
            self.send_alert_email()
            self.ping_healthcheck("failure")
```

### Example 4: Test Database Operations
```python
# tests/test_nav_calculations.py
import pytest

def test_daily_nav_calculation(populated_db):
    """Test NAV calculation accuracy"""
    cursor = populated_db.cursor()
    
    # Insert test NAV
    cursor.execute("""
        INSERT INTO daily_nav (date, portfolio_value, total_shares, nav_per_share)
        VALUES ('2026-02-13', 100000, 1000, 100)
    """)
    populated_db.commit()
    
    # Verify calculation
    cursor.execute("SELECT nav_per_share FROM daily_nav WHERE date='2026-02-13'")
    nav = cursor.fetchone()[0]
    
    assert nav == 100.0, f"Expected 100.0, got {nav}"
    
    # Verify share purchase with new NAV
    cursor.execute("""
        INSERT INTO transactions 
        (date, investor_id, transaction_type, amount, shares_transacted, nav_per_share)
        VALUES ('2026-02-13', '01A', 'Contribution', 5000, 50, 100)
    """)
    
    cursor.execute(
        "SELECT shares_transacted FROM transactions WHERE investor_id='01A'"
    )
    shares = cursor.fetchone()[0]
    assert shares == 50.0, f"Expected 50 shares, got {shares}"
```



---

## Key Integration Points

### Tradier API Integration
- **Module**: `src/api/tradier.py`
- **Config**: TRADIER_API_KEY, TRADIER_ACCOUNT_ID from settings
- **Use Cases**:
  - Fetch current portfolio positions
  - Get transaction history for reconciliation
  - Daily NAV uses real positions from Tradier
- **Error Handling**: Network timeouts wrapped with retry logic

### Email Delivery
- **Module**: `scripts/email_adapter.py`
- **SMTP**: Gmail (smtp.gmail.com:587) or custom SMTP_SERVER from settings
- **Use Cases**: 
  - Daily failures (via daily_nav_enhanced.py)
  - Monthly investor statements
  - Alert notifications
- **Logging**: All emails logged to email_logs table

### Monitoring & Alerts
- **Heartbeat Files**: 
  - `logs/daily_nav_heartbeat.txt` - checked by watchdog_monitor.py
  - Age > N hours triggers alert
- **External Monitor** (optional):
  - HEALTHCHECK_DAILY_NAV_URL in settings (ping after daily run)
- **Audit Log**: All significant operations logged to audit_log table

---

## Common Tasks & How-To

### Add New Investor
1. Insert into `investors` table with investor_id (unique), name, join_date
2. Initial transaction → creates first_shares = initial_contribution / nav_per_share_at_date

### Process Contribution
```
scripts/investor/contribution_processor.py --investor-id <id> --amount <amt>
Calculates: shares_purchased = amount / current_nav_per_share
Updates: investor.current_shares, transactions table
```

### Calculate Daily NAV
```
scripts/daily_nav_enhanced.py  (automated nightly)
Formula: nav_per_share = total_portfolio_value / sum(all_current_shares)
```

### Generate Investor Statement
```
scripts/reporting/monthly_statements.py --month 202601
Includes: holdings, contributions, withdrawals, tax events, unrealized gains
Emails PDF to investor
```

### Validate Data Integrity
```
python run.py validate
# 8-point validation:
#  1. No orphaned transactions
#  2. All investors have valid shares
#  3. Sum(investor_shares) == total_shares from latest daily_nav
#  4. All transactions have matching investor_id
#  5. No negative shares/contributions
#  6. Tax amounts don't exceed realized gains
#  7. No duplicate daily NAV entries
#  8. Audit log has no gaps
```

---

## Development Checklist

When adding features:
- [ ] Update/add to appropriate subdirectory (api, scripts, tests)
- [ ] Use `settings` singleton, never hardcode values
- [ ] Add environment variables to settings.py if needed
- [ ] Log operations (use log() pattern or settings.LOG_TO_FILE)
- [ ] Write tests in tests/ folder (use conftest fixtures)
- [ ] Update audit_log table for data changes
- [ ] Handle Windows vs Unix paths (use pathlib.Path)
- [ ] Add command to run.py if it's a public operation
- [ ] Document in README or QUICK_START.md

---

## Files & Where Things Live

| Category | Location | Key Files |
|----------|----------|-----------|
| **Configuration** | `config/` | `settings.py` (singleton), `.env.<env>` |
| **Database** | `src/database/` | `schema_v2.py` (tables), `models.py` (SQLAlchemy) |
| **API Backend** | `apps/investor_portal/api/` | `main.py` (FastAPI app), `routes/` (endpoints), `models/` (queries) |
| **Frontend** | `apps/investor_portal/frontend/` | React app, port 5173 |
| **Automation** | `scripts/` | `daily_nav_enhanced.py` (main), `nav_helper.py`, subdirs by purpose |
| **Tests** | `tests/` | `conftest.py` (fixtures), `test_*.py` (test modules) |
| **Tradier API** | `src/api/` | `tradier.py` (client) |
| **Docs** | `docs/` | Architecture, guides, cheat sheets |

---

## Troubleshooting

| Problem | Check | Solution |
|---------|-------|----------|
| Import errors when running scripts | Python path | Use `python run.py` or ensure PROJECT_ROOT in sys.path |
| Database locked | Concurrent access | Only one uvicorn process or daily runner at a time |
| Daily NAV fails | Tradier API | Check TRADIER_API_KEY, test with `python run.py api` |
| Email not sending | SMTP config | Verify SMTP_SERVER, SMTP_USER, SMTP_PASSWORD in .env |
| Tests fail with import errors | Test isolation | Use pytest, fixtures from conftest.py handle test_db |
| React frontend won't start | Dependencies | Run `npm install` if node_modules missing, check port 5173 |

---

**Last Updated**: February 2026
