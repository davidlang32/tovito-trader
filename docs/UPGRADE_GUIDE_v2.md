# TOVITO TRADER v2.0 UPGRADE GUIDE
## Live Streaming, Database Improvements & Data Fixes

---

## 🎯 WHAT'S NEW IN v2.0

### **1. Live Tradier Streaming**
Real-time market data via WebSocket:
- Live quotes (bid/ask/last)
- Trade data
- Portfolio monitoring
- Auto-reconnection

### **2. Improved Database Schema**
Better data integrity and features:
- Audit logging (track all changes)
- Soft deletes (keep history)
- Better indexes (faster queries)
- Useful views (pre-built reports)
- Proper constraints (data validation)

### **3. Live Dashboard**
Real-time portfolio view:
- Current portfolio value
- NAV calculation
- Investor positions
- Live quotes
- Auto-update after market close

### **4. Data Fix Tools**
Scripts to fix data issues:
- Missing contribution fixer
- ACH reconciliation validator
- Database integrity checker

---

## 🚀 QUICK START

### **Option A: Run Upgrade Script (Recommended)**

```cmd
cd C:\tovito-trader

# Run the upgrade
python scripts\upgrade_v2.py
```

This will:
1. ✅ Create a backup
2. ✅ Migrate database schema
3. ✅ Check for missing contributions (Ken & Beth)
4. ✅ Offer to fix issues

### **Option B: Step by Step**

```cmd
cd C:\tovito-trader

# 1. Backup first!
python run.py backup

# 2. Install new dependencies
pip install websockets colorama

# 3. Fix Ken & Beth contributions
python scripts\fix_missing_contributions.py

# 4. Migrate database (optional but recommended)
python src\database\schema_v2.py migrate

# 5. Validate
python run.py validate
```

---

## 📊 FIXING KEN & BETH'S CONTRIBUTIONS

### **The Problem:**
- Ken and Beth each contributed $1,000 when NAV = $1.0000
- Tradier shows $2,000 ACH deposit
- But NO transaction records exist in database

### **The Fix:**

```cmd
python scripts\fix_missing_contributions.py
```

**Interactive prompts:**
```
Date of contributions [2026-01-02]: <Enter>
NAV at contribution [1.0000]: <Enter>
Ken's contribution amount [1000]: <Enter>
Beth's contribution amount [1000]: <Enter>

Proceed? (yes/no): yes
```

**Result:**
```
✅ Added Initial for Ken: $1,000.00 = 1,000.0000 shares at NAV $1.0000
✅ Added Initial for Beth: $1,000.00 = 1,000.0000 shares at NAV $1.0000
```

### **Verify After Fix:**

```cmd
python scripts\validate_with_ach.py
```

Should show:
```
ACH RECONCILIATION:
Date         ACH          Investor Txns    Status
2026-01-02   $2,000.00    $2,000.00        ✅ Match (2 investors, 1 ACH)

✅ ALL CHECKS PASSED!
```

---

## 📡 LIVE STREAMING

### **Basic Quote Streaming:**

```python
from src.streaming import TradierStreaming

client = TradierStreaming()
client.subscribe(['SGOV', 'TQQQ', 'SPY'])

@client.on_quote
def handle_quote(quote):
    print(f"{quote.symbol}: ${quote.last:.2f}")

client.start()
```

### **Command Line:**

```cmd
# Stream quotes
python src\streaming\tradier_streaming.py SGOV TQQQ SPY

# Monitor portfolio
python src\streaming\tradier_streaming.py --portfolio
```

### **Output:**
```
Starting quote stream for: SGOV, TQQQ, SPY
✅ Connected!
📈 SGOV: $100.45 (Bid: $100.44 x 100 | Ask: $100.46 x 200)
📈 TQQQ: $67.23 (Bid: $67.22 x 500 | Ask: $67.24 x 300)
📈 SPY: $523.67 (Bid: $523.66 x 1000 | Ask: $523.68 x 800)
```

---

## 📺 LIVE DASHBOARD

### **Start Dashboard:**

```cmd
python scripts\live_dashboard.py
```

### **With Options:**

```cmd
# Add extra symbols to watch
python scripts\live_dashboard.py --symbols AAPL,MSFT,GOOGL

# Faster refresh (every 10 seconds)
python scripts\live_dashboard.py --refresh 10

# Auto-update NAV after market close
python scripts\live_dashboard.py --auto-update

# Single snapshot (no refresh)
python scripts\live_dashboard.py --once
```

### **Dashboard Display:**

```
══════════════════════════════════════════════════════════════════════
  TOVITO TRADER - LIVE DASHBOARD
══════════════════════════════════════════════════════════════════════
  Last update: 2026-01-27 10:30:45

📊 PORTFOLIO SUMMARY
──────────────────────────────────────────────────────
  Total Value:     $25,377.00
  Cash:            $1,234.56
  Equity:          $24,142.44

📈 NAV CALCULATION
──────────────────────────────────────────────────────
  Portfolio Value: $25,377.00
  Total Shares:    20,432.62
  Current NAV:     $1.2418

  Last Recorded:   $1.2350 (2026-01-26)
  Change:          +0.55% (+$0.0068)

📋 POSITIONS
──────────────────────────────────────────────────────────────────────
  Symbol          Qty        Price          Value           P/L
  ────────── ────────── ──────────── ────────────── ────────────
  SGOV        240.00    $100.45      $24,108.00     +$108.00 (+0.5%)

👥 INVESTOR POSITIONS
──────────────────────────────────────────────────────────────────────
  Name                     Shares          Value     Return    %Port
  ──────────────────── ──────────── ────────────── ────────── ────────
  David Lang           18,432.6185    $22,892.34    +20.5%    90.2%
  Ken Lang              1,000.0000     $1,241.80    +24.2%     4.9%
  Beth Lenz             1,000.0000     $1,241.80    +24.2%     4.9%
```

---

## 🗄️ DATABASE IMPROVEMENTS

### **New Schema Features:**

| Feature | Description |
|---------|-------------|
| **Audit Log** | Track all changes to data |
| **Soft Deletes** | `is_deleted` flag instead of removing |
| **Timestamps** | `created_at`, `updated_at` on all tables |
| **Constraints** | CHECK constraints for data validation |
| **Foreign Keys** | Proper referential integrity |
| **Indexes** | Faster queries |
| **Views** | Pre-built reports |

### **Migrate Existing Database:**

```cmd
python src\database\schema_v2.py migrate --db data\tovito.db
```

### **New Views Available:**

```sql
-- Investor positions with calculated values
SELECT * FROM v_investor_positions;

-- Transaction summary by investor
SELECT * FROM v_investor_transactions;

-- NAV history with changes
SELECT * FROM v_nav_history;

-- ACH summary
SELECT * FROM v_ach_summary;

-- Tax summary
SELECT * FROM v_tax_summary;
```

### **Check Schema:**

```cmd
python src\database\schema_v2.py validate --db data\tovito.db
```

---

## 📁 NEW FILE STRUCTURE

```
C:\tovito-trader\
├── src\
│   ├── streaming\                    # NEW!
│   │   ├── __init__.py
│   │   └── tradier_streaming.py      # WebSocket client
│   └── database\
│       └── schema_v2.py              # NEW! Improved schema
├── scripts\
│   ├── fix_missing_contributions.py  # NEW! Fix Ken & Beth
│   ├── live_dashboard.py             # NEW! Real-time view
│   └── upgrade_v2.py                 # NEW! Upgrade script
├── requirements.txt                  # Updated
└── UPGRADE_GUIDE_v2.md              # This file
```

---

## ⚡ QUICK REFERENCE

### **Fix Ken & Beth:**
```cmd
python scripts\fix_missing_contributions.py
```

### **Live Dashboard:**
```cmd
python scripts\live_dashboard.py
```

### **Stream Quotes:**
```cmd
python src\streaming\tradier_streaming.py SGOV TQQQ
```

### **Validate Data:**
```cmd
python run.py validate
python scripts\validate_with_ach.py
```

### **Database Stats:**
```cmd
python src\database\schema_v2.py stats --db data\tovito.db
```

---

## 🔧 TROUBLESHOOTING

### **"websockets not installed"**
```cmd
pip install websockets
```

### **"Streaming won't connect"**
- Check `TRADIER_API_KEY` in `.env`
- Verify market is open (M-F 9:30 AM - 4 PM ET)
- Tradier streaming requires active data subscription

### **"NAV doesn't match"**
```cmd
# Validate data
python run.py validate

# Check ACH reconciliation
python scripts\validate_with_ach.py

# Fix if needed
python scripts\fix_missing_contributions.py
```

### **"Dashboard shows stale data"**
- Check internet connection
- Verify Tradier API credentials
- Try running with `--once` flag first

---

## 📋 CHECKLIST

After upgrading:

- [ ] Ran `python scripts\upgrade_v2.py`
- [ ] Ken & Beth contributions fixed
- [ ] `python run.py validate` passes
- [ ] `python scripts\validate_with_ach.py` passes
- [ ] Tested `python scripts\live_dashboard.py`
- [ ] Created backup: `python run.py backup`

---

## 🚀 NEXT STEPS

1. **Daily Operations:**
   - Run live dashboard for real-time view
   - NAV updates automatically at 4:05 PM
   
2. **Weekly:**
   - Review audit log for any issues
   - Backup database
   
3. **Monthly:**
   - Generate investor reports
   - Validate ACH reconciliation

---

## 📞 QUESTIONS?

If you have issues:

1. Check validation first:
   ```cmd
   python run.py validate
   ```

2. Review logs:
   ```cmd
   type logs\daily_runner.log
   ```

3. Ask Claude for help with your specific scenario!

---

**Enjoy your upgraded Tovito Trader system! 🎉**
