# 04_TRADING - TRADING JOURNAL CHEAT SHEET
## Trading Activity Tracking & Analysis

---

## 📁 WHAT'S IN THIS FOLDER

**4 Scripts for trading journal and performance analysis**

---

## 📥 IMPORT TRADING HISTORY

### **Import Tradier History** ⭐⭐
**File:** `import_tradier_history.py`  
**Purpose:** Import all trades from Tradier into database

---

### **COMMANDS:**

**Preview what will be imported:**
```cmd
python scripts\04_trading\import_tradier_history.py --check
```

**Actually import:**
```cmd
python scripts\04_trading\import_tradier_history.py --import
```

**Import specific date range:**
```cmd
python scripts\04_trading\import_tradier_history.py --import --start-date 2026-01-01
```

---

### **WHAT IT IMPORTS:**

- ✅ Stock trades (SGOV, TQQQ, etc.)
- ✅ Options trades (all details)
- ✅ ACH deposits/withdrawals
- ✅ Commissions & fees
- ✅ Dividends
- ✅ Interest

**Stored in:** `trades` table in database

**Auto-categorizes:**
- Trade (buy/sell)
- ACH (deposit/withdrawal)
- Fee (commission)
- Dividend
- Interest

---

### **WHEN TO RUN:**

**Initial setup:** Once (imports entire history)

**Ongoing:** Weekly or monthly
```cmd
# Get new trades from last week
python scripts\04_trading\import_tradier_history.py --import --start-date 2026-01-20
```

---

## 🔍 QUERY TRADING DATA

### **Query Trades** ⭐⭐⭐
**File:** `query_trades.py`  
**Purpose:** View and analyze trading activity

---

### **INTERACTIVE MENU:**
```cmd
python scripts\04_trading\query_trades.py
```

**Menu options:**
1. View ACH summary
2. View trades for specific symbol
3. View all symbols summary
4. View monthly activity
5. View overall summary
6. Exit

---

### **QUICK QUERIES:**

**ACH deposits/withdrawals:**
```cmd
python scripts\04_trading\query_trades.py --ach
```

**Trades for specific symbol:**
```cmd
python scripts\04_trading\query_trades.py --symbol SGOV
python scripts\04_trading\query_trades.py --symbol TQQQ
```

**All symbols summary:**
```cmd
python scripts\04_trading\query_trades.py --symbols
```

**Monthly breakdown:**
```cmd
python scripts\04_trading\query_trades.py --monthly
```

**Overall statistics:**
```cmd
python scripts\04_trading\query_trades.py --summary
```

---

### **EXAMPLE OUTPUTS:**

**ACH Summary:**
```
Date         Type        Amount
2026-01-02   Deposit     $2,000.00
2026-01-21   Deposit     $4,000.00
Total Deposits: $6,000.00
```

**Symbol Summary:**
```
Symbol  Trades  Total P&L    Commissions
SGOV    45      $1,250.00    $45.00
TQQQ    32      $3,800.00    $32.00
SPY     12      $650.00      $12.00
```

**Monthly Activity:**
```
Month     Trades  Volume       P&L
2026-01   89      $450,000     $5,700
```

---

## 🔄 SYNC TRANSACTIONS

### **Sync Tradier Transactions**
**File:** `sync_tradier_transactions.py`  
**Purpose:** Continuous sync with Tradier

```cmd
python scripts\04_trading\sync_tradier_transactions.py
```

**Use when:**
- Want automatic ongoing sync
- Alternative to manual imports

---

## 📊 TRADING SCHEMA

### **Trades Table Schema**
**File:** `trades_table_schema.py`  
**Purpose:** Database schema definition

**Run once:** Creates trades table structure

```cmd
python scripts\04_trading\trades_table_schema.py
```

**Note:** Usually run automatically by import script

---

## 🔄 COMMON WORKFLOWS

### **Initial Setup (One-Time)**
```cmd
# 1. Import entire trading history
python scripts\04_trading\import_tradier_history.py --check
python scripts\04_trading\import_tradier_history.py --import

# 2. Verify ACH matches investor transactions
python scripts\05_validation\validate_with_ach.py

# 3. Explore your data
python scripts\04_trading\query_trades.py
```

---

### **Weekly Update**
```cmd
# Import new trades from last week
python scripts\04_trading\import_tradier_history.py --import --start-date 2026-01-20

# Check ACH reconciliation
python scripts\04_trading\query_trades.py --ach

# Validate matches investor contributions
python scripts\05_validation\validate_with_ach.py
```

---

### **Monthly Reconciliation**
```cmd
# 1. Import all month's trades
python scripts\04_trading\import_tradier_history.py --import --start-date 2026-01-01

# 2. View monthly summary
python scripts\04_trading\query_trades.py --monthly

# 3. Check ACH matches
python scripts\04_trading\query_trades.py --ach

# 4. Validate
python scripts\05_validation\validate_with_ach.py
```

---

### **Performance Analysis**
```cmd
# View overall performance
python scripts\04_trading\query_trades.py --summary

# Analyze specific symbols
python scripts\04_trading\query_trades.py --symbol SGOV
python scripts\04_trading\query_trades.py --symbol TQQQ

# Monthly breakdown
python scripts\04_trading\query_trades.py --monthly

# All symbols comparison
python scripts\04_trading\query_trades.py --symbols
```

---

### **ACH Reconciliation**
```cmd
# 1. View all ACH transactions
python scripts\04_trading\query_trades.py --ach

# 2. Compare to investor contributions
python scripts\05_validation\validate_with_ach.py

# Should match! Example:
# ACH: $2,000 (Jan 2)
# Investor: Ken $1,000 + Beth $1,000 = $2,000 ✓
```

---

## 📊 QUICK REFERENCE

| Task | Command | Frequency |
|------|---------|-----------|
| Import trades | `import_tradier_history.py --import` | Weekly/Monthly |
| View ACH | `query_trades.py --ach` | Monthly |
| Performance | `query_trades.py --summary` | Monthly |
| Symbol analysis | `query_trades.py --symbol SGOV` | As needed |
| Monthly stats | `query_trades.py --monthly` | Monthly |

---

## 🎯 WHY USE TRADING JOURNAL?

**System 1 (NAV Tracking):**
- Tracks who owns what % of fund
- Daily NAV calculations
- Investor returns

**System 2 (Trading Journal):**
- Tracks every trade for analysis
- Performance by symbol
- Commission tracking
- Tax reporting detail

**The Bridge:**
- ACH reconciliation ensures deposits match attributions
- Validates investor contributions = actual money received

---

## ⚠️ IMPORTANT NOTES

**Import frequency:**
- Initial: Once (full history)
- Ongoing: Weekly or monthly
- Before month-end close

**ACH reconciliation:**
- ACH deposits MUST match investor contributions
- Split transactions (Ken + Beth) are OK
- Use validate_with_ach.py to verify

**Performance:**
- Trading journal = detailed analysis
- NAV system = investor returns
- Both work together

---

## 🔧 TROUBLESHOOTING

**Import fails:**
```cmd
# Check Tradier API key in .env
type .env

# Test API connection
python run.py api

# Verify dates are correct
python scripts\04_trading\import_tradier_history.py --check
```

**ACH doesn't match:**
```cmd
# View all ACH transactions
python scripts\04_trading\query_trades.py --ach

# Compare to investor transactions
python scripts\05_validation\validate_with_ach.py

# Common cause: Split deposit (multiple investors, one ACH)
# Solution: Assign_pending_contribution.py
```

**Duplicate trades:**
- Script prevents duplicates automatically
- Uses unique Tradier transaction ID
- Safe to re-run import

**No data showing:**
```cmd
# Make sure you ran import first
python scripts\04_trading\import_tradier_history.py --import

# Check database has data
python scripts\04_trading\query_trades.py --summary
```

---

## 💡 PRO TIPS

1. **Import regularly** - Weekly or monthly keeps data current
2. **Check ACH monthly** - Ensures reconciliation stays accurate
3. **Analyze performance** - Use symbol queries to evaluate strategies
4. **Track commissions** - Monitor if fees eating into returns
5. **Export for taxes** - Trading journal provides detailed history for Schedule D

---

**Most used: import_tradier_history.py (weekly), query_trades.py --ach (monthly)** ⭐
