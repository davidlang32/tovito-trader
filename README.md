# Tovito Trader

A pooled investment fund management platform for tracking investor portfolios, calculating daily NAV, and providing investor access through a web portal.

## Overview

Tovito Trader manages a shared investment portfolio where all investors participate in the same positions. The system calculates daily Net Asset Value (NAV) per share, tracks contributions and withdrawals through a unified fund flow lifecycle, records realized gains for quarterly tax settlement, and provides investors with real-time access to their positions.

### Key Features

- **Daily NAV Calculation** - Automated portfolio valuation at market close
- **Investor Management** - Track multiple investors with proportional ownership
- **Transaction Processing** - Handle contributions and withdrawals with proper share accounting
- **Tax Tracking** - Realized gains recorded at withdrawal, settled quarterly
- **Investor Portal** - Web-based dashboard for investors to view positions
- **REST API** - Secure API with JWT authentication
- **Brokerage Integration** - TastyTrade (primary) + Tradier (legacy) via protocol pattern
- **Comprehensive Validation** - 8-point validation suite for data integrity

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    TOVITO TRADER                            │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐     │
│  │   Investor  │    │   Fund API  │    │   Market    │     │
│  │   Portal    │───▶│  (FastAPI)  │───▶│   Monitor   │     │
│  │   (React)   │    │  Port 8000  │    │  (Future)   │     │
│  └─────────────┘    └──────┬──────┘    └─────────────┘     │
│                            │                                │
│                     ┌──────▼──────┐                        │
│                     │  tovito.db  │                        │
│                     │  (SQLite)   │                        │
│                     └──────┬──────┘                        │
│                            │                                │
│                     ┌──────▼──────┐                        │
│                     │ TastyTrade  │                        │
│                     │  / Tradier  │                        │
│                     └─────────────┘                        │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

## Quick Start

See [QUICK_START.md](QUICK_START.md) for setup instructions.

**TL;DR:**
```cmd
# Clone/download project
cd C:\tovito-trader

# Install Python dependencies
pip install -r requirements.txt

# Run daily NAV (after market close)
python scripts\nav\daily_nav_enhanced.py

# Validate data
python run.py validate

# Start API
python -m uvicorn apps.investor_portal.api.main:app --port 8000

# Start Portal (separate terminal)
cd apps\investor_portal\frontend\investor_portal
npm install
npm run dev
```

## Project Structure

```
C:\tovito-trader\
├── apps\
│   ├── market_monitor\         # Real-time market dashboard (future)
│   ├── fund_manager\           # Admin application (future)
│   └── investor_portal\
│       ├── api\                # FastAPI backend
│       │   ├── main.py
│       │   ├── routes\
│       │   ├── models\
│       │   └── services\
│       └── frontend\           # React frontend
│           └── investor_portal\
│
├── config\                     # Environment configuration
│   ├── .env.development
│   ├── .env.production
│   └── settings.py
│
├── data\
│   └── tovito.db              # Main fund database
│
├── scripts\
│   ├── nav\                   # NAV calculation
│   ├── investor\              # Investor management
│   ├── reporting\             # Reports and exports
│   ├── validation\            # Data validation
│   ├── tax\                   # Tax handling
│   ├── trading\               # Tradier integration
│   ├── email\                 # Email services
│   └── utilities\             # Maintenance tools
│
├── docs\
│   └── cheat_sheets\          # Quick reference guides
│
├── run.py                     # Main CLI entry point
├── requirements.txt           # Python dependencies
├── test_api_regression.py     # API test suite
└── verify_investor.py         # Portal access setup
```

## Documentation

| Document | Description |
|----------|-------------|
| [FUND_ADMIN_GUIDE.md](FUND_ADMIN_GUIDE.md) | Complete administration guide |
| [QUICK_START.md](QUICK_START.md) | 5-minute setup guide |
| [FUND_API_DESIGN.md](FUND_API_DESIGN.md) | API architecture and endpoints |
| [docs/cheat_sheets/](docs/cheat_sheets/) | Quick reference for specific tasks |

## Daily Operations

### Automated (Task Scheduler)
- **4:05 PM EST** - Daily NAV calculation
- **Healthcheck** - External monitoring confirms execution

### Manual Commands
```cmd
# Calculate today's NAV
python scripts\nav\daily_nav_enhanced.py

# Validate database
python run.py validate

# Fund flow workflow (contributions & withdrawals)
python scripts\investor\submit_fund_flow.py         # Step 1: Submit request
python scripts\investor\match_fund_flow.py           # Step 2: Match to brokerage ACH
python scripts\investor\process_fund_flow.py         # Step 3: Execute share accounting

# Generate monthly report
python scripts\reporting\generate_monthly_report.py --month 2 --year 2026
```

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/auth/login` | POST | Authenticate user |
| `/investor/position` | GET | Current portfolio position |
| `/investor/transactions` | GET | Transaction history |
| `/nav/current` | GET | Current NAV per share |
| `/nav/performance` | GET | Fund performance metrics |
| `/fund-flow/estimate` | GET | Contribution/withdrawal estimate |
| `/fund-flow/requests` | GET | List fund flow requests |

Full API documentation: http://localhost:8000/docs

## Testing

```cmd
# Run all API tests
set TEST_PASSWORD=YourPassword
python test_api_regression.py

# Generate HTML report
python test_api_regression.py --report

# Test specific section
python test_api_regression.py --section auth

# Verbose output
python test_api_regression.py --verbose
```

## Technology Stack

| Component | Technology |
|-----------|------------|
| Backend | Python 3.13, FastAPI |
| Frontend | React 18, Vite, Tailwind CSS |
| Database | SQLite |
| Authentication | JWT (python-jose), bcrypt |
| Market Data | TastyTrade SDK, Tradier API (legacy) |
| Task Scheduling | Windows Task Scheduler |

## Security

- **JWT Authentication** - 30-minute access tokens, 7-day refresh tokens
- **Password Hashing** - bcrypt with 12 rounds
- **Account Lockout** - 5 failed attempts = 15-minute lockout
- **Data Isolation** - Investors only see their own data
- **HTTPS Ready** - Configure for production deployment

## Requirements

- Python 3.11+
- Node.js 18+
- Windows 10/11 (for Task Scheduler automation)
- TastyTrade account (or Tradier API account for legacy mode)

## License

Private - Tovito Trader © 2026

## Support

For issues or questions, contact the fund administrator.
