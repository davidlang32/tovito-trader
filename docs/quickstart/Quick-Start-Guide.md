# Quick Start Guide - Monthly Application Review System

## 🚀 Get Started in 5 Minutes

### Step 1: Setup ServiceNow (One-Time)

```powershell
.\Setup-ServiceNowCredentials.ps1
```

**You'll be prompted for:**
- ServiceNow username (your service account)
- ServiceNow password
- ServiceNow base URL (e.g., `https://yourinstance.service-now.com`)

**Result:** Creates `servicenow-creds.json` file

---

### Step 2: Run First Review Session

```powershell
.\Review-MonthlyApplications.ps1
```

**What happens:**
1. Loads actionable applications (Risk >= 75 + issues)
2. Groups by SLT member
3. Shows interactive menu
4. You select apps to review
5. ServiceNow tickets auto-populate
6. You fill in manual fields
7. Review is saved to CSV

---

### Step 3: Review an Application

**Menu appears:**
```
Actionable Applications (22 total):

━━━ Kumar ━━━
  1. [CRITICAL] Oracle Database (P0) Risk: 100
  2. [HIGH] Azure DevOps Server (P2) Risk: 99

Select application number to review: 1
```

**System shows:**
- Application details (risk, usage, bottleneck)
- ServiceNow tickets (auto-found)
- Previous reviews (from CSV history)

**You provide:**
- Hostname
- URI (optional)
- Service Pool (optional)
- Short description
- Full description
- Require review? (Y/N)
- Review reason
- Notes (optional)

**System saves:**
- All your inputs
- Auto-populated data (SLT member, dates, etc.)
- ServiceNow ticket numbers

---

### Step 4: Add Multiple Servers (If Needed)

If one application has multiple servers:

```powershell
.\Add-MultipleServersToReview.ps1 -ApplicationName "Oracle Database"
```

**Quick workflow:**
1. System loads your previous review as template
2. You add Server 2, Server 3, etc.
3. Only need: hostname, URI, notes
4. System replicates rest of the data

---

## 📋 Common Commands

### Test Without Saving
```powershell
.\Review-MonthlyApplications.ps1 -WhatIf
```

### Work Offline (Skip ServiceNow)
```powershell
.\Review-MonthlyApplications.ps1 -SkipServiceNow
```

### Both Combined
```powershell
.\Review-MonthlyApplications.ps1 -WhatIf -SkipServiceNow
```

### Custom Tracking File Location
```powershell
.\Review-MonthlyApplications.ps1 -ReviewTrackingPath "C:\Custom\tracking.csv"
```

---

## 🎯 Key Features at a Glance

| Feature | How It Works |
|---------|--------------|
| **Auto-Populate Fields** | Month, date, SLT member, app name, bottleneck, ServiceNow tickets |
| **ServiceNow Integration** | Finds related tickets automatically |
| **Review History** | Shows last 3 reviews for context |
| **SLT Grouping** | Apps organized by owner |
| **Risk Ordering** | Highest risk apps first |
| **Skip Complex Apps** | Press 'S' to skip, handle later |
| **Multiple Servers** | Easy batch add for same app |
| **CSV Tracking** | All reviews saved for future reference |

---

## 📊 Review Data Flow

```
BMC Helix Metrics (CSV)
        ↓
[Filter: Risk >= 75 + Issues]
        ↓
Actionable Applications (22)
        ↓
[Group by SLT Member]
        ↓
Interactive Menu
        ↓
[User Selects App]
        ↓
[Query ServiceNow] ← service account
        ↓
[Load Previous Reviews] ← tracking CSV
        ↓
Show Details to User
        ↓
[User Inputs Manual Fields]
        ↓
Confirm & Save
        ↓
monthly-application-review.csv
```

---

## 🔑 Keyboard Shortcuts

| Key | Action |
|-----|--------|
| `1-22` | Select application number |
| `S` | Skip current application |
| `Q` | Quit and save progress |
| `Y` | Confirm save |
| `N` | Cancel |

---

## 📁 Where Everything Lives

```
\\nc_sensitive1\performanceandcapacity\BHCO-Reports\
├── scripts\
│   ├── Review-MonthlyApplications.ps1          ← Main script
│   ├── Setup-ServiceNowCredentials.ps1         ← One-time setup
│   ├── Add-MultipleServersToReview.ps1         ← Batch server add
│   └── config\
│       └── servicenow-creds.json               ← (Created by setup)
├── tracking\
│   └── monthly-application-review.csv          ← (Auto-created)
└── output\
    ├── BMC_Helix_AHO_Executive_Report_*.html   ← Auto-linked
    └── BMC_Helix_AHO_Slide3_*.html             ← Auto-linked
```

---

## 💡 Pro Tips

### Tip 1: Start with High-Risk Apps
The script orders apps by risk score. Start at #1 and work down.

### Tip 2: Use ServiceNow Context
The auto-found tickets give you instant history. Read them before filling in your review.

### Tip 3: Copy Previous Notes
If an app was reviewed last month, use similar wording for continuity.

### Tip 4: Skip Complex Apps
For apps needing deep investigation, press 'S' and handle manually later.

### Tip 5: Batch Similar Servers
If you have 5 Oracle servers, do the first one fully, then use Add-MultipleServers for the rest.

### Tip 6: Review the CSV
After your session, open the CSV in Excel to see all your reviews in one place.

---

## ⚠️ Troubleshooting Quick Fixes

### "ServiceNow credentials not found"
```powershell
.\Setup-ServiceNowCredentials.ps1
```

### "No actionable applications found"
Check if metrics CSV exists:
```powershell
Test-Path "\\nc_sensitive1\performanceandcapacity\BHCO-Reports\BMCHelixAHOmetrics.csv"
```

### "Can't find previous reviews"
First run creates the CSV automatically. It's normal on first use.

### ServiceNow not working
Run with skip flag:
```powershell
.\Review-MonthlyApplications.ps1 -SkipServiceNow
```

---

## 📞 Need Help?

1. ✅ Read the full documentation: `Monthly-Application-Review-Documentation.md`
2. ✅ Check inline script help: `Get-Help .\Review-MonthlyApplications.ps1 -Full`
3. ✅ Test with WhatIf mode
4. ✅ Contact team lead

---

## 🎓 5-Minute Tutorial

**Try this on your first run:**

1. Open PowerShell
2. Navigate to scripts folder
3. Run: `.\Review-MonthlyApplications.ps1 -WhatIf -SkipServiceNow`
4. See the menu
5. Type `1` to select first app
6. Fill in sample data
7. Review the summary
8. Type `N` to cancel (WhatIf mode anyway)
9. Type `Q` to quit

**Now you know how it works!**

**Next, do it for real:**
```powershell
.\Review-MonthlyApplications.ps1
```

---

## 📅 Monthly Workflow

**Week 1 of Month:**
```powershell
# Review all actionable apps
.\Review-MonthlyApplications.ps1

# Add multiple servers if needed
.\Add-MultipleServersToReview.ps1 -ApplicationName "App Name"
```

**Week 2:**
- Open CSV in Excel
- Review what you logged
- Create ServiceNow tickets for new issues
- Follow up on existing tickets

**Week 3-4:**
- Monitor ticket progress
- Update CSV with outcomes
- Prepare for next month

---

**Happy Reviewing! 🎉**
