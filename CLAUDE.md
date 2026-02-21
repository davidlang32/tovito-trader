# CLAUDE.md - Tovito Trader Project Context

## Project Overview

Tovito Trader is a **pooled investment fund management platform** launched January 1, 2026. The fund manager day trades for multiple investors using a **share-based NAV system** similar to a mutual fund. Each investor owns shares that appreciate/depreciate based on portfolio performance.

- **Fund Structure:** Pass-through tax entity — gains flow to manager's personal income
- **NAV Calculation:** Daily at 4:05 PM EST based on total portfolio value / total shares
- **Tax Rate:** 37% federal rate on realized gains from withdrawals
- **Brokerage:** Recently migrated from Tradier to **TastyTrade**
- **Current Investors:** 5 active accounts (real names stored in database only — never reference real investor names in code comments, logs, or documentation)

## Tech Stack

- **Language:** Python 3.11+
- **Database:** SQLite (file: `data/tovito.db`, analytics: `analytics/analytics.db`)
- **Brokerage API:** TastyTrade SDK (`tastytrade` Python package) with 2FA support
- **Web Frontend:** React + Vite + Tailwind CSS (investor portal)
- **Backend API:** FastAPI with JWT auth (investor portal API)
- **Desktop Apps:** Streamlit (market monitor, ops dashboard), CustomTkinter (fund manager dashboard)
- **Email:** Gmail SMTP for automated investor communications
- **Automation:** Windows Task Scheduler for daily NAV updates
- **Reports:** ReportLab for PDF generation
- **Testing:** pytest
- **OS:** Windows (all scripts and .bat files target Windows/PowerShell)

## Directory Structure

```
C:\tovito-trader\
├── apps/                    # Application modules
│   ├── fund_manager/        # Fund admin dashboard (CustomTkinter)
│   ├── investor_portal/     # Investor-facing web app
│   │   ├── api/             # FastAPI backend (auth, nav, withdraw, fund_flow, profile, referral)
│   │   └── frontend/        # React + Vite frontend
│   ├── market_monitor/      # Alert system & live dashboard (Streamlit)
│   └── ops_dashboard/       # Operations health dashboard (Streamlit, port 8502)
├── analytics/               # Analytics database and tools
├── config/                  # Environment configs (.env.development, .env.production)
├── data/                    # Production database, backups, exports, reports
│   ├── tovito.db            # PRIMARY DATABASE - handle with extreme care
│   ├── backups/             # Timestamped database backups
│   ├── exports/             # Excel/CSV exports
│   └── reports/             # Generated PDF statements
├── docs/                    # All documentation
│   ├── cheat_sheets/        # Quick reference guides
│   ├── guides/              # Architecture, requirements, admin guides
│   ├── quickstart/          # Setup and installation docs
│   └── reference/           # Detailed reference docs
├── logs/                    # Application logs
├── reports/                 # Generated investor statements (PDF, TXT)
├── scripts/                 # All operational scripts
│   ├── daily_nav_enhanced.py  # Main daily NAV update script
│   ├── daily_runner.py      # Orchestrates daily automation
│   ├── email/               # Email config, testing, service
│   ├── investor/            # Contributions, withdrawals, fund flows, profiles, referrals
│   ├── prospects/           # Prospect management and outreach
│   ├── reporting/           # Monthly reports, Excel exports
│   ├── setup/               # Database migrations, schema checks
│   ├── tax/                 # Quarterly tax payments, year-end reconciliation
│   ├── trading/             # Trade sync, import, query (TastyTrade import working)
│   ├── utilities/           # Backups, reversals, log viewing
│   └── validation/          # Health checks, reconciliation, comprehensive validation
├── src/                     # Core library modules
│   ├── api/                 # Brokerage API clients (tradier.py, tastytrade_client.py, brokerage.py protocol)
│   ├── automation/          # NAV calculator, email service (with email_logs), scheduler
│   ├── database/            # Models (SQLAlchemy) and schema_v2 (raw SQL)
│   ├── etl/                 # Brokerage ETL pipeline (extract → transform → load)
│   │   ├── extract.py       # Pull raw data from brokerage APIs into staging table
│   │   ├── transform.py     # Normalize staging rows into canonical trades format
│   │   └── load.py          # Insert into production trades, update ETL status
│   ├── monitoring/          # Operations health checks data layer (HealthCheckService, get_remediation)
│   ├── reporting/           # Chart generation (matplotlib) for PDF reports
│   ├── streaming/           # Real-time market data streaming
│   └── utils/               # Safe logging (PIIProtector), encryption (FieldEncryptor), formatting
├── tests/                   # pytest test suite
├── .env                     # Environment variables (NEVER commit)
└── CLAUDE.md                # This file
```

## Database Schema (Key Tables)

The primary database is `data/tovito.db` using SQLite. Schema defined in `src/database/schema_v2.py` (raw SQL) and `src/database/models.py` (SQLAlchemy ORM). Schema version: **2.2.0**.

### Core Financial Tables
- **investors** — investor_id (TEXT PK, format: '20260101-01A'), name, email, current_shares, net_investment, status, join_date
- **daily_nav** — date (PK), nav_per_share, total_portfolio_value, total_shares, daily_change_dollars/percent, source
- **transactions** — transaction_id (INT PK), date, investor_id (FK), transaction_type (Initial/Contribution/Withdrawal), amount, share_price, shares_transacted, notes
- **tax_events** — event_id (INT PK), date, investor_id (FK), withdrawal_amount, realized_gain, tax_due, net_proceeds, tax_rate
- **trades** — trade_id (INT PK), date, trade_type, symbol, quantity, price, amount, source (tradier/tastytrade), brokerage_transaction_id, description, category

### Position Tracking
- **holdings_snapshots** — snapshot_id (INT PK), date, source, snapshot_time, total_positions. UNIQUE(date, source). Populated daily by NAV pipeline Step 4.
- **position_snapshots** — position_id (INT PK), snapshot_id (FK), symbol, quantity, market_value, cost_basis, unrealized_pl, instrument_type

### ETL & Staging
- **brokerage_transactions_raw** — raw_id (INT PK), source, brokerage_transaction_id (UNIQUE w/ source), raw_data (JSON), transaction_date, transaction_type, transaction_subtype, symbol, amount, description, etl_status (pending/transformed/skipped/error), etl_trade_id (FK to trades), ingested_at. Populated by ETL extract step.

### Fund Flow Lifecycle
- **fund_flow_requests** — request_id (INT PK), investor_id (FK), flow_type (contribution/withdrawal), requested_amount, request_date, request_method, status (pending/approved/awaiting_funds/matched/processed/rejected/cancelled), matched_trade_id (FK to trades), matched_raw_id (FK to brokerage_transactions_raw), transaction_id (FK to transactions), shares_transacted, nav_per_share, realized_gain, tax_withheld, net_proceeds, notes. Links: `transactions.reference_id = 'ffr-{request_id}'`.

### Investor Profiles & Referrals
- **investor_profiles** — profile_id (INT PK), investor_id (TEXT UNIQUE FK), contact info (name, address, phone, email), personal info (DOB encrypted, marital_status, citizenship), employment info, encrypted PII (ssn_encrypted, tax_id_encrypted, bank_routing_encrypted, bank_account_encrypted), accreditation fields, preferences, profile_completed flag. Sensitive fields use Fernet encryption via `src/utils/encryption.py`.
- **referrals** — referral_id (INT PK), referrer_investor_id (FK), referral_code (UNIQUE, format: 'TOVITO-XXXXXX'), referred_name/email/date, status (pending/contacted/onboarded/expired/declined), converted_investor_id, incentive_type/amount/paid.

### Monitoring & Audit
- **system_logs** — log_id, timestamp, log_type (INFO/WARNING/ERROR/SUCCESS), category, message, details
- **email_logs** — email_id, sent_at, recipient, subject, email_type (MonthlyReport/Alert/General), status (Sent/Failed). Populated by EmailService on every send.
- **daily_reconciliation** — date (PK), tradier_balance, calculated_portfolio_value, difference, total_shares, nav_per_share, status (matched/mismatch), notes. Populated daily by NAV pipeline Step 5.
- **audit_log** — log_id, timestamp, table_name, record_id, action, old_values (JSON), new_values (JSON)

### Removed Tables/Columns (historical)
- `tradier_transactions` table — dropped (was empty legacy table)
- `tradier_transaction_id` column on trades — removed, replaced by `source` + `brokerage_transaction_id`

## Critical Rules — DO NOT VIOLATE

### Data Integrity
1. **Never delete records.** Always use reversing entries for corrections. Maintain GAAP-compliant audit trails.
2. **Never modify `data/tovito.db` without creating a backup first.** Use `scripts/utilities/backup_database.py`.
3. **NAV can never be negative.** Validate before writing to database.
4. **All financial calculations must use consistent rounding** — 4 decimal places for share prices/NAV, 2 decimal places for dollar amounts.
5. **Proportional allocation** for withdrawals (not FIFO). Each withdrawal reduces shares proportionally across the investor's history.
6. **Tax withholding at 37%** on realized gains from withdrawals. Gains = withdrawal amount - cost basis of shares redeemed.

### Privacy & Security (TOP PRIORITY)
7. **Never expose PII in logs, code comments, documentation, or CLI output.** This includes investor names, emails, phone numbers, account numbers, and financial balances. Use masking utilities from `src/utils/safe_logging.py`.
8. **Real values shown ONLY in interactive terminal sessions** where the fund manager is actively viewing data. All automated/logged output must be masked.
9. **Never hardcode credentials, API keys, or passwords.** All secrets go in `.env` (which is in `.gitignore`).
10. **Never reference real investor names** in code comments, test files, commit messages, or documentation. Use pseudonyms (e.g., "Investor A", "Investor B") or generated test data.
11. **Industry-standard security practices required.** This includes: JWT with proper expiration, bcrypt for password hashing, account lockout mechanisms, input validation/sanitization on all user inputs, and parameterized SQL queries (never string concatenation).
12. **Future accreditation goal.** The database and systems will need to support storing sensitive customer PII (SSN, bank accounts, etc.) under regulatory compliance. All new features should be designed with this in mind — encrypt at rest, minimize data exposure, principle of least privilege.
13. **All development and testing must use the Dev/Test environment** with synthetic data. Never test against production data unless absolutely necessary and with a backup in place.

### Communication & Debugging
14. **CLI outputs and log files are the primary communication channel.** When Claude Code makes changes or runs diagnostics, results should be clearly formatted for terminal review. Include meaningful log entries that the fund manager can review in `logs/` directory.
15. **Log files must be parseable and actionable.** Use consistent log levels (INFO, WARNING, ERROR) and include timestamps. Errors should include enough context to diagnose without exposing PII.

## Brokerage Integration: TastyTrade (Primary) + Tradier (Legacy)

The fund migrated from Tradier to TastyTrade in early 2026. Architecture uses a **BrokerageClient Protocol** (`src/api/brokerage.py`) with factory pattern (`get_brokerage_client(provider)`) supporting both providers.

### TastyTrade (active — `src/api/tastytrade_client.py`)
- **Auth:** `TASTYTRADE_USERNAME` and `TASTYTRADE_PASSWORD` env vars with optional 2FA via authenticator app
- **Session persistence:** Serialized to `.tastytrade_session` file, auto-expire after 7 days
- **Known SDK bug:** `has-institutional-assets` Pydantic validation error on `get_customer()` — session is still valid when this occurs
- **Working features:** Account balance, positions, transaction history import, daily NAV updates
- **Trade import:** 8 TastyTrade transactions imported + 4 reversals for pre-Tovito trades

### Tradier (legacy — `src/api/tradier.py`)
- Legacy code kept for reference, original 21 trades imported from Tradier
- **DO NOT** remove Tradier code until full decommission is decided

### Multi-Brokerage Support
- `BROKERAGE_PROVIDER` env var selects active provider (default: 'tradier')
- `BROKERAGE_PROVIDERS` env var for comma-separated list when using combined balance
- `trades` table has `source` column ('tradier' or 'tastytrade') + `brokerage_transaction_id` for deduplication
- Both clients implement `get_raw_transactions()` for ETL pipeline (returns raw API response dicts)
- ETL canonical mapping in `src/etl/transform.py` normalizes both brokerages to consistent trade_type/category/subcategory

## Planned Features (Not Yet Built)

1. **Analytics Package** — Trade analysis, market trend detection, portfolio analysis. Will use `analytics/analytics.db`. Shared resource used by market monitor, investor portal, and trade journal.
2. **Trade Journal** — Log trades with entry/exit analysis. Will leverage analytics package components for post-trade review and pattern recognition.
3. **Full Dev/Test Environment** — See below.
4. **Code Reorganization** — Some legacy scripts may still reference old paths or have duplicated logic from pre-reorganization. Ongoing cleanup needed.
5. **Ops Dashboard in Fund Manager App** — The health check data layer (`src/monitoring/health_checks.py`) is designed UI-agnostic so it can be integrated into the CustomTkinter fund manager dashboard alongside the current Streamlit standalone version.
6. **Investor Portal Frontend Enhancements** — Dashboard NAV chart with time range selector, cash/stock/option breakdown, daily P&L cards, contribution/withdrawal request forms, profile management pages, referral code sharing. React Router for multi-page navigation.

## Recently Completed Features

1. **Brokerage ETL Pipeline** (Phase 1) — Raw brokerage data lands in `brokerage_transactions_raw` staging table, then ETL normalizes into `trades` with canonical mapping for both TastyTrade and Tradier. Integrated as Step 6 of daily NAV pipeline. CLI: `scripts/trading/run_etl.py`.
2. **Fund Flow Lifecycle** (Phase 2) — Unified `fund_flow_requests` table tracks contributions and withdrawals through full lifecycle: pending → approved → awaiting_funds → matched → processed. Links to brokerage ACH via `matched_trade_id`, and to share accounting via `transaction_id` + `reference_id`. CLI: `submit_fund_flow.py`, `match_fund_flow.py`, `process_fund_flow.py`. API: `/fund-flow/*` endpoints.
3. **Investor Profiles & KYC** (Phase 3) — Comprehensive `investor_profiles` table with contact, personal, employment, and accreditation info. Sensitive PII (SSN, bank details) encrypted at rest using Fernet via `src/utils/encryption.py`. Referral tracking via `referrals` table with `TOVITO-XXXXXX` codes. CLI: `manage_profile.py`, `generate_referral_code.py`. API: `/profile/*`, `/referral/*` endpoints.

## Development & Test Environment

Environment configs exist in `config/` (.env.development, .env.production) but full separation is still being built out.

**Principles:**
- **Never develop or test against production data.** Use `scripts/setup/setup_test_database.py` to create synthetic test databases.
- **All new features must be developed in the dev environment first**, validated in test, then promoted to production.
- **Test data must be fully synthetic** — no real investor names, emails, or financial data in test fixtures.
- **Config-driven environment switching** — scripts should read from the appropriate .env file based on context.
- **Goal:** Eventually support `--env dev|test|prod` flag across all scripts.

## Automation & Regression Testing

**Automation Philosophy:** Automate everything that runs more than twice. Manual processes introduce errors and don't scale.

**Current Automation:**
- Daily NAV updates via Windows Task Scheduler (`run_daily.bat` → `scripts/daily_nav_enhanced.py`)
- Watchdog monitoring (`run_watchdog.bat` → `apps/market_monitor/watchdog_monitor.py`)
- Weekly validation (`run_weekly_validation.bat`)
- Monthly report generation and email delivery (`send_monthly_reports.bat`)

**Daily NAV Pipeline (6 steps in `daily_nav_enhanced.py`):**
1. Fetch portfolio balance from brokerage (TastyTrade or Tradier via `BROKERAGE_PROVIDER`)
2. Calculate NAV (total_portfolio_value / total_shares), write to `daily_nav` table
3. Write heartbeat file (`logs/daily_nav_heartbeat.txt`) + ping healthchecks.io
4. Snapshot holdings → `holdings_snapshots` + `position_snapshots` tables (non-fatal)
5. Run daily reconciliation → `daily_reconciliation` table (non-fatal)
6. Sync brokerage trades via ETL pipeline for last 3 days (non-fatal) — extract → transform → load

**Email Logging:** All emails sent via `EmailService` are automatically logged to `email_logs` table (both successes and failures). Added Feb 2026.

**Failure Alerting:** Uses `EmailService` (not raw smtplib) so alerts are logged. Reads `SMTP_USERNAME` (falls back to `SMTP_USER`) and `ADMIN_EMAIL` (falls back to `ALERT_EMAIL`).

**Operations Health Dashboard:** `apps/ops_dashboard/app.py` — Streamlit dashboard (port 8502) showing health score, data freshness, automation status, reconciliation, NAV gaps, system logs, email delivery. Includes actionable remediation guidance for every non-green indicator. Data layer in `src/monitoring/health_checks.py` is UI-agnostic for reuse in CustomTkinter.

**External Monitoring (healthchecks.io):** Two cron-job monitors configured at https://healthchecks.io under the "Tovito Watch Dog" project:
- **Daily NAV** — Pinged by `daily_nav_enhanced.py` at end of each run (success or fail endpoint). Expected daily at ~4:05 PM EST. If no ping arrives within the grace period, healthchecks.io sends an email alert. Env var: `HEALTHCHECK_DAILY_NAV_URL`.
- **Watchdog** — Pinged by `watchdog_monitor.py` only when ALL system checks pass AND no warnings. If the watchdog detects issues (stale NAV, heartbeat missing, log errors), it does NOT ping success. Env var: `HEALTHCHECK_WATCHDOG_URL`.
- **Important:** Both scripts ping at the END of execution. If a script crashes before reaching the ping code, no ping is sent and healthchecks.io will eventually alert.
- **Batch file dependency:** The `.bat` launchers must resolve the correct Python path. When Python is upgraded (e.g., 3.13 → 3.14), update the hardcoded paths in `run_daily.bat` and `run_watchdog.bat` to match. Current: `C:\Python314\python.exe`.

**Regression Testing Requirements:**
- **Run `pytest tests/ -v` before and after every significant code change.**
- All new features must include corresponding test cases in `tests/`.
- Test coverage should include: happy path, edge cases, error handling, and data validation.
- Tests must never touch production data — use test database fixtures from `tests/conftest.py`.
- **CI goal:** Eventually integrate automated test runs on every commit via GitHub Actions.

## Professional Standards

This is a **professional financial tool** managing real investor money. All code must meet industry best practices:

- **Financial accuracy** — rounding errors, off-by-one, and race conditions can cost real money
- **Audit compliance** — every transaction must be traceable and reversible
- **Security first** — assume all data will eventually be regulated; build accordingly
- **Error handling** — fail safely, log clearly, never silently swallow exceptions
- **Documentation** — code should be self-documenting with clear docstrings; complex logic needs inline comments explaining the "why"

## Common Commands

```powershell
# Daily NAV update (runs automatically via Task Scheduler)
python scripts/daily_nav_enhanced.py

# Process a new contribution (legacy — use fund flow workflow instead)
python scripts/investor/process_contribution.py

# Process a withdrawal (legacy — use fund flow workflow instead)
python scripts/investor/process_withdrawal.py

# Fund flow workflow (new — preferred for contributions & withdrawals)
python scripts/investor/submit_fund_flow.py      # Step 1: Submit request
python scripts/investor/match_fund_flow.py        # Step 2: Match to brokerage ACH
python scripts/investor/process_fund_flow.py      # Step 3: Execute share accounting

# Run ETL pipeline (sync brokerage trades)
python scripts/trading/run_etl.py --days 7        # Last 7 days (default)
python scripts/trading/run_etl.py --source tastytrade --dry-run

# Investor profile management
python scripts/investor/manage_profile.py         # View/edit investor profiles
python scripts/investor/generate_referral_code.py # Generate referral codes

# Database migrations (run once per new feature deployment)
python scripts/setup/migrate_add_brokerage_raw.py  # ETL staging table
python scripts/setup/migrate_add_fund_flow.py       # Fund flow requests table
python scripts/setup/migrate_add_profiles.py        # Profiles + referrals tables

# Generate monthly reports
python scripts/reporting/generate_monthly_report.py --month 2 --year 2026 --email

# Run validation
python scripts/validation/validate_comprehensive.py

# Backup database
python scripts/utilities/backup_database.py

# Run tests
pytest tests/ -v

# Start investor portal API
cd apps/investor_portal/api && uvicorn main:app --reload

# Start investor portal frontend
cd apps/investor_portal/frontend/investor_portal && npm run dev

# Start market monitor
cd apps/market_monitor && streamlit run main.py

# Start operations health dashboard
python -m streamlit run apps/ops_dashboard/app.py --server.port 8502

# Run watchdog manually
python apps/market_monitor/watchdog_monitor.py
```

## Environment Variables (from .env)

```
# TastyTrade (active brokerage)
TASTYTRADE_USERNAME=...        # TastyTrade login email
TASTYTRADE_PASSWORD=...        # TastyTrade password

# Brokerage selection
BROKERAGE_PROVIDER=tastytrade  # 'tradier' or 'tastytrade'
BROKERAGE_PROVIDERS=tastytrade # Comma-separated for combined balance

# Tradier (legacy)
TRADIER_API_KEY=...
TRADIER_ACCOUNT_ID=...

# Database
DATABASE_PATH=data/tovito.db

# Email (Gmail SMTP)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=...              # Note: code reads SMTP_USERNAME first, falls back to SMTP_USER
SMTP_PASSWORD=...              # Gmail app password
SMTP_FROM_EMAIL=...
ADMIN_EMAIL=...                # Note: code reads ALERT_EMAIL first, falls back to ADMIN_EMAIL

# External monitoring
HEALTHCHECK_DAILY_NAV_URL=...  # healthchecks.io ping URL (optional)
HEALTHCHECK_WATCHDOG_URL=...   # healthchecks.io ping URL (optional)

# Encryption (for investor profile PII)
ENCRYPTION_KEY=...             # Fernet key — generate via: python src/utils/encryption.py
                               # CRITICAL: back up separately — data unrecoverable without it

# Fund settings
TAX_RATE=0.37
MARKET_CLOSE_TIME=16:00
TIMEZONE=America/New_York
```

**Note:** Never log or display these values. Never commit `.env` to version control.

## Testing

- Tests are in `tests/` using pytest (~306 tests, ~302 passing, 4 pre-existing failures)
- Test database setup: `scripts/setup/setup_test_database.py`
- Test fixtures in `tests/conftest.py` — creates full schema including email_logs, daily_reconciliation, holdings_snapshots, position_snapshots, brokerage_transactions_raw, fund_flow_requests, investor_profiles, referrals
- **Always run tests against a test database, never production**
- Key test files: test_contributions.py, test_withdrawals.py, test_nav_calculations.py, test_database_validation.py, test_chart_generation.py, test_ops_health_checks.py, test_remediation.py, test_brokerage_factory.py, test_combined_brokerage.py, test_tastytrade_client.py, test_etl.py, test_fund_flow.py, test_encryption.py, test_investor_profiles.py

## Coding Conventions

- Use descriptive variable names and docstrings on all functions and classes
- All scripts should handle errors gracefully with try/except — never let exceptions crash silently
- Interactive scripts should have a `--test` or dry-run mode when possible
- Log important operations to both console and system_logs table
- Use `src/utils/safe_logging.py` for any logging that might contain PII
- All new code must have corresponding tests in `tests/`
- Use parameterized queries for all database operations — never use string formatting for SQL
- Follow Python conventions: snake_case for functions/variables, PascalCase for classes
- Keep functions focused — if a function exceeds ~50 lines, consider refactoring
- All file paths should use `pathlib.Path` or `os.path` — never hardcode path separators

## Maintaining This File

**Update CLAUDE.md at the end of any session that:**
1. Adds new modules, directories, or apps
2. Changes database schema (new tables, columns, removed items)
3. Changes automation pipelines or daily workflow steps
4. Fixes infrastructure (env vars, monitoring, alerting)
5. Adds significant new capabilities or test coverage

This file is the primary context for future Claude Code sessions. If it's stale, future work starts from wrong assumptions.
