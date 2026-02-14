# Tovito Trader - Architecture Document
## Version 1.0.0 | January 2026

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [System Overview](#system-overview)
3. [Current State Architecture](#current-state-architecture)
4. [Target State Architecture](#target-state-architecture)
5. [Application Architecture](#application-architecture)
6. [Database Architecture](#database-architecture)
7. [Data Flow](#data-flow)
8. [API Architecture](#api-architecture)
9. [Environment Management](#environment-management)
10. [Security Architecture](#security-architecture)
11. [Deployment Architecture](#deployment-architecture)
12. [Technology Stack](#technology-stack)

---

## 1. Executive Summary

### Purpose

Tovito Trader is a pooled investment fund management system that:
- Calculates daily Net Asset Value (NAV) from broker account data
- Manages investor accounts, contributions, and withdrawals
- Handles tax calculations and withholding (37% on realized gains)
- Generates professional reports and statements
- Provides real-time market monitoring and alerts

### Architecture Principles

| Principle | Description |
|-----------|-------------|
| **Single Source of Truth** | NAV stored in `daily_nav` table, all scripts read from it |
| **Separation of Concerns** | Three distinct applications for different purposes |
| **API-First Design** | Portal backend exposes REST API for flexibility |
| **Local-First Development** | Build and test locally, deploy when ready |
| **Environment Isolation** | Separate Dev/Test/Production configurations |

### Key Stakeholders

| Role | Users | Access Level |
|------|-------|--------------|
| Fund Manager | David | Full access to all applications |
| Investors | Ken, Beth, David | Read-only via Investor Portal |
| System | Automated tasks | Scheduled operations |

---

## 2. System Overview

### High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────┐
│                        TOVITO TRADER SYSTEM                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐     │
│  │  MARKET MONITOR │  │  FUND MANAGER   │  │ INVESTOR PORTAL │     │
│  │    (Desktop)    │  │    (Desktop)    │  │     (Web)       │     │
│  │                 │  │                 │  │                 │     │
│  │ • Live Quotes   │  │ • NAV Mgmt      │  │ • View Position │     │
│  │ • Alerts        │  │ • Investors     │  │ • Request W/D   │     │
│  │ • Projections   │  │ • Reports       │  │ • Statements    │     │
│  └────────┬────────┘  └────────┬────────┘  └────────┬────────┘     │
│           │                    │                    │               │
│           ▼                    ▼                    ▼               │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                     CORE LIBRARY (src/)                      │   │
│  │  ┌─────────┐  ┌──────────┐  ┌──────────┐  ┌───────────┐     │   │
│  │  │   API   │  │Automation│  │ Database │  │   Utils   │     │   │
│  │  │ Tradier │  │NAV Calc  │  │  Models  │  │  Logging  │     │   │
│  │  │TastyTrd*│  │Email Svc │  │  Schema  │  │ Formatter │     │   │
│  │  └─────────┘  └──────────┘  └──────────┘  └───────────┘     │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                │                                    │
│                                ▼                                    │
│           ┌────────────────────┴────────────────────┐              │
│           │              DATABASES                   │              │
│           │  ┌─────────────┐    ┌─────────────┐     │              │
│           │  │  tovito.db  │    │analytics.db │     │              │
│           │  │ (Fund Data) │    │(Market Data)│     │              │
│           │  └─────────────┘    └─────────────┘     │              │
│           └─────────────────────────────────────────┘              │
│                                                                     │
│  ┌─────────────────────────────────────────────────────────────┐   │
│  │                    EXTERNAL SERVICES                         │   │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐         │   │
│  │  │ Tradier │  │  SMTP   │  │  Auth*  │  │Hosting* │         │   │
│  │  │   API   │  │  Email  │  │(Clerk)  │  │(Railway)│         │   │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘         │   │
│  └─────────────────────────────────────────────────────────────┘   │
│                                                     * = Future      │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 3. Current State Architecture

### Current Folder Structure

```
tovito-trader/                    # Current state
├── run.py                        # Main CLI entry point
├── .env                          # Configuration
├── requirements.txt
├── README.md
│
├── dashboard/                    # ⚠️ Mixed: Monitor + Manager
│   ├── tovito_dashboard.py       # Fund management UI
│   ├── alert_system.py           # Alerting
│   ├── alerts_tab.py
│   ├── alert_notifications.py
│   ├── tovito.db                 # ⚠️ Duplicate database
│   └── config/
│       └── alert_rules.json
│
├── src/                          # ✅ Core library (well organized)
│   ├── api/
│   │   └── tradier.py
│   ├── automation/
│   │   ├── nav_calculator.py
│   │   ├── email_service.py
│   │   └── scheduler.py
│   ├── database/
│   │   ├── models.py
│   │   └── schema_v2.py
│   ├── streaming/
│   │   └── tradier_streaming.py
│   └── utils/
│       ├── safe_formatter.py
│       └── safe_logging.py
│
├── scripts/                      # ✅ Organized by function
│   ├── 02_investor/              # ⚠️ Numbered folders
│   ├── 03_reporting/
│   ├── 04_trading/
│   ├── 05_validation/
│   ├── 06_tax/
│   ├── 07_email/
│   ├── 08_setup/
│   ├── 09_prospects/
│   ├── 10_utilities/
│   └── 99_archive/
│
├── data/
│   ├── tovito.db                 # ✅ Production database
│   ├── backups/
│   ├── exports/
│   └── reports/
│
├── docs/                         # ⚠️ Needs consolidation
│   ├── guides/                   # 25+ guide files
│   ├── quickstart/               # Setup docs
│   └── reference/
│
├── tests/                        # ✅ Test suite
├── logs/
└── excel/                        # ⚠️ Deprecated
```

### Current Issues

| Issue | Impact | Resolution |
|-------|--------|------------|
| Two databases | Potential data sync issues | Single source: `data/tovito.db` |
| Dashboard mixed | Hard to maintain | Split into 3 apps |
| Numbered folders | Non-intuitive naming | Rename to plain names |
| Duplicate scripts | Confusion | Remove duplicates |
| No environment separation | Risk of prod data corruption | Add Dev/Test/Prod |

---

## 4. Target State Architecture

### Target Folder Structure

```
tovito-trader/                    # Target state (v1.0.0)
│
├── run.py                        # Main CLI entry point
├── .env                          # → Links to config/.env.{environment}
├── requirements.txt
├── README.md
├── CHANGELOG.md
├── setup.py
│
├── config/                       # NEW: Environment configuration
│   ├── .env.development
│   ├── .env.test
│   ├── .env.production
│   └── settings.py               # Environment-aware settings loader
│
├── apps/                         # NEW: Standalone applications
│   │
│   ├── market_monitor/           # Real-time monitoring (Desktop)
│   │   ├── __init__.py
│   │   ├── main.py               # Entry: python -m apps.market_monitor
│   │   ├── config/
│   │   │   └── alert_rules.json
│   │   ├── alerts/
│   │   │   ├── __init__.py
│   │   │   ├── alert_system.py
│   │   │   └── notifications.py
│   │   ├── streaming/
│   │   │   ├── __init__.py
│   │   │   └── quote_handler.py
│   │   └── ui/
│   │       ├── __init__.py
│   │       └── dashboard.py      # CustomTkinter UI
│   │
│   ├── fund_manager/             # Fund administration (Desktop)
│   │   ├── __init__.py
│   │   ├── main.py               # Entry: python -m apps.fund_manager
│   │   ├── views/
│   │   │   ├── __init__.py
│   │   │   ├── investor_view.py
│   │   │   ├── nav_view.py
│   │   │   ├── transaction_view.py
│   │   │   └── reports_view.py
│   │   └── ui/
│   │       ├── __init__.py
│   │       └── dashboard.py      # CustomTkinter UI
│   │
│   └── investor_portal/          # Investor-facing (Web)
│       ├── __init__.py
│       ├── main.py               # Entry: uvicorn apps.investor_portal.main:app
│       ├── config/
│       │   └── settings.py
│       ├── api/
│       │   ├── __init__.py
│       │   ├── dependencies.py   # Auth, DB injection
│       │   └── routes/
│       │       ├── __init__.py
│       │       ├── auth.py
│       │       ├── positions.py
│       │       ├── withdrawals.py
│       │       └── documents.py
│       ├── models/
│       │   ├── __init__.py
│       │   └── schemas.py        # Pydantic models
│       └── frontend/             # React app (when ready)
│           ├── src/
│           ├── public/
│           └── package.json
│
├── src/                          # Core library (shared)
│   ├── __init__.py
│   ├── api/
│   │   ├── __init__.py
│   │   ├── tradier.py
│   │   └── tastytrade.py         # Future
│   ├── automation/
│   │   ├── __init__.py
│   │   ├── nav_calculator.py
│   │   ├── email_service.py
│   │   └── scheduler.py
│   ├── database/
│   │   ├── __init__.py
│   │   ├── models.py
│   │   ├── schema.py
│   │   └── queries.py            # Common query functions
│   ├── streaming/
│   │   ├── __init__.py
│   │   └── tradier_streaming.py
│   └── utils/
│       ├── __init__.py
│       ├── safe_formatter.py
│       └── safe_logging.py
│
├── scripts/                      # CLI tools (renamed folders)
│   ├── investor/
│   │   ├── process_contribution.py
│   │   ├── process_withdrawal.py
│   │   ├── request_withdrawal.py
│   │   ├── list_investors.py
│   │   └── close_investor_account.py
│   ├── reporting/
│   │   ├── generate_monthly_report.py
│   │   └── export_transactions_excel.py
│   ├── trading/
│   │   ├── import_tradier_history.py
│   │   ├── sync_tradier_transactions.py
│   │   └── query_trades.py
│   ├── validation/
│   │   ├── validate_comprehensive.py
│   │   ├── validate_reconciliation.py
│   │   └── system_health_check.py
│   ├── tax/
│   │   ├── quarterly_tax_payment.py
│   │   └── yearend_tax_reconciliation.py
│   ├── email/
│   │   ├── test_email.py
│   │   └── check_email_config.py
│   ├── prospects/
│   │   ├── add_prospect.py
│   │   ├── list_prospects.py
│   │   └── send_prospect_report.py
│   ├── setup/
│   │   ├── migrate_*.py
│   │   └── setup_test_database.py
│   └── utilities/
│       ├── backup_database.py
│       ├── reverse_transaction.py
│       └── view_logs.py
│
├── data/
│   ├── tovito.db                 # Production fund database
│   ├── tovito_dev.db             # Development database
│   ├── tovito_test.db            # Test database
│   ├── backups/
│   ├── exports/
│   └── reports/
│
├── analytics/                    # Market Monitor data (separate)
│   └── analytics.db
│
├── docs/                         # Consolidated documentation
│   ├── 01_REQUIREMENTS.md
│   ├── 02_ARCHITECTURE.md        # This document
│   ├── 03_USER_GUIDE.md
│   ├── 04_ADMIN_GUIDE.md
│   ├── 05_API_REFERENCE.md
│   ├── 06_DEVELOPMENT.md
│   ├── QUICK_REFERENCE.md
│   └── archive/                  # Old docs
│
├── tests/
│   ├── __init__.py
│   ├── conftest.py
│   ├── requirements/             # Tests mapped to REQ-xxx
│   │   ├── test_nav_requirements.py
│   │   ├── test_investor_requirements.py
│   │   └── test_tax_requirements.py
│   ├── integration/
│   │   ├── test_tradier_integration.py
│   │   └── test_portal_api.py
│   └── unit/
│
├── automation/                   # Scheduled tasks
│   ├── run_daily.bat
│   ├── run_dev.bat
│   ├── run_test.bat
│   ├── run_prod.bat
│   ├── run_watchdog.bat
│   └── run_weekly_validation.bat
│
├── logs/
│
└── archive/                      # Deprecated code/files
    └── excel/
        └── Tovito_Account_Tracker_v5.0_Development.xlsm
```

---

## 5. Application Architecture

### 5.1 Market Monitor (Desktop)

**Purpose:** Real-time market monitoring, alerts, and projections for the fund manager.

```
┌─────────────────────────────────────────────────────────────┐
│                     MARKET MONITOR                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    UI Layer                          │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │   │
│  │  │ Quote Panel │ │ Alert Panel │ │ Chart Panel │    │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  Business Layer                      │   │
│  │  ┌─────────────┐ ┌─────────────┐ ┌─────────────┐    │   │
│  │  │Quote Handler│ │Alert System │ │ Projections │    │   │
│  │  └─────────────┘ └─────────────┘ └─────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   Data Layer                         │   │
│  │  ┌─────────────────────┐ ┌─────────────────────┐    │   │
│  │  │ Tradier Streaming   │ │   analytics.db      │    │   │
│  │  │ (WebSocket)         │ │   (Local storage)   │    │   │
│  │  └─────────────────────┘ └─────────────────────┘    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key Components:**

| Component | File | Responsibility |
|-----------|------|----------------|
| Main Entry | `main.py` | Application startup, UI initialization |
| Quote Handler | `streaming/quote_handler.py` | Process incoming quotes |
| Alert System | `alerts/alert_system.py` | Evaluate alert rules, trigger notifications |
| Notifications | `alerts/notifications.py` | Desktop/sound/email alerts |
| Dashboard UI | `ui/dashboard.py` | CustomTkinter interface |

**Data Flow:**
```
Tradier WebSocket → Quote Handler → Alert Evaluation → UI Update
                                  ↓
                           analytics.db (history)
```

---

### 5.2 Fund Manager (Desktop)

**Purpose:** Fund administration, investor management, NAV tracking, and reporting.

```
┌─────────────────────────────────────────────────────────────┐
│                      FUND MANAGER                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                    UI Layer                          │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐          │   │
│  │  │  NAV Tab  │ │Investor   │ │Transaction│          │   │
│  │  │           │ │Tab        │ │Tab        │          │   │
│  │  └───────────┘ └───────────┘ └───────────┘          │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐          │   │
│  │  │ Reports   │ │ Tax Tab   │ │ Settings  │          │   │
│  │  │ Tab       │ │           │ │ Tab       │          │   │
│  │  └───────────┘ └───────────┘ └───────────┘          │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                  View Layer                          │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐          │   │
│  │  │ NAV View  │ │ Investor  │ │Transaction│          │   │
│  │  │           │ │ View      │ │View       │          │   │
│  │  └───────────┘ └───────────┘ └───────────┘          │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   Data Layer                         │   │
│  │  ┌─────────────────────┐ ┌─────────────────────┐    │   │
│  │  │   src/database/     │ │   src/automation/   │    │   │
│  │  │   (models, queries) │ │   (NAV, email)      │    │   │
│  │  └─────────────────────┘ └─────────────────────┘    │   │
│  │                    │                                 │   │
│  │              ┌─────────────┐                         │   │
│  │              │  tovito.db  │                         │   │
│  │              └─────────────┘                         │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**Key Components:**

| Component | File | Responsibility |
|-----------|------|----------------|
| Main Entry | `main.py` | Application startup |
| NAV View | `views/nav_view.py` | Display/edit NAV history |
| Investor View | `views/investor_view.py` | Manage investor accounts |
| Transaction View | `views/transaction_view.py` | Process contributions/withdrawals |
| Reports View | `views/reports_view.py` | Generate statements |
| Dashboard UI | `ui/dashboard.py` | CustomTkinter tabbed interface |

---

### 5.3 Investor Portal (Web)

**Purpose:** Self-service portal for investors to view positions and request withdrawals.

```
┌─────────────────────────────────────────────────────────────┐
│                    INVESTOR PORTAL                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Frontend (React - Future)               │   │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐          │   │
│  │  │  Login    │ │ Dashboard │ │ Withdrawal│          │   │
│  │  │  Page     │ │ Page      │ │ Page      │          │   │
│  │  └───────────┘ └───────────┘ └───────────┘          │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │ HTTP/REST                       │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              Backend (FastAPI)                       │   │
│  │  ┌───────────────────────────────────────────────┐  │   │
│  │  │              API Routes                        │  │   │
│  │  │  /api/v1/auth/*      Authentication           │  │   │
│  │  │  /api/v1/positions   Get investor position    │  │   │
│  │  │  /api/v1/nav-history NAV history for charts   │  │   │
│  │  │  /api/v1/withdrawals Request/view withdrawals │  │   │
│  │  │  /api/v1/documents   Download statements      │  │   │
│  │  └───────────────────────────────────────────────┘  │   │
│  │                         │                            │   │
│  │  ┌───────────────────────────────────────────────┐  │   │
│  │  │           Dependencies/Middleware              │  │   │
│  │  │  • Authentication (JWT/Session)               │  │   │
│  │  │  • Database connection                        │  │   │
│  │  │  • Rate limiting                              │  │   │
│  │  │  • Logging                                    │  │   │
│  │  └───────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────┘   │
│                           │                                 │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                   Data Layer                         │   │
│  │  ┌─────────────────────┐                             │   │
│  │  │  tovito.db          │  READ-ONLY for positions   │   │
│  │  │  (Fund database)    │  WRITE for withdrawal req  │   │
│  │  └─────────────────────┘                             │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

**API Endpoints:**

| Endpoint | Method | Description | Auth |
|----------|--------|-------------|------|
| `/api/v1/auth/login` | POST | Authenticate investor | Public |
| `/api/v1/auth/logout` | POST | End session | Required |
| `/api/v1/auth/me` | GET | Get current user info | Required |
| `/api/v1/positions` | GET | Get investor's current position | Required |
| `/api/v1/nav-history` | GET | Get NAV history (for charts) | Required |
| `/api/v1/withdrawals` | GET | List withdrawal requests | Required |
| `/api/v1/withdrawals` | POST | Submit withdrawal request | Required |
| `/api/v1/documents` | GET | List available documents | Required |
| `/api/v1/documents/{id}` | GET | Download document | Required |

---

## 6. Database Architecture

### 6.1 Database Separation

| Database | Location | Purpose | Applications |
|----------|----------|---------|--------------|
| `tovito.db` | `data/` | Fund management data | Fund Manager, Portal, Scripts |
| `tovito_dev.db` | `data/` | Development copy | Development only |
| `tovito_test.db` | `data/` | Test database | Automated tests |
| `analytics.db` | `analytics/` | Market data, alerts | Market Monitor |

### 6.2 Fund Database Schema (tovito.db)

#### Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐
│    investors    │       │   daily_nav     │
├─────────────────┤       ├─────────────────┤
│ investor_id PK  │       │ date PK         │
│ name            │       │ nav_per_share   │
│ email           │       │ total_portfolio │
│ phone           │       │ total_shares    │
│ initial_capital │       │ daily_change_$  │
│ current_shares  │       │ daily_change_%  │
│ net_investment  │       │ source          │
│ status          │       │ created_at      │
│ join_date       │       └─────────────────┘
│ created_at      │
│ updated_at      │
│ is_deleted      │
└────────┬────────┘
         │
         │ 1:N
         ▼
┌─────────────────┐       ┌─────────────────┐
│  transactions   │       │   tax_events    │
├─────────────────┤       ├─────────────────┤
│ transaction_id  │       │ event_id PK     │
│ date            │       │ date            │
│ investor_id FK  │───────│ investor_id FK  │
│ type            │       │ withdrawal_amt  │
│ amount          │       │ realized_gain   │
│ share_price     │       │ tax_due         │
│ shares_trans    │       │ net_proceeds    │
│ notes           │       │ tax_rate        │
│ created_at      │       │ notes           │
│ is_deleted      │       │ created_at      │
└─────────────────┘       └─────────────────┘
         │
         │
         ▼
┌─────────────────┐       ┌─────────────────┐
│     trades      │       │   audit_log     │
├─────────────────┤       ├─────────────────┤
│ trade_id PK     │       │ log_id PK       │
│ tradier_tx_id   │       │ timestamp       │
│ date            │       │ table_name      │
│ trade_type      │       │ record_id       │
│ symbol          │       │ action          │
│ quantity        │       │ old_values      │
│ price           │       │ new_values      │
│ amount          │       │ performed_by    │
│ commission      │       └─────────────────┘
│ fees            │
│ created_at      │
└─────────────────┘

┌─────────────────┐       ┌─────────────────┐
│  system_logs    │       │   email_logs    │
├─────────────────┤       ├─────────────────┤
│ log_id PK       │       │ email_id PK     │
│ timestamp       │       │ sent_at         │
│ log_type        │       │ recipient       │
│ category        │       │ subject         │
│ message         │       │ email_type      │
│ details         │       │ status          │
└─────────────────┘       │ error_message   │
                          └─────────────────┘

┌─────────────────┐       ┌─────────────────┐
│    prospects    │       │withdrawal_reqs  │
├─────────────────┤       ├─────────────────┤
│ prospect_id PK  │       │ request_id PK   │
│ name            │       │ investor_id FK  │
│ email           │       │ requested_amt   │
│ phone           │       │ status          │
│ source          │       │ submitted_at    │
│ notes           │       │ processed_at    │
│ status          │       │ notes           │
│ created_at      │       └─────────────────┘
└─────────────────┘
```

#### Core Tables

**investors**
```sql
CREATE TABLE investors (
    investor_id TEXT PRIMARY KEY,      -- Format: 'YYYYMMDD-NNA'
    name TEXT NOT NULL,
    email TEXT,
    phone TEXT,
    initial_capital REAL NOT NULL DEFAULT 0,
    current_shares REAL NOT NULL DEFAULT 0,
    net_investment REAL NOT NULL DEFAULT 0,
    status TEXT DEFAULT 'Active',      -- Active, Inactive, Suspended
    join_date DATE NOT NULL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0
);
```

**daily_nav** (Single Source of Truth)
```sql
CREATE TABLE daily_nav (
    date DATE PRIMARY KEY,
    nav_per_share REAL NOT NULL,
    total_portfolio_value REAL NOT NULL,
    total_shares REAL NOT NULL,
    daily_change_dollars REAL DEFAULT 0,
    daily_change_percent REAL DEFAULT 0,
    tradier_balance REAL,
    cash_balance REAL,
    equity_value REAL,
    source TEXT DEFAULT 'API',         -- API, Manual, Imported
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**transactions**
```sql
CREATE TABLE transactions (
    transaction_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    investor_id TEXT NOT NULL REFERENCES investors(investor_id),
    transaction_type TEXT NOT NULL,    -- Initial, Contribution, Withdrawal, Tax_Payment
    amount REAL NOT NULL,
    share_price REAL NOT NULL,
    shares_transacted REAL NOT NULL,
    description TEXT,
    notes TEXT,
    reference_id TEXT,                 -- External reference (ACH ID)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_deleted INTEGER DEFAULT 0
);
```

**tax_events**
```sql
CREATE TABLE tax_events (
    event_id INTEGER PRIMARY KEY AUTOINCREMENT,
    date DATE NOT NULL,
    investor_id TEXT NOT NULL REFERENCES investors(investor_id),
    withdrawal_amount REAL NOT NULL,
    realized_gain REAL NOT NULL,
    tax_due REAL NOT NULL,
    net_proceeds REAL NOT NULL,
    tax_rate REAL NOT NULL DEFAULT 0.37,
    related_transaction_id INTEGER REFERENCES transactions(transaction_id),
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

### 6.3 Analytics Database Schema (analytics.db)

```sql
-- Quote history
CREATE TABLE quote_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    symbol TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    bid REAL,
    ask REAL,
    last REAL,
    volume INTEGER,
    change REAL,
    change_pct REAL
);

-- Alert history
CREATE TABLE alert_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    alert_type TEXT NOT NULL,
    symbol TEXT,
    condition TEXT,
    triggered_value REAL,
    threshold REAL,
    acknowledged INTEGER DEFAULT 0
);

-- Portfolio snapshots (intraday)
CREATE TABLE portfolio_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp DATETIME NOT NULL,
    total_value REAL NOT NULL,
    cash REAL,
    equity REAL,
    day_change REAL,
    day_change_pct REAL
);
```

---

## 7. Data Flow

### 7.1 Daily NAV Update Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   4:05 PM    │     │   Tradier    │     │  Database    │
│  Scheduler   │────▶│     API      │────▶│   Update     │
└──────────────┘     └──────────────┘     └──────────────┘
                            │                    │
                            ▼                    ▼
                     ┌──────────────┐     ┌──────────────┐
                     │  Get Account │     │  daily_nav   │
                     │   Balance    │     │   INSERT     │
                     └──────────────┘     └──────────────┘
                            │                    │
                            ▼                    ▼
                     ┌──────────────┐     ┌──────────────┐
                     │  Calculate   │     │   Email      │
                     │     NAV      │     │Notification  │
                     └──────────────┘     └──────────────┘
```

**Steps:**
1. Task Scheduler triggers at 4:05 PM EST (after market close)
2. `nav_calculator.fetch_and_update_nav()` called
3. Fetch account balance from Tradier API
4. Get total shares from investors table
5. Calculate: `NAV = Total Portfolio Value / Total Shares`
6. Insert/update `daily_nav` table
7. Log success to `system_logs`
8. Send email notification

### 7.2 Contribution Flow

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Investor   │     │   Process    │     │  Validate    │
│   Request    │────▶│ Contribution │────▶│    Data      │
└──────────────┘     └──────────────┘     └──────────────┘
                                                 │
                     ┌───────────────────────────┘
                     ▼
              ┌──────────────┐
              │  Get Current │
              │     NAV      │
              └──────────────┘
                     │
                     ▼
              ┌──────────────┐
              │  Calculate   │
              │   Shares     │
              │ amt / NAV    │
              └──────────────┘
                     │
        ┌────────────┼────────────┐
        ▼            ▼            ▼
┌──────────────┐ ┌──────────────┐ ┌──────────────┐
│ transactions │ │  investors   │ │   Email      │
│   INSERT     │ │   UPDATE     │ │Confirmation  │
└──────────────┘ └──────────────┘ └──────────────┘
```

### 7.3 Withdrawal Flow (Request → Approve → Process)

```
┌──────────────────────────────────────────────────────────────────┐
│                      WITHDRAWAL WORKFLOW                          │
├──────────────────────────────────────────────────────────────────┤
│                                                                  │
│  STEP 1: Request                                                 │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     │
│  │   Investor   │────▶│   Log        │────▶│withdrawal_   │     │
│  │   Request    │     │   Request    │     │requests      │     │
│  └──────────────┘     └──────────────┘     │status=PENDING│     │
│                                            └──────────────┘     │
│                                                                  │
│  STEP 2: Review & Approve (Fund Manager)                        │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     │
│  │   Review     │────▶│  Calculate   │────▶│   Approve    │     │
│  │   Request    │     │  Tax Impact  │     │  or Reject   │     │
│  └──────────────┘     └──────────────┘     └──────────────┘     │
│                                                   │              │
│  STEP 3: Process (if approved)                   │              │
│                       ┌──────────────────────────┘              │
│                       ▼                                          │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     │
│  │  Calculate   │────▶│   Execute    │────▶│   Update     │     │
│  │  Final Tax   │     │  Withdrawal  │     │   Records    │     │
│  └──────────────┘     └──────────────┘     └──────────────┘     │
│         │                    │                    │              │
│         ▼                    ▼                    ▼              │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐     │
│  │  tax_events  │     │ transactions │     │  investors   │     │
│  │   INSERT     │     │   INSERT     │     │   UPDATE     │     │
│  └──────────────┘     └──────────────┘     └──────────────┘     │
│                              │                                   │
│                              ▼                                   │
│                       ┌──────────────┐                          │
│                       │ Email with   │                          │
│                       │ Tax Details  │                          │
│                       └──────────────┘                          │
│                                                                  │
└──────────────────────────────────────────────────────────────────┘
```

### 7.4 Tax Calculation Logic

```
┌─────────────────────────────────────────────────────────────┐
│                  TAX CALCULATION                             │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Inputs:                                                    │
│  • withdrawal_amount                                        │
│  • current_value (shares × NAV)                            │
│  • net_investment (cost basis)                             │
│  • tax_rate (default 37%)                                  │
│                                                             │
│  Calculation:                                               │
│  ┌─────────────────────────────────────────────────────┐   │
│  │ unrealized_gain = current_value - net_investment    │   │
│  │                                                     │   │
│  │ IF unrealized_gain > 0:                             │   │
│  │   proportion = withdrawal_amount / current_value    │   │
│  │   realized_gain = unrealized_gain × proportion      │   │
│  │   tax_withheld = realized_gain × tax_rate          │   │
│  │ ELSE:                                               │   │
│  │   realized_gain = 0                                 │   │
│  │   tax_withheld = 0                                  │   │
│  │                                                     │   │
│  │ net_proceeds = withdrawal_amount - tax_withheld     │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  Example:                                                   │
│  • Net Investment: $19,000                                 │
│  • Current Value: $23,712                                  │
│  • Unrealized Gain: $4,712                                 │
│  • Withdrawal: $50                                         │
│  • Proportion: 50/23712 = 0.211%                          │
│  • Realized Gain: $4,712 × 0.211% = $9.94                 │
│  • Tax (37%): $9.94 × 0.37 = $3.68                        │
│  • Net Proceeds: $50 - $3.68 = $46.32                     │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 8. API Architecture

### 8.1 External APIs

#### Tradier API

| Endpoint | Method | Purpose |
|----------|--------|---------|
| `/accounts/{id}/balances` | GET | Account balance for NAV |
| `/accounts/{id}/positions` | GET | Current holdings |
| `/accounts/{id}/history` | GET | Transaction history |
| `/accounts/{id}/gainloss` | GET | Realized gains/losses |
| `/markets/clock` | GET | Market open/close status |
| `/markets/calendar` | GET | Trading calendar |

**Configuration:**
```
TRADIER_API_KEY=your_api_key
TRADIER_ACCOUNT_ID=your_account_id
TRADIER_API_URL=https://api.tradier.com/v1
```

#### Tradier WebSocket (Streaming)

| Stream | Data |
|--------|------|
| Quotes | Real-time bid/ask/last prices |
| Trades | Individual trade executions |
| Summary | End-of-day summaries |

### 8.2 Internal API (Investor Portal)

**Base URL:** `http://localhost:8000/api/v1` (local) or `https://api.tovitotrader.com/api/v1` (production)

#### Authentication

```json
POST /api/v1/auth/login
Request:
{
    "email": "ken@example.com",
    "password": "********"
}

Response:
{
    "access_token": "eyJ...",
    "token_type": "bearer",
    "investor_id": "20260101-02A",
    "name": "Kenneth Lang"
}
```

#### Position Endpoint

```json
GET /api/v1/positions
Headers: Authorization: Bearer <token>

Response:
{
    "investor_id": "20260101-02A",
    "name": "Kenneth Lang",
    "current_shares": 1000.0000,
    "nav_per_share": 1.2864,
    "current_value": 1286.40,
    "net_investment": 1000.00,
    "unrealized_gain": 286.40,
    "unrealized_gain_pct": 28.64,
    "tax_liability": 105.97,
    "after_tax_value": 1180.43,
    "as_of_date": "2026-01-31"
}
```

#### NAV History Endpoint

```json
GET /api/v1/nav-history?start_date=2026-01-01&end_date=2026-01-31
Headers: Authorization: Bearer <token>

Response:
{
    "data": [
        {
            "date": "2026-01-01",
            "nav_per_share": 1.0000,
            "daily_change_pct": 0.0
        },
        {
            "date": "2026-01-02",
            "nav_per_share": 1.0125,
            "daily_change_pct": 1.25
        }
        // ...
    ]
}
```

#### Withdrawal Request Endpoint

```json
POST /api/v1/withdrawals
Headers: Authorization: Bearer <token>

Request:
{
    "amount": 500.00,
    "notes": "Partial withdrawal for expenses"
}

Response:
{
    "request_id": 42,
    "status": "PENDING",
    "requested_amount": 500.00,
    "estimated_tax": 35.50,
    "estimated_net_proceeds": 464.50,
    "submitted_at": "2026-01-31T14:30:00Z",
    "message": "Your withdrawal request has been submitted for review."
}
```

---

## 9. Environment Management

### 9.1 Configuration Files

**config/.env.development**
```ini
# Environment
TOVITO_ENV=development

# Database
DATABASE_PATH=data/tovito_dev.db
ANALYTICS_DB_PATH=analytics/analytics_dev.db

# Tradier (sandbox)
TRADIER_API_KEY=sandbox_key_here
TRADIER_ACCOUNT_ID=sandbox_account
TRADIER_API_URL=https://sandbox.tradier.com/v1

# Email (test mode)
EMAIL_ENABLED=false
SMTP_SERVER=localhost
SMTP_PORT=1025

# Logging
LOG_LEVEL=DEBUG
LOG_TO_FILE=true

# Tax Rate
TAX_RATE=0.37
```

**config/.env.test**
```ini
# Environment
TOVITO_ENV=test

# Database (in-memory or test file)
DATABASE_PATH=data/tovito_test.db

# Tradier (mocked)
TRADIER_API_KEY=test_key
TRADIER_ACCOUNT_ID=test_account

# Email (disabled)
EMAIL_ENABLED=false

# Logging
LOG_LEVEL=WARNING
LOG_TO_FILE=false
```

**config/.env.production**
```ini
# Environment
TOVITO_ENV=production

# Database
DATABASE_PATH=data/tovito.db
ANALYTICS_DB_PATH=analytics/analytics.db

# Tradier (live)
TRADIER_API_KEY=live_key_here
TRADIER_ACCOUNT_ID=live_account
TRADIER_API_URL=https://api.tradier.com/v1

# Email (enabled)
EMAIL_ENABLED=true
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your_email@gmail.com
SMTP_PASSWORD=app_specific_password
ADMIN_EMAIL=david@tovitotrader.com

# Logging
LOG_LEVEL=INFO
LOG_TO_FILE=true

# Tax Rate
TAX_RATE=0.37
```

### 9.2 Settings Loader

```python
# config/settings.py
import os
from pathlib import Path
from dotenv import load_dotenv

class Settings:
    def __init__(self):
        self.ENV = os.getenv('TOVITO_ENV', 'development')
        
        # Load environment-specific .env file
        env_file = Path(__file__).parent / f'.env.{self.ENV}'
        if env_file.exists():
            load_dotenv(env_file)
        
        # Database
        self.DATABASE_PATH = os.getenv('DATABASE_PATH', 'data/tovito.db')
        self.ANALYTICS_DB_PATH = os.getenv('ANALYTICS_DB_PATH', 'analytics/analytics.db')
        
        # Tradier
        self.TRADIER_API_KEY = os.getenv('TRADIER_API_KEY')
        self.TRADIER_ACCOUNT_ID = os.getenv('TRADIER_ACCOUNT_ID')
        self.TRADIER_API_URL = os.getenv('TRADIER_API_URL', 'https://api.tradier.com/v1')
        
        # Email
        self.EMAIL_ENABLED = os.getenv('EMAIL_ENABLED', 'false').lower() == 'true'
        self.SMTP_SERVER = os.getenv('SMTP_SERVER')
        self.SMTP_PORT = int(os.getenv('SMTP_PORT', 587))
        self.SMTP_USER = os.getenv('SMTP_USER')
        self.SMTP_PASSWORD = os.getenv('SMTP_PASSWORD')
        self.ADMIN_EMAIL = os.getenv('ADMIN_EMAIL')
        
        # Logging
        self.LOG_LEVEL = os.getenv('LOG_LEVEL', 'INFO')
        self.LOG_TO_FILE = os.getenv('LOG_TO_FILE', 'true').lower() == 'true'
        
        # Business Rules
        self.TAX_RATE = float(os.getenv('TAX_RATE', 0.37))
    
    @property
    def is_production(self):
        return self.ENV == 'production'
    
    @property
    def is_development(self):
        return self.ENV == 'development'
    
    @property
    def is_test(self):
        return self.ENV == 'test'

# Singleton instance
settings = Settings()
```

### 9.3 Running Different Environments

```cmd
# Windows batch files

# automation/run_dev.bat
@echo off
set TOVITO_ENV=development
python run.py %*

# automation/run_test.bat
@echo off
set TOVITO_ENV=test
python -m pytest %*

# automation/run_prod.bat
@echo off
set TOVITO_ENV=production
python run.py %*
```

---

## 10. Security Architecture

### 10.1 Data Classification

| Data Type | Classification | Protection |
|-----------|---------------|------------|
| API Keys | Secret | Environment variables, never in code |
| Investor PII | Confidential | Encrypted at rest, access logged |
| Financial Data | Confidential | Database access controls |
| NAV/Portfolio | Internal | Read-only for investors |
| System Logs | Internal | Rotating, no PII |

### 10.2 Authentication & Authorization

**Investor Portal:**
- JWT tokens for API authentication
- Session timeout: 30 minutes
- Password hashing: bcrypt
- Rate limiting: 100 requests/minute

**Desktop Apps:**
- Local execution only
- Windows user permissions
- No network authentication required

### 10.3 Data Protection

```
┌─────────────────────────────────────────────────────────────┐
│                   SECURITY LAYERS                           │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Network Layer:                                             │
│  • HTTPS for all web traffic (future)                      │
│  • API rate limiting                                        │
│  • IP allowlisting (optional)                              │
│                                                             │
│  Application Layer:                                         │
│  • Input validation                                         │
│  • SQL parameterization (no injection)                     │
│  • Error handling (no stack traces to users)               │
│                                                             │
│  Data Layer:                                                │
│  • SQLite file permissions                                  │
│  • Backup encryption (recommended)                         │
│  • Audit logging for all changes                           │
│                                                             │
│  Environment Layer:                                         │
│  • Secrets in environment variables                        │
│  • Production config separate from code                    │
│  • .env files in .gitignore                                │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 11. Deployment Architecture

### 11.1 Local Development

```
┌─────────────────────────────────────────────────────────────┐
│                   LOCAL DEVELOPMENT                          │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  Developer Machine (Windows)                                │
│  ┌─────────────────────────────────────────────────────┐   │
│  │                                                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌───────────┐   │   │
│  │  │   Market    │  │    Fund     │  │  Portal   │   │   │
│  │  │   Monitor   │  │   Manager   │  │ (localhost│   │   │
│  │  │  (Desktop)  │  │  (Desktop)  │  │   :8000)  │   │   │
│  │  └─────────────┘  └─────────────┘  └───────────┘   │   │
│  │         │                │                │         │   │
│  │         └────────────────┼────────────────┘         │   │
│  │                          ▼                          │   │
│  │                   ┌─────────────┐                   │   │
│  │                   │  SQLite DBs │                   │   │
│  │                   │  (local)    │                   │   │
│  │                   └─────────────┘                   │   │
│  │                                                     │   │
│  └─────────────────────────────────────────────────────┘   │
│                          │                                  │
│                          ▼                                  │
│                   ┌─────────────┐                          │
│                   │  Tradier    │                          │
│                   │  Sandbox    │                          │
│                   └─────────────┘                          │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 11.2 Production (Future)

```
┌─────────────────────────────────────────────────────────────┐
│                   PRODUCTION DEPLOYMENT                      │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  David's Machine                    Cloud (Railway/Render)  │
│  ┌─────────────────────┐           ┌─────────────────────┐ │
│  │                     │           │                     │ │
│  │  ┌─────────────┐   │           │  ┌─────────────┐    │ │
│  │  │   Market    │   │           │  │  Investor   │    │ │
│  │  │   Monitor   │   │           │  │   Portal    │    │ │
│  │  └─────────────┘   │           │  │  (FastAPI)  │    │ │
│  │                     │           │  └──────┬──────┘    │ │
│  │  ┌─────────────┐   │           │         │           │ │
│  │  │    Fund     │   │  Sync     │  ┌──────▼──────┐    │ │
│  │  │   Manager   │◄──┼───────────┼──│  PostgreSQL │    │ │
│  │  └─────────────┘   │           │  │  (or SQLite)│    │ │
│  │         │          │           │  └─────────────┘    │ │
│  │         ▼          │           │                     │ │
│  │  ┌─────────────┐   │           └─────────────────────┘ │
│  │  │  SQLite DB  │   │                                   │
│  │  │  (primary)  │   │           TovitoTrader.com        │
│  │  └─────────────┘   │                                   │
│  │                     │                                   │
│  └─────────────────────┘                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

---

## 12. Technology Stack

### 12.1 Current Stack

| Layer | Technology | Version |
|-------|------------|---------|
| **Language** | Python | 3.11+ |
| **Database** | SQLite | 3.x |
| **ORM** | SQLAlchemy | 2.0 |
| **Desktop UI** | CustomTkinter | 5.x |
| **API Client** | Requests | 2.x |
| **WebSocket** | websockets | 12.x |
| **PDF Generation** | ReportLab | 4.x |
| **Excel** | openpyxl | 3.x |
| **Email** | smtplib | stdlib |
| **Scheduling** | Windows Task Scheduler | - |
| **Testing** | pytest | 7.x |

### 12.2 Portal Stack (Future)

| Layer | Technology | Version |
|-------|------------|---------|
| **Backend** | FastAPI | 0.100+ |
| **Frontend** | React | 18.x |
| **Styling** | Tailwind CSS | 3.x |
| **Charts** | Recharts | 2.x |
| **Auth** | Clerk or Auth0 | - |
| **Hosting** | Railway or Render | - |

### 12.3 Dependencies

```
# requirements.txt

# Core
python-dotenv>=1.0.0
sqlalchemy>=2.0.0

# API
requests>=2.31.0
websockets>=12.0

# Desktop UI
customtkinter>=5.2.0

# PDF/Excel
reportlab>=4.0.0
openpyxl>=3.1.0

# Web (Portal)
fastapi>=0.100.0
uvicorn>=0.23.0
pydantic>=2.0.0
python-jose>=3.3.0  # JWT
passlib>=1.7.4      # Password hashing
bcrypt>=4.0.0

# Testing
pytest>=7.4.0
pytest-cov>=4.1.0
httpx>=0.24.0       # Async test client
```

---

## Appendix A: Glossary

| Term | Definition |
|------|------------|
| **NAV** | Net Asset Value - total portfolio value divided by total shares |
| **Investor** | Person who has invested capital in the fund |
| **Contribution** | Money added to an investor's account |
| **Withdrawal** | Money removed from an investor's account |
| **Realized Gain** | Profit that becomes taxable when withdrawn |
| **Unrealized Gain** | Paper profit that hasn't been withdrawn |
| **Cost Basis** | Original investment amount (net_investment) |
| **Prospect** | Potential investor not yet invested |

---

## Appendix B: Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-31 | David/Claude | Initial architecture document |

---

*This document is the authoritative reference for Tovito Trader system architecture.*
