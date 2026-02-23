# Tovito Trader - Requirements Document
## Version 1.0.0 | January 2026

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [Requirements Overview](#2-requirements-overview)
3. [NAV Requirements (REQ-NAV)](#3-nav-requirements-req-nav)
4. [Investor Requirements (REQ-INV)](#4-investor-requirements-req-inv)
5. [Transaction Requirements (REQ-TXN)](#5-transaction-requirements-req-txn)
6. [Tax Requirements (REQ-TAX)](#6-tax-requirements-req-tax)
7. [Reporting Requirements (REQ-RPT)](#7-reporting-requirements-req-rpt)
8. [Validation Requirements (REQ-VAL)](#8-validation-requirements-req-val)
9. [API Requirements (REQ-API)](#9-api-requirements-req-api)
10. [Portal Requirements (REQ-PRT)](#10-portal-requirements-req-prt)
11. [Prospect Requirements (REQ-PRO)](#11-prospect-requirements-req-pro)
12. [Security Requirements (REQ-SEC)](#12-security-requirements-req-sec)
13. [Test Coverage Matrix](#13-test-coverage-matrix)
14. [Appendix: Business Rules](#appendix-business-rules)

---

## 1. Introduction

### 1.1 Purpose

This document defines the formal requirements for the Tovito Trader pooled investment fund management system. Each requirement is assigned a unique identifier for traceability to tests, code, and documentation.

### 1.2 Requirement Format

```
REQ-{CATEGORY}-{NUMBER}: {Title}
┌─────────────────────────────────────────────────────────────────┐
│ Description: What the system shall do                           │
│ Business Rule: The underlying calculation or logic              │
│ Acceptance Criteria: How to verify the requirement is met       │
│ Test Coverage: pytest test file/function that validates this    │
│ Status: Implemented | Partial | Planned | Not Started           │
│ Priority: Critical | High | Medium | Low                        │
└─────────────────────────────────────────────────────────────────┘
```

### 1.3 Requirement Categories

| Category | Prefix | Description |
|----------|--------|-------------|
| NAV | REQ-NAV | Net Asset Value calculations and storage |
| Investor | REQ-INV | Investor account management |
| Transaction | REQ-TXN | Contributions and withdrawals |
| Tax | REQ-TAX | Tax calculations and withholding |
| Reporting | REQ-RPT | Reports and statements |
| Validation | REQ-VAL | Data integrity and validation |
| API | REQ-API | External API integrations |
| Portal | REQ-PRT | Investor portal (web) |
| Prospect | REQ-PRO | Prospect tracking |
| Security | REQ-SEC | Security and access control |

### 1.4 Priority Definitions

| Priority | Definition |
|----------|------------|
| **Critical** | Core functionality; system cannot operate without it |
| **High** | Important for daily operations |
| **Medium** | Improves efficiency or user experience |
| **Low** | Nice to have; can be deferred |

---

## 2. Requirements Overview

### 2.1 Requirements Summary

| Category | Total | Critical | High | Medium | Low | Implemented |
|----------|-------|----------|------|--------|-----|-------------|
| REQ-NAV | 8 | 5 | 2 | 1 | 0 | 8 |
| REQ-INV | 7 | 3 | 3 | 1 | 0 | 7 |
| REQ-TXN | 9 | 5 | 3 | 1 | 0 | 9 |
| REQ-TAX | 6 | 4 | 2 | 0 | 0 | 6 |
| REQ-RPT | 5 | 2 | 2 | 1 | 0 | 5 |
| REQ-VAL | 8 | 4 | 3 | 1 | 0 | 8 |
| REQ-API | 5 | 3 | 2 | 0 | 0 | 5 |
| REQ-PRT | 6 | 2 | 3 | 1 | 0 | 0 |
| REQ-PRO | 4 | 1 | 2 | 1 | 0 | 4 |
| REQ-SEC | 5 | 3 | 2 | 0 | 0 | 3 |
| **Total** | **63** | **32** | **24** | **7** | **0** | **55** |

---

## 3. NAV Requirements (REQ-NAV)

### REQ-NAV-001: Daily NAV Calculation
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall calculate NAV per share daily using the formula: │
│   NAV = Total Portfolio Value / Total Shares Outstanding        │
│                                                                 │
│ Business Rule:                                                  │
│   NAV = Tradier Account Balance / SUM(investor.current_shares)  │
│   NAV must be calculated AFTER market close (4:00 PM EST)       │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - NAV calculated matches portfolio/shares within 0.0001       │
│   - NAV stored in daily_nav table                               │
│   - Calculation occurs at 4:05 PM EST daily                     │
│                                                                 │
│ Test Coverage:                                                  │
│   test_nav_calculations.py::TestBasicNAV                        │
│   test_nav_calculations.py::TestNAVAccuracy                     │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-NAV-002: Initial NAV Value
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   On fund inception (Day 1), NAV per share shall be $1.00       │
│                                                                 │
│ Business Rule:                                                  │
│   January 1, 2026: NAV = $1.00                                  │
│   Initial shares = Initial investment amount                    │
│   Example: $21,000 invested = 21,000 shares @ $1.00             │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - daily_nav record for 2026-01-01 has nav_per_share = 1.0000  │
│   - total_portfolio_value equals sum of initial investments     │
│   - total_shares equals total_portfolio_value                   │
│                                                                 │
│ Test Coverage:                                                  │
│   test_nav_calculations.py::test_initial_nav_is_one_dollar      │
│   validate_comprehensive.py::CHECK 4                            │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-NAV-003: NAV Single Source of Truth
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   All system components shall read NAV from daily_nav table.    │
│   No component shall calculate NAV independently.               │
│                                                                 │
│ Business Rule:                                                  │
│   - daily_nav table is the ONLY source of NAV values            │
│   - Scripts use get_current_nav() or get_nav_for_date()         │
│   - NAV calculations happen ONLY in nav_calculator.py           │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Contribution script reads NAV from database                 │
│   - Withdrawal script reads NAV from database                   │
│   - Monthly report reads NAV from database                      │
│   - No NAV = portfolio/shares calculations in other scripts     │
│                                                                 │
│ Test Coverage:                                                  │
│   Code review required                                          │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-NAV-004: NAV Precision
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   NAV shall be stored and displayed with 4 decimal places       │
│                                                                 │
│ Business Rule:                                                  │
│   nav_per_share REAL with 4 decimal precision                   │
│   Display format: $X.XXXX                                       │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Database stores 4+ decimal places                           │
│   - Reports display 4 decimal places                            │
│   - Calculations maintain precision throughout                  │
│                                                                 │
│ Test Coverage:                                                  │
│   test_nav_calculations.py::test_nav_precision                  │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-NAV-005: Daily Change Tracking
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall track daily change in portfolio value            │
│                                                                 │
│ Business Rule:                                                  │
│   daily_change_dollars = today_value - yesterday_value          │
│   daily_change_percent = (change / yesterday_value) * 100       │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - daily_nav stores daily_change_dollars                       │
│   - daily_nav stores daily_change_percent                       │
│   - Negative changes handled correctly                          │
│                                                                 │
│ Test Coverage:                                                  │
│   test_nav_calculations.py::TestDailyChanges                    │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-NAV-006: NAV After Contribution Unchanged
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   NAV per share shall not change when a contribution is made    │
│                                                                 │
│ Business Rule:                                                  │
│   new_shares = contribution / current_nav                       │
│   new_nav = (portfolio + contribution) / (shares + new_shares)  │
│   new_nav ≈ current_nav (within rounding)                       │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Before and after NAV differ by < 0.0001                     │
│   - Total shares increase by contribution / NAV                 │
│   - Total portfolio increases by contribution amount            │
│                                                                 │
│ Test Coverage:                                                  │
│   test_nav_calculations.py::test_nav_stays_same_after_contrib   │
│   test_contributions.py::test_scenario_2_single_contribution    │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-NAV-007: NAV History Preservation
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall preserve complete NAV history                    │
│                                                                 │
│ Business Rule:                                                  │
│   - One record per trading day                                  │
│   - Records never deleted, only soft-deleted if needed          │
│   - History supports performance calculations                   │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Query can retrieve NAV for any historical date              │
│   - Monthly performance can be calculated from history          │
│   - No gaps in trading day records                              │
│                                                                 │
│ Test Coverage:                                                  │
│   test_nav_calculations.py::test_nav_history_ordering           │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-NAV-008: Zero Shares Handling
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   If total shares is zero, NAV defaults to $1.00                │
│                                                                 │
│ Business Rule:                                                  │
│   IF total_shares = 0 THEN nav_per_share = 1.0                  │
│   This handles initial fund setup before first investment       │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - No division by zero errors                                  │
│   - Empty fund shows NAV = $1.00                                │
│                                                                 │
│ Test Coverage:                                                  │
│   test_nav_calculations.py::test_zero_shares_returns_one_dollar │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Medium                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 4. Investor Requirements (REQ-INV)

### REQ-INV-001: Investor Registration
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall maintain investor account records                │
│                                                                 │
│ Business Rule:                                                  │
│   Required fields: investor_id, name, initial_capital, join_dt  │
│   Optional fields: email, phone, notes                          │
│   investor_id format: YYYYMMDD-NNA (date + sequence + alpha)    │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - All required fields validated on creation                   │
│   - investor_id is unique                                       │
│   - join_date cannot be in the future                           │
│                                                                 │
│ Test Coverage:                                                  │
│   test_database_validation.py::test_investor_creation           │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-INV-002: Investor Status Management
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Investors shall have a status indicating account state        │
│                                                                 │
│ Business Rule:                                                  │
│   Valid statuses: Active, Inactive, Suspended                   │
│   Active = participating in fund                                │
│   Inactive = fully withdrawn, account closed                    │
│   Suspended = temporarily restricted                            │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Status transitions are logged                               │
│   - Only Active investors included in share calculations        │
│   - Inactive investors excluded from percentage calculations    │
│                                                                 │
│ Test Coverage:                                                  │
│   test_withdrawals.py::test_full_withdrawal_closes_account      │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-INV-003: Current Shares Tracking
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall track each investor's current share count        │
│                                                                 │
│ Business Rule:                                                  │
│   current_shares increased by contributions                     │
│   current_shares decreased by withdrawals                       │
│   current_shares >= 0 always                                    │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Shares updated atomically with transactions                 │
│   - Share count matches transaction history                     │
│   - No negative share counts                                    │
│                                                                 │
│ Test Coverage:                                                  │
│   test_contributions.py::test_single_contribution               │
│   test_withdrawals.py::test_single_withdrawal                   │
│   validate_comprehensive.py::CHECK 1                            │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-INV-004: Net Investment Tracking
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall track each investor's net investment (cost basis)│
│                                                                 │
│ Business Rule:                                                  │
│   net_investment = SUM(contributions) - SUM(withdrawn_principal)│
│   This is the cost basis for tax calculations                   │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - net_investment matches sum of transactions                  │
│   - Updated correctly on contributions and withdrawals          │
│   - Never negative                                              │
│                                                                 │
│ Test Coverage:                                                  │
│   validate_comprehensive.py::CHECK 8                            │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-INV-005: Portfolio Percentage Calculation
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall calculate each investor's portfolio percentage   │
│                                                                 │
│ Business Rule:                                                  │
│   percentage = (investor_shares / total_shares) * 100           │
│   SUM(all investor percentages) = 100.00%                       │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Percentages sum to 100% (within 0.01%)                      │
│   - Percentages update after any transaction                    │
│   - View v_investor_positions provides percentages              │
│                                                                 │
│ Test Coverage:                                                  │
│   validate_comprehensive.py::CHECK 2                            │
│   test_contributions.py::test_investor_percentage_changes       │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-INV-006: Investor Value Calculation
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall calculate investor's current position value      │
│                                                                 │
│ Business Rule:                                                  │
│   current_value = current_shares * current_nav                  │
│   unrealized_gain = current_value - net_investment              │
│   return_percent = (unrealized_gain / net_investment) * 100     │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Value calculation uses latest NAV                           │
│   - Unrealized gain can be negative (loss)                      │
│   - Return percent handles zero investment edge case            │
│                                                                 │
│ Test Coverage:                                                  │
│   test_contributions.py::test_contribution_increases_unreal_gain│
│   nav_calculator.py::get_investor_value()                       │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-INV-007: Investor Listing
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall provide list of all investors with positions     │
│                                                                 │
│ Business Rule:                                                  │
│   List shows: name, shares, value, percentage, status           │
│   Filterable by status (Active, Inactive, All)                  │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - list_investors.py displays all active investors             │
│   - Can filter by status                                        │
│   - Totals match daily_nav values                               │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing                                                │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Medium                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 5. Transaction Requirements (REQ-TXN)

### REQ-TXN-001: Transaction Recording
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   All financial transactions shall be recorded in database      │
│                                                                 │
│ Business Rule:                                                  │
│   Required: date, investor_id, type, amount, share_price, shares│
│   Types: Initial, Contribution, Withdrawal, Tax_Payment, Fee    │
│   Transactions are immutable (soft delete only)                 │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Every contribution creates transaction record               │
│   - Every withdrawal creates transaction record                 │
│   - Transactions cannot be modified, only reversed              │
│                                                                 │
│ Test Coverage:                                                  │
│   test_contributions.py::test_single_contribution               │
│   test_withdrawals.py::test_single_withdrawal                   │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-TXN-002: Contribution Processing
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall process investor contributions                   │
│                                                                 │
│ Business Rule:                                                  │
│   shares_purchased = contribution_amount / current_nav          │
│   Update: investor.current_shares += shares_purchased           │
│   Update: investor.net_investment += contribution_amount        │
│   Record: transaction with type = 'Contribution'                │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Shares calculated at current NAV                            │
│   - Investor record updated                                     │
│   - Transaction logged                                          │
│   - NAV unchanged after processing                              │
│                                                                 │
│ Test Coverage:                                                  │
│   test_contributions.py::TestContributionWorkflow               │
│   test_contributions.py::TestContributionScenarios              │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-TXN-003: Withdrawal Request Submission
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Investors shall be able to submit withdrawal requests         │
│                                                                 │
│ Business Rule:                                                  │
│   Request includes: investor_id, requested_amount, notes        │
│   Request status: PENDING → APPROVED/REJECTED → PROCESSED       │
│   Estimated tax shown at request time                           │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Request recorded in fund_flow_requests table                │
│   - Status set to PENDING                                       │
│   - Estimated tax and net proceeds displayed                    │
│   - Cannot request more than current value                      │
│                                                                 │
│ Test Coverage:                                                  │
│   pytest tests/test_fund_flow.py (automated)                    │
│                                                                 │
│ Status: Implemented (consolidated into fund flow workflow)       │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-TXN-004: Withdrawal Processing
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall process approved withdrawals                     │
│                                                                 │
│ Business Rule:                                                  │
│   shares_removed = withdrawal_amount / current_nav              │
│   Update: investor.current_shares -= shares_removed             │
│   Update: investor.net_investment -= principal_portion          │
│   Record: transaction with type = 'Withdrawal'                  │
│   Record: tax_event with realized gain and tax                  │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Tax calculated proportionally (see REQ-TAX-001)             │
│   - Investor shares reduced                                     │
│   - Transaction and tax_event logged                            │
│   - Cannot withdraw more than current value                     │
│                                                                 │
│ Test Coverage:                                                  │
│   test_withdrawals.py::TestWithdrawalWorkflow                   │
│   test_withdrawals.py::TestWithdrawalScenarios                  │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-TXN-005: Full Withdrawal (Account Closure)
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Investor can withdraw entire position and close account       │
│                                                                 │
│ Business Rule:                                                  │
│   withdrawal_amount = current_shares * current_nav              │
│   All unrealized gain becomes realized                          │
│   investor.status set to 'Inactive'                             │
│   investor.current_shares set to 0                              │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Full value withdrawn                                        │
│   - All gain taxed at 37%                                       │
│   - Account marked Inactive                                     │
│   - Investor excluded from future calculations                  │
│                                                                 │
│ Test Coverage:                                                  │
│   test_withdrawals.py::test_full_withdrawal_closes_account      │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-TXN-006: Transaction Amount Validation
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Transaction amounts shall be validated before processing      │
│                                                                 │
│ Business Rule:                                                  │
│   Contribution: amount > 0                                      │
│   Withdrawal: 0 < amount <= current_value                       │
│   Amount must be numeric                                        │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Negative amounts rejected                                   │
│   - Withdrawals exceeding value rejected                        │
│   - Non-numeric input rejected                                  │
│   - Clear error messages displayed                              │
│                                                                 │
│ Test Coverage:                                                  │
│   test_withdrawals.py::test_withdrawal_exceeds_balance          │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-TXN-007: Transaction Reversal
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall support reversing erroneous transactions         │
│                                                                 │
│ Business Rule:                                                  │
│   Original transaction soft-deleted (is_deleted = 1)            │
│   Reversing transaction created with opposite amount            │
│   Investor shares/investment adjusted                           │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Reversal creates new transaction, doesn't modify original   │
│   - Audit trail preserved                                       │
│   - Investor totals corrected                                   │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing (reverse_transaction.py)                       │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-TXN-008: Multiple Same-Day Transactions
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall handle multiple transactions on same day         │
│                                                                 │
│ Business Rule:                                                  │
│   Each transaction uses NAV at time of processing               │
│   Multiple contributions from different investors OK            │
│   Multiple transactions from same investor OK                   │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - All transactions recorded individually                      │
│   - Each uses correct NAV                                       │
│   - Daily NAV updated once with total changes                   │
│                                                                 │
│ Test Coverage:                                                  │
│   test_contributions.py::test_multiple_contributions_same_day   │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-TXN-009: Transaction History Query
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall provide transaction history queries              │
│                                                                 │
│ Business Rule:                                                  │
│   Filter by: investor, date range, type                         │
│   Sort by: date (asc/desc)                                      │
│   Include: all transaction details                              │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Can retrieve all transactions for an investor               │
│   - Can filter by date range                                    │
│   - Can filter by transaction type                              │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing (export_transactions_excel.py)                 │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Medium                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Tax Requirements (REQ-TAX)

### REQ-TAX-001: Proportional Gain Calculation
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Tax shall be calculated on proportional realized gain only    │
│                                                                 │
│ Business Rule:                                                  │
│   unrealized_gain = current_value - net_investment              │
│   proportion = withdrawal_amount / current_value                │
│   realized_gain = unrealized_gain * proportion                  │
│                                                                 │
│   Example:                                                      │
│   - Investment: $19,000, Value: $23,712, Gain: $4,712           │
│   - Withdraw $50: proportion = 50/23712 = 0.211%                │
│   - Realized gain = $4,712 × 0.211% = $9.94                     │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Tax only on gain portion, not principal                     │
│   - Proportional to amount withdrawn                            │
│   - Handles losses (no tax)                                     │
│                                                                 │
│ Test Coverage:                                                  │
│   test_withdrawals.py::test_proportional_gain_calculation       │
│   test_withdrawals.py::TestWithdrawalTaxCalculations            │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-TAX-002: Tax Rate Application
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall apply 37% tax rate on realized gains             │
│                                                                 │
│ Business Rule:                                                  │
│   tax_withheld = realized_gain * 0.37                           │
│   Tax rate configurable via TAX_RATE environment variable       │
│   Default: 37% (highest federal bracket)                        │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Tax calculated as 37% of realized gain                      │
│   - Tax rate can be configured                                  │
│   - No tax when realized_gain <= 0                              │
│                                                                 │
│ Test Coverage:                                                  │
│   test_withdrawals.py::test_basic_tax_calculation               │
│   test_withdrawals.py::test_full_withdrawal_with_gain           │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-TAX-003: Net Proceeds Calculation
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall calculate net proceeds after tax                 │
│                                                                 │
│ Business Rule:                                                  │
│   net_proceeds = withdrawal_amount - tax_withheld               │
│   This is the amount investor actually receives                 │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Net proceeds displayed before confirmation                  │
│   - Net proceeds = withdrawal - tax                             │
│   - Full amount if no gain (net_proceeds = withdrawal)          │
│                                                                 │
│ Test Coverage:                                                  │
│   test_withdrawals.py::test_withdrawal_with_loss                │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-TAX-004: No Tax on Losses
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   No tax shall be withheld when position is at a loss           │
│                                                                 │
│ Business Rule:                                                  │
│   IF unrealized_gain <= 0 THEN tax_withheld = 0                 │
│   Investor receives full withdrawal amount                      │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Loss positions have zero tax                                │
│   - Net proceeds equals withdrawal amount                       │
│   - System displays "no tax" message                            │
│                                                                 │
│ Test Coverage:                                                  │
│   test_withdrawals.py::test_withdrawal_with_loss                │
│   test_withdrawals.py::test_withdrawal_all_basis_no_tax         │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-TAX-005: Tax Event Recording
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   All tax events shall be recorded for reporting                │
│                                                                 │
│ Business Rule:                                                  │
│   Record: date, investor_id, withdrawal_amount, realized_gain   │
│   Record: tax_due, net_proceeds, tax_rate                       │
│   Used for year-end tax reporting                               │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Every withdrawal creates tax_event record                   │
│   - Tax events queryable by investor and date                   │
│   - Year-to-date tax totals available                           │
│                                                                 │
│ Test Coverage:                                                  │
│   test_withdrawals.py::TestTaxEventLogging                      │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-TAX-006: Principal/Gain Breakdown Display
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall display clear principal vs gain breakdown        │
│                                                                 │
│ Business Rule:                                                  │
│   principal_portion = withdrawal_amount - realized_gain         │
│   Display shows: principal (no tax), gain (taxed), tax, net     │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Withdrawal screen shows breakdown                           │
│   - Principal clearly marked "no tax"                           │
│   - Gain portion and tax clearly shown                          │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing                                                │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 7. Reporting Requirements (REQ-RPT)

### REQ-RPT-001: Monthly Statement Generation
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall generate monthly account statements              │
│                                                                 │
│ Business Rule:                                                  │
│   Statement includes:                                           │
│   - Current position (shares, value, NAV)                       │
│   - Month transactions                                          │
│   - Performance (start NAV, end NAV, return %)                  │
│   - Tax summary if withdrawals occurred                         │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - PDF generated for each investor                             │
│   - Data matches database records                               │
│   - Professional formatting                                     │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing (generate_monthly_report.py)                   │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-RPT-002: Report NAV from Database
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Reports shall use NAV values from daily_nav table             │
│                                                                 │
│ Business Rule:                                                  │
│   Reports must NOT calculate NAV independently                  │
│   Use get_nav_for_date() for historical NAV                     │
│   Consistent with REQ-NAV-003 (single source of truth)          │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Report NAV matches daily_nav table                          │
│   - No NAV calculation in report generator                      │
│                                                                 │
│ Test Coverage:                                                  │
│   Code review                                                   │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-RPT-003: Report Email Delivery
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Reports shall be delivered via email                          │
│                                                                 │
│ Business Rule:                                                  │
│   Email includes:                                               │
│   - PDF attachment                                              │
│   - Summary in email body                                       │
│   - Professional formatting                                     │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - PDF attached to email                                       │
│   - Email logged in email_logs table                            │
│   - Failed deliveries logged                                    │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing (test_email.py)                                │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-RPT-004: Transaction Export
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall export transactions to Excel                     │
│                                                                 │
│ Business Rule:                                                  │
│   Export includes: all transaction fields                       │
│   Filter by: investor, date range                               │
│   Format: XLSX with proper headers                              │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Excel file generated                                        │
│   - All columns properly labeled                                │
│   - Dates formatted correctly                                   │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing (export_transactions_excel.py)                 │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-RPT-005: Prospect Report Generation
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall generate fund performance reports for prospects  │
│                                                                 │
│ Business Rule:                                                  │
│   Prospect report includes:                                     │
│   - Fund performance summary                                    │
│   - NAV history chart                                           │
│   - No investor PII                                             │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - PDF generated without investor details                      │
│   - Performance metrics accurate                                │
│   - Professional marketing quality                              │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing (send_prospect_report.py)                      │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Medium                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 8. Validation Requirements (REQ-VAL)

### REQ-VAL-001: Share Total Consistency
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Sum of investor shares shall match daily_nav total_shares     │
│                                                                 │
│ Business Rule:                                                  │
│   SUM(investors.current_shares WHERE status='Active')           │
│   = daily_nav.total_shares (latest)                             │
│   Tolerance: 0.01 shares                                        │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Validation check passes                                     │
│   - Mismatch triggers alert                                     │
│                                                                 │
│ Test Coverage:                                                  │
│   validate_comprehensive.py::CHECK 1                            │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-VAL-002: Percentage Sum Validation
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Investor percentages shall sum to 100%                        │
│                                                                 │
│ Business Rule:                                                  │
│   SUM(investor percentage) = 100.00%                            │
│   Tolerance: 0.01%                                              │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Validation check passes                                     │
│   - Shows breakdown by investor                                 │
│                                                                 │
│ Test Coverage:                                                  │
│   validate_comprehensive.py::CHECK 2                            │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-VAL-003: NAV Calculation Verification
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Stored NAV shall match calculated NAV                         │
│                                                                 │
│ Business Rule:                                                  │
│   stored_nav = portfolio_value / total_shares                   │
│   Tolerance: 0.0001                                             │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Validation check passes                                     │
│   - Identifies any miscalculated entries                        │
│                                                                 │
│ Test Coverage:                                                  │
│   validate_comprehensive.py::CHECK 3, CHECK 6                   │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-VAL-004: Initial NAV Validation
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   January 1, 2026 NAV shall be $1.00                            │
│                                                                 │
│ Business Rule:                                                  │
│   daily_nav WHERE date='2026-01-01' has nav_per_share = 1.0000  │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Validation check passes                                     │
│   - Alerts if Jan 1 NAV is wrong                                │
│                                                                 │
│ Test Coverage:                                                  │
│   validate_comprehensive.py::CHECK 4                            │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-VAL-005: Portfolio Value Consistency
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Day 1 portfolio shall match sum of investments                │
│                                                                 │
│ Business Rule:                                                  │
│   Jan 1 total_portfolio_value = SUM(net_investment)             │
│   Tolerance: $1.00                                              │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Validation check passes                                     │
│   - Identifies missing/extra amounts                            │
│                                                                 │
│ Test Coverage:                                                  │
│   validate_comprehensive.py::CHECK 5                            │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-VAL-006: No Negative Values
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall prevent negative shares and investments          │
│                                                                 │
│ Business Rule:                                                  │
│   current_shares >= 0                                           │
│   net_investment >= 0                                           │
│   total_portfolio_value >= 0                                    │
│   nav_per_share > 0                                             │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Validation check passes                                     │
│   - Database constraints prevent negatives                      │
│                                                                 │
│ Test Coverage:                                                  │
│   validate_comprehensive.py::CHECK 7                            │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-VAL-007: Transaction Sum Verification
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Transaction sum shall match net_investment                    │
│                                                                 │
│ Business Rule:                                                  │
│   SUM(transactions.amount) = investor.net_investment            │
│   For each investor                                             │
│   Tolerance: $0.01                                              │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Validation check passes for all investors                   │
│   - Identifies missing transactions                             │
│                                                                 │
│ Test Coverage:                                                  │
│   validate_comprehensive.py::CHECK 8                            │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-VAL-008: Daily Validation Automation
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Validation shall run automatically after NAV updates          │
│                                                                 │
│ Business Rule:                                                  │
│   Run validate_comprehensive.py after daily NAV update          │
│   Alert admin if any check fails                                │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Validation in daily scheduled task                          │
│   - Email alert on failures                                     │
│   - Logs validation results                                     │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing                                                │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Medium                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 9. API Requirements (REQ-API)

### REQ-API-001: Tradier Account Balance
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall fetch account balance from Tradier API           │
│                                                                 │
│ Business Rule:                                                  │
│   Endpoint: GET /accounts/{id}/balances                         │
│   Response: total_equity used for NAV calculation               │
│   Frequency: Daily at 4:05 PM EST                               │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - API call succeeds                                           │
│   - total_equity parsed correctly                               │
│   - Error handling for API failures                             │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing (python run.py api)                            │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-API-002: Tradier Positions
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall fetch positions from Tradier API                 │
│                                                                 │
│ Business Rule:                                                  │
│   Endpoint: GET /accounts/{id}/positions                        │
│   Response: List of current holdings                            │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Positions retrieved successfully                            │
│   - Symbol, quantity, cost parsed                               │
│   - Empty positions handled                                     │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing                                                │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-API-003: Tradier Market Status
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall check market open/close status                   │
│                                                                 │
│ Business Rule:                                                  │
│   Endpoint: GET /markets/clock                                  │
│   Used to determine if NAV update should run                    │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Market status retrieved                                     │
│   - Holidays detected                                           │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing                                                │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-API-004: Tradier Transaction History
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall fetch transaction history from Tradier           │
│                                                                 │
│ Business Rule:                                                  │
│   Endpoint: GET /accounts/{id}/history                          │
│   Used to sync trades to local database                         │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - History retrieved for date range                            │
│   - Trades parsed and categorized                               │
│   - Duplicates prevented                                        │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing (sync_tradier_transactions.py)                 │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-API-005: Tradier Streaming Quotes
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall receive real-time quotes via WebSocket           │
│                                                                 │
│ Business Rule:                                                  │
│   WebSocket connection to Tradier streaming API                 │
│   Subscribe to: SGOV, TQQQ, SPY quotes                          │
│   Used for Market Monitor real-time display                     │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - WebSocket connects successfully                             │
│   - Quotes received in real-time                                │
│   - Auto-reconnect on disconnect                                │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing (tradier_streaming.py)                         │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 10. Portal Requirements (REQ-PRT)

### REQ-PRT-001: Investor Authentication
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Investors shall authenticate to access portal                 │
│                                                                 │
│ Business Rule:                                                  │
│   Login with email + password                                   │
│   JWT token for session management                              │
│   Session timeout: 30 minutes                                   │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Login endpoint returns JWT token                            │
│   - Invalid credentials rejected                                │
│   - Token required for protected endpoints                      │
│                                                                 │
│ Test Coverage:                                                  │
│   test_portal_api.py (planned)                                  │
│                                                                 │
│ Status: Planned                                                 │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-PRT-002: Position View
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Investors shall view their current position                   │
│                                                                 │
│ Business Rule:                                                  │
│   Display: shares, NAV, value, gain, return %                   │
│   Data from: investors table + daily_nav                        │
│   Investor sees only their own data                             │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Position endpoint returns investor data                     │
│   - Values match database                                       │
│   - Other investor data not accessible                          │
│                                                                 │
│ Test Coverage:                                                  │
│   test_portal_api.py (planned)                                  │
│                                                                 │
│ Status: Planned                                                 │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-PRT-003: NAV History View
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Investors shall view NAV history for performance charts       │
│                                                                 │
│ Business Rule:                                                  │
│   Return: date, nav_per_share, daily_change_percent             │
│   Filter by: date range                                         │
│   Used for: interactive performance chart                       │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - NAV history endpoint returns data                           │
│   - Filterable by date range                                    │
│   - Data supports charting                                      │
│                                                                 │
│ Test Coverage:                                                  │
│   test_portal_api.py (planned)                                  │
│                                                                 │
│ Status: Planned                                                 │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-PRT-004: Withdrawal Request Submission
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Investors shall submit withdrawal requests via portal         │
│                                                                 │
│ Business Rule:                                                  │
│   Submit: requested_amount, notes                               │
│   Response: estimated_tax, estimated_net_proceeds               │
│   Status: PENDING until processed                               │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Withdrawal request created in database                      │
│   - Tax estimate shown                                          │
│   - Cannot exceed current value                                 │
│                                                                 │
│ Test Coverage:                                                  │
│   test_portal_api.py (planned)                                  │
│                                                                 │
│ Status: Planned                                                 │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-PRT-005: Withdrawal Status View
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Investors shall view status of withdrawal requests            │
│                                                                 │
│ Business Rule:                                                  │
│   Display: request_id, amount, status, submitted_at             │
│   Status: PENDING, APPROVED, REJECTED, PROCESSED                │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - List of requests returned                                   │
│   - Status updated in real-time                                 │
│   - Only investor's own requests shown                          │
│                                                                 │
│ Test Coverage:                                                  │
│   test_portal_api.py (planned)                                  │
│                                                                 │
│ Status: Planned                                                 │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-PRT-006: Document Download
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Investors shall download statements and documents             │
│                                                                 │
│ Business Rule:                                                  │
│   Available: monthly statements, tax summaries                  │
│   Format: PDF                                                   │
│   Only investor's own documents accessible                      │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Document list endpoint returns available docs               │
│   - Download endpoint returns PDF                               │
│   - Other investor documents not accessible                     │
│                                                                 │
│ Test Coverage:                                                  │
│   test_portal_api.py (planned)                                  │
│                                                                 │
│ Status: Planned                                                 │
│ Priority: Medium                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 11. Prospect Requirements (REQ-PRO)

### REQ-PRO-001: Prospect Tracking
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall track potential investors (prospects)            │
│                                                                 │
│ Business Rule:                                                  │
│   Store: name, email, phone, source, notes, status              │
│   Status: New, Contacted, Interested, Converted, Declined       │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Prospects stored in prospects table                         │
│   - Can add/edit/list prospects                                 │
│   - Status trackable                                            │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing (add_prospect.py, list_prospects.py)           │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-PRO-002: Prospect Import
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall import prospects from CSV                        │
│                                                                 │
│ Business Rule:                                                  │
│   CSV columns: Name, Email, Phone, Source, Notes                │
│   Email required, others optional                               │
│   Duplicate emails detected                                     │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - CSV parsed successfully                                     │
│   - Duplicates skipped with warning                             │
│   - Valid prospects imported                                    │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing (import_prospects.py)                          │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-PRO-003: Prospect Report Email
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall email fund performance reports to prospects      │
│                                                                 │
│ Business Rule:                                                  │
│   Report: fund performance, no investor PII                     │
│   Test mode: send to admin only                                 │
│   Live mode: send to prospect list                              │
│   Log: all communications in prospect_communications            │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - PDF attached to email                                       │
│   - Test mode works                                             │
│   - Communications logged                                       │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing (send_prospect_report.py --test-email)         │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-PRO-004: Communication Logging
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   All prospect communications shall be logged                   │
│                                                                 │
│ Business Rule:                                                  │
│   Log: date, prospect_id, type, subject, status                 │
│   Types: email, call, meeting                                   │
│   Used for: audit trail, follow-up tracking                     │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Every email logged                                          │
│   - Query by prospect                                           │
│   - Query by date range                                         │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing                                                │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Medium                                                │
└─────────────────────────────────────────────────────────────────┘
```

---

## 12. Security Requirements (REQ-SEC)

### REQ-SEC-001: API Key Protection
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   API keys shall be stored securely                             │
│                                                                 │
│ Business Rule:                                                  │
│   API keys in environment variables or .env file                │
│   Never in source code or logs                                  │
│   .env in .gitignore                                            │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - No API keys in code                                         │
│   - .env file excluded from git                                 │
│   - Keys loaded from environment                                │
│                                                                 │
│ Test Coverage:                                                  │
│   Code review                                                   │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-SEC-002: PII Protection
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Investor PII shall be protected                               │
│                                                                 │
│ Business Rule:                                                  │
│   PII: name, email, phone, SSN (future)                         │
│   PII masked in logs                                            │
│   PII excluded from prospect reports                            │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Logs use safe_logging (no PII)                              │
│   - Prospect reports have no investor details                   │
│   - API responses masked appropriately                          │
│                                                                 │
│ Test Coverage:                                                  │
│   Code review                                                   │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-SEC-003: Database Backup
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Database shall be backed up regularly                         │
│                                                                 │
│ Business Rule:                                                  │
│   Backup before any risky operation                             │
│   Daily automated backup                                        │
│   Retention: 30 days minimum                                    │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Backup script exists                                        │
│   - Backups timestamped                                         │
│   - Restore process documented                                  │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing (backup_database.py)                           │
│                                                                 │
│ Status: Implemented                                             │
│ Priority: Critical                                              │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-SEC-004: Portal Authentication Security
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   Portal shall implement secure authentication                  │
│                                                                 │
│ Business Rule:                                                  │
│   Passwords hashed with bcrypt                                  │
│   JWT tokens with expiration                                    │
│   HTTPS required in production                                  │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - Passwords not stored in plaintext                           │
│   - Tokens expire appropriately                                 │
│   - Failed logins rate-limited                                  │
│                                                                 │
│ Test Coverage:                                                  │
│   test_portal_api.py (planned)                                  │
│                                                                 │
│ Status: Planned                                                 │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### REQ-SEC-005: Audit Trail
```
┌─────────────────────────────────────────────────────────────────┐
│ Description:                                                    │
│   System shall maintain audit trail of changes                  │
│                                                                 │
│ Business Rule:                                                  │
│   Log: timestamp, table, record_id, action, old/new values      │
│   Actions: INSERT, UPDATE, DELETE                               │
│   Used for: compliance, debugging, reversal                     │
│                                                                 │
│ Acceptance Criteria:                                            │
│   - audit_log table populated                                   │
│   - Changes queryable                                           │
│   - Supports transaction reversal                               │
│                                                                 │
│ Test Coverage:                                                  │
│   Manual testing                                                │
│                                                                 │
│ Status: Partial (table exists, not fully populated)             │
│ Priority: High                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## 13. Test Coverage Matrix

### 13.1 Requirements by Test File

| Test File | Requirements Covered |
|-----------|---------------------|
| `test_nav_calculations.py` | REQ-NAV-001, 002, 004, 005, 006, 007, 008 |
| `test_contributions.py` | REQ-TXN-002, 008, REQ-INV-003, 005, 006 |
| `test_withdrawals.py` | REQ-TXN-004, 005, 006, REQ-TAX-001, 002, 003, 004, 005 |
| `test_database_validation.py` | REQ-INV-001 |
| `validate_comprehensive.py` | REQ-VAL-001, 002, 003, 004, 005, 006, 007 |
| `test_portal_api.py` (planned) | REQ-PRT-001, 002, 003, 004, 005, 006 |

### 13.2 Coverage Summary

| Status | Count | Percentage |
|--------|-------|------------|
| Automated tests | 35 | 56% |
| Manual testing | 15 | 24% |
| Code review | 5 | 8% |
| Planned | 8 | 12% |
| **Total** | **63** | **100%** |

### 13.3 Test Gaps (Needs Coverage)

| Requirement | Gap | Priority |
|-------------|-----|----------|
| REQ-NAV-003 | Need automated check for no NAV calculations in scripts | High |
| REQ-TXN-003 | Need automated tests for withdrawal request submission | Medium |
| REQ-TXN-007 | Need automated tests for transaction reversal | Medium |
| REQ-SEC-005 | Need tests for audit trail population | High |
| REQ-PRT-* | All portal requirements need tests (planned) | High |

---

## Appendix: Business Rules

### A.1 NAV Calculation Formula

```
NAV per Share = Total Portfolio Value / Total Shares Outstanding

Where:
- Total Portfolio Value = Tradier Account Balance (total_equity)
- Total Shares = SUM(investor.current_shares WHERE status = 'Active')
```

### A.2 Share Purchase Formula (Contribution)

```
Shares Purchased = Contribution Amount / Current NAV

Example:
- Contribution: $5,000
- Current NAV: $1.0526
- Shares: $5,000 / $1.0526 = 4,750.095 shares
```

### A.3 Tax Calculation Formula (Withdrawal)

```
Unrealized Gain = Current Value - Net Investment
Proportion = Withdrawal Amount / Current Value
Realized Gain = Unrealized Gain × Proportion
Tax Withheld = Realized Gain × Tax Rate (37%)
Net Proceeds = Withdrawal Amount - Tax Withheld

Example:
- Net Investment: $19,000
- Current Value: $23,712.18
- Unrealized Gain: $4,712.18
- Withdrawal: $50
- Proportion: 50 / 23712.18 = 0.211%
- Realized Gain: $4,712.18 × 0.211% = $9.94
- Tax: $9.94 × 37% = $3.68
- Net Proceeds: $50 - $3.68 = $46.32
```

### A.4 Portfolio Percentage Formula

```
Investor Percentage = (Investor Shares / Total Shares) × 100

Validation: SUM(all percentages) = 100.00%
```

### A.5 Daily Change Calculation

```
Daily Change ($) = Today's Portfolio Value - Yesterday's Portfolio Value
Daily Change (%) = (Daily Change ($) / Yesterday's Value) × 100
```

---

## Document History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0.0 | 2026-01-31 | David/Claude | Initial requirements document |

---

*This document defines the authoritative requirements for Tovito Trader. All development and testing shall trace back to these requirements.*
