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
│   │   ├── api/             # FastAPI backend (auth, nav, fund_flow, profile, referral, reports, analysis, public, admin)
│   │   └── frontend/        # React + Vite frontend
│   ├── market_monitor/      # Alert system & live dashboard (Streamlit)
│   └── ops_dashboard/       # Operations health dashboard (Streamlit, port 8502)
├── analytics/               # Analytics database and tools
├── config/                  # Environment configs (.env.development, .env.production)
├── data/                    # Production database, backups, exports, reports
│   ├── tovito.db            # PRIMARY DATABASE - handle with extreme care
│   ├── backups/             # Timestamped database backups (simple .db + full_* directories)
│   ├── devops/              # DevOps automation data (gitignored)
│   │   ├── dependency_reports/  # JSON dependency check reports
│   │   └── upgrade_snapshots/   # Pre-upgrade requirements file snapshots
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
│   ├── devops/              # DevOps automation (dependency monitor, upgrade automation, synthetic monitor)
│   ├── utilities/           # Backups, reversals, log viewing, GitHub sync, weekly restart
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
│   ├── plans/               # Plan classification system (plan_cash, plan_etf, plan_a)
│   ├── reporting/           # Chart generation (matplotlib) for PDF reports
│   ├── streaming/           # Real-time market data streaming
│   └── utils/               # Safe logging (PIIProtector), encryption (FieldEncryptor), formatting, Discord webhook utilities
├── tests/                   # pytest test suite
├── .env                     # Environment variables (NEVER commit)
└── CLAUDE.md                # This file
```

## Database Schema (Key Tables)

The primary database is `data/tovito.db` using SQLite. Schema defined in `src/database/schema_v2.py` (raw SQL) and `src/database/models.py` (SQLAlchemy ORM). Schema version: **2.4.0**.

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

### Plan Performance Tracking
- **plan_daily_performance** — date (TEXT), plan_id (TEXT: 'plan_cash', 'plan_etf', 'plan_a'), market_value (REAL), cost_basis (REAL), unrealized_pl (REAL), allocation_pct (REAL), position_count (INTEGER). PK(date, plan_id). Populated daily by NAV pipeline Step 4b. Classification logic in `src/plans/classification.py`. Migration: `scripts/setup/migrate_add_plan_performance.py`.

### Prospect Access
- **prospect_access_tokens** — token_id (INT PK AUTOINCREMENT), prospect_id (INT FK→prospects.id), token (TEXT UNIQUE), created_at (TIMESTAMP), expires_at (TIMESTAMP), last_accessed_at (TIMESTAMP), access_count (INT DEFAULT 0), is_revoked (INT DEFAULT 0), created_by (TEXT DEFAULT 'admin'). One active token per prospect. Migration: `scripts/setup/migrate_add_prospect_access.py`. Indexed on token and prospect_id.

### Monitoring & Audit
- **system_logs** — log_id, timestamp, log_type (INFO/WARNING/ERROR/SUCCESS), category, message, details
- **email_logs** — email_id, sent_at, recipient, subject, email_type (MonthlyReport/Alert/General), status (Sent/Failed). Populated by EmailService on every send.
- **daily_reconciliation** — date (PK), tradier_balance, calculated_portfolio_value, difference, total_shares, nav_per_share, status (matched/mismatch), notes. Populated daily by NAV pipeline Step 5.
- **audit_log** — log_id, timestamp, table_name, record_id, action, old_values (JSON), new_values (JSON). Triggers on `investor_profiles` log INSERT/UPDATE with `[ENCRYPTED]` placeholders for PII fields.
- **pii_access_log** — log_id (INT PK AUTOINCREMENT), timestamp (TIMESTAMP), investor_id (TEXT), field_name (TEXT), access_type (TEXT, 'read'/'write'), performed_by (TEXT, default 'system'), ip_address (TEXT), context (TEXT). Indexes on investor_id and timestamp. Logged by `log_pii_access()` in `database.py`. Migration: `scripts/setup/migrate_add_pii_audit.py`. Also created idempotently on API startup.

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
3. ~~**Full Dev/Test Environment**~~ — **DONE** (Phase 17). API auto-loads `config/.env.{TOVITO_ENV}`, dev launcher script, synthetic dev database.
4. **Code Reorganization** — Some legacy scripts may still reference old paths or have duplicated logic from pre-reorganization. Ongoing cleanup needed.
5. **Ops Dashboard in Fund Manager App** — The health check data layer (`src/monitoring/health_checks.py`) is designed UI-agnostic so it can be integrated into the CustomTkinter fund manager dashboard alongside the current Streamlit standalone version.
6. **Investor Portal Frontend Enhancements** — Daily P&L cards, contribution/withdrawal request forms, profile management pages, referral code sharing. React Router for multi-page navigation.
7. **Admin Portal** — Separate local-only React app (`apps/admin_portal/`) for the fund manager to view all investor data, troubleshoot what each investor sees, and manage prospects. Never deployed publicly — runs only on localhost. Option A architecture: completely separate from investor portal with its own frontend and potentially its own API routes.
8. ~~**PII Security Hardening (HIGH PRIORITY)**~~ — **PARTIALLY DONE** (Phase 19 + Phase 20C). Completed: encryption key rotation framework (versioned ciphertext, multi-key support, `rotate_encryption_key.py`), field-level PII access logging (`pii_access_log` table + `log_pii_access()`), `investor_profiles` audit triggers, security headers middleware, startup encryption validation, secure backup of `.env` and encryption keys (Phase 20C full backup with PBKDF2 encryption). Remaining: data retention policies, SOC 2 / regulatory compliance readiness assessment, network-level protections if PII is ever served via API, penetration testing.
9. **Primary Laptop Failover** — Long-term goal to enable OPS-AUTOMATION as a warm standby for OPS-PRIMARY. Would require secure database replication strategy and runbook for failover activation. Not urgent — focus on automation split first.
10. ~~**Portal Dark Theme Redesign**~~ — **DONE** (Phase 18). All authenticated portal pages now have full `dark:` variant coverage.

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
14. **Public Landing Page** (Phase 11) — Marketing landing page at root URL (`/`) to capture prospective investors. 618 tests.
    - **Route restructuring**: Landing page is now the root route `/`. Authenticated dashboard moved to `/dashboard`. Updated all navigation references (App.jsx, Layout.jsx, LoginPage.jsx, TutorialsPage.jsx, ReportsPage.jsx) to redirect to `/dashboard` instead of `/`.
    - **Public API endpoints**: New `apps/investor_portal/api/routes/public.py` router with NO authentication required. `GET /public/teaser-stats` returns public-safe fund metrics (since-inception %, investor count, trading days — no dollar amounts or NAV prices). `POST /public/inquiry` creates prospect with email enumeration prevention (same response for new and duplicate emails).
    - **Database functions**: `get_teaser_stats()` queries `daily_nav` and `investors` for aggregate metrics only. `create_prospect()` inserts into existing `prospects` table with duplicate email handling via `IntegrityError`.
    - **Rate limiting**: In-memory per-IP rate limiter (5 inquiries per IP per hour) on the inquiry endpoint.
    - **Background emails**: New prospect inquiries trigger two background emails — confirmation to prospect and notification to admin with prospect details. Uses existing `EmailService` pattern.
    - **LandingPage.jsx**: Full marketing page with sticky navbar (auth-aware CTAs via `useAuth()`), hero section with animated gradient blobs, live teaser stats bar (fetched via plain `fetch()`, not `useApi`), How It Works cards, Features grid, inquiry form (replaces with success message on submit), and footer with legal disclaimer.
    - **Prospect management**: Leverages existing `prospects` table (created by `scripts/setup/migrate_add_communications_tracking.py`). CLI management via `scripts/prospects/` scripts.
15. **Admin Auth + Production NAV Sync** (Phase 12) — Server-to-server sync from automation laptop to Railway production database. 645 tests.
    - **Admin API key authentication**: New `ADMIN_API_KEY` env var in `config.py`. Replaced `get_admin_user()` stub in `dependencies.py` with working `verify_admin_key()` dependency that validates `X-Admin-Key` header. Uses static API key (not JWT) since sync runs unattended via Task Scheduler.
    - **Admin sync endpoint**: New `apps/investor_portal/api/routes/admin.py` with `POST /admin/sync` accepting batch payload of daily_nav, holdings_snapshot + positions, trades, benchmark_prices, and reconciliation data. Uses `INSERT OR REPLACE` for idempotency. Logs sync events to `system_logs` table. Registered in `main.py` with `/admin` prefix.
    - **Upsert database functions**: Five new functions in `database.py` — `upsert_daily_nav()`, `upsert_holdings_snapshot()`, `upsert_trades()` (dedup by source + brokerage_transaction_id), `upsert_benchmark_prices()` (INSERT OR IGNORE), `upsert_reconciliation()`.
    - **Sync client script**: New `scripts/sync_to_production.py` — collects today's pipeline data from local SQLite, POSTs to production API. Supports `--date`, `--days`, `--dry-run` flags. Reads `PRODUCTION_API_URL` and `ADMIN_API_KEY` from `.env`.
    - **Daily pipeline Step 9**: Added production sync as non-fatal Step 9 in `daily_nav_enhanced.py`. Runs after benchmark refresh. Skips if `PRODUCTION_API_URL` or `ADMIN_API_KEY` not configured.
    - **SEO blocking**: Added `robots.txt` (Disallow: /) and `<meta name="robots" content="noindex, nofollow">` to prevent search engine crawling during early access period.
16. **Plan-Based Position Categorization** (Phase 13) — Every position classified into one of three investment plans with per-plan performance tracking. 692 tests.
    - **Plan classification system**: New `src/plans/classification.py` module with `classify_position()` and `classify_position_by_underlying()` functions. Three plans: Plan CASH (SGOV, BIL, SHV, SCHO, VMFXX, VUSXX + Cash/money-market instrument types), Plan ETF (SPY, QQQ, SPXL, TQQQ, IWM, DIA, VOO as equity shares only), Plan A (everything else — options, individual stocks, leveraged options). Key rule: options on ETF symbols (e.g., SPY calls) go to Plan A, not Plan ETF.
    - **Plan performance table**: New `plan_daily_performance` table with `(date, plan_id)` composite PK. Stores market_value, cost_basis, unrealized_pl, allocation_pct, position_count per plan per day. Migration: `scripts/setup/migrate_add_plan_performance.py` with `--backfill` option to populate from historical position_snapshots.
    - **Daily pipeline Step 4b**: Added `compute_plan_performance()` method to `daily_nav_enhanced.py`. Reads today's position_snapshots, classifies each position, aggregates by plan, writes to plan_daily_performance. Runs between Step 4 (holdings snapshot) and Step 5 (reconciliation). Non-fatal.
    - **Plan analysis API endpoints**: Two new endpoints in `apps/investor_portal/api/routes/analysis.py` — `GET /analysis/plan-allocation` (latest per-plan breakdown with metadata) and `GET /analysis/plan-performance` (time series with days parameter, 7-730). Both authenticated via JWT.
    - **Sync integration**: Added `PlanPerformanceSync` model and `plan_performance` field to admin sync payload. New `collect_plan_performance()` in `sync_to_production.py`. New `upsert_plan_performance()` in `database.py`. Plan data synced to production in Step 9.
    - **Helper functions**: `compute_plan_performance()` aggregates position lists into per-plan dicts. `get_plan_metadata()` returns display info (name, description, strategy, risk_level). `PLAN_METADATA` dict and `PLAN_IDS` tuple for iteration.
17. **Gated Prospect Access** (Phase 14) — Approved prospects receive token-based links to view fund performance + plan breakdown without creating an investor account. 741 tests.
    - **Prospect access tokens table**: New `prospect_access_tokens` table with token_id, prospect_id (FK), token (UNIQUE), expires_at, last_accessed_at, access_count, is_revoked, created_by. Migration: `scripts/setup/migrate_add_prospect_access.py`. One active token per prospect; creating new token auto-revokes existing ones.
    - **Database functions**: Five new functions in `database.py` -- `create_prospect_access_token()` (revokes existing, inserts new), `validate_prospect_token()` (checks expiry/revocation, updates access tracking), `revoke_prospect_token()` (sets is_revoked=1), `get_prospect_access_list()` (LEFT JOIN prospects with non-revoked tokens), `get_prospect_performance_data()` (percentage-only fund data -- NO dollar amounts, NO nav_per_share).
    - **Admin prospect management endpoints**: Three new endpoints in `admin.py` -- `POST /admin/prospect/{id}/grant-access` (generates `secrets.token_urlsafe(36)` token, 30-day default expiry, returns prospect URL), `DELETE /admin/prospect/{id}/revoke-access`, `GET /admin/prospects` (lists all prospects with token status). All protected by X-Admin-Key.
    - **Prospect performance endpoint**: New `GET /public/prospect-performance?token=XXX&days=90` in `public.py`. Token-authenticated (no JWT). Returns percentage-only data: since_inception_pct, monthly_returns, plan_allocation, benchmark_comparison (fund vs SPY/QQQ). Invalid/expired/revoked tokens return `{valid: false}`.
    - **CLI script**: New `scripts/prospects/grant_prospect_access.py` with interactive mode (shows prospect table, prompts for ID) and non-interactive mode (`--prospect-id`, `--days` flags).
    - **FundPreviewPage.jsx**: New React page at `/fund-preview?token=XXX`. Dark theme (bg-slate-950, emerald accents) matching landing page. Sections: hero with since-inception badge, stats bar, monthly returns table (color-coded), plan allocation cards (3 plans with allocation bars), benchmark comparison cards (fund vs SPY/QQQ), CTA section, footer with legal disclaimer. Error states for invalid/expired tokens and network errors.
    - **Security design**: Tokens are cryptographically random (`secrets.token_urlsafe(36)`). Access tracking (count + last_accessed_at) on every validation. Database enforces token uniqueness. No dollar amounts or NAV prices ever exposed to prospects.
18. **Landing Page Content + Prospect Email Verification** (Phase 15) — Content corrections, feature card update, and email verification for prospect inquiries. 753 tests.
    - **Hero text fix**: "Personalized for You" changed to "Built for Growth" (fund is pooled, not personalized). "Day trading" changed to "swing trading and momentum-based strategies" (accurate to fund strategy).
    - **Feature card swap**: Replaced "Tax-Efficient Structure" (Shield icon) with "2027 USIC Competitor" (Trophy icon) — fund manager preparing to compete in the 2027 United States Investing Championship.
    - **Prospect email verification**: Full email verification flow before admin notification. Prospect submits inquiry form -> verification email sent with `secrets.token_urlsafe(32)` token (24h expiry) -> prospect clicks link -> `GET /public/verify-prospect?token=XXX` marks `email_verified=1` -> confirmation email to prospect + admin notification sent only after verification. Unverified duplicate submissions resend the verification email.
    - **Database changes**: Added `email_verified` (INTEGER DEFAULT 0), `verification_token` (TEXT), `verification_token_expires` (TIMESTAMP) columns to `prospects` table. Migration: `scripts/setup/migrate_add_prospect_verification.py`. Also added as idempotent startup migration in `main.py`.
    - **New database functions**: `store_prospect_verification_token()`, `verify_prospect_email()`. Modified `create_prospect()` to return `email_verified` status and `prospect_id` for duplicates.
    - **VerifyProspectPage.jsx**: New React page at `/verify-prospect?token=XXX`. Dark emerald theme. States: loading, success (green checkmark), error (invalid/expired link), network error. Links back to landing page.
    - **Inquiry form UX**: Success message changed from "Thank You!" to "Check Your Email" with Mail icon and verification instructions.
19. **Settings & UI Polish + Chart Gap Fix** (Phase 16) — Settings page cleanup, dark mode infrastructure, sidebar gradient, and portfolio chart interpolation. 759 tests.
    - **Statement Delivery removal**: Removed the "Both" (electronic + physical mail) toggle from Settings page. Electronic-only delivery — no mail option offered. Fund is a pass-through entity with no regulatory requirement for mailed statements.
    - **Dark mode toggle**: New `ThemeContext.jsx` with `ThemeProvider` and `useTheme()` hook. Persists to `localStorage`. Tailwind `darkMode: 'class'` strategy enabled. New `AppearanceSection` in Settings page with Light/Dark toggle buttons. Theme wrapped around entire app in `App.jsx`.
    - **Sidebar emerald gradient**: Changed sidebar background from `bg-slate-800` to `bg-gradient-to-b from-slate-900 via-emerald-900 to-slate-900` matching the landing page gradient. Updated nav item active state to `bg-emerald-500/15 text-emerald-400`, hover states to `bg-emerald-500/10`. Logo shadow updated to `shadow-emerald-500/30`. Border colors updated to `border-emerald-800/50`.
    - **Portfolio chart gap interpolation**: New `_interpolate_trading_day_gaps()` helper in `database.py`. Detects gaps >3 calendar days in `daily_nav` data and inserts linearly interpolated weekday points (Mon-Fri). Fixes the Feb 2-18 gap where the chart showed a misleading straight line. Interpolation covers both portfolio_value and nav_per_share. Applied as post-processing in `get_investor_value_history()`.
    - **New tests**: 6 tests for `_interpolate_trading_day_gaps()` covering no gaps, weekend gaps, multi-day gaps, linear value progression, edge cases, and NAV direction consistency.
20. **Dev/Test Environment Separation** (Phase 17) — Complete environment isolation so local development never touches production data. 759 tests.
    - **Environment-specific config loading**: Modified `apps/investor_portal/api/config.py` to read `TOVITO_ENV` (default: `development`), load `config/.env.{TOVITO_ENV}` first, fall back to root `.env`. On Railway, `TOVITO_ENV=production` and settings come from OS env vars (no config file).
    - **Development defaults**: Rewrote `config/.env.development` with complete dev defaults — `DATABASE_PATH=data/dev_tovito.db`, dev-only JWT secret, email disabled, all Discord/monitoring/sync integrations disabled.
    - **Rich synthetic dev database**: Enhanced `scripts/setup/setup_test_database.py` with all missing tables (prospects, prospect_communications, prospect_access_tokens, benchmark_prices, plan_daily_performance, audit_log), ~57 trading days of NAV (Jan 1 to today), benchmark prices (SPY/QQQ/BTC-USD), plan performance data, sample trades, investor profiles. Added `--reset-prospects` flag to clear prospect data without rebuilding everything.
    - **Startup environment banner**: API now prints clear banner on startup showing environment name, database path, DB existence, and warns loudly if production database detected in non-production mode.
    - **Dev launcher script**: New `scripts/setup/start_dev.py` — one command that sets `TOVITO_ENV=development`, auto-creates dev DB if missing, starts uvicorn with reload. Supports `--port`, `--reset-db`, `--reset-prospects` flags.
    - **Safety design**: Default `DATABASE_PATH` changed from `data/tovito.db` to `data/dev_tovito.db` so forgetting to set `TOVITO_ENV` never touches production.
21. **Portal Dark Theme Redesign** (Phase 18) — Full dark mode coverage for all 8 authenticated portal pages. 759 tests.
    - **Layout.jsx**: Dark variants for page background (`dark:bg-slate-950`), mobile header, footer, and bottom nav bar (`dark:bg-slate-900 dark:border-slate-700`).
    - **SettingsPage.jsx**: All section containers, form inputs, toggle buttons, status badges, field rows, quick links, and save messages.
    - **ReportsPage.jsx**: Header, tab buttons, card containers, form labels/inputs, and status message boxes.
    - **TutorialsPage.jsx**: Detail/list headers, tutorial cards, category badges, thumbnail placeholders.
    - **DashboardPage.jsx**: StatCard, PortfolioValueChart, PerformancePills, RecentActivity, AccountSummary. **Recharts theming**: axis tick/grid colors via `darkMode` ternary (`useTheme()` hook), tooltip backgrounds.
    - **PerformancePage.jsx**: BenchmarkChart legend, ComparisonCards, MonthlyHeatmap, RollingReturnsChart, RiskMetricCards. **TradingView chart**: theme-aware grid/text colors, `darkMode` added to `useEffect` dependency array to rebuild chart on theme toggle. **Recharts (RollingReturns)**: axis color ternaries. `RISK_METRIC_CONFIGS` icon colors updated.
    - **PortfolioPage.jsx**: OverviewCard, AllocationDonut, AllocationByType, HoldingsTable, ConcentrationAnalysis. **SVG text theming**: `renderActiveShape` moved into component scope via `useCallback` to access `darkMode` for `fill` colors. **Donut Cell stroke**: `stroke={darkMode ? '#1e293b' : 'white'}`. `getDiversificationGrade` returns dark-variant class strings.
    - **ActivityPage.jsx**: NewRequestForm, SummaryCards, CashFlowChart, FundFlowCard/StatusBadge, TransactionHistory, NavTimeline. **STATUS_CONFIG**: dark variants appended to color/bg/border class strings. **Recharts (BarChart)**: axis/grid/ReferenceLine colors via `darkMode` ternary. **TYPE_ICONS**: bg values include dark variants.
    - **SectionHeader pattern**: Each page's local `SectionHeader` updated with `dark:text-slate-100` (title) and `dark:text-slate-400` (subtitle). Call sites pass dark variants in `iconBg`/`iconColor` props.
    - **Standard palette**: Consistent mapping across all pages — `bg-white` → `dark:bg-slate-800/50`, `bg-gray-50` → `dark:bg-slate-950`, `border-gray-100` → `dark:border-slate-700/50`, `text-gray-900` → `dark:text-slate-100`, `bg-{color}-50` → `dark:bg-{color}-900/30`.
22. **PII Security Hardening** (Phase 19) — Production-grade encryption key management, PII access audit logging, and API security hardening. 806 tests.
    - **Versioned ciphertext + multi-key support**: Upgraded `FieldEncryptor` in `src/utils/encryption.py`. New encryptions produce `v1:<ciphertext>` prefix. Decrypt tries current key first, then each legacy key in order (supports seamless key rotation without downtime). Unversioned `gAAAAA...` ciphertext treated as v0 for backward compatibility. New `ENCRYPTION_LEGACY_KEYS` env var (comma-separated list of old Fernet keys). `is_encrypted()` recognizes both `v1:gAAAAA` and bare `gAAAAA` formats. `reset_encryptor()` function for re-initialization after env changes.
    - **PII access audit log**: New `pii_access_log` table tracking who accessed/modified encrypted fields — investor_id, field_name, access_type ('read'/'write'), performed_by, ip_address, context. Indexes on investor_id and timestamp. New `log_pii_access()` function in `database.py` (non-fatal — wrapped in try/except). Migration: `scripts/setup/migrate_add_pii_audit.py`. Schema version bumped to 2.4.0.
    - **Audit triggers on investor_profiles**: INSERT and UPDATE triggers write to `audit_log` table. Encrypted field values (SSN, bank details, tax ID, DOB) logged as `[ENCRYPTED]` placeholder — never plaintext or ciphertext in audit trail.
    - **Startup encryption validation**: New `_validate_encryption()` in API startup pipeline. Tests round-trip encrypt/decrypt on boot, prints `[OK] Encryption: verified` or `[WARN] Encryption: not configured` to startup banner. Reports legacy key count if present. Non-fatal.
    - **Security headers middleware**: Six headers added to all API responses — `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `X-XSS-Protection: 1; mode=block`, `Referrer-Policy: strict-origin-when-cross-origin`, `Permissions-Policy: camera=(), microphone=(), geolocation=()`, `Cache-Control: no-store`. Skips HSTS (Cloudflare handles TLS) and CSP (API-only, no HTML).
    - **Key rotation script**: New `scripts/setup/rotate_encryption_key.py` — decrypts all `investor_profiles` PII fields with current key, re-encrypts with new key (v1: format), validates round-trip for every field, commits in single transaction. Supports `--dry-run`, `--new-key KEY`, `--skip-backup`. Creates database backup before starting. Prints post-rotation instructions (update ENCRYPTION_KEY, add old key to ENCRYPTION_LEGACY_KEYS).
    - **Test suite**: New `tests/test_pii_security.py` (47 tests) covering: versioned ciphertext format, backward compatibility with unversioned tokens, multi-key decryption, key rotation end-to-end, `is_encrypted()` for both formats, PII access log writes, audit triggers, security headers on all responses, startup validation, `reset_encryptor()`.
23. **DevOps Automation Pipeline** (Phase 20) — Four-part automation suite reducing manual maintenance overhead and catching issues proactively. 878 tests.
    - **Phase 20C — Backup & Restore Enhancement**: Enhanced `scripts/utilities/backup_database.py` with `create_full_backup(passphrase)` (backs up `tovito.db` + `.env` + `.tastytrade_session` into `data/backups/full_YYYY-MM-DD_HHMMSS/` with `manifest.json` containing SHA256 checksums; sensitive files encrypted with Fernet using PBKDF2-derived key from user passphrase), `verify_backup(path)` (validates checksums + `PRAGMA integrity_check`), `rotate_backups(keep_count, keep_days)` (removes old backups, always preserves oldest baseline). New `scripts/utilities/restore_database.py` with `restore_database()` (creates safety backup first), `restore_env()` (decrypts `.env` with masked diff), `list_available_backups()`. Health check integration: `get_backup_status()` warns if no backup in >7 days.
    - **Phase 20A — Dependency Monitor**: New `scripts/devops/dependency_monitor.py` with `DependencyMonitor` class — runs `pip list --outdated --format=json` cross-referenced with requirements files, `npm outdated --json` in frontend dir, classifies upgrades as major/minor/patch via `packaging.version`. Generates JSON reports to `data/devops/dependency_reports/`, sends Discord (gold embed) + email notifications when outdated packages found. CLI: `--no-notify`, `--pip-only`, `--npm-only`, `--json`. New `run_dependency_check.bat` for Task Scheduler (weekly Monday 9 AM). Health check: `get_dependency_status()` flags major updates.
    - **Phase 20B — Upgrade Automation**: New `scripts/devops/upgrade_packages.py` with `PackageUpgrader` class — safety guard refuses to run if `TOVITO_ENV=production`. Pre-upgrade backup (DB + requirements snapshot to `data/devops/upgrade_snapshots/`), pip/npm upgrade with major/minor separation, `pytest` test gate, requirements file update, rollback from snapshot. Never auto-deploys — prints promotion commands on success. CLI: `--all-minor`, `--package NAME`, `--npm`, `--dry-run`, `--rollback SNAPSHOT`, `--list-snapshots`.
    - **Phase 20D — Synthetic Monitoring**: New `scripts/devops/synthetic_monitor.py` with `SyntheticMonitor` class — 7 HTTP-based production checks: health endpoint, public teaser stats, login flow (synthetic account), NAV freshness (within 3 calendar days), authenticated endpoints, frontend accessibility, admin endpoint. Sends Discord (critical red) + email on failures only. Pings `HEALTHCHECK_SYNTHETIC_URL`. New `run_synthetic_monitor.bat` for Task Scheduler (every 4 hours on OPS-AUTOMATION). Health check: `get_synthetic_monitor_status()`.
    - **Health check integration**: Three new methods in `src/monitoring/health_checks.py` — `get_backup_status()`, `get_dependency_status()`, `get_synthetic_monitor_status()` with remediation guidance for each.
    - **Test suites**: `test_backup_restore.py` (20 tests), `test_dependency_monitor.py` (15 tests), `test_upgrade_packages.py` (12 tests), `test_synthetic_monitor.py` (22 tests) — 69 new tests total. One-time manual setup required for synthetic monitoring: create synthetic investor account, add env vars, create healthchecks.io monitor.
24. **Auto-Grant Prospect Access + Enhanced Emails** (Phase 21) — Automated prospect onboarding flow that delivers value immediately after email verification. 885 tests.
    - **Auto-grant fund preview token**: On email verification, system automatically creates a `prospect_access_tokens` entry (`secrets.token_urlsafe(36)`, 30-day expiry, `created_by='auto_verification'`) and constructs the fund preview URL. Non-fatal: if token creation fails, emails still send without the preview link (degraded mode).
    - **Enhanced prospect confirmation email**: Replaced generic "thanks, we'll be in touch" with warm, trust-building message. Includes: company overview (pooled fund, swing/momentum strategies), auto-generated fund preview link with description of what they'll see (inception returns, monthly performance, plan allocation, benchmark comparisons), link expiry notice, "trust is earned, not given" messaging, and 24-48 hour follow-up commitment. Subject changed from "Email Verified" to "Welcome Aboard".
    - **Enhanced admin notification email**: Replaced bare-bones notification with actionable format. Includes: "New Verified Prospect Inquiry" header, prospect details, auto-generated preview URL (or "auto-grant failed" note), next-steps checklist, and CLI commands with `--prospect-id`.
    - **Test suite**: 8 new/modified tests in `test_landing_page_api.py` — auto-grant token creation, graceful failure degradation, preview URL and prospect_id passing, and 3 email content validation tests.

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

# Admin API (for production sync)
ADMIN_API_KEY=<generated-hex-key>
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

### Environment Switching (TOVITO_ENV)

The API uses `TOVITO_ENV` environment variable to select which config to load:

| Environment | TOVITO_ENV | Config File | Database | How Set |
|---|---|---|---|---|
| **Development** (default) | `development` | `config/.env.development` | `data/dev_tovito.db` | Default when unset |
| **Production** (Railway) | `production` | OS env vars (no file) | `/app/data/tovito.db` | Railway env var |
| **Production** (local) | `production` | root `.env` | `data/tovito.db` | `set TOVITO_ENV=production` |

**How it works:** `apps/investor_portal/api/config.py` calls `_load_env_file()` at module load time, which reads `TOVITO_ENV` (default: `development`), looks for `config/.env.{TOVITO_ENV}`, and falls back to root `.env` if the env-specific file doesn't exist. On Railway, there's no config folder — settings come from OS-level env vars.

**Safety net:** The API startup banner warns if a non-dev database (`data/tovito.db`) is detected in non-production mode.

### Quick Start — Local Development

```powershell
# One-command dev launcher (creates dev DB if needed, starts API):
python scripts/setup/start_dev.py

# Or manually:
python scripts/setup/setup_test_database.py --env dev     # Create dev DB
python -m uvicorn apps.investor_portal.api.main:app --reload --port 8000

# Frontend (separate terminal):
cd apps/investor_portal/frontend/investor_portal && npm run dev
```

**Dev launcher options:**
```powershell
python scripts/setup/start_dev.py                    # Start API (default port 8000)
python scripts/setup/start_dev.py --port 8001        # Custom port
python scripts/setup/start_dev.py --reset-db          # Rebuild dev database from scratch
python scripts/setup/start_dev.py --reset-prospects   # Clear prospect data only
```

**Dev test accounts:**
| Email | Password | Role |
|---|---|---|
| `alpha@test.com` | `TestPass123!` | Active investor (100 shares) |
| `bravo@test.com` | `TestPass123!` | Active investor (50 shares) |
| `charlie@test.com` | `TestPass123!` | Active investor (75 shares) |
| `delta@test.com` | `TestPass123!` | Active investor (25 shares) |

### Switching to Production (Local)

When you need to run the daily NAV pipeline or production scripts locally:

```powershell
# Set production mode for the current terminal session:
set TOVITO_ENV=production

# Now uvicorn/scripts will load root .env → data/tovito.db
python -m uvicorn apps.investor_portal.api.main:app --reload --port 8000

# Reset back to development:
set TOVITO_ENV=development
```

**Important:** Production automation scripts (`daily_nav_enhanced.py`, etc.) load root `.env` directly and do NOT use the `TOVITO_ENV` switching mechanism. This is intentional — they always target production data.

### Principles
- **Never develop or test against production data.** Use `scripts/setup/setup_test_database.py` to create synthetic test databases.
- **All new features must be developed in the dev environment first**, validated in test, then promoted to production.
- **Test data must be fully synthetic** — no real investor names, emails, or financial data in test fixtures.
- **Config-driven environment switching** — the API loads from the appropriate .env file based on `TOVITO_ENV`.
- **Dev database schema matches production** — `setup_test_database.py` creates all tables including prospects, benchmark_prices, plan_daily_performance, prospect_access_tokens, and pii_access_log.

## Automation & Regression Testing

**Automation Philosophy:** Automate everything that runs more than twice. Manual processes introduce errors and don't scale.

**Automation Split — Primary vs Management Laptop:**

The guiding principle: **automations that write to `data/tovito.db` run on the primary laptop; everything else runs on the management laptop.** Weekly validation and monthly reports are run manually on the primary laptop as needed.

*Primary Laptop — **OPS-PRIMARY** (writes to local database):*
- Daily NAV updates via Task Scheduler (`run_daily.bat` → `scripts/daily_nav_enhanced.py`) — writes to 9 tables
- Watchdog monitoring via Task Scheduler (`run_watchdog.bat` → `apps/market_monitor/watchdog_monitor.py`) — reads local DB to verify pipeline ran

*Management Laptop — **OPS-AUTOMATION** (no local database dependency):*
- Discord trade notifier via Task Scheduler (`run_trade_notifier.bat` → `scripts/trading/discord_trade_notifier.py`) — polls brokerage APIs directly, posts to Discord
- Synthetic monitoring via Task Scheduler (`run_synthetic_monitor.bat` → `scripts/devops/synthetic_monitor.py`) — every 4 hours, validates production from user's perspective
- GitHub code sync via Task Scheduler (`scripts/utilities/sync_from_github.bat` — every 30 min)
- Weekly maintenance restart via Task Scheduler (`scripts/utilities/weekly_restart.bat` — Sunday 3 AM)

*Primary Laptop — scheduled:*
- Dependency check via Task Scheduler (`run_dependency_check.bat` → `scripts/devops/dependency_monitor.py`) — weekly Monday 9 AM

*Manual / on-demand (primary laptop):*
- Weekly validation (`run_weekly_validation.bat`) — reads local DB
- Monthly report generation and email delivery (`send_monthly_reports.bat`) — reads local DB
- Upgrade automation (`scripts/devops/upgrade_packages.py --dry-run`) — interactive, never auto-deploys

**Daily NAV Pipeline (10 steps in `daily_nav_enhanced.py`):**
1. Fetch portfolio balance from brokerage (TastyTrade or Tradier via `BROKERAGE_PROVIDER`)
2. Calculate NAV (total_portfolio_value / total_shares), write to `daily_nav` table
3. Write heartbeat file (`logs/daily_nav_heartbeat.txt`) + ping healthchecks.io
4. Snapshot holdings → `holdings_snapshots` + `position_snapshots` tables (non-fatal)
4b. Compute plan performance → `plan_daily_performance` table (non-fatal) — classifies positions into Plan CASH/ETF/A, aggregates per-plan market_value, cost_basis, unrealized_pl, allocation_pct
5. Run daily reconciliation → `daily_reconciliation` table (non-fatal)
6. Sync brokerage trades via ETL pipeline for last 3 days (non-fatal) — extract → transform → load
7. Update Discord pinned NAV message with chart (non-fatal) — connects as bot, edits pinned embed + chart image
8. Refresh benchmark data cache (non-fatal) — fetches latest SPY/QQQ/BTC-USD prices via yfinance into `benchmark_prices` table
9. Sync to production (non-fatal) — pushes NAV, positions, trades, benchmarks, reconciliation, plan performance to Railway via `POST /admin/sync`. Skips if `PRODUCTION_API_URL` or `ADMIN_API_KEY` not configured. Script: `scripts/sync_to_production.py`

**Email Logging:** All emails sent via `EmailService` are automatically logged to `email_logs` table (both successes and failures). Added Feb 2026.

**Failure Alerting:** Uses `EmailService` (not raw smtplib) so alerts are logged. Reads `SMTP_USERNAME` (falls back to `SMTP_USER`) and `ADMIN_EMAIL` (falls back to `ALERT_EMAIL`).

**Operations Health Dashboard:** `apps/ops_dashboard/app.py` — Streamlit dashboard (port 8502) showing health score, data freshness, automation status, reconciliation, NAV gaps, system logs, email delivery. Includes actionable remediation guidance for every non-green indicator. Data layer in `src/monitoring/health_checks.py` is UI-agnostic for reuse in CustomTkinter.

**External Monitoring (healthchecks.io):** Three cron-job monitors configured at https://healthchecks.io under the "Tovito Watch Dog" project:
- **Daily NAV** — Pinged by `daily_nav_enhanced.py` at end of each run (success or fail endpoint). Expected daily at ~4:05 PM EST. If no ping arrives within the grace period, healthchecks.io sends an email alert. Env var: `HEALTHCHECK_DAILY_NAV_URL`.
- **Watchdog** — Pinged by `watchdog_monitor.py` only when ALL system checks pass AND no warnings. If the watchdog detects issues (stale NAV, heartbeat missing, log errors), it does NOT ping success. Env var: `HEALTHCHECK_WATCHDOG_URL`.
- **Synthetic Monitor** — Pinged by `synthetic_monitor.py` on pass/fail after running all HTTP checks against production. Expected every 4 hours on OPS-AUTOMATION. Env var: `HEALTHCHECK_SYNTHETIC_URL`.
- **Important:** All scripts ping at the END of execution. If a script crashes before reaching the ping code, no ping is sent and healthchecks.io will eventually alert.
- **Batch file dependency:** The `.bat` launchers must resolve the correct Python path. When Python is upgraded (e.g., 3.13 → 3.14), update the hardcoded paths in `run_daily.bat`, `run_watchdog.bat`, `run_trade_notifier.bat`, `run_dependency_check.bat`, `run_synthetic_monitor.bat`, `sync_from_github.bat`, and `weekly_restart.bat` to match. Current: `C:\Python314\python.exe`.

**Discord Trade Notifier:** `scripts/trading/discord_trade_notifier.py` — Persistent service that polls TastyTrade and Tradier every 5 minutes during market hours (9:25 AM - 4:30 PM ET) for new trades and posts opening/closing trades to the `#tovito-trader-trades` Discord channel via webhook. Launcher: `run_trade_notifier.bat`. Env var: `DISCORD_TRADES_WEBHOOK_URL`.

**Discord Pinned NAV Message:** `scripts/discord/update_nav_message.py` — One-shot bot script (using discord.py) that connects, updates a pinned embed with current NAV + chart image, and disconnects. Runs as Step 7 of the daily NAV pipeline (non-fatal). Finds its own pinned message each run (no message ID storage). First run posts + pins; subsequent runs edit in place. Env vars: `DISCORD_BOT_TOKEN`, `DISCORD_NAV_CHANNEL_ID`. Requires discord.py (`pip install discord.py`) and bot setup in Discord Developer Portal with Send Messages, Manage Messages, Attach Files, Read Message History permissions.

**Management Laptop (OPS-AUTOMATION):** A dedicated always-on laptop that runs automations with NO local database dependency. It is NOT a development replica — no copy of `tovito.db`, no database-writing scripts. It only needs: `.env` (brokerage credentials + Discord webhook URL), Python + `tastytrade` package, and Git.

*Scheduled tasks (4):*
- **Discord Trade Notifier** (`run_trade_notifier.bat`) — Weekdays 9:20 AM. Persistent service polling brokerage APIs every 5 min during market hours, posting trades to Discord. No database reads/writes.
- **Synthetic Monitor** (`run_synthetic_monitor.bat`) — Every 4 hours. Validates production from user's perspective via HTTP checks (health, login, NAV freshness, frontend). Sends Discord/email alerts on failures only. Pings healthchecks.io.
- **GitHub Code Sync** (`scripts/utilities/sync_from_github.bat`) — Every 30 minutes. Fetches `origin/main`, skips pull if no changes (silent exit, no log noise). When changes exist: pulls, auto-installs Python/npm dependencies if `requirements.txt` or `package.json` changed, logs changed migration scripts for manual review.
- **Weekly Restart** (`scripts/utilities/weekly_restart.bat`) — Sunday 3 AM. Gracefully terminates Python/Node processes, issues `shutdown /r /t 30` to apply pending Windows updates. Task Scheduler tasks resume automatically after reboot.

*Required Windows settings:*
- Power & sleep → Never sleep (plugged in)
- Lid close action → Do nothing
- Disable hibernation: `powercfg /hibernate off`
- Windows Update active hours: 9 AM - 6 PM (prevents restarts during market hours)

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
# Start dev environment (one command — creates dev DB if needed)
python scripts/setup/start_dev.py                    # Start API in dev mode
python scripts/setup/start_dev.py --reset-db          # Rebuild dev database first
python scripts/setup/start_dev.py --reset-prospects   # Clear prospect data only

# Create/rebuild dev database manually
python scripts/setup/setup_test_database.py --env dev
python scripts/setup/setup_test_database.py --env dev --reset-prospects

# Daily NAV update (runs automatically via Task Scheduler)
python scripts/daily_nav_enhanced.py

# Fund flow workflow (ONLY pathway for contributions & withdrawals)
python scripts/investor/submit_fund_flow.py      # Step 1: Submit request
python scripts/investor/match_fund_flow.py        # Step 2: Match to brokerage ACH
python scripts/investor/process_fund_flow.py      # Step 3: Execute share accounting

# Sync to production (push pipeline data to Railway)
python scripts/sync_to_production.py              # Push today's data
python scripts/sync_to_production.py --dry-run    # Show payload without sending
python scripts/sync_to_production.py --date 2026-02-24 --days 5  # Specific date + lookback

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
python scripts/setup/migrate_add_plan_performance.py            # Plan daily performance table
python scripts/setup/migrate_add_plan_performance.py --backfill # Backfill from position snapshots
python scripts/setup/migrate_add_prospect_access.py             # Prospect access tokens table
python scripts/setup/migrate_add_prospect_verification.py      # Prospect email verification columns
python scripts/setup/migrate_add_pii_audit.py                  # PII access audit log + investor_profiles triggers
python scripts/setup/backfill_fund_flow_requests.py --dry-run  # Backfill historical FFR records

# Encryption key rotation
python scripts/setup/rotate_encryption_key.py                  # Generate new key and rotate all PII fields
python scripts/setup/rotate_encryption_key.py --dry-run        # Preview without writing
python scripts/setup/rotate_encryption_key.py --new-key KEY    # Use specific new key

# Grant prospect access (gated fund preview page)
python scripts/prospects/grant_prospect_access.py               # Interactive mode
python scripts/prospects/grant_prospect_access.py --prospect-id 1 --days 30  # Non-interactive

# Generate monthly reports
python scripts/reporting/generate_monthly_report.py --month 2 --year 2026 --email

# Run validation
python scripts/validation/validate_comprehensive.py

# Backup database
python scripts/utilities/backup_database.py                        # Simple DB backup
python scripts/utilities/backup_database.py --full                 # Full backup (DB + .env + session)
python scripts/utilities/backup_database.py --full --passphrase X  # Full backup with encrypted .env
python scripts/utilities/backup_database.py --verify PATH          # Verify backup integrity
python scripts/utilities/backup_database.py --rotate               # Remove old backups (keep 30, 90 days)
python scripts/utilities/backup_database.py --list                 # List all backups

# Restore database
python scripts/utilities/restore_database.py --list                # List available backups
python scripts/utilities/restore_database.py --restore PATH        # Restore from specific backup
python scripts/utilities/restore_database.py --latest              # Restore from most recent
python scripts/utilities/restore_database.py --full DIR --passphrase X  # Full restore with .env

# Dependency monitoring (weekly automated, manual on-demand)
python scripts/devops/dependency_monitor.py                        # Check all dependencies + notify
python scripts/devops/dependency_monitor.py --no-notify            # Check without notifications
python scripts/devops/dependency_monitor.py --pip-only             # Python packages only
python scripts/devops/dependency_monitor.py --npm-only             # Node packages only
python scripts/devops/dependency_monitor.py --json                 # JSON output

# Upgrade automation (interactive, NEVER run in production)
python scripts/devops/upgrade_packages.py --dry-run                # Preview what would change
python scripts/devops/upgrade_packages.py --all-minor              # Upgrade all minor/patch versions
python scripts/devops/upgrade_packages.py --package NAME           # Upgrade specific package (incl. major)
python scripts/devops/upgrade_packages.py --npm                    # Upgrade npm packages
python scripts/devops/upgrade_packages.py --rollback SNAPSHOT      # Rollback to snapshot
python scripts/devops/upgrade_packages.py --list-snapshots         # List available snapshots

# Synthetic monitoring (validates production from user's perspective)
python scripts/devops/synthetic_monitor.py                         # Run all checks
python scripts/devops/synthetic_monitor.py --check health          # Run specific check
python scripts/devops/synthetic_monitor.py --url http://localhost:8000  # Check local dev
python scripts/devops/synthetic_monitor.py --no-notify             # Skip Discord/email alerts
python scripts/devops/synthetic_monitor.py --json                  # JSON output

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
HEALTHCHECK_SYNTHETIC_URL=...  # healthchecks.io ping URL for synthetic monitor (optional)

# Synthetic monitoring (Phase 20D)
SYNTHETIC_MONITOR_EMAIL=...    # Synthetic investor account email (e.g., synthetic-monitor@tovitotrader.com)
SYNTHETIC_MONITOR_PASSWORD=... # Synthetic investor account password

# Encryption (for investor profile PII)
ENCRYPTION_KEY=...             # Fernet key — generate via: python src/utils/encryption.py
                               # CRITICAL: back up separately — data unrecoverable without it
ENCRYPTION_LEGACY_KEYS=...     # Comma-separated old Fernet keys for key rotation transition
                               # After rotating, add old ENCRYPTION_KEY here so existing data still decrypts

# Investor portal
PORTAL_BASE_URL=http://localhost:3000  # Base URL for email links (verification, password reset)

# Admin API (for production sync from automation laptop)
ADMIN_API_KEY=...              # Shared secret — same value on Railway and local .env
                               # Generate: python -c "import secrets; print(secrets.token_hex(32))"
PRODUCTION_API_URL=https://api.tovitotrader.com  # Local .env only (not on Railway)

# Fund settings
TAX_RATE=0.37
MARKET_CLOSE_TIME=16:00
TIMEZONE=America/New_York
```

**Note:** Never log or display these values. Never commit `.env` to version control.

## Testing

- Tests are in `tests/` using pytest (~885 tests, all passing)
- Test database setup: `scripts/setup/setup_test_database.py`
- Test fixtures in `tests/conftest.py` — creates full schema including email_logs, daily_reconciliation, holdings_snapshots, position_snapshots, brokerage_transactions_raw, fund_flow_requests, investor_profiles, referrals, prospects, prospect_communications, plan_daily_performance, prospect_access_tokens, pii_access_log
- **Always run tests against a test database, never production**
- Key test files: test_contributions.py, test_withdrawals.py, test_nav_calculations.py, test_database_validation.py, test_chart_generation.py (includes TestBenchmarkChart), test_benchmarks.py (market data caching, normalization), test_ops_health_checks.py, test_remediation.py, test_brokerage_factory.py, test_combined_brokerage.py, test_tastytrade_client.py, test_etl.py, test_fund_flow.py, test_encryption.py, test_investor_profiles.py, test_discord_trade_notifier.py, test_discord_utils.py, test_discord_nav_updater.py, test_api_regression.py (tests fund-flow + benchmark + analysis endpoints), test_tutorials.py (tutorial infrastructure: annotator, HTML generator, video composer, terminal rendering), test_mindmap.py (data model, layout, Mermaid/PNG/SVG/HTML generators), test_portfolio_analysis.py (risk metrics, holdings aggregation, monthly performance, DB integration), test_report_generation_api.py (job tracking, input validation, rate limiting), test_auth_service.py (password validation, bcrypt hashing, verification flow, login/lockout, password reset), test_landing_page_api.py (teaser stats, prospect creation, public endpoints, rate limiting, input validation), test_admin_sync.py (admin key auth, upsert functions, sync payload assembly, endpoint integration), test_plan_classification.py (plan classification logic, compute_plan_performance, upsert_plan_performance, sync integration, plan API endpoints), test_prospect_access.py (token creation/validation/revocation, access tracking, prospect performance data, admin endpoints, security constraints), test_pii_security.py (versioned ciphertext, multi-key decryption, key rotation, PII access log, audit triggers, security headers, startup validation), test_backup_restore.py (full backup, verify, rotate, restore, manifest checksums), test_dependency_monitor.py (classify upgrades, pip/npm checks, reports, notifications), test_upgrade_packages.py (environment safety, backup, upgrade, test gate, rollback), test_synthetic_monitor.py (7 HTTP checks, notifications, healthchecks.io pings)

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
