# Fund API Design Document
## Tovito Trader - Investor Portal API

### Overview

The Fund API provides secure, authenticated access to fund data for the Investor Portal.
It enforces the principle that **investors can only see their own data**.

```
┌─────────────────────────────────────────────────────────────┐
│  Investor Portal (React/Web)                                │
│                                                             │
│   Login Page → Dashboard → Transactions → Withdraw Request  │
└──────────────────────────┬──────────────────────────────────┘
                           │ HTTPS
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  Fund API (FastAPI)                                         │
│                                                             │
│   /auth/*     - Authentication (JWT tokens)                 │
│   /investor/* - Investor's own data (position, history)     │
│   /nav/*      - Fund NAV data (public to authenticated)     │
│   /withdraw/* - Withdrawal requests                         │
│                                                             │
│   Security: JWT auth, investor_id from token, rate limiting │
└──────────────────────────┬──────────────────────────────────┘
                           │ SQLite
                           ▼
┌─────────────────────────────────────────────────────────────┐
│  tovito.db                                                  │
│                                                             │
│   investors, transactions, daily_nav, withdrawal_requests   │
└─────────────────────────────────────────────────────────────┘
```

---

## Authentication

### JWT Token Flow

```
1. Investor logs in with email + password
2. API verifies credentials against investors table
3. API returns JWT token (valid 30 min) + refresh token (valid 7 days)
4. Portal includes token in all subsequent requests
5. API extracts investor_id from token - no spoofing possible
```

### Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| POST | `/auth/login` | Login with email/password |
| POST | `/auth/refresh` | Get new access token |
| POST | `/auth/logout` | Invalidate refresh token |
| GET | `/auth/me` | Get current user info |

---

## API Endpoints

### Investor Data (Own Data Only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/investor/profile` | Name, email, join date |
| GET | `/investor/position` | Current shares, value, return % |
| GET | `/investor/transactions` | Transaction history |
| GET | `/investor/statements` | List available statements |
| GET | `/investor/statements/{period}` | Download PDF statement |

### NAV Data (Fund-Wide, Read-Only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/nav/current` | Current NAV per share |
| GET | `/nav/history` | Historical NAV for charts |
| GET | `/nav/performance` | Fund performance metrics |

### Withdrawal Requests

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/withdraw/estimate` | Calculate tax on withdrawal amount |
| POST | `/withdraw/request` | Submit withdrawal request |
| GET | `/withdraw/pending` | View pending requests |
| DELETE | `/withdraw/cancel/{id}` | Cancel pending request |

---

## Data Models (Response Schemas)

### Position Response
```json
{
  "investor_id": "20260101-01A",
  "name": "David Lang",
  "current_shares": 18432.618,
  "current_nav": 1.1587,
  "current_value": 21358.42,
  "net_investment": 19000.00,
  "total_return_dollars": 2358.42,
  "total_return_percent": 12.41,
  "portfolio_percentage": 90.21,
  "as_of_date": "2026-02-01"
}
```

### Transaction Response
```json
{
  "transactions": [
    {
      "date": "2026-01-21",
      "type": "Contribution",
      "amount": 4000.00,
      "shares": 3432.62,
      "nav_at_transaction": 1.1653,
      "notes": "Additional investment"
    }
  ],
  "total_contributions": 19000.00,
  "total_withdrawals": 0.00
}
```

### Withdrawal Estimate Response
```json
{
  "requested_amount": 1000.00,
  "current_value": 21358.42,
  "proportion_of_account": 4.68,
  "estimated_realized_gain": 110.39,
  "estimated_tax": 40.84,
  "estimated_net_proceeds": 959.16,
  "tax_rate": 0.37,
  "note": "Actual amounts calculated at time of processing"
}
```

### NAV History Response
```json
{
  "current": {
    "date": "2026-02-01",
    "nav_per_share": 1.1587,
    "total_portfolio": 23675.61,
    "daily_change_percent": -0.01
  },
  "history": [
    {"date": "2026-01-31", "nav": 1.1588},
    {"date": "2026-01-30", "nav": 1.1520},
    ...
  ],
  "performance": {
    "mtd_return": 3.45,
    "ytd_return": 15.87,
    "since_inception": 15.87
  }
}
```

---

## Security Features

### 1. JWT Token Security
- Tokens expire after 30 minutes
- Refresh tokens expire after 7 days
- Tokens contain only investor_id (no sensitive data)
- Tokens are signed with secret key (HS256)

### 2. Data Isolation
```python
# EVERY endpoint extracts investor_id from the JWT token
# Investors CANNOT request other investors' data

@app.get("/investor/position")
async def get_position(current_user: User = Depends(get_current_user)):
    # current_user.investor_id comes from JWT - cannot be spoofed
    return get_investor_position(current_user.investor_id)
```

### 3. Rate Limiting
- 100 requests per minute per user
- 5 failed login attempts = 15 minute lockout

### 4. HTTPS Only
- API only accepts HTTPS connections
- No sensitive data over HTTP

### 5. Input Validation
- All inputs validated with Pydantic
- SQL injection prevented via parameterized queries

---

## File Structure

```
apps/investor_portal/
├── api/
│   ├── __init__.py
│   ├── main.py              # FastAPI app entry point
│   ├── config.py            # API configuration
│   ├── dependencies.py      # Auth dependencies
│   ├── routes/
│   │   ├── __init__.py
│   │   ├── auth.py          # /auth/* endpoints
│   │   ├── investor.py      # /investor/* endpoints
│   │   ├── nav.py           # /nav/* endpoints
│   │   └── withdraw.py      # /withdraw/* endpoints
│   ├── models/
│   │   ├── __init__.py
│   │   ├── schemas.py       # Pydantic response models
│   │   └── database.py      # Database connection
│   └── services/
│       ├── __init__.py
│       ├── auth_service.py  # JWT creation/validation
│       ├── investor_service.py
│       ├── nav_service.py
│       └── withdraw_service.py
├── frontend/                # React app (future)
│   └── ...
└── README.md
```

---

## Example Usage

### Login
```bash
curl -X POST http://localhost:8000/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "dlang32@gmail.com", "password": "****"}'

# Response:
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9...",
  "token_type": "bearer",
  "expires_in": 1800
}
```

### Get Position
```bash
curl http://localhost:8000/investor/position \
  -H "Authorization: Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9..."

# Response:
{
  "investor_id": "20260101-01A",
  "current_shares": 18432.618,
  "current_value": 21358.42,
  ...
}
```

### Request Withdrawal
```bash
curl -X POST http://localhost:8000/withdraw/request \
  -H "Authorization: Bearer eyJ0eXAi..." \
  -H "Content-Type: application/json" \
  -d '{"amount": 1000.00, "method": "ACH", "notes": "Partial withdrawal"}'

# Response:
{
  "request_id": 1,
  "status": "PENDING",
  "message": "Withdrawal request submitted. You will receive email confirmation."
}
```

---

## Implementation Priority

### Phase 1: Core API (MVP)
1. ✅ Authentication (login, JWT)
2. ✅ GET /investor/position
3. ✅ GET /nav/current
4. ✅ GET /nav/history

### Phase 2: Full Read Access
5. GET /investor/transactions
6. GET /investor/statements
7. GET /nav/performance

### Phase 3: Withdrawals
8. GET /withdraw/estimate
9. POST /withdraw/request
10. GET /withdraw/pending

### Phase 4: Polish
11. Rate limiting
12. Email notifications
13. Audit logging

---

## Local Development Setup

```bash
# Install dependencies
pip install fastapi uvicorn python-jose passlib bcrypt python-multipart

# Run API server
cd apps/investor_portal/api
uvicorn main:app --reload --port 8000

# API docs available at:
# http://localhost:8000/docs (Swagger UI)
# http://localhost:8000/redoc (ReDoc)
```
