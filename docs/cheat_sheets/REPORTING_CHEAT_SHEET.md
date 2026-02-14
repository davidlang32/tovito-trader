# 03_REPORTING - REPORTS & STATEMENTS CHEAT SHEET
## Monthly Reports & Data Exports

---

## 📁 WHAT'S IN THIS FOLDER

**2 Scripts + 1 Batch File for investor reporting**

---

## 📊 MONTHLY REPORTS (PRIMARY)

### **Generate Monthly Report** ⭐⭐⭐
**File:** `generate_monthly_report.py`  
**Purpose:** Create and email monthly investor statements

---

### **AUTOMATED (Recommended):**
**Runs:** 1st of month, 9:00 AM via Task Scheduler

```cmd
# Batch file (automated)
send_monthly_reports.bat
```

**What it does:**
- Generates previous month's reports
- Creates PDF for each investor
- Emails automatically
- **Hands-free!** ✅

---

### **MANUAL COMMANDS:**

**Current month (default):**
```cmd
python scripts\03_reporting\generate_monthly_report.py --email
```

**Previous month (for automation):**
```cmd
python scripts\03_reporting\generate_monthly_report.py --previous-month --email
```

**Specific month:**
```cmd
python scripts\03_reporting\generate_monthly_report.py --month 1 --year 2026 --email
```

**Single investor:**
```cmd
python scripts\03_reporting\generate_monthly_report.py --investor 20260101-01A --email
```

**Generate without emailing:**
```cmd
python scripts\03_reporting\generate_monthly_report.py --month 1 --year 2026
```

**Text format (no PDF):**
```cmd
python scripts\03_reporting\generate_monthly_report.py --text
```

---

### **FLAGS:**

| Flag | Purpose | Example |
|------|---------|---------|
| `--month N` | Specific month (1-12) | `--month 1` |
| `--year YYYY` | Specific year | `--year 2026` |
| `--investor ID` | Single investor only | `--investor 20260101-01A` |
| `--email` | Send via email | `--email` |
| `--previous-month` | Use last month | `--previous-month` |
| `--text` | Text instead of PDF | `--text` |

---

### **REPORT CONTENTS:**

**Page 1:**
- Account Summary (shares, value, returns)
- Performance Metrics (NAV change, contributions, withdrawals)
- Transactions This Month (with NAV column)
- Tax Summary (unrealized gains, tax liability, after-tax value)
- Portfolio Allocation (% of total)

**Page 2:**
- Disclaimer
- Report generation timestamp

**Output:** `data\reports\monthly_statement_ID_YYYYMM.pdf`

---

## 📑 EXCEL EXPORTS

### **Export Transactions to Excel** ⭐
**File:** `export_transactions_excel.py`  
**Purpose:** Export transaction history to spreadsheet

---

### **COMMANDS:**

**All transactions:**
```cmd
python scripts\03_reporting\export_transactions_excel.py
```

**Specific date range:**
```cmd
python scripts\03_reporting\export_transactions_excel.py --start-date 2026-01-01 --end-date 2026-01-31
```

**Specific investor:**
```cmd
python scripts\03_reporting\export_transactions_excel.py --investor 20260101-01A
```

**Combination:**
```cmd
python scripts\03_reporting\export_transactions_excel.py --investor 20260101-01A --start-date 2026-01-01 --end-date 2026-12-31
```

---

### **OUTPUT:**

**File:** `data\reports\transactions_YYYYMMDD.xlsx`

**Columns:**
- Date
- Investor ID
- Investor Name
- Transaction Type
- Amount
- Shares Transacted
- Share Price
- Notes

**Use for:**
- Tax preparation
- Investor requests
- Quarterly reviews
- Annual summaries

---

## 🔄 COMMON WORKFLOWS

### **Monthly Routine (Automated)**
```cmd
# Last trading day of month
# → Final NAV update (automated 4:05 PM)

# 1st of new month
# → Reports sent automatically at 9:00 AM ✅

# Manual check (optional)
python scripts\10_utilities\view_positions.py
```

---

### **Month-End Manual Process**
```cmd
# 1. Generate reports
python scripts\03_reporting\generate_monthly_report.py --previous-month --email

# 2. Verify sent successfully
# Check inbox for confirmations

# 3. Backup
python run.py backup
```

---

### **Investor Request: "Send me my statement"**
```cmd
# Generate specific investor's current month
python scripts\03_reporting\generate_monthly_report.py --investor 20260101-01A --email
```

---

### **Tax Season Prep**
```cmd
# Export full year transactions for each investor
python scripts\03_reporting\export_transactions_excel.py --investor 20260101-01A --start-date 2026-01-01 --end-date 2026-12-31

# Repeat for each investor
# Provide Excel files to accountant
```

---

### **Quarterly Review**
```cmd
# Export Q1 transactions
python scripts\03_reporting\export_transactions_excel.py --start-date 2026-01-01 --end-date 2026-03-31

# Generate March report (if needed)
python scripts\03_reporting\generate_monthly_report.py --month 3 --year 2026
```

---

## 📅 SCHEDULE RECOMMENDATIONS

**Daily:** None (reports are monthly)

**Monthly:** 
- Automated on 1st at 9 AM ✅
- Or manual if preferred

**Quarterly:**
- Export transactions for quarter
- Review with investors

**Annually:**
- Export full year
- Provide to accountant
- Archive all reports

---

## 📊 QUICK REFERENCE

| Task | Command | When |
|------|---------|------|
| Monthly reports (all) | `generate_monthly_report.py --previous-month --email` | 1st of month |
| Single investor report | `generate_monthly_report.py --investor ID --email` | On request |
| Export all transactions | `export_transactions_excel.py` | Tax time |
| Export date range | `export_transactions_excel.py --start-date X --end-date Y` | Quarterly |

---

## ⚠️ IMPORTANT NOTES

**Before generating reports:**
- ✅ Finalize previous month's NAV
- ✅ All transactions recorded
- ✅ Validation passed

**Email requirements:**
- Configured in `.env` file
- SMTP settings correct
- Gmail users: App Password required

**PDF requirements:**
- reportlab installed: `pip install reportlab`
- If missing, generates text format instead

---

## 🔧 TROUBLESHOOTING

**Reports not emailing:**
```cmd
# Check email config
python scripts\07_email\test_email.py

# Verify SMTP settings in .env
type .env

# Test with single investor
python scripts\03_reporting\generate_monthly_report.py --investor 20260101-01A --email
```

**PDF not generating:**
```cmd
# Install reportlab
pip install reportlab

# Or use text format
python scripts\03_reporting\generate_monthly_report.py --text
```

**Wrong month generated:**
```cmd
# Make sure using --previous-month on 1st of new month
# Or specify exact month with --month and --year
```

**Excel export empty:**
```cmd
# Check date range
# Verify transactions exist for that period
python scripts\10_utilities\view_positions.py
```

---

## 💡 PRO TIPS

1. **Automate monthly reports** - Set up Task Scheduler once, never manually send again
2. **Archive reports** - Keep PDF copies for your records
3. **Export annually** - Excel export for each investor at year-end
4. **Test email first** - Before automating, test with `--investor ID --email`
5. **Backup reports** - Include `data\reports\` in your backup routine

---

## 📧 TASK SCHEDULER SETUP

**If not set up yet:**

1. Copy `send_monthly_reports.bat` to `C:\tovito-trader\`
2. Task Scheduler → Create Task
3. Trigger: Monthly, day 1, 9:00 AM
4. Action: Run `C:\tovito-trader\send_monthly_reports.bat`
5. Done! Hands-free monthly reports ✅

**See:** `MONTHLY_REPORT_AUTOMATION.md` for complete setup guide

---

**Most used: generate_monthly_report.py (automated), export_transactions_excel.py (quarterly)** ⭐
