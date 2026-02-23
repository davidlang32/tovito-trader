# WITHDRAWAL SYSTEM — CURRENT STATE
## Fund Flow Lifecycle (Consolidated)

---

## STATUS: CONSOLIDATED INTO FUND FLOW

> **As of February 2026**, the original standalone withdrawal system described in this document
> has been retired and consolidated into the unified **fund flow lifecycle**. All contributions
> and withdrawals now use a single pathway. See `docs/audit/CHANGELOG.md` for full details.

---

## CURRENT WITHDRAWAL WORKFLOW

### Fund Flow Lifecycle: submit -> match -> process

**Step 1: Submit Withdrawal Request**
```cmd
python scripts\investor\submit_fund_flow.py
```
- Select investor, choose "withdrawal", enter amount
- Creates `fund_flow_requests` record (status: pending)

**Step 2: Match to Brokerage ACH**
```cmd
python scripts\investor\match_fund_flow.py
```
- Links fund flow request to brokerage ACH transfer
- Provides audit trail proving money movement

**Step 3: Process Share Accounting**
```cmd
python scripts\investor\process_fund_flow.py
```
- Calculates shares to redeem (proportional allocation)
- Records realized gain in `tax_events` table
- Disburses **full amount** to investor (no tax withholding)
- Updates investor shares, net_investment, and portfolio totals
- Sends confirmation email to investor and admin

### Investor Portal API
- `POST /fund-flow/request` — Submit withdrawal request
- `GET /fund-flow/estimate?flow_type=withdrawal&amount=5000` — Preview
- `GET /fund-flow/requests` — List all requests
- `DELETE /fund-flow/cancel/{id}` — Cancel pending request

---

## TAX POLICY: QUARTERLY SETTLEMENT

**Previous approach (retired):** 37% tax withheld at withdrawal time.

**Current approach:** No tax withholding at withdrawal. Realized gains are tracked
in the `tax_events` table (event_type: 'Realized_Gain') and settled quarterly via:

```cmd
python scripts\tax\quarterly_tax_payment.py --quarter Q --year YYYY
```

### Eligible Withdrawal
The API and monthly reports show an "eligible withdrawal" field:
- `eligible_withdrawal = current_value - estimated_tax_liability`
- `estimated_tax_liability = max(0, unrealized_gain) * 0.37`

This gives investors visibility into their after-tax withdrawal capacity.

---

## DATABASE TABLES

| Table | Role |
|-------|------|
| `fund_flow_requests` | Full lifecycle tracking (pending -> processed) |
| `transactions` | Share accounting ledger (reference_id = 'ffr-{request_id}') |
| `tax_events` | Realized gain records for quarterly settlement |
| `brokerage_transactions_raw` | Matched ACH via matched_trade_id |

> **Note:** The legacy `withdrawal_requests` table still exists in the schema
> but is no longer written to by any script or API endpoint.

---

## RETIRED COMPONENTS

The following scripts and endpoints were removed in the Phase 5 consolidation:

### Scripts Removed
- `scripts/investor/process_contribution.py`
- `scripts/investor/process_withdrawal.py`
- `scripts/investor/process_withdrawal_enhanced.py`
- `scripts/investor/request_withdrawal.py`
- `scripts/investor/submit_withdrawal_request.py`
- `scripts/investor/view_pending_withdrawals.py`
- `scripts/investor/check_pending_withdrawals.py`
- `scripts/setup/migrate_add_withdrawal_requests.py`

### API Endpoints Removed
- `DELETE /withdraw/cancel/{id}`
- `GET /withdraw/estimate`
- `GET /withdraw/pending`
- `POST /withdraw/request`

### Database Functions Removed
- `calculate_withdrawal_estimate()`
- `create_withdrawal_request()`
- `get_pending_withdrawals()`
- `cancel_withdrawal_request()`

---

*Last Updated: February 2026*
*See `docs/audit/CHANGELOG.md` for the complete audit trail of this consolidation.*
