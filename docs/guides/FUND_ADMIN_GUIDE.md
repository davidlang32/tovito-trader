# Tovito Trader - Fund Administration Guide

**Version:** 2.0  
**Last Updated:** February 2026  
**Author:** David Lang

---

## Table of Contents

1. [Quick Reference](#1-quick-reference)
2. [Daily Operations](#2-daily-operations)
3. [Investor Management](#3-investor-management)
4. [Contributions](#4-contributions)
5. [Withdrawals](#5-withdrawals)
6. [Monthly Reports](#6-monthly-reports)
7. [Tax Handling](#7-tax-handling)
8. [Validation & Reconciliation](#8-validation--reconciliation)
9. [API & Portal Management](#9-api--portal-management)
10. [Troubleshooting](#10-troubleshooting)
11. [Database Maintenance](#11-database-maintenance)
12. [Script Reference](#12-script-reference)

---

## 1. Quick Reference

### Essential Commands

```cmd
# Navigate to project
cd C:\tovito-trader

# Daily NAV update (run after market close ~4:05 PM EST)
python scripts\nav\daily_nav_enhanced.py

# Validate database integrity
python run.py validate

# Start API server
python -m uvicorn apps.investor_portal.api.main:app --port 8000

# Start Investor Portal
cd apps\investor_portal\frontend\investor_portal
npm run dev

# Run regression tests
set TEST_PASSWORD=YourPassword
python test_api_regression.py --report
```

### Key File Locations

| Item | Location |
|------|----------|
| Main Database | `data\tovito.db` |
| Config Files | `config\` |
| Daily NAV Script | `scripts\nav\daily_nav_enhanced.py` |
| Investor Scripts | `scripts\investor\` |
| Reporting Scripts | `scripts\reporting\` |
| API | `apps\investor_portal\api\` |
| Portal Frontend | `apps\investor_portal\frontend\` |

### Current Investors

| Name | ID | Email | Status |
|------|-----|-------|--------|
| David Lang | 20260101-01A | dlang32@gmail.com | Active |
| Elizabeth Lenz | 20260101-02A | blenz08@yahoo.com | Active |
| Kenneth Lang | 20260101-03A | kenlang67@gmail.com | Active |

---

## 2. Daily Operations

### 2.1 Daily NAV Calculation

**When:** Every market day after 4:00 PM EST (market close)

**Automated Method (Recommended):**
- Windows Task Scheduler runs `run_daily.bat` automatically
- Healthcheck monitoring confirms execution

**Manual Method:**
```cmd
cd C:\tovito-trader
python scripts\nav\daily_nav_enhanced.py
```

**What it does:**
1. Fetches current portfolio value from Tradier
2. Calculates total shares outstanding
3. Computes NAV per share = Portfolio Value / Total Shares
4. Records daily change ($ and %)
5. Stores in `daily_nav` table

**Expected Output:**
```
============================================================
 DAILY NAV CALCULATION
============================================================
 Date: 2026-02-01
 Portfolio Value: $23,674.52
 Total Shares: 20,432.6185
 NAV per Share: $1.1587
 Daily Change: +$45.23 (+0.19%)
============================================================
 ✅ NAV saved successfully
============================================================
```

### 2.2 Verify NAV Calculation

```cmd
python run.py validate
```

All 8 checks should pass:
- ✅ Share totals match
- ✅ Percentages sum to 100%
- ✅ NAV calculation correct
- ✅ January 1 NAV = $1.00
- ✅ Day 1 investments match
- ✅ All NAV entries valid
- ✅ No negative values
- ✅ Transaction sums match

### 2.3 Weekend/Holiday Handling

- **No market days:** Skip NAV calculation
- **System uses last available NAV** for display
- **Check market calendar** before investigating "missing" NAV

---

## 3. Investor Management

### 3.1 List All Investors

```cmd
python scripts\investor\list_investors.py
```

Shows: Name, ID, Email, Status, Shares, Net Investment, Portfolio %

### 3.2 Add New Investor

**Step 1:** Prepare investor information
- Full name
- Email address
- Phone (optional)
- Initial contribution amount

**Step 2:** Add to database
```cmd
python scripts\investor\add_investor.py
```

Follow the prompts to enter details.

**Step 3:** Process initial contribution via fund flow workflow
```cmd
python scripts\investor\submit_fund_flow.py      # Submit request
python scripts\investor\match_fund_flow.py        # Match to brokerage ACH
python scripts\investor\process_fund_flow.py      # Execute share accounting
```

**Step 4:** Set up portal access
```cmd
python verify_investor.py --email newinvestor@email.com --password "SecurePass123!"
```

**Step 5:** Send welcome email with portal instructions

### 3.3 View Investor Details

```cmd
python scripts\investor\view_investor.py --id 20260101-01A
```

### 3.4 Update Investor Email

```cmd
python scripts\utilities\update_investor_emails.py
```

### 3.5 Close Investor Account

**Warning:** Only use for complete withdrawal/exit

```cmd
python scripts\investor\close_investor_account.py --id INVESTOR_ID
```

---

## 4. Contributions

### 4.1 Process a New Contribution (Fund Flow Workflow)

**Prerequisites:**
- Funds received and cleared in brokerage account
- Current NAV calculated for today

**Step 1:** Submit contribution request
```cmd
python scripts\investor\submit_fund_flow.py
```
Select investor, enter amount, choose "contribution" flow type.

**Step 2:** Match to brokerage ACH deposit
```cmd
python scripts\investor\match_fund_flow.py
```
Links the fund flow request to the actual brokerage ACH transaction.

**Step 3:** Process share accounting
```cmd
python scripts\investor\process_fund_flow.py
```
Calculates shares at current NAV and updates all database tables.

**What happens:**
1. `fund_flow_requests` record tracks full lifecycle (pending → processed)
2. New shares calculated: Amount / Current NAV
3. Investor's `current_shares` and `net_investment` updated
4. Transaction recorded in `transactions` table with `reference_id = 'ffr-{request_id}'`
5. Linked to brokerage ACH via `matched_trade_id`

### 4.2 Assign Pending Contribution

If contribution was recorded but not yet assigned:
```cmd
python scripts\investor\assign_pending_contribution.py
```

### 4.3 Contribution Rules

- Contributions processed at **end of day NAV**
- Minimum contribution: $1,000 (configurable)
- Shares issued = Contribution Amount / NAV per Share
- Fractional shares allowed (4 decimal places)

---

## 5. Withdrawals

### 5.1 Process a Withdrawal (Fund Flow Workflow)

**Step 1:** Investor submits request (via portal or email)

**Step 2:** Submit the withdrawal request
```cmd
python scripts\investor\submit_fund_flow.py
```
Select investor, enter amount, choose "withdrawal" flow type.

**Step 3:** Match to brokerage ACH transfer
```cmd
python scripts\investor\match_fund_flow.py
```

**Step 4:** Process share accounting
```cmd
python scripts\investor\process_fund_flow.py
```

The preview shows realized gain (informational only — tax is settled quarterly):
```
============================================================
 WITHDRAWAL PREVIEW
============================================================
 Investor ID: 20260101-01A
 Requested Amount: $5,000.00

 CALCULATION:
 Current Shares: 18,432.6185
 Current NAV: $1.1587
 Shares to Redeem: 4,315.2846

 TAX INFORMATION (Proportional Method):
 Cost Basis of Shares: $4,450.23
 Realized Gain: $549.77
 Tax: settled quarterly (no withholding at withdrawal)

 NET PROCEEDS: $5,000.00 (full amount disbursed)

 Confirm? (y/n):
```

### 5.2 Withdrawal Tax Policy — Quarterly Settlement

The system uses **proportional allocation** (average cost method):

1. **Calculate shares to redeem:** Withdrawal Amount / Current NAV
2. **Calculate cost basis:** (Shares Redeemed / Total Shares) × Net Investment
3. **Calculate realized gain:** Redemption Value - Cost Basis
4. **Record realized gain:** Stored in `tax_events` for quarterly settlement
5. **Net proceeds:** Full withdrawal amount (no withholding)

Tax on realized gains is settled quarterly via `scripts/tax/quarterly_tax_payment.py`.

### 5.3 Eligible Withdrawal

The API and monthly reports show an **eligible withdrawal** field:
- `eligible_withdrawal = current_value - estimated_tax_liability`
- `estimated_tax_liability = max(0, unrealized_gain) × 0.37`

This shows investors how much they could receive if they liquidated their entire position.

### 5.4 Withdrawal Rules

- Processed at **end of day NAV**
- Tax settled quarterly (no withholding at withdrawal time)
- Minimum withdrawal: $500 (configurable)
- Partial withdrawals allowed
- Full withdrawal = account closure (use `close_investor_account.py`)

---

## 6. Monthly Reports

### 6.1 Generate Monthly Report

```cmd
python scripts\reporting\generate_monthly_report.py --month 2026-01
```

**Report includes:**
- Fund performance summary
- Individual investor statements
- Transaction log
- NAV history chart data

### 6.2 Send Reports to Investors

```cmd
python scripts\reporting\send_monthly_reports.py --month 2026-01
```

Or use the batch file:
```cmd
send_monthly_reports.bat
```

### 6.3 Export Transactions to Excel

```cmd
python scripts\reporting\export_transactions_excel.py --start 2026-01-01 --end 2026-01-31
```

### 6.4 Monthly Report Checklist

- [ ] All daily NAVs recorded for the month
- [ ] Validation passes (all 8 checks)
- [ ] Generate reports
- [ ] Review for accuracy
- [ ] Send to investors by 5th of following month

---

## 7. Tax Handling

### 7.1 Tax Policy — Quarterly Settlement

Current tax rate: **37%** (highest marginal rate)

**Policy:** Tax on realized gains from withdrawals is **not withheld at withdrawal time**. Instead, realized gains are tracked in the `tax_events` table and settled quarterly.

- Investors receive the **full withdrawal amount** (no deduction)
- Realized gains are recorded for quarterly tax settlement
- Eligible withdrawal shown on monthly reports and portal

To modify the tax rate, update in:
- `apps\investor_portal\api\config.py` (TAX_RATE setting)

### 7.2 Quarterly Tax Payments

```cmd
python scripts\tax\quarterly_tax_payment.py
```

Reviews accumulated realized gains from withdrawals and prepares estimated tax payment.

### 7.3 Year-End Tax Reconciliation

```cmd
python scripts\tax\yearend_tax_reconciliation.py
```

Generates:
- Summary of all realized gains by investor
- Quarterly payments vs. actual liability
- K-1 preparation data

### 7.4 Tax Records

All realized gains recorded in:
- `tax_events` table (event_type: 'Realized_Gain', with tax_due = 0 at withdrawal)
- `fund_flow_requests` table (realized_gain field on processed withdrawals)

---

## 8. Validation & Reconciliation

### 8.1 Run Full Validation

```cmd
python run.py validate
```

Or directly:
```cmd
python scripts\validation\validate_comprehensive.py
```

### 8.2 Validation Checks

| Check | What It Verifies |
|-------|------------------|
| 1. Share Totals | Sum of investor shares = daily_nav total_shares |
| 2. Percentages | All investor percentages sum to 100% |
| 3. NAV Calculation | NAV × Total Shares = Portfolio Value |
| 4. January 1 NAV | Starting NAV was exactly $1.00 |
| 5. Day 1 Match | Initial investments match Day 1 portfolio |
| 6. NAV Validity | All NAV entries have valid values |
| 7. No Negatives | No negative shares, NAV, or investments |
| 8. Transaction Sums | Transaction totals match net investments |

### 8.3 Reconcile with Brokerage

```cmd
python scripts\validation\validate_reconciliation.py
```

Compares:
- Database portfolio value vs. Tradier account value
- Position counts
- Cash balances

### 8.4 Weekly Validation

Run comprehensive validation weekly:
```cmd
run_weekly_validation.bat
```

---

## 9. API & Portal Management

### 9.1 Start the API

```cmd
cd C:\tovito-trader
python -m uvicorn apps.investor_portal.api.main:app --port 8000
```

API available at: http://localhost:8000
API docs at: http://localhost:8000/docs

### 9.2 Start the Investor Portal

```cmd
cd C:\tovito-trader\apps\investor_portal\frontend\investor_portal
npm run dev
```

Portal available at: http://localhost:3000

### 9.3 Run Both (Two Terminals)

**Terminal 1 - API:**
```cmd
cd C:\tovito-trader
python -m uvicorn apps.investor_portal.api.main:app --port 8000
```

**Terminal 2 - Portal:**
```cmd
cd C:\tovito-trader\apps\investor_portal\frontend\investor_portal
npm run dev
```

### 9.4 Investor Portal Access Setup

```cmd
python verify_investor.py --list
```

To set up an investor's password:
```cmd
python verify_investor.py --email investor@email.com --password "SecurePass123!"
```

**Password Requirements:**
- 8-72 characters
- At least one uppercase letter
- At least one lowercase letter
- At least one number
- At least one special character (!@#$%^&*()_+-=[]{}|;:,.<>?)

### 9.5 Run API Regression Tests

```cmd
cd C:\tovito-trader
set TEST_PASSWORD=YourPassword
python test_api_regression.py --report
```

Opens `test_report.html` with results.

---

## 10. Troubleshooting

### 10.1 NAV Calculation Issues

**Problem:** NAV not updating
- Check Tradier API connection
- Verify market was open today
- Check `data\tovito.db` is not locked

**Problem:** NAV seems wrong
```cmd
python run.py validate
```
Review which check fails.

### 10.2 API Issues

**Problem:** API won't start
```cmd
# Check if port is in use
netstat -ano | findstr :8000

# Kill process if needed
taskkill /PID <pid> /F
```

**Problem:** 401 Unauthorized errors
- Token may be expired (30 min)
- Re-login to get new token

### 10.3 Portal Issues

**Problem:** Portal can't connect to API
- Verify API is running on port 8000
- Check browser console for CORS errors
- Ensure both are on localhost

**Problem:** Login fails
- Verify password with `verify_investor.py --list`
- Check if account is locked (5 failed attempts = 15 min lockout)

### 10.4 Database Issues

**Problem:** Database locked
- Close DB Browser for SQLite
- Stop any running Python scripts
- Restart the API

**Problem:** Data seems corrupted
```cmd
# Backup first!
python scripts\utilities\backup_database.py

# Then validate
python run.py validate
```

### 10.5 Common Error Messages

| Error | Solution |
|-------|----------|
| `ModuleNotFoundError` | Run `pip install <module>` |
| `ENOENT: no such file` | Check file path, run from project root |
| `Connection refused` | Start the API server |
| `Invalid token` | Re-login, token expired |
| `Database is locked` | Close other DB connections |

---

## 11. Database Maintenance

### 11.1 Backup Database

```cmd
python scripts\utilities\backup_database.py
```

Creates timestamped backup in `backups\` folder.

**Recommended schedule:**
- Daily: Automatic with NAV calculation
- Weekly: Manual verification
- Monthly: Archive to external storage

### 11.2 Database Location

| Database | Path | Purpose |
|----------|------|---------|
| Main Fund DB | `data\tovito.db` | All fund data |
| Analytics DB | `analytics\analytics.db` | Market data (future) |

### 11.3 View Database

Use **DB Browser for SQLite**:
1. Download from: https://sqlitebrowser.org/
2. Open `data\tovito.db`
3. Browse tables and run queries

**Important:** Close DB Browser before running scripts!

### 11.4 Key Tables

| Table | Purpose |
|-------|---------|
| `investors` | Investor profiles and current positions |
| `transactions` | All contributions and withdrawals |
| `daily_nav` | Daily NAV history |
| `investor_auth` | Portal authentication |
| `fund_flow_requests` | Contribution/withdrawal lifecycle tracking |
| `positions` | Current portfolio positions |

### 11.5 Reverse a Transaction

**Use with extreme caution!**
```cmd
python scripts\utilities\reverse_transaction.py --id TRANSACTION_ID
```

Always:
1. Backup first
2. Document the reason
3. Re-run validation after

---

## 12. Script Reference

### Navigation Scripts (scripts\nav\)

| Script | Purpose |
|--------|---------|
| `daily_nav_enhanced.py` | Calculate and store daily NAV |
| `quick_nav_update.py` | Quick NAV check without saving |

### Investor Scripts (scripts\investor\)

| Script | Purpose |
|--------|---------|
| `list_investors.py` | List all investors |
| `submit_fund_flow.py` | Submit contribution/withdrawal request |
| `match_fund_flow.py` | Match request to brokerage ACH |
| `process_fund_flow.py` | Execute share accounting |
| `close_investor_account.py` | Close an account (uses fund flow) |
| `manage_profile.py` | View/edit investor profiles |
| `generate_referral_code.py` | Generate referral codes |

### Reporting Scripts (scripts\reporting\)

| Script | Purpose |
|--------|---------|
| `generate_monthly_report.py` | Generate monthly report |
| `export_transactions_excel.py` | Export to Excel |

### Validation Scripts (scripts\validation\)

| Script | Purpose |
|--------|---------|
| `validate_comprehensive.py` | Full validation suite |
| `validate_reconciliation.py` | Reconcile with brokerage |
| `validate_with_ach.py` | Validate with ACH records |

### Utility Scripts (scripts\utilities\)

| Script | Purpose |
|--------|---------|
| `backup_database.py` | Backup database |
| `reverse_transaction.py` | Reverse a transaction |
| `update_investor_emails.py` | Update emails |
| `view_logs.py` | View system logs |

### Tax Scripts (scripts\tax\)

| Script | Purpose |
|--------|---------|
| `quarterly_tax_payment.py` | Quarterly tax prep |
| `yearend_tax_reconciliation.py` | Year-end tax reconciliation |

---

## Appendix A: Daily Checklist

### Market Days (Mon-Fri, excluding holidays)

- [ ] **4:05 PM** - NAV calculation runs (automated)
- [ ] **4:10 PM** - Check healthcheck dashboard for confirmation
- [ ] **End of day** - Review any pending fund flow requests

### Weekly (Friday)

- [ ] Run full validation: `python run.py validate`
- [ ] Review transaction log for anomalies
- [ ] Backup database

### Monthly (1st-5th)

- [ ] Generate monthly reports
- [ ] Send to investors
- [ ] Review fund performance
- [ ] Archive transaction exports

### Quarterly

- [ ] Tax payment review
- [ ] Investor communication
- [ ] System health check

### Annually

- [ ] Year-end tax reconciliation
- [ ] K-1 preparation
- [ ] Annual report generation

---

## Appendix B: Emergency Procedures

### API Down

1. Check if process is running
2. Restart: `python -m uvicorn apps.investor_portal.api.main:app --port 8000`
3. Verify with: `python test_api_regression.py`

### Database Corruption Suspected

1. **Stop all services immediately**
2. Copy current database as evidence
3. Restore from most recent backup
4. Run validation
5. Compare with Tradier records

### Tradier API Issues

1. Check Tradier status page
2. Verify API key in `.env`
3. Test with: `python scripts\trading\query_trades.py`
4. If persistent, contact Tradier support

### Investor Cannot Login

1. Check auth status: `python verify_investor.py --list`
2. If locked, wait 15 minutes
3. Reset password: `python verify_investor.py --email X --password Y`
4. Verify API is running

---

*End of Fund Administration Guide*
