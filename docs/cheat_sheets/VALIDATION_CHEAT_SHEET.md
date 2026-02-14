# 05_VALIDATION - DATA INTEGRITY CHEAT SHEET
## Validation & System Health Checks

---

## 📁 WHAT'S IN THIS FOLDER

**4 Scripts for verifying data accuracy and system health**

---

## ✅ COMPREHENSIVE VALIDATION (PRIMARY)

### **Validate with ACH** ⭐⭐⭐
**File:** `validate_with_ach.py`  
**Purpose:** Complete data integrity check including ACH reconciliation

```cmd
python scripts\05_validation\validate_with_ach.py
```

---

### **CHECKS PERFORMED (8 Total):**

**Basic Accounting (5 checks):**
1. ✅ Share totals match (investors vs daily_nav)
2. ✅ Percentages = 100%
3. ✅ NAV calculations correct
4. ✅ January 1 NAV = $1.00
5. ✅ Transaction totals match net investments

**ACH Reconciliation (3 checks):**
6. ✅ ACH deposits (Tradier) = Investor contributions (database)
7. ✅ Date-by-date reconciliation
8. ✅ Handles split transactions (multiple investors, one ACH)

---

### **EXAMPLE OUTPUT:**

```
BASIC ACCOUNTING CHECKS:
✅ Check 1: Share totals match (48,724.32 = 48,724.32)
✅ Check 2: Percentages = 100.00%
✅ Check 3: NAV calculation correct
✅ Check 4: January 1 NAV = $1.00
✅ Check 5: Transaction totals match

ACH RECONCILIATION:
Date         ACH (Tradier)    Investor Txns    Status
2026-01-02   $2,000.00       $2,000.00        ⚠️ 2 investors, 1 ACH
                                              💡 Split transaction - OK!
2026-01-21   $4,000.00       $4,000.00        ✅ Match

✅ ALL CHECKS PASSED!
```

---

### **WHEN TO RUN:**

**Required:**
- After every contribution
- After every withdrawal
- Monthly reconciliation
- Before generating reports

**Recommended:**
- Weekly routine check
- After any data correction
- Before backups

---

## ✅ BASIC VALIDATION

### **Validate Comprehensive**
**File:** `validate_comprehensive.py`  
**Purpose:** Basic validation without ACH checks

```cmd
python scripts\05_validation\validate_comprehensive.py
# OR
python run.py validate
```

---

### **CHECKS PERFORMED (5 Total):**

1. ✅ Share totals match
2. ✅ Percentages = 100%
3. ✅ NAV calculations correct
4. ✅ January 1 NAV verified
5. ✅ Transaction totals match

**Use when:**
- Quick check without trading journal
- Don't need ACH reconciliation
- Basic verification

---

## 🔄 RECONCILIATION

### **Validate Reconciliation**
**File:** `validate_reconciliation.py`  
**Purpose:** Specialized reconciliation checks

```cmd
python scripts\05_validation\validate_reconciliation.py
```

**Checks:**
- Cross-table consistency
- Data integrity between sheets
- Calculation accuracy

---

## 🏥 SYSTEM HEALTH

### **System Health Check** ⭐
**File:** `system_health_check.py`  
**Purpose:** Overall system status

```cmd
python scripts\05_validation\system_health_check.py
```

---

### **CHECKS PERFORMED:**

**Database:**
- ✅ Connection works
- ✅ All tables exist
- ✅ Schema correct

**API:**
- ✅ Tradier connection
- ✅ API credentials valid
- ✅ Account accessible

**Email:**
- ✅ SMTP configured
- ✅ Credentials valid
- ✅ Can send test email

**Files:**
- ✅ Directory structure
- ✅ Permissions OK
- ✅ Backups exist

**Data Integrity:**
- ✅ Basic validation passes
- ✅ Recent backups exist

---

### **WHEN TO RUN:**

- Weekly system check
- After configuration changes
- Troubleshooting issues
- New environment setup

---

## 🔄 COMMON WORKFLOWS

### **After Contribution**
```cmd
# 1. Process contribution
python scripts\02_investor\process_contribution.py

# 2. Validate immediately
python scripts\05_validation\validate_with_ach.py

# 3. Should show all checks pass ✅
```

---

### **After Withdrawal**
```cmd
# 1. Process withdrawal
python scripts\02_investor\process_withdrawal.py

# 2. Validate immediately
python scripts\05_validation\validate_with_ach.py

# 3. Verify all checks pass ✅
```

---

### **Weekly Routine**
```cmd
# 1. Import latest trades
python scripts\04_trading\import_tradier_history.py --import

# 2. Comprehensive validation
python scripts\05_validation\validate_with_ach.py

# 3. System health check
python scripts\05_validation\system_health_check.py

# All should pass ✅
```

---

### **Monthly Reconciliation**
```cmd
# 1. Import all month's trades
python scripts\04_trading\import_tradier_history.py --import --start-date 2026-01-01

# 2. Validate with ACH
python scripts\05_validation\validate_with_ach.py

# 3. Check ACH specifically
python scripts\04_trading\query_trades.py --ach

# 4. All should reconcile ✅
```

---

### **Troubleshooting Data Issues**
```cmd
# 1. Quick validation
python run.py validate

# 2. If fails, run comprehensive
python scripts\05_validation\validate_with_ach.py

# 3. Read error messages carefully
# 4. Fix identified issues
# 5. Re-validate

# 6. If still issues, system health check
python scripts\05_validation\system_health_check.py
```

---

## 📊 QUICK REFERENCE

| Script | Use Case | When |
|--------|----------|------|
| validate_with_ach.py | Full validation | After transactions, monthly |
| validate_comprehensive.py | Quick check | Daily/weekly |
| validate_reconciliation.py | Deep dive | Troubleshooting |
| system_health_check.py | System status | Weekly, setup |

---

## ⚠️ COMMON VALIDATION ERRORS

### **"Share totals don't match"**
```
Investors: 48,724.32 shares
Daily NAV: 48,500.00 shares
```

**Cause:** Recent transaction not recorded in Daily NAV

**Fix:**
1. Check last transaction in Transactions table
2. Verify Daily NAV updated
3. Run daily update if needed

---

### **"Percentages don't equal 100%"**
```
Total: 102.3%
```

**Cause:** Investor shares don't match Daily NAV total shares

**Fix:**
1. Check investor shares in Investors table
2. Sum should match Daily NAV total shares
3. Likely data entry error

---

### **"ACH deposits don't match"**
```
Date: 2026-01-02
ACH: $2,000
Investor transactions: $1,000
Difference: $1,000
```

**Cause:** Missing investor contribution

**Fix:**
1. Check if split transaction (Ken + Beth)
2. Verify all contributions recorded for that date
3. Use assign_pending_contribution.py if needed

---

### **"January 1 NAV ≠ $1.00"**
```
Expected: $1.00
Actual: $0.9824
```

**Cause:** Initial setup error

**Fix:**
1. Check initial capital entries
2. Verify shares = dollars on Jan 1
3. May need to run migration script

---

## 🔧 TROUBLESHOOTING

**Validation script won't run:**
```cmd
# Check you're in correct directory
cd C:\tovito-trader

# Verify Python installed
python --version

# Check database exists
dir data\tovito.db
```

**All checks fail:**
```cmd
# Database may be corrupted
# Restore from backup
copy data\backups\tovito_backup_LATEST.db data\tovito.db

# Re-validate
python scripts\05_validation\validate_with_ach.py
```

**ACH check fails but everything else passes:**
```cmd
# View ACH transactions
python scripts\04_trading\query_trades.py --ach

# View investor transactions
python scripts\02_investor\list_investors.py

# Compare dates and amounts manually
# Look for split transactions or missing contributions
```

---

## 💡 PRO TIPS

1. **Validate after EVERY transaction** - Catches errors immediately
2. **Weekly validation** - Regular health check
3. **Read error messages** - They tell you exactly what's wrong
4. **ACH reconciliation** - Most important check for data integrity
5. **System health monthly** - Comprehensive system verification

---

## 🎯 VALIDATION HIERARCHY

**Level 1 (Daily):**
```cmd
python run.py validate
```
Quick check, no ACH

**Level 2 (After transactions):**
```cmd
python scripts\05_validation\validate_with_ach.py
```
Full validation including ACH

**Level 3 (Weekly):**
```cmd
python scripts\05_validation\system_health_check.py
```
Complete system verification

**Level 4 (Troubleshooting):**
```cmd
python scripts\05_validation\validate_reconciliation.py
```
Deep diagnostic validation

---

**Most used: validate_with_ach.py (after every transaction), system_health_check.py (weekly)** ⭐
