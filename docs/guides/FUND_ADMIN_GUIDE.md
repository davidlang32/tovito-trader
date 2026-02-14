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

**Step 3:** Process initial contribution
```cmd
python scripts\investor\process_contribution.py
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

### 4.1 Process a New Contribution

**Prerequisites:**
- Funds received and cleared in brokerage account
- Current NAV calculated for today

**Step 1:** Run contribution script
```cmd
python scripts\investor\process_contribution.py
```

**Step 2:** Enter details when prompted:
- Investor ID (e.g., 20260101-01A)
- Amount (e.g., 5000)
- Date (default: today)

**Step 3:** Verify the calculation
```
============================================================
 CONTRIBUTION PREVIEW
============================================================
 Investor: David Lang (20260101-01A)
 Amount: $5,000.00
 Current NAV: $1.1587
 Shares to Issue: 4,315.2846
 
 Confirm? (y/n):
```

**Step 4:** Confirm to process

**What happens:**
1. New shares calculated: Amount / Current NAV
2. Investor's `current_shares` increased
3. Investor's `net_investment` increased
4. Transaction recorded in `transactions` table
5. Total fund shares updated

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

### 5.1 Process a Withdrawal Request

**Step 1:** Investor submits request (via portal or email)

**Step 2:** Check pending requests
```cmd
python scripts\investor\view_pending_withdrawals.py
```

**Step 3:** Calculate withdrawal details
```cmd
python scripts\investor\process_withdrawal_enhanced.py
```

**Step 4:** Enter details:
- Investor ID
- Amount requested
- Date

**Step 5:** Review tax calculation
```
============================================================
 WITHDRAWAL PREVIEW
============================================================
 Investor: David Lang (20260101-01A)
 Requested Amount: $5,000.00
 
 CALCULATION:
 Current Shares: 18,432.6185
 Current NAV: $1.1587
 Shares to Redeem: 4,315.2846
 
 TAX CALCULATION (Proportional Method):
 Cost Basis of Shares: $4,450.23
 Realized Gain: $549.77
 Tax (37%): $203.42
 
 NET PROCEEDS: $4,796.58
 
 Confirm? (y/n):
```

**Step 6:** Confirm to process

### 5.2 Withdrawal Tax Logic

The system uses **proportional allocation** (average cost method):

1. **Calculate shares to redeem:** Withdrawal Amount / Current NAV
2. **Calculate cost basis:** (Shares Redeemed / Total Shares) × Net Investment
3. **Calculate gain:** Redemption Value - Cost Basis
4. **Calculate tax:** Gain × Tax Rate (37%)
5. **Net proceeds:** Withdrawal Amount - Tax

### 5.3 Submit Withdrawal Request (for investors)

```cmd
python scripts\investor\submit_withdrawal_request.py
```

### 5.4 Withdrawal Rules

- Processed at **end of day NAV**
- Tax withheld on realized gains
- Minimum withdrawal: $500 (configurable)
- Partial withdrawals allowed
- Full withdrawal = account closure

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

### 7.1 Tax Rate Configuration

Current tax rate: **37%** (highest marginal rate)

To modify, update in:
- `apps\investor_portal\api\config.py`
- `scripts\investor\process_withdrawal_enhanced.py`

### 7.2 Quarterly Tax Payments

```cmd
python scripts\tax\quarterly_tax_payment.py
```

Reviews accumulated tax withholdings and prepares estimated payment.

### 7.3 Year-End Tax Reconciliation

```cmd
python scripts\tax\yearend_tax_reconciliation.py
```

Generates:
- Summary of all realized gains by investor
- Tax withheld vs. actual liability
- K-1 preparation data

### 7.4 Tax Records

All tax withholdings recorded in:
- `transactions` table (individual events)
- `tax_withholdings` table (summary by investor)

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
| `withdrawal_requests` | Pending withdrawal requests |
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
| `process_contribution.py` | Process new contribution |
| `process_withdrawal.py` | Process withdrawal |
| `process_withdrawal_enhanced.py` | Withdrawal with tax calculation |
| `submit_withdrawal_request.py` | Submit withdrawal request |
| `view_pending_withdrawals.py` | View pending requests |
| `close_investor_account.py` | Close an account |

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
- [ ] **End of day** - Review any pending withdrawal requests

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
