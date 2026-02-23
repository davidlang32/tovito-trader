# WITHDRAWAL SYSTEM - QUICK INSTALL (ARCHIVED)
## ~~15-Minute Setup Guide~~

> **⚠️ ARCHIVED:** This installation guide is obsolete. The standalone withdrawal system
> described here has been retired and consolidated into the unified **fund flow lifecycle**.
> All contributions and withdrawals now use: `submit_fund_flow.py` → `match_fund_flow.py`
> → `process_fund_flow.py`. Tax is settled quarterly (no withholding at withdrawal).
> See `docs/audit/CHANGELOG.md` and `docs/reference/WITHDRAWAL_DELIVERY_SUMMARY.md` for details.

---

## 🎯 WHAT YOU'RE INSTALLING

**Complete withdrawal management system with:**
- ✅ Request logging (from any source)
- ✅ Manual approval workflow
- ✅ Tax calculations (37% on realized gains)
- ✅ Email confirmations
- ✅ Daily automation alerts

**Matches your contribution system quality!**

---

## 🚀 INSTALLATION (6 Steps, 15 Minutes)

### **STEP 1: Copy Scripts** (1 min)

```cmd
cd C:\tovito-trader
copy migrate_add_withdrawal_requests.py scripts\
copy request_withdrawal.py scripts\
copy submit_withdrawal_request.py scripts\
copy view_pending_withdrawals.py scripts\
copy process_withdrawal_enhanced.py scripts\
copy check_pending_withdrawals.py scripts\
```

---

### **STEP 2: Run Database Migration** (1 min)

```cmd
python scripts\migrate_add_withdrawal_requests.py
```

**Expected output:**
```
DATABASE MIGRATION - WITHDRAWAL REQUESTS
=========================================

This will add the withdrawal_requests table...

Proceed with migration? (yes/no): yes

✅ withdrawal_requests table created
✅ Indexes created
✅ MIGRATION COMPLETE!
```

---

### **STEP 3: Test Request Submission** (3 min)

```cmd
python scripts\request_withdrawal.py
```

**Follow prompts:**
1. Select an investor
2. Enter amount (e.g., 1000)
3. Select source: Email
4. Notes: "Test request"
5. Confirm: yes

**Expected output:**
```
✅ Withdrawal request logged (ID: 1)

Next steps:
  1. Review: python scripts/list_withdrawal_requests.py
  2. Approve: python scripts/approve_withdrawal.py
```

---

### **STEP 4: View Pending Requests** (30 sec)

```cmd
python scripts\view_pending_withdrawals.py
```

**Expected output:**
```
PENDING WITHDRAWAL REQUESTS
===========================

⏳ Request #1 - Pending
   Investor: David Lang
   Amount: $1,000.00
   Date: 2026-01-25
   Method: Email
   Notes: Test request
```

---

### **STEP 5: Process Withdrawal** (5 min)

```cmd
python scripts\process_withdrawal_enhanced.py
```

**What happens:**
1. Shows pending request with full calculation
2. Displays tax breakdown
3. Asks for approval
4. Sends email confirmations
5. Updates database

**Expected output:**
```
WITHDRAWAL CALCULATION:
  Current Value:      $18,975.00
  Net Investment:     $15,000.00
  Unrealized Gain:    $3,975.00

  Withdrawal Amount:  $1,000.00
  Proportion:         5.27%
  Shares to Sell:     777.5000

  Realized Gain:      $209.49
  Tax (37%):          $77.51
  Net Proceeds:       $922.49

Approve and process this withdrawal? (yes/no): yes

✅ WITHDRAWAL PROCESSED SUCCESSFULLY
📧 Investor email sent
📧 Admin email sent
```

**Check your email!** You should receive:
- Confirmation to investor
- Notification to admin

---

### **STEP 6: Add to Daily Automation** (3 min)

**Option A: Standalone script**

Create `check_withdrawals_daily.bat`:
```batch
@echo off
python scripts\check_pending_withdrawals.py
pause
```

Run daily after your NAV update.

**Option B: Integrate with daily runner**

Add to existing daily automation script at the end:
```python
# Check for pending withdrawal requests
print("\n" + "=" * 70)
print("CHECKING WITHDRAWAL REQUESTS")
print("=" * 70 + "\n")

result = subprocess.run(
    [sys.executable, 'scripts/check_pending_withdrawals.py'],
    capture_output=True,
    text=True
)
print(result.stdout)
```

**Test it:**
```cmd
python scripts\check_pending_withdrawals.py
```

If pending requests exist, you'll get email alert! ✅

---

## ✅ VERIFICATION CHECKLIST

After installation:

- [ ] Database migration completed
- [ ] Created test withdrawal request
- [ ] Viewed pending requests
- [ ] Processed test withdrawal
- [ ] Received investor email confirmation
- [ ] Received admin notification email
- [ ] Tested daily check script
- [ ] Added to daily automation

**All checked?** System ready! 🎉

---

## 🔄 DAILY WORKFLOW

### **When Investor Requests Withdrawal:**

**1. Log it immediately** (1 min)
```cmd
python scripts\request_withdrawal.py
```

**2. Daily check alerts you** (automatic)
Email arrives if pending requests exist.

**3. Process when ready** (3 min)
```cmd
python scripts\process_withdrawal_enhanced.py
```

**Total time: 4 minutes per withdrawal** ✅

---

## 📧 EMAIL CONFIRMATIONS

### **Investor receives:**
```
Subject: Withdrawal Processed - Tovito Trader

Your withdrawal has been processed successfully.

WITHDRAWAL SUMMARY
==================
Withdrawal Amount:     $1,000.00
Realized Gain:         $209.49
Tax Withheld (37%):    $77.51
Net Proceeds:          $922.49

UPDATED POSITION
================
Shares Remaining:      13,972.5000
Current Value (Gross): $17,975.00

The tax withheld will be paid to the IRS on your behalf...
```

### **You receive:**
```
Subject: Withdrawal Processed - David Lang - $1,000.00

Withdrawal Request #1 has been processed.

DETAILS:
Withdrawal Amount:  $1,000.00
Realized Gain:      $209.49
Tax Withheld:       $77.51
Net Proceeds:       $922.49

Investor confirmation email has been sent.
```

---

## 🎯 COMMON COMMANDS

**Submit request:**
```cmd
# Interactive
python scripts\request_withdrawal.py

# Command line
python scripts\request_withdrawal.py --investor 20260101-01A --amount 5000
```

**View pending:**
```cmd
# Pending only
python scripts\view_pending_withdrawals.py

# All requests (including processed)
python scripts\view_pending_withdrawals.py --all
```

**Process:**
```cmd
# Interactive (shows all pending)
python scripts\process_withdrawal_enhanced.py

# Specific request
python scripts\process_withdrawal_enhanced.py --request-id 5
```

**Daily check:**
```cmd
python scripts\check_pending_withdrawals.py
```

---

## 🚨 TROUBLESHOOTING

### **"No such table: withdrawal_requests"**
```cmd
python scripts\migrate_add_withdrawal_requests.py
```

### **"Email service not available"**
```cmd
python src\automation\email_service.py
```

### **"No NAV data found"**
```cmd
python scripts\daily_nav_enhanced.py
```

### **Tax calculation looks wrong**
Check `.env` file:
```ini
TAX_RATE=0.37
```

---

## 💡 PRO TIPS

**1. Log requests immediately**
Don't wait - log as soon as investor contacts you.

**2. Process same day**
Keep withdrawal times fast for good investor experience.

**3. Use notes field**
Record context: "Emergency medical", "House down payment", etc.

**4. Review calculations**
Always check the tax breakdown before approving.

**5. Keep email confirmations**
Professional and provides audit trail.

---

## 🎉 YOU'RE DONE!

**Your withdrawal system now has:**
- ✅ Request tracking
- ✅ Manual approval workflow
- ✅ Tax calculations
- ✅ Email confirmations
- ✅ Daily automation
- ✅ Complete audit trail

**Same quality as your contribution system!** 🚀

---

## 📚 FULL DOCUMENTATION

See `WITHDRAWAL_SYSTEM_GUIDE.md` for:
- Complete workflows
- Example scenarios
- Email templates
- Best practices
- Advanced features

---

**Start with Step 1 and work through the installation!** ✅

Questions? Check the full guide! 📖
