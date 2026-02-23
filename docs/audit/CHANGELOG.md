# Tovito Trader — System Change Audit Log

This document records significant system changes, policy decisions, and data modifications for compliance and historical reference. Each entry documents what was changed, why, the scope of impact, and the date.

---

## 2026-02-22 — Consolidate Transaction Processing to Single Fund Flow Pathway

### Summary
Removed legacy transaction processing scripts and unified all investor contribution and withdrawal processing through the fund flow lifecycle (`fund_flow_requests` table). Standardized tax policy to quarterly settlement (no withholding at withdrawal). Added "eligible withdrawal" visibility for investors.

### Reason for Change
The system had two parallel paths for processing investor transactions:
1. **Legacy scripts** (`process_contribution.py`, `process_withdrawal.py`, `process_withdrawal_enhanced.py`) — wrote directly to the `transactions` table with no lifecycle tracking, no brokerage ACH linkage, and inconsistent tax handling.
2. **Fund flow workflow** (`submit_fund_flow.py` → `match_fund_flow.py` → `process_fund_flow.py`) — full lifecycle tracking via `fund_flow_requests` table with ACH matching, approval workflow, and complete audit trail.

Dual paths created data integrity risks:
- Transactions entered via legacy scripts had no `fund_flow_requests` record, making them invisible to the investor portal and ops dashboard.
- Tax withholding was inconsistent: the enhanced withdrawal script set `tax_withheld = 0`, while the fund flow path withheld 37%.
- No brokerage ACH linkage on legacy path meant we could not prove money movement for those transactions.

### Changes Made

#### Scripts Removed (8 files)
- `scripts/investor/process_contribution.py` — Legacy direct contribution processing
- `scripts/investor/process_withdrawal.py` — Legacy direct withdrawal processing
- `scripts/investor/process_withdrawal_enhanced.py` — Legacy enhanced withdrawal with approval
- `scripts/investor/request_withdrawal.py` — Created legacy `withdrawal_requests` records
- `scripts/investor/submit_withdrawal_request.py` — Submitted to legacy `withdrawal_requests` table
- `scripts/investor/view_pending_withdrawals.py` — Viewed legacy `withdrawal_requests`
- `scripts/investor/check_pending_withdrawals.py` — Checked legacy `withdrawal_requests`
- `scripts/setup/migrate_add_withdrawal_requests.py` — Migration for legacy `withdrawal_requests` table

#### API Endpoints Removed
- `DELETE /withdraw/cancel/{id}` — Cancelled legacy withdrawal requests
- `GET /withdraw/estimate` — Legacy withdrawal tax estimate
- `GET /withdraw/pending` — Listed legacy pending withdrawals
- `POST /withdraw/request` — Submitted legacy withdrawal requests
- File removed: `apps/investor_portal/api/routes/withdraw.py`
- Legacy database functions removed from `apps/investor_portal/api/models/database.py`:
  `calculate_withdrawal_estimate()`, `create_withdrawal_request()`, `get_pending_withdrawals()`, `cancel_withdrawal_request()`

#### Tax Policy Change
- **Before:** Fund flow withdrawals withheld 37% tax on realized gains at withdrawal time.
- **After:** No tax is withheld at withdrawal. Realized gains are still calculated and recorded as `tax_events` (event_type='Realized_Gain') for reporting. Tax is settled quarterly via `scripts/tax/quarterly_tax_payment.py`.
- **Affected file:** `scripts/investor/process_fund_flow.py` — `process_withdrawal()` function

#### New Feature: Eligible Withdrawal Amount
- Added `unrealized_gain`, `estimated_tax_liability`, and `eligible_withdrawal` fields to:
  - API endpoint `GET /investor/position`
  - API endpoint `GET /fund-flow/estimate` (withdrawal estimates)
  - Monthly PDF and text reports (Tax Summary section)
- Formula: `eligible_withdrawal = current_value - (max(0, unrealized_gain) * 0.37)`

#### Script Updated: close_investor_account.py
- Refactored to create `fund_flow_requests` records instead of writing directly to `transactions`
- Provides full audit trail with `reference_id = 'ffr-{request_id}'` linkage

#### Data Backfill
- Created `scripts/setup/backfill_fund_flow_requests.py` to retroactively create `fund_flow_requests` records for all historical transactions processed through legacy scripts
- All existing transactions now have corresponding lifecycle records
- Backfill marked with `request_method = 'admin'` and `notes = 'Historical backfill from transaction #{id}'`

### Database Impact
- **No tables dropped.** The `withdrawal_requests` table remains in the database (GAAP compliance — never delete records) but is no longer written to by any active code.
- **No records deleted.** All existing transaction records remain intact.
- **New records added:** `fund_flow_requests` backfill records for historical transactions.

### Documentation Updated
- `CLAUDE.md` — Removed legacy script references, added Phase 5 completion
- `docs/guides/FUND_ADMIN_GUIDE.md`
- `docs/cheat_sheets/INVESTOR_CHEAT_SHEET.md`
- `docs/cheat_sheets/operations_cheat_sheet.md`
- `docs/reference/WITHDRAWAL_DELIVERY_SUMMARY.md`
