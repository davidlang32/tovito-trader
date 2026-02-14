# PROSPECT SYSTEM - QUICK FIX
## CSV Path & Email Service Issues

---

## ✅ ISSUES FOUND

1. **Email service not loading** - Import path issue
2. **CSV file not found** - Path resolution issue

---

## 🔧 FIX (2 Minutes)

### **Step 1: Update Script**

```cmd
cd C:\tovito-trader
copy /Y send_prospect_report.py scripts\
```

**Fixed:**
- ✅ Email service import with proper path
- ✅ Smart CSV file location finder
- ✅ Better error messages

---

### **Step 2: Recommended File Organization**

**For prospects.csv, choose ONE:**

**Option A: Project Root (RECOMMENDED)** ⭐
```
C:\tovito-trader\prospects.csv
```
- Easy to find
- Easy to edit
- Works with scripts automatically

**Option B: Data Folder**
```
C:\tovito-trader\data\prospects.csv
```
- Keeps data organized
- Script will find it automatically

**Option C: Dedicated Prospects Folder**
```
C:\tovito-trader\prospects\prospects.csv
```
- Best for multiple prospect lists
- Clean organization

---

## 📁 RECOMMENDED STRUCTURE

```
C:\tovito-trader\
├── data\
│   ├── tovito.db
│   └── backups\
├── prospects\              ← NEW! (optional)
│   ├── prospects.csv       ← Active prospects
│   ├── prospects_hot.csv   ← High priority
│   └── prospects_sent.csv  ← Already contacted
├── reports\
│   └── (monthly PDFs)
├── scripts\
│   └── (all your scripts)
└── prospects.csv           ← OR keep here (simple)
```

**For now, just keep it in root:**
```
C:\tovito-trader\prospects.csv
```

---

## ✅ TEST IT NOW

### **Test 1: Email Service**
```cmd
python src\automation\email_service.py
```

**Should see:**
```
Testing email service...
Sending test email to: dlang32@gmail.com

✅ Email sent successfully!
```

### **Test 2: Find CSV File**

Make sure your CSV is in root:
```cmd
dir C:\tovito-trader\prospects.csv
```

Should show the file!

### **Test 3: Send Prospect Report (Test Mode)**
```cmd
python scripts\send_prospect_report.py --month 1 --year 2026 --prospects prospects.csv --test-email
```

**Should see:**
```
Found prospects file: C:\tovito-trader\prospects.csv

SEND PROSPECT REPORTS
======================================================================

Period: January 2026
Prospects: 4
Mode: TEST (all emails to admin)

  1. George Greanias <g.c.greanias@gmail.com>
  2. John Watson <johnwtsn0@gmail.com>
  3. Michael McCollum <MichaelGMcCollum@me.com>
  4. Rick Anderson <rianders3668@gmail.com>

Send reports? (yes/no):
```

---

## 💡 WHERE THE SCRIPT LOOKS FOR CSV

The script now searches in this order:

1. Exact path you provide
2. Current directory
3. **C:\tovito-trader\** (project root) ⭐
4. C:\tovito-trader\data\
5. C:\tovito-trader\prospects\

**So if your CSV is in any of these places, it will find it!** ✅

---

## 📋 YOUR PROSPECTS.CSV

**Current prospects:**
- George Greanias
- John Watson  
- Michael McCollum
- Rick Anderson

**Make sure your CSV has headers:**
```csv
Name,Email,Phone,Source,Notes
George Greanias,g.c.greanias@gmail.com,(571) 730-7722,Friend,
John Watson,johnwtsn0@gmail.com,(772) 538-1183,Friend,
Michael McCollum,MichaelGMcCollum@me.com,(703) 801-2023,Friend,
Rick Anderson,rianders3668@gmail.com,(301) 752-4721,Friend,
```

Save as: `C:\tovito-trader\prospects.csv`

---

## 🚀 READY TO GO!

After copying the fixed script:

```cmd
# Test mode first!
python scripts\send_prospect_report.py --month 1 --year 2026 --prospects prospects.csv --test-email
```

**What happens:**
1. ✅ Script finds email service
2. ✅ Script finds prospects.csv in root
3. ✅ Generates professional PDF
4. ✅ Sends 4 test emails to dlang32@gmail.com
5. ✅ Logs to database
6. ✅ You get admin summary

**Check your email!** Should have 4 test emails + 1 admin summary!

---

## ⚙️ IF STILL HAVING ISSUES

### **Email service not working:**

```cmd
# Test email service directly
python src\automation\email_service.py
```

If this fails, check your .env file has:
```
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SMTP_USERNAME=dlang32@gmail.com
SMTP_PASSWORD=(your app password)
ADMIN_EMAIL=dlang32@gmail.com
```

### **CSV not found:**

```cmd
# Check where you are
cd

# Should be: C:\tovito-trader

# Check if file exists
dir prospects.csv
```

If file is elsewhere, either:
- Move it to C:\tovito-trader\
- Or provide full path: `--prospects C:\path\to\prospects.csv`

---

## ✅ SUCCESS CHECKLIST

After running the command:

- [ ] Script finds email service (no warning)
- [ ] Script finds prospects.csv
- [ ] Shows "Found prospects file: ..."
- [ ] Lists 4 prospects
- [ ] Generates PDF
- [ ] Sends 4 test emails to you
- [ ] You receive emails with PDF attached
- [ ] Database logs show communications

**All checked?** You're ready for live send! 🎉

---

## 🎯 NEXT: GO LIVE

When test emails look good:

```cmd
# Remove --test-email flag
python scripts\send_prospect_report.py --month 1 --year 2026 --prospects prospects.csv
```

**This sends to ACTUAL prospects!**

You'll get admin summary showing who received it! ✅

---

**Copy the fixed script and try again!** 🚀
