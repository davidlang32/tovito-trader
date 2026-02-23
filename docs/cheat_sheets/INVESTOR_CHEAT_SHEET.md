# INVESTOR MANAGEMENT CHEAT SHEET
## All Investor Operations & Transactions

---

## 📁 WHAT'S IN THIS FOLDER

**Scripts for managing investor accounts, contributions, and withdrawals via the fund flow workflow.**

---

## 💰 FUND FLOW WORKFLOW (Contributions & Withdrawals)

All contributions and withdrawals use the **fund flow lifecycle**: submit -> match -> process.

### **Step 1: Submit Request** ⭐
**File:** `submit_fund_flow.py`
**Purpose:** Submit a new contribution or withdrawal request

```cmd
python scripts\investor\submit_fund_flow.py
```

**Prompts:**
1. Select investor
2. Choose flow type (contribution/withdrawal)
3. Enter amount
4. Confirm

**Creates:** `fund_flow_requests` record with status "pending"

---

### **Step 2: Match to Brokerage ACH** ⭐
**File:** `match_fund_flow.py`
**Purpose:** Link request to brokerage ACH transaction

```cmd
python scripts\investor\match_fund_flow.py
```

**Links:** fund_flow_request -> brokerage_transactions_raw (ACH deposit/withdrawal)

---

### **Step 3: Process Share Accounting** ⭐
**File:** `process_fund_flow.py`
**Purpose:** Execute share accounting and finalize

```cmd
python scripts\investor\process_fund_flow.py
```

**For contributions:**
- Calculates shares at current NAV
- Updates investor shares and net_investment
- Records transaction with reference_id linkage

**For withdrawals:**
- Calculates shares to redeem (proportional method)
- Records realized gain (for quarterly tax settlement)
- Disburses full amount (no tax withheld)
- Sends confirmation email

---

## 👥 INVESTOR INFORMATION

### **List Investors** ⭐
**File:** `list_investors.py`
**Purpose:** View all investor positions

```cmd
python scripts\investor\list_investors.py
```

**Shows:**
- ID, name, email
- Current shares
- Net investment
- Current value
- Returns (% and $)
- % of portfolio

---

### **Close Account**
**File:** `close_investor_account.py`
**Purpose:** Complete account closure (100% withdrawal)

```cmd
python scripts\investor\close_investor_account.py --id INVESTOR_ID
```

**When:** Investor leaving completely

**Process:**
1. Creates fund_flow_request for full withdrawal
2. Calculates realized gain (recorded for quarterly tax)
3. Disburses full value (no tax withholding)
4. Sets investor status to inactive
5. Sends confirmation email

---

## 💵 OTHER INVESTOR SCRIPTS

### **Assign Pending Contribution**
**File:** `assign_pending_contribution.py`

```cmd
python scripts\investor\assign_pending_contribution.py
```

**Purpose:** Assign ACH deposit to specific investor(s)

### **Investor Profile Management**
```cmd
python scripts\investor\manage_profile.py         # View/edit profiles
python scripts\investor\generate_referral_code.py  # Generate referral codes
```

---

## 🔄 COMMON WORKFLOWS

### **New Investor Joins**
```cmd
# 1. Money arrives (ACH in brokerage)

# 2. Submit contribution via fund flow
python scripts\investor\submit_fund_flow.py

# 3. Match to brokerage ACH
python scripts\investor\match_fund_flow.py

# 4. Process share accounting
python scripts\investor\process_fund_flow.py

# 5. Validate
python scripts\validation\validate_comprehensive.py

# 6. Backup
python scripts\utilities\backup_database.py
```

---

### **Investor Withdraws**
```cmd
# 1. Submit withdrawal request
python scripts\investor\submit_fund_flow.py

# 2. Match to brokerage ACH
python scripts\investor\match_fund_flow.py

# 3. Process (full amount disbursed, tax settled quarterly)
python scripts\investor\process_fund_flow.py

# 4. Validate
python scripts\validation\validate_comprehensive.py

# 5. Backup
python scripts\utilities\backup_database.py
```

---

## 📊 QUICK REFERENCE

| Script | Use When | Frequency |
|--------|----------|-----------|
| submit_fund_flow.py | Contribution or withdrawal | As needed |
| match_fund_flow.py | Link to brokerage ACH | As needed |
| process_fund_flow.py | Finalize transaction | As needed |
| list_investors.py | Check positions | Weekly |
| close_investor_account.py | Complete exit | Rare |
| assign_pending_contribution.py | Split deposits | As needed |
| manage_profile.py | Update investor info | As needed |

---

## ⚠️ IMPORTANT NOTES

**Before contributions:**
- Verify ACH deposit received in brokerage
- Update Daily NAV first (get current share price)
- Validate after processing

**Before withdrawals:**
- Update Daily NAV first
- Use /fund-flow/estimate API to preview (or process_fund_flow.py --preview)
- Validate after processing
- Backup database

**Tax policy (quarterly settlement):**
- Withdrawals disburse the **full amount** (no withholding)
- Realized gains are tracked in `tax_events` table
- Tax settled quarterly via `scripts/tax/quarterly_tax_payment.py`
- Monthly reports show "eligible withdrawal" (value after estimated tax)

---

## 🎯 BEST PRACTICES

1. **Always update NAV first** before processing transactions
2. **Use fund flow workflow** for all contributions and withdrawals
3. **Validate immediately** after each transaction
4. **Backup before major transactions** (large withdrawals, account closures)
5. **Match to ACH** to maintain complete audit trail

---

## 📞 TROUBLESHOOTING

**Contribution not matching shares:**
- Check NAV was updated first
- Verify share price calculation
- Run validate_comprehensive.py

**Withdrawal realized gain looks wrong:**
- Check unrealized gains (proportional method)
- Verify cost basis (net_investment)
- Gain = 37% of gain portion, settled quarterly

**ACH doesn't match fund flow:**
- Use match_fund_flow.py to link
- Verify brokerage transaction was imported via ETL
- Check dates match

---

**Most used: submit_fund_flow.py, process_fund_flow.py, list_investors.py** ⭐
