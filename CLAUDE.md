# CLAUDE.md - Tovito Trader Project Context

## Project Overview

Tovito Trader is a **pooled investment fund management platform** launched January 1, 2026. The fund manager day trades for multiple investors using a **share-based NAV system** similar to a mutual fund. Each investor owns shares that appreciate/depreciate based on portfolio performance.

- **Fund Structure:** Pass-through tax entity — gains flow to manager's personal income
- **NAV Calculation:** Daily at 4:05 PM EST based on total portfolio value / total shares
- **Tax Policy:** 37% federal rate on realized gains, settled quarterly (no withholding at withdrawal)
- **Brokerage:** Recently migrated from Tradier to **TastyTrade**
- **Current Investors:** 5 active accounts (real names stored in database only — never reference real investor names in code comments, logs, or documentation)

## Tech Stack

- **Language:** Python 3.11+
- **Database:** SQLite (file: `data/tovito.db`, analytics: `analytics/analytics.db`)
- **Market Data:** Yahoo Finance via `yfinance` (SPY, QQQ, BTC-USD benchmark caching)
- **Brokerage API:** TastyTrade SDK (`tastytrade` Python package) with 2FA support
- **Web Frontend:** React + Vite + Tailwind CSS + TradingView Lightweight Charts (investor portal)
- **Backend API:** FastAPI with JWT auth (investor portal API)
- **Desktop Apps:** Streamlit (market monitor, ops dashboard), CustomTkinter (fund manager dashboard)
- **Email:** Resend HTTP API (production), SMTP (local development)
- **Automation:** Windows Task Scheduler for daily NAV updates
- **Reports:** ReportLab for PDF generation
- **Discord:** discord.py (bot API for pinned NAV message), webhooks for trade/alert notifications
- **Testing:** pytest
- **OS:** Windows (all scripts and .bat files target Windows/PowerShell)

## Directory Structure

```
C:\tovito-trader\
├── apps/                    # Application modules
│   ├── fund_manager/        # Fund admin dashboard (CustomTkinter)
│   ├── investor_portal/     # Investor-facing web app
│   │   ├── api/             # FastAPI backend (auth, nav, fund_flow, profile, referral, reports, analysis)
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
│   ├── audit/               # System change audit log (CHANGELOG.md)
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
│   ├── discord/             # Discord channel setup content, pinned NAV message bot
│   ├── reporting/           # Monthly reports, Excel exports, Discord monthly summary
│   ├── setup/               # Database migrations, schema checks
│   ├── tax/                 # Quarterly tax payments, year-end reconciliation
│   ├── trading/             # Trade sync, import, query, Discord trade notifier
│   ├── tutorials/           # Tutorial generation pipeline (recorders, annotators, HTML/video)
│   │   ├── admin/           # Admin CLI tutorial scripts (6 tutorials)
│   │   ├── investor/        # Investor browser tutorial scripts (4 tutorials, Playwright)
│   │   ├── launching/       # Application launch tutorial scripts (4 tutorials)
│   │   ├── templates/       # Jinja2 HTML guide template
│   │   └── generate_all.py  # Master generation script
│   ├── utilities/           # Backups, reversals, log viewing
│   └── validation/          # Health checks, reconciliation, comprehensive validation
├── src/                     # Core library modules
│   ├── api/                 # Brokerage API clients (tradier.py, tastytrade_client.py, brokerage.py protocol)
│   ├── automation/          # NAV calculator, email service (with email_logs), scheduler
│   ├── market_data/         # Benchmark data fetching and caching (yfinance → benchmark_prices table)
│   ├── database/            # Models (SQLAlchemy) and schema_v2 (raw SQL)
│   ├── etl/                 # Brokerage ETL pipeline (extract → transform → load)
│   │   ├── extract.py       # Pull raw data from brokerage APIs into staging table
│   │   ├── transform.py     # Normalize staging rows into canonical trades format
│   │   └── load.py          # Insert into production trades, update ETL status
│   ├── monitoring/          # Operations health checks data layer (HealthCheckService, get_remediation)
│   ├── reporting/           # Chart generation (matplotlib) for PDF reports
│   ├── streaming/           # Real-time market data streaming
│   └── utils/               # Safe logging (PIIProtector), encryption (FieldEncryptor), formatting, Discord webhook utilities
├── tests/                   # pytest test suite
├── .env                     # Environment variables (NEVER commit)
└── CLAUDE.md                # This file
```

## Database Schema (Key Tables)

The primary database is `data/tovito.db` using SQLite. Schema defined in `src/database/schema_v2.py` (raw SQL) and `src/database/models.py` (SQLAlchemy ORM). Schema version: **2.3.0**.

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

### Market Data
- **benchmark_prices** — date (TEXT), ticker (TEXT), close_price (REAL), created_at. PK(date, ticker). Cache for SPY, QQQ, BTC-USD daily close prices from Yahoo Finance. Populated by Step 8 of daily NAV pipeline via `src/market_data/benchmarks.py`. Used by `generate_benchmark_chart()` for portal, Discord, and PDF reports.

### Portal Authentication
- **investor_auth** — id (INT PK), investor_id (TEXT UNIQUE FK), password_hash (bcrypt, nullable until setup), email_verified (0/1), verification_token/expires (24h), reset_token/expires (1h), last_login, failed_attempts (lockout at 5), locked_until (15 min), created_at/updated_at. Created by `scripts/setup/migrate_add_auth_table.py`. Manual setup via `scripts/setup/verify_investor.py`.

### Monitoring & Audit
- **system_logs** — log_id, timestamp, log_type (INFO/WARNING/ERROR/SUCCESS), category, message, details
- **email_logs** — email_id, sent_at, recipient, subject, email_type (MonthlyReport/Alert/General), status (Sent/Failed). Populated by EmailService on every send.
- **daily_reconciliation** — date (PK), tradier_balance, calculated_portfolio_value, difference, total_shares, nav_per_share, status (matched/mismatch), notes. Populated daily by NAV pipeline Step 5.
- **audit_log** — log_id, timestamp, table_name, record_id, action, old_values (JSON), new_values (JSON)

### Removed/Archived Tables/Columns (historical)
- `tradier_transactions` table — dropped (was empty legacy table)
- `tradier_transaction_id` column on trades — removed, replaced by `source` + `brokerage_transaction_id`
- `withdrawal_requests` table — archived, no longer written to by any script or API endpoint (replaced by `fund_flow_requests`)

## Critical Rules — DO NOT VIOLATE

### Data Integrity
1. **Never delete records.** Always use reversing entries for corrections. Maintain GAAP-compliant audit trails.
2. **Never modify `data/tovito.db` without creating a backup first.** Use `scripts/utilities/backup_database.py`.
3. **NAV can never be negative.** Validate before writing to database.
4. **All financial calculations must use consistent rounding** — 4 decimal places for share prices/NAV, 2 decimal places for dollar amounts.
5. **Proportional allocation** for withdrawals (not FIFO). Each withdrawal reduces shares proportionally across the investor's history.
6. **Tax settled quarterly at 37%** on realized gains. No tax withheld at withdrawal — full amount disbursed to investor. Realized gains tracked via `tax_events` table (event_type='Realized_Gain') and settled via `scripts/tax/quarterly_tax_payment.py`. "Eligible withdrawal" = current_value - estimated_tax_liability shown to investors.

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
6. **Investor Portal Frontend Enhancements** — Daily P&L cards, contribution/withdrawal request forms, profile management pages, referral code sharing. React Router for multi-page navigation.

## Recently Completed Features

1. **Brokerage ETL Pipeline** (Phase 1) — Raw brokerage data lands in `brokerage_transactions_raw` staging table, then ETL normalizes into `trades` with canonical mapping for both TastyTrade and Tradier. Integrated as Step 6 of daily NAV pipeline. CLI: `scripts/trading/run_etl.py`.
2. **Fund Flow Lifecycle** (Phase 2) — Unified `fund_flow_requests` table tracks contributions and withdrawals through full lifecycle: pending → approved → awaiting_funds → matched → processed. Links to brokerage ACH via `matched_trade_id`, and to share accounting via `transaction_id` + `reference_id`. **This is the ONLY pathway for processing contributions and withdrawals.** CLI: `submit_fund_flow.py`, `match_fund_flow.py`, `process_fund_flow.py`. API: `/fund-flow/*` endpoints.
3. **Investor Profiles & KYC** (Phase 3) — Comprehensive `investor_profiles` table with contact, personal, employment, and accreditation info. Sensitive PII (SSN, bank details) encrypted at rest using Fernet via `src/utils/encryption.py`. Referral tracking via `referrals` table with `TOVITO-XXXXXX` codes. CLI: `manage_profile.py`, `generate_referral_code.py`. API: `/profile/*`, `/referral/*` endpoints.
4. **Discord Trade Notifier** (Phase 4) — Persistent service polling TastyTrade and Tradier every 5 minutes during market hours (9:25 AM - 4:30 PM ET). Posts opening/closing trades to Discord `#tovito-trader-trades` channel via webhook with color-coded embeds (green=open, red=close). In-memory deduplication with warm-up on startup prevents duplicate posts. CLI: `discord_trade_notifier.py --test|--once`. Launcher: `run_trade_notifier.bat`. Scheduled via Task Scheduler weekdays at 9:20 AM.
5. **Discord Integration Suite** (Phase 4b) — Shared webhook utilities (`src/utils/discord.py`), monthly performance summary poster (`discord_monthly_summary.py`), portfolio alert forwarding (DiscordNotifier reads `DISCORD_ALERTS_WEBHOOK_URL` env var), and channel setup content scripts (`scripts/discord/setup_channels.py`) for welcome/about/FAQ/rules. 73 total Discord-related tests.
6. **Discord Pinned NAV Message** (Phase 4c) — Bot script (`scripts/discord/update_nav_message.py`) that connects via discord.py bot API, queries latest NAV data, generates a NAV chart PNG (reuses `src/reporting/charts.py`), builds a rich embed (NAV/share, daily change, inception return, trading days, investor count), and edits an existing pinned message in place (or posts + pins on first run). Integrated as Step 7 of daily NAV pipeline (non-fatal). No message ID storage — bot finds its own pinned message each time. CLI: `update_nav_message.py --test|--days N`. Env vars: `DISCORD_BOT_TOKEN`, `DISCORD_NAV_CHANNEL_ID`. 22 tests.
7. **Transaction Processing Consolidation** (Phase 5) — Removed all legacy contribution/withdrawal scripts (8 files: `process_contribution.py`, `process_withdrawal.py`, `process_withdrawal_enhanced.py`, `request_withdrawal.py`, `submit_withdrawal_request.py`, `view_pending_withdrawals.py`, `check_pending_withdrawals.py`, `migrate_add_withdrawal_requests.py`). Removed `/withdraw/*` API endpoints and route module. Removed legacy DB functions (`calculate_withdrawal_estimate`, `create_withdrawal_request`, `get_pending_withdrawals`, `cancel_withdrawal_request`). Standardized tax policy to quarterly settlement (no withholding at withdrawal — `tax_events` records `event_type='Realized_Gain'` with `tax_due=0`). Added "eligible withdrawal" field (`current_value - max(0, unrealized_gain) * 0.37`) to investor position API and monthly reports. Refactored `close_investor_account.py` to use fund flow pathway. Created `backfill_fund_flow_requests.py` and backfilled all historical transactions with `fund_flow_requests` records. See `docs/audit/CHANGELOG.md` for full details. 408 tests.
8. **Tutorial Video & Screenshot Guide System** (Phase 6) — Automated tutorial generation pipeline producing MP4 videos and self-contained HTML screenshot guides for 14 tutorials across 3 categories: Admin CLI operations (6), Launching applications (4), and Investor portal workflows (4). Core infrastructure in `scripts/tutorials/` with `BaseRecorder` abstract class, `BrowserRecorder` (Playwright), `CLIRecorder` (wexpect + Pillow terminal rendering), `ScreenshotAnnotator` (numbered callouts, arrows, labels), `HtmlGenerator` (Jinja2 with base64-embedded screenshots), and `VideoComposer` (ffmpeg). Frontend Help/Tutorials page embedded in investor portal (`App.jsx` + `tutorialData.js`) with category tabs, tutorial cards, and HTML5 video player. CLI: `python scripts/tutorials/generate_all.py [--category admin|investor|launching] [--tutorial ID] [--skip-video] [--deploy]`. Dependencies: playwright, wexpect, Pillow, Jinja2, bcrypt; ffmpeg (system, via Chocolatey) for video encoding. 444 tests.
9. **Platform Mind Map** — Comprehensive visual mind map of the entire platform architecture showing all 5 applications, 15 database tables, 4 automation pipelines, 5 external integrations, 6 operational workflows, and 7 core library modules — with 25 data flow arrows showing cross-component connections. Generates 3 formats: interactive HTML (zoom, pan, collapsible nodes, search, tooltips), Mermaid Markdown (renderable in GitHub/VS Code), and high-res PNG + SVG (3500x3600px for printing). Single script (`scripts/generate_mindmap.py`) with radial tree layout engine, no new dependencies. CLI: `python scripts/generate_mindmap.py [--format html|mermaid|png] [--open]`. Output: `data/mindmap/`. 499 tests.
10. **NAV vs Benchmarks Chart** (Phase 7) — Reusable comparison chart showing fund performance against SPY, QQQ, and BTC-USD. NAV "mountain" fill in background (left Y-axis) with normalized percentage-change overlay lines (right Y-axis). New `benchmark_prices` SQLite table caches daily close prices from Yahoo Finance via `yfinance` (incremental fetch, no API key). New `src/market_data/benchmarks.py` module handles fetch/cache/normalize. Chart function `generate_benchmark_chart()` in `src/reporting/charts.py` used by: investor portal (via `/nav/benchmark-chart` API endpoint with time range selector), Discord pinned NAV message (replaces NAV-only chart), and monthly PDF reports (new chart page). Daily pipeline Step 8 refreshes cache automatically. Migration: `scripts/setup/migrate_add_benchmarks.py`. 530 tests.
11. **Investor Portal Enhancement Suite** (Phase 8) — Four interrelated features enhancing the investor portal experience. 555 tests.
    - **Gradient Mountain Charts**: Replaced flat `fill_between(alpha=0.08)` with a professional top-to-bottom gradient fill (solid → transparent) using `imshow()` clipped to a polygon `PathPatch`. New `_gradient_fill()` helper in `src/reporting/charts.py` applied to all three chart functions: `generate_nav_chart()`, `generate_investor_value_chart()`, and `generate_benchmark_chart()`. Also added NAV callout annotation with boxed label and arrow on benchmark chart.
    - **Interactive TradingView Charts**: Replaced static PNG benchmark chart with interactive JavaScript chart using TradingView's `lightweight-charts` npm package. New `InteractiveBenchmarkChart` React component with: area series for NAV mountain (left price scale, built-in gradient), line series for fund % and benchmarks (right price scale), crosshair tooltip showing all values on hover, time range selector (30D/90D/6M/1Y/All), responsive via `ResizeObserver`, and legend bar. Backend: added `nav_per_share` to `/nav/benchmark-data` response via new `FundDataItem` model. Static PNG endpoints preserved for Discord/PDF.
    - **On-Demand Report Generation**: New `apps/investor_portal/api/routes/reports.py` with 5 endpoints — `POST /reports/monthly`, `POST /reports/custom`, `POST /reports/ytd` (return 202 Accepted with job_id), `GET /reports/status/{job_id}` (polling), `GET /reports/download/{job_id}` (FileResponse). Uses FastAPI `BackgroundTasks` for async PDF generation. In-memory thread-safe job tracking with `MAX_JOBS_PER_INVESTOR=3` rate limit. Monthly reports reuse existing `generate_monthly_report()` script. Custom/YTD reports generate PDFs with ReportLab. Frontend `ReportsPage` component with type tabs, form fields, polling progress, and download button.
    - **Portfolio Analysis Suite**: New `apps/investor_portal/api/routes/analysis.py` with 3 endpoints — `GET /analysis/holdings` (position snapshots with option aggregation, allocation weights, donut chart data), `GET /analysis/risk-metrics` (Sharpe ratio at 5.25% risk-free, max drawdown with dates, annualized volatility, best/worst days, win rate), `GET /analysis/monthly-performance` (queries `v_monthly_performance` SQL view, calculates return_pct per month). Frontend `PortfolioAnalysis` component with 3 tabs: Holdings (SVG donut chart + sortable table), Risk Metrics (2×4 metric card grid), Monthly Returns (color-coded bar chart). New test files: `tests/test_portfolio_analysis.py` (13 tests), `tests/test_report_generation_api.py` (7 tests).
12. **Investor Account Registration Flow** (Phase 9) — Self-service account setup for new investors. 595 tests.
    - **AccountSetupPage**: New frontend page where investors enter their email to request a setup link. POSTs to `/auth/initiate`. Success shows generic message; "already set up" error links to login. Accessible from LoginPage via "First time? Set up your account" link.
    - **VerifyPage**: New frontend page for `/verify?token=XXX` email links. Password + confirm password form, POSTs to `/auth/verify`, auto-login on success via new `loginWithTokens()` AuthContext function. URL cleaned after verification. Expired/invalid tokens link to AccountSetupPage.
    - **Email enumeration hardening**: `/auth/initiate` endpoint now returns generic success for "not found" and "not active" cases (matching `/auth/forgot-password` pattern). Only "already set up" returns a distinguishable 400 error.
    - **Configurable portal URL**: New `PORTAL_BASE_URL` setting in API config (default: `http://localhost:3000`). Verification and reset email links use this instead of hardcoded localhost. Env var: `PORTAL_BASE_URL`.
    - **Improved verification email**: Added password requirements to the email body so investors know what to prepare before clicking the setup link.
    - **Auth service test suite**: New `tests/test_auth_service.py` (40 tests) covering: password validation rules, bcrypt hashing, initiate/complete verification, login with lockout tracking, password reset flow, and end-to-end registration + reset integration tests.
13. **Investor Portal Production Redesign** (Phase 10) — Dashboard overhaul based on first production review. 595 tests.
    - **Avg Cost Per Share**: New `avg_cost_per_share` field in `get_investor_position()` (database.py) and `PositionResponse` model. Replaces "Portfolio Share" stat card on dashboard. Also shown in expanded Account Summary.
    - **Dashboard layout**: Removed Fund Performance section (fund-level returns inappropriate for individual investor view). Expanded Account Summary from 4 to 6 fields (added Avg Cost/Share, Fund Size, Inception Date). Recent Transactions made full-width with "Show All / Show Recent" toggle (fetches up to 200 transactions).
    - **Benchmark chart error handling**: Added `noData` state and try/catch in `renderChart()` for TradingView Lightweight Charts. Handles empty data gracefully with "Not enough data for this range" message and suggested range button.
    - **SQL view optimization**: Rewrote `v_monthly_performance` from O(n^2) correlated subqueries to O(n) using `ROW_NUMBER()` window functions.
    - **API startup pipeline**: Added `_refresh_benchmark_cache()` (fetches Yahoo Finance data for SPY/QQQ/BTC-USD on startup, essential for Railway where daily pipeline doesn't run) and `_run_data_migrations()` (idempotent one-time data fixes). Changed `_ensure_db_views()` to drop-then-create so schema changes to views take effect on deploy without manual migration.
    - **Test transaction cleanup**: Soft-deleted +100/-100 test transactions (IDs 1, 2) via startup data migration. Queries already filter `is_deleted = 1`.
    - **useApi infinite loop fix**: The React `useApi` hook had `options = {}` default parameter creating a new object on every render, causing infinite re-render loop (~800 API requests/sec). Fixed by using `useRef` for `options` and `getAuthHeaders` so only `endpoint` string changes trigger re-fetches.

## Production Deployment (Launched Feb 2026)

The investor portal is deployed to production at **tovitotrader.com**.

### Architecture
- **Frontend:** Cloudflare Pages — React/Vite SPA at `tovitotrader.com`
- **Backend API:** Railway — FastAPI at `api.tovitotrader.com`
- **Database:** SQLite on Railway persistent volume (`/app/data/tovito.db`)
- **Email:** Resend HTTP API (Railway blocks all SMTP ports 587/465)
- **DNS/TLS:** Cloudflare (DNS proxy + SSL for frontend, CNAME for API)
- **Domain Registrar:** Cloudflare
- **Business Email:** Zoho Mail (`david.lang@tovitotrader.com`, `support@`, `admin@` aliases)

### Deployment Files
- **`railway.toml`** — Railway config (Nixpacks builder, healthcheck at `/health`, 120s timeout)
- **`nixpacks.toml`** — Minimal config letting Nixpacks auto-detect Python from `requirements.txt`
- **`requirements.txt`** — API-only dependencies (renamed from `requirements-api.txt` for Nixpacks)
- **`requirements-full.txt`** — Full desktop+server dependencies (streamlit, customtkinter, etc.)

### Railway Environment Variables
```
# Email (Resend HTTP API — SMTP blocked on Railway)
EMAIL_PROVIDER=resend
RESEND_API_KEY=re_xxxxxxxxx
SMTP_FROM_EMAIL=david.lang@tovitotrader.com
SMTP_FROM_NAME=Tovito Trader

# Database
DATABASE_PATH=/app/data/tovito.db

# Auth
JWT_SECRET_KEY=<generated>

# Portal
PORTAL_BASE_URL=https://tovitotrader.com
TOVITO_ENV=production

# Encryption
ENCRYPTION_KEY=<fernet-key>
```

### Cloudflare DNS Records
- `tovitotrader.com` — Cloudflare Pages (proxied)
- `api.tovitotrader.com` — CNAME to Railway (`*.up.railway.app`, DNS only)
- MX + SPF/DKIM records for Zoho Mail + Resend

### Email Transport (`src/automation/email_service.py`)
The email service supports two transports via `EMAIL_PROVIDER` env var:
- **`smtp`** (default) — Traditional SMTP, used locally with Zoho/Gmail
- **`resend`** — Resend HTTP API (`https://api.resend.com/emails`), used on Railway where SMTP ports are blocked

Local development uses SMTP (no changes to local `.env` needed). Production uses Resend.

### Deployment Commands
```powershell
# Standard deploy: push code to GitHub then deploy backend
git push origin main              # Triggers Cloudflare Pages frontend rebuild automatically
railway up                        # Pushes code to Railway, triggers backend build

# View Railway logs (check startup messages, errors)
railway logs

# SSH into Railway container
railway ssh

# Redeploy with same image (picks up env var changes only)
railway redeploy

# Note: After changing BOTH code AND env vars, run railway redeploy first
# (to pick up env vars), then railway up (to push new code)
```

### API Startup Pipeline (`main.py` lifespan)
On every API startup (local dev or Railway deploy), these run in order:
1. **`_ensure_db_views()`** — Drops and recreates all SQL views from `schema_v2.py`. Ensures view schema changes take effect without manual migration.
2. **`_refresh_benchmark_cache()`** — Fetches latest SPY/QQQ/BTC-USD prices via yfinance into `benchmark_prices` table. Essential for Railway where the daily NAV pipeline doesn't run.
3. **`_run_data_migrations()`** — Idempotent one-time data fixes (e.g., soft-deleting test transactions). Safe to run repeatedly — checks before acting.

All three are non-fatal (wrapped in try/except). If any fail, the API still starts.

### Frontend Build (Cloudflare Pages)
Build settings in Cloudflare Pages dashboard:
- **Build command:** `npm run build`
- **Build output:** `dist`
- **Root directory:** `apps/investor_portal/frontend/investor_portal`
- **Environment variable:** `VITE_API_BASE_URL=https://api.tovitotrader.com`

## Development & Test Environment

### Development Workflow (Local → GitHub → Production)

All development happens **locally on Windows**. The flow is one-directional:

1. **Develop & test locally** — edit code, run `pytest tests/ -v`, test the frontend/API on localhost
2. **Commit & push to GitHub** — `git push origin main`
3. **Deploy to production:**
   - **Frontend** auto-deploys: Cloudflare Pages watches the GitHub repo and rebuilds on push
   - **Backend** requires manual deploy: `railway up` (pushes code and triggers build on Railway)
   - If **only env vars** changed on Railway: `railway redeploy` (no code push needed)
   - If **both** code and env vars changed: `railway redeploy` first, then `railway up`

**Local and production databases are completely independent.** The local `data/tovito.db` and Railway's `/app/data/tovito.db` never sync automatically. Password changes, data migrations, and NAV updates on one do not affect the other.

**When to mention environment:** Only specify "dev" or "prod" when discussing something environment-specific (e.g., "my password doesn't work in dev", "Railway logs show an error"). Otherwise, all work is assumed to be local development.

### Principles
- **Never develop or test against production data.** Use `scripts/setup/setup_test_database.py` to create synthetic test databases.
- **All new features must be developed in the dev environment first**, validated in test, then promoted to production.
- **Test data must be fully synthetic** — no real investor names, emails, or financial data in test fixtures.
- **Config-driven environment switching** — scripts should read from the appropriate .env file based on context.
- **Goal:** Eventually support `--env dev|test|prod` flag across all scripts.

Environment configs exist in `config/` (.env.development, .env.production) but full separation is still being built out.

## Automation & Regression Testing

**Automation Philosophy:** Automate everything that runs more than twice. Manual processes introduce errors and don't scale.

**Current Automation:**
- Daily NAV updates via Windows Task Scheduler (`run_daily.bat` → `scripts/daily_nav_enhanced.py`)
- Watchdog monitoring (`run_watchdog.bat` → `apps/market_monitor/watchdog_monitor.py`)
- Weekly validation (`run_weekly_validation.bat`)
- Monthly report generation and email delivery (`send_monthly_reports.bat`)

**Daily NAV Pipeline (7 steps in `daily_nav_enhanced.py`):**
1. Fetch portfolio balance from brokerage (TastyTrade or Tradier via `BROKERAGE_PROVIDER`)
2. Calculate NAV (total_portfolio_value / total_shares), write to `daily_nav` table
3. Write heartbeat file (`logs/daily_nav_heartbeat.txt`) + ping healthchecks.io
4. Snapshot holdings → `holdings_snapshots` + `position_snapshots` tables (non-fatal)
5. Run daily reconciliation → `daily_reconciliation` table (non-fatal)
6. Sync brokerage trades via ETL pipeline for last 3 days (non-fatal) — extract → transform → load
7. Update Discord pinned NAV message with chart (non-fatal) — connects as bot, edits pinned embed + chart image
8. Refresh benchmark data cache (non-fatal) — fetches latest SPY/QQQ/BTC-USD prices via yfinance into `benchmark_prices` table

**Email Logging:** All emails sent via `EmailService` are automatically logged to `email_logs` table (both successes and failures). Added Feb 2026.

**Failure Alerting:** Uses `EmailService` (not raw smtplib) so alerts are logged. Reads `SMTP_USERNAME` (falls back to `SMTP_USER`) and `ADMIN_EMAIL` (falls back to `ALERT_EMAIL`).

**Operations Health Dashboard:** `apps/ops_dashboard/app.py` — Streamlit dashboard (port 8502) showing health score, data freshness, automation status, reconciliation, NAV gaps, system logs, email delivery. Includes actionable remediation guidance for every non-green indicator. Data layer in `src/monitoring/health_checks.py` is UI-agnostic for reuse in CustomTkinter.

**External Monitoring (healthchecks.io):** Two cron-job monitors configured at https://healthchecks.io under the "Tovito Watch Dog" project:
- **Daily NAV** — Pinged by `daily_nav_enhanced.py` at end of each run (success or fail endpoint). Expected daily at ~4:05 PM EST. If no ping arrives within the grace period, healthchecks.io sends an email alert. Env var: `HEALTHCHECK_DAILY_NAV_URL`.
- **Watchdog** — Pinged by `watchdog_monitor.py` only when ALL system checks pass AND no warnings. If the watchdog detects issues (stale NAV, heartbeat missing, log errors), it does NOT ping success. Env var: `HEALTHCHECK_WATCHDOG_URL`.
- **Important:** Both scripts ping at the END of execution. If a script crashes before reaching the ping code, no ping is sent and healthchecks.io will eventually alert.
- **Batch file dependency:** The `.bat` launchers must resolve the correct Python path. When Python is upgraded (e.g., 3.13 → 3.14), update the hardcoded paths in `run_daily.bat`, `run_watchdog.bat`, and `run_trade_notifier.bat` to match. Current: `C:\Python314\python.exe`.

**Discord Trade Notifier:** `scripts/trading/discord_trade_notifier.py` — Persistent service that polls TastyTrade and Tradier every 5 minutes during market hours (9:25 AM - 4:30 PM ET) for new trades and posts opening/closing trades to the `#tovito-trader-trades` Discord channel via webhook. Launcher: `run_trade_notifier.bat`. Env var: `DISCORD_TRADES_WEBHOOK_URL`.

**Discord Pinned NAV Message:** `scripts/discord/update_nav_message.py` — One-shot bot script (using discord.py) that connects, updates a pinned embed with current NAV + chart image, and disconnects. Runs as Step 7 of the daily NAV pipeline (non-fatal). Finds its own pinned message each run (no message ID storage). First run posts + pins; subsequent runs edit in place. Env vars: `DISCORD_BOT_TOKEN`, `DISCORD_NAV_CHANNEL_ID`. Requires discord.py (`pip install discord.py`) and bot setup in Discord Developer Portal with Send Messages, Manage Messages, Attach Files, Read Message History permissions.

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

# Fund flow workflow (ONLY pathway for contributions & withdrawals)
python scripts/investor/submit_fund_flow.py      # Step 1: Submit request
python scripts/investor/match_fund_flow.py        # Step 2: Match to brokerage ACH
python scripts/investor/process_fund_flow.py      # Step 3: Execute share accounting

# Run ETL pipeline (sync brokerage trades)
python scripts/trading/run_etl.py --days 7        # Last 7 days (default)
python scripts/trading/run_etl.py --source tastytrade --dry-run

# Discord trade notifier (persistent service — polls every 5 min)
python scripts/trading/discord_trade_notifier.py          # Run service
python scripts/trading/discord_trade_notifier.py --test   # Test webhook
python scripts/trading/discord_trade_notifier.py --once   # One-shot post

# Discord monthly performance summary
python scripts/reporting/discord_monthly_summary.py                    # Previous month
python scripts/reporting/discord_monthly_summary.py --month 1 --year 2026  # Specific month

# Discord channel setup (post welcome/about/FAQ/rules content)
python scripts/discord/setup_channels.py --channel welcome  # Post Welcome content
python scripts/discord/setup_channels.py --channel about --webhook <URL>
python scripts/discord/setup_channels.py --list           # Show available channels

# Discord pinned NAV message (bot — updates pinned message with NAV + chart)
python scripts/discord/update_nav_message.py              # Update pinned NAV (runs as Step 7 of daily pipeline)
python scripts/discord/update_nav_message.py --test       # Post test message (not pinned)
python scripts/discord/update_nav_message.py --days 180   # Custom chart range (default: 90)

# Investor profile management
python scripts/investor/manage_profile.py         # View/edit investor profiles
python scripts/investor/generate_referral_code.py # Generate referral codes

# Database migrations (run once per new feature deployment)
python scripts/setup/migrate_add_brokerage_raw.py  # ETL staging table
python scripts/setup/migrate_add_fund_flow.py       # Fund flow requests table
python scripts/setup/migrate_add_profiles.py        # Profiles + referrals tables
python scripts/setup/migrate_add_benchmarks.py      # Benchmark prices cache table
python scripts/setup/backfill_fund_flow_requests.py --dry-run  # Backfill historical FFR records

# Generate monthly reports
python scripts/reporting/generate_monthly_report.py --month 2 --year 2026 --email

# Run validation
python scripts/validation/validate_comprehensive.py

# Backup database
python scripts/utilities/backup_database.py

# Generate tutorials (video + HTML screenshot guides)
python scripts/tutorials/generate_all.py                          # All 14 tutorials
python scripts/tutorials/generate_all.py --category admin         # Admin CLI tutorials only
python scripts/tutorials/generate_all.py --category investor      # Investor portal tutorials only
python scripts/tutorials/generate_all.py --category launching     # Launch tutorials only
python scripts/tutorials/generate_all.py --tutorial admin_fund_flow  # Single tutorial
python scripts/tutorials/generate_all.py --skip-video             # HTML guides only (no ffmpeg needed)
python scripts/tutorials/generate_all.py --deploy                 # Copy outputs to frontend public/

# Generate platform mind map (interactive HTML, Mermaid, PNG/SVG)
python scripts/generate_mindmap.py                    # All formats
python scripts/generate_mindmap.py --format html       # Interactive HTML only
python scripts/generate_mindmap.py --format mermaid    # Mermaid diagram only
python scripts/generate_mindmap.py --format png        # PNG + SVG only
python scripts/generate_mindmap.py --open              # Open HTML in browser after generation

# Run tests
pytest tests/ -v

# Start investor portal API (MUST run from project root for relative imports)
cd C:\tovito-trader && python -m uvicorn apps.investor_portal.api.main:app --reload --port 8000

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

# Email transport selection
EMAIL_PROVIDER=smtp             # 'smtp' (local default) or 'resend' (production/Railway)

# SMTP settings (used when EMAIL_PROVIDER=smtp)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=...              # Note: code reads SMTP_USERNAME first, falls back to SMTP_USER
SMTP_PASSWORD=...              # Gmail app password or Zoho app-specific password

# Resend settings (used when EMAIL_PROVIDER=resend — for Railway where SMTP is blocked)
RESEND_API_KEY=...             # API key from https://resend.com (free tier: 100/day, 3000/mo)

# Email common
SMTP_FROM_EMAIL=...            # Sender address (used by both transports)
SMTP_FROM_NAME=Tovito Trader   # Display name in From header
ADMIN_EMAIL=...                # Note: code reads ALERT_EMAIL first, falls back to ADMIN_EMAIL

# Discord bot (for pinned NAV message)
DISCORD_BOT_TOKEN=...          # Bot token from Discord Developer Portal
DISCORD_NAV_CHANNEL_ID=...    # Channel ID for pinned NAV display

# Discord webhooks
DISCORD_TRADES_WEBHOOK_URL=... # Webhook for #tovito-trader-trades channel
DISCORD_ALERTS_WEBHOOK_URL=... # Webhook for #portfolio-alerts channel (optional)
DISCORD_WELCOME_WEBHOOK_URL=...# Webhook for #welcome channel (one-time setup)
DISCORD_ABOUT_WEBHOOK_URL=...  # Webhook for #about-tovito channel (one-time setup)
DISCORD_FAQ_WEBHOOK_URL=...    # Webhook for #faq channel (one-time setup)
DISCORD_RULES_WEBHOOK_URL=...  # Webhook for #rules-and-disclaimers channel (one-time setup)

# External monitoring
HEALTHCHECK_DAILY_NAV_URL=...  # healthchecks.io ping URL (optional)
HEALTHCHECK_WATCHDOG_URL=...   # healthchecks.io ping URL (optional)

# Encryption (for investor profile PII)
ENCRYPTION_KEY=...             # Fernet key — generate via: python src/utils/encryption.py
                               # CRITICAL: back up separately — data unrecoverable without it

# Investor portal
PORTAL_BASE_URL=http://localhost:3000  # Base URL for email links (verification, password reset)

# Fund settings
TAX_RATE=0.37
MARKET_CLOSE_TIME=16:00
TIMEZONE=America/New_York
```

**Note:** Never log or display these values. Never commit `.env` to version control.

## Testing

- Tests are in `tests/` using pytest (~595 tests, all passing)
- Test database setup: `scripts/setup/setup_test_database.py`
- Test fixtures in `tests/conftest.py` — creates full schema including email_logs, daily_reconciliation, holdings_snapshots, position_snapshots, brokerage_transactions_raw, fund_flow_requests, investor_profiles, referrals
- **Always run tests against a test database, never production**
- Key test files: test_contributions.py, test_withdrawals.py, test_nav_calculations.py, test_database_validation.py, test_chart_generation.py (includes TestBenchmarkChart), test_benchmarks.py (market data caching, normalization), test_ops_health_checks.py, test_remediation.py, test_brokerage_factory.py, test_combined_brokerage.py, test_tastytrade_client.py, test_etl.py, test_fund_flow.py, test_encryption.py, test_investor_profiles.py, test_discord_trade_notifier.py, test_discord_utils.py, test_discord_nav_updater.py, test_api_regression.py (tests fund-flow + benchmark + analysis endpoints), test_tutorials.py (tutorial infrastructure: annotator, HTML generator, video composer, terminal rendering), test_mindmap.py (data model, layout, Mermaid/PNG/SVG/HTML generators), test_portfolio_analysis.py (risk metrics, holdings aggregation, monthly performance, DB integration), test_report_generation_api.py (job tracking, input validation, rate limiting), test_auth_service.py (password validation, bcrypt hashing, verification flow, login/lockout, password reset)

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
- **No emoji characters in server-side code** — Windows cp1252 console encoding cannot handle Unicode emoji (🚀, ✅, ⚠️, etc.), causing `UnicodeEncodeError` crashes. Use ASCII text alternatives like `[OK]`, `[WARN]`, `[ERROR]`, `[START]`. When printing exception messages (`{e}`, `{exc}`), wrap in `try/except UnicodeEncodeError` with `ascii()` fallback since external error messages may contain Unicode.

## Maintaining This File

**Update CLAUDE.md at the end of any session that:**
1. Adds new modules, directories, or apps
2. Changes database schema (new tables, columns, removed items)
3. Changes automation pipelines or daily workflow steps
4. Fixes infrastructure (env vars, monitoring, alerting)
5. Adds significant new capabilities or test coverage

This file is the primary context for future Claude Code sessions. If it's stale, future work starts from wrong assumptions.

## Tutorial Maintenance (CRITICAL)

The tutorial system is a key operational resource for onboarding and training with limited staff. **Tutorials must stay current whenever the workflows they document change.**

**When to regenerate tutorials:**
- Any change to the fund flow workflow (contribution, withdrawal, account closure)
- Changes to the investor portal UI (new pages, redesigned components, renamed fields)
- Changes to CLI scripts that tutorials demonstrate (new flags, renamed scripts, changed output)
- Changes to application launch procedures (new ports, new services, new dependencies)
- Adding new operational workflows that staff need to learn

**How to regenerate:**
```powershell
# Regenerate a single tutorial after changing its workflow
python scripts/tutorials/generate_all.py --tutorial admin_fund_flow

# Regenerate an entire category
python scripts/tutorials/generate_all.py --category admin

# Regenerate everything and deploy to investor portal
python scripts/tutorials/generate_all.py --deploy

# Quick HTML-only regeneration (no ffmpeg needed)
python scripts/tutorials/generate_all.py --skip-video
```

**Adding new tutorials:**
1. Add entry to `TUTORIAL_REGISTRY` in `scripts/tutorials/config.py`
2. Create recorder script in the appropriate category folder (`admin/`, `investor/`, `launching/`)
3. Run `python scripts/tutorials/generate_all.py --tutorial <new_id> --deploy`
4. Metadata file (`tutorialData.js`) auto-updates — no manual frontend changes needed

**Current inventory (14 tutorials):**
| Category | ID | Title |
|---|---|---|
| admin | admin_fund_flow | Processing a Contribution/Withdrawal |
| admin | admin_daily_nav | Running Daily NAV Update |
| admin | admin_close_account | Closing an Investor Account |
| admin | admin_profile_mgmt | Managing Investor Profiles |
| admin | admin_monthly_report | Generating Monthly Reports |
| admin | admin_backup | Backing Up the Database |
| launching | launch_investor_portal | Starting the Investor Portal |
| launching | launch_market_monitor | Starting the Market Monitor |
| launching | launch_ops_dashboard | Starting the Ops Dashboard |
| launching | launch_fund_manager | Starting the Fund Manager |
| getting-started | investor_login | Logging Into Your Account |
| getting-started | investor_dashboard | Your Dashboard Overview |
| getting-started | investor_portfolio | Viewing Your Portfolio |
| getting-started | investor_transactions | Transaction History |

**Output locations:**
- Videos: `data/tutorials/videos/` (MP4, ~25-70 KB each)
- HTML guides: `data/tutorials/guides/` (self-contained, ~50-1700 KB each)
- Screenshots: `data/tutorials/screenshots/` (intermediate PNGs)
- Frontend deployment: `apps/investor_portal/frontend/investor_portal/public/tutorials/`
- Dev database: `data/dev_tovito.db` (synthetic data — never touches production)

## Platform Mind Map (CRITICAL — System Understanding)

The mind map is the fastest way for anyone — new staff, the fund manager, or future Claude sessions — to understand how the entire Tovito Trader platform works. **Three views, three formats each, all generated from a single script.**

### Three Views

| View | File Prefix | Purpose |
|------|-------------|---------|
| **Platform Architecture** | `tovito_platform` | Comprehensive overview: all 5 apps, 15 DB tables, automation, integrations, workflows, libraries + 25 data flow arrows |
| **Database Impact** | `database_impact` | Which processes WRITE to and READ from which tables. Three-column layout: writers ← tables → readers |
| **Business Processes** | `business_process` | End-to-end manual workflows: contribution, withdrawal, daily NAV, monthly reporting, tax settlement, onboarding, account closure |

### How to Generate

```powershell
python scripts/generate_mindmap.py                    # All 3 views, all formats (12 files)
python scripts/generate_mindmap.py --format html       # Interactive HTML only
python scripts/generate_mindmap.py --format mermaid    # Mermaid Markdown only
python scripts/generate_mindmap.py --format png        # PNG + SVG only
python scripts/generate_mindmap.py --open              # Open architecture HTML in browser
```

### Output Files (data/mindmap/)
Each view generates 4 files (12 total):
- `*.html` — Interactive: zoom, pan, collapsible nodes, search, hover tooltips
- `*.md` — Mermaid diagram renderable in GitHub, VS Code, any Mermaid viewer
- `*.png` — High-res (3500×3600px) for printing and embedding
- `*.svg` — Vector format for scaling

### When to Regenerate
**Regenerate the mind map whenever the system architecture changes:**
- New application or service added
- Database schema changes (new tables, columns)
- New automation pipeline or scheduled task
- New external integration (brokerage, webhook, API)
- New business process or workflow change
- Changes to the fund flow lifecycle or tax policy

To regenerate: `python scripts/generate_mindmap.py`

### Why This Matters
With limited staff, this is the single best resource for:
- **Onboarding** — New team members see the entire system in one view
- **Debugging** — Database Impact view shows exactly which processes touch which tables
- **Business continuity** — Business Process view documents every manual workflow end-to-end
- **Future Claude sessions** — Provides immediate architectural context
