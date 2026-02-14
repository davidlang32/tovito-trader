# 02_INVESTOR - INVESTOR MANAGEMENT CHEAT SHEET
## All Investor Operations & Transactions

---

## 📁 WHAT'S IN THIS FOLDER

**10 Scripts for managing investor accounts and transactions**

---

## 💰 CORE TRANSACTIONS (Most Used)

### **Process Contribution** ⭐
**File:** `process_contribution.py`  
**Purpose:** Record investor deposits

```cmd
python scripts\02_investor\process_contribution.py
```

**When:** Investor adds money (ACH received)

**Prompts:**
1. Select investor (1-5)
2. Enter amount
3. Confirm

**Updates:**
- Investor shares
- Daily NAV
- Transactions table

**Example:**
```
Ken contributes $1,000
→ Calculates shares at current NAV ($1.05)
→ Ken receives 952.38 shares
→ Updates position
```

---

### **Process Withdrawal** ⭐
**File:** `process_withdrawal.py`  
**Purpose:** Record withdrawals with tax calculations

```cmd
python scripts\02_investor\process_withdrawal.py
```

**When:** Investor wants to take money out

**Shows:**
- Current position
- Unrealized gains
- Tax liability (37%)
- After-tax value

**Calculates:**
- Realized gains
- Tax due
- Net proceeds

**Example:**
```
Beth withdraws $5,000
→ Shows tax breakdown
→ Realized gain: $1,200
→ Tax due: $444
→ Net proceeds: $4,556
```

---

### **Enhanced Withdrawal**
**File:** `process_withdrawal_enhanced.py`  
**Purpose:** Withdrawal with additional features

```cmd
python scripts\02_investor\process_withdrawal_enhanced.py
```

**Extra features:**
- More detailed tax breakdown
- Additional validation
- Enhanced reporting

**Use:** When you need extra detail/validation

---

## 👥 INVESTOR INFORMATION

### **List Investors** ⭐
**File:** `list_investors.py`  
**Purpose:** View all investor positions

```cmd
python scripts\02_investor\list_investors.py
```

**Shows:**
- ID, name, email
- Current shares
- Net investment
- Current value
- Returns (% and $)
- % of portfolio

**Example output:**
```
Investor 1 (20260101-01A)
  Shares: 15,000.0000
  Investment: $15,000.00
  Value: $18,750.00
  Return: +25.00%
```

---

### **Close Account**
**File:** `close_investor_account.py`  
**Purpose:** Complete account closure (100% withdrawal)

```cmd
python scripts\02_investor\close_investor_account.py
```

**When:** Investor leaving completely

**Process:**
1. Calculates full withdrawal
2. Computes final taxes
3. Processes complete payout
4. Sets status to inactive

---

## 📋 WITHDRAWAL REQUEST WORKFLOW

### **1. Request Withdrawal**
**File:** `request_withdrawal.py`

```cmd
python scripts\02_investor\request_withdrawal.py
```

**Purpose:** Investor submits withdrawal request

**Creates:** Pending withdrawal request in database

---

### **2. View Pending Withdrawals** ⭐
**File:** `view_pending_withdrawals.py`

```cmd
python scripts\02_investor\view_pending_withdrawals.py
```

**Purpose:** See all pending withdrawal requests

**Shows:**
- Request date
- Investor
- Amount requested
- Current status

---

### **3. Check Pending Withdrawals**
**File:** `check_pending_withdrawals.py`

```cmd
python scripts\02_investor\check_pending_withdrawals.py
```

**Purpose:** Check if any pending withdrawals exist

**Returns:** Count and summary

---

### **4. Submit Withdrawal Request**
**File:** `submit_withdrawal_request.py`

```cmd
python scripts\02_investor\submit_withdrawal_request.py
```

**Purpose:** Process approved withdrawal request

**Workflow:**
1. Select pending request
2. Review details
3. Process withdrawal
4. Mark as complete

---

## 💵 CONTRIBUTION MANAGEMENT

### **Assign Pending Contribution**
**File:** `assign_pending_contribution.py`

```cmd
python scripts\02_investor\assign_pending_contribution.py
```

**Purpose:** Assign ACH deposit to specific investor(s)

**When:** 
- ACH received
- Need to assign to investor(s)
- Split deposits (Ken + Beth = 1 ACH)

**Example:**
```
ACH deposit: $2,000
→ Assign $1,000 to Ken
→ Assign $1,000 to Beth
→ Total matches ACH ✓
```

---

## 🔄 COMMON WORKFLOWS

### **New Investor Joins**
```cmd
# 1. Money arrives (ACH in Tradier)

# 2. Record contribution
python scripts\02_investor\process_contribution.py

# 3. Validate
python scripts\05_validation\validate_with_ach.py

# 4. Backup
python run.py backup
```

---

### **Investor Withdraws**
```cmd
# 1. Process withdrawal
python scripts\02_investor\process_withdrawal.py

# 2. Validate
python scripts\05_validation\validate_with_ach.py

# 3. Send confirmation (shown in output)

# 4. Backup
python run.py backup
```

---

### **Withdrawal Request Process**
```cmd
# 1. Investor requests withdrawal
python scripts\02_investor\request_withdrawal.py

# 2. You review pending requests
python scripts\02_investor\view_pending_withdrawals.py

# 3. When ready, submit/process
python scripts\02_investor\submit_withdrawal_request.py

# 4. Validate
python scripts\05_validation\validate_with_ach.py
```

---

### **Split Deposit Assignment**
```cmd
# Scenario: $2,000 ACH = Ken $1K + Beth $1K

# 1. Assign pending contribution
python scripts\02_investor\assign_pending_contribution.py
   → Assign $1,000 to Ken
   → Assign $1,000 to Beth

# 2. Validate ACH matches
python scripts\05_validation\validate_with_ach.py
   → Should show: $2,000 ACH = $2,000 investor txns ✓
```

---

## 📊 QUICK REFERENCE

| Script | Use When | Frequency |
|--------|----------|-----------|
| process_contribution.py | Money received | As needed |
| process_withdrawal.py | Investor withdrawing | As needed |
| list_investors.py | Check positions | Weekly |
| request_withdrawal.py | Investor requests out | As needed |
| view_pending_withdrawals.py | Review requests | Weekly |
| submit_withdrawal_request.py | Approve withdrawal | As needed |
| assign_pending_contribution.py | Split deposits | As needed |
| close_investor_account.py | Complete exit | Rare |

---

## ⚠️ IMPORTANT NOTES

**Before contributions:**
- ✅ Verify ACH deposit received in Tradier
- ✅ Update Daily NAV first (get current share price)
- ✅ Validate after processing

**Before withdrawals:**
- ✅ Update Daily NAV first
- ✅ Review tax impact with investor
- ✅ Validate after processing
- ✅ Backup database

**Tax calculations:**
- All withdrawals calculate 37% tax
- Shows realized gains vs. cost basis
- Net proceeds = Withdrawal - Tax

---

## 🎯 BEST PRACTICES

1. **Always update NAV first** before processing transactions
2. **Validate immediately** after each transaction
3. **Backup before major transactions** (large withdrawals, account closures)
4. **Use withdrawal requests** for audit trail
5. **Assign contributions** immediately when ACH received

---

## 📞 TROUBLESHOOTING

**Contribution not matching shares:**
- Check NAV was updated first
- Verify share price calculation
- Run validate_with_ach.py

**Withdrawal tax looks wrong:**
- Check unrealized gains
- Verify cost basis (net investment)
- Tax = 37% of gain portion only

**ACH doesn't match contributions:**
- Use assign_pending_contribution.py for splits
- Validate with validate_with_ach.py
- Check dates match

---

**Most used: process_contribution.py, process_withdrawal.py, list_investors.py** ⭐
