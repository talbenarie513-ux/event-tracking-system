# מערכת ניהול אירועים - תכנון ופיתוח
## Event Management System - Planning & Development

---

## 📋 תיאור המערכת / System Description

**אפליקציית שולחן עבודה עצמאית** לניהול ומעקב אחר אירועים, תקלות ופניות פיתוח.

המערכת נפתחת **בחלון נפרד** (לא בדפדפן!) ועובדת לחלוטין ללא אינטרנט.

A standalone desktop application (not a website!) for tracking bugs and development requests.

---

## 🎯 תכונות עיקריות / Key Features

- ✅ ניהול אירועים מלא (יצירה, עריכה, מחיקה)
- ✅ 3 רמות הרשאות: אדמין, תכנון, פיתוח
- ✅ מעקב אחר סטטוס ולו"ז
- ✅ התראות על איחורים
- ✅ העלאת קבצים
- ✅ ניתוח נתונים וגרפים
- ✅ ייצוא דוחות Excel
- ✅ ניהול רשימת תפוצה
- ✅ עובד ללא אינטרנט (מקומי)
- ✅ **נפתח בחלון נפרד - לא בדפדפן!**
- ✅ ממשק מהיר ונוח לשימוש יומיומי
- ✅ יומן שינויים מלא (Audit Log) לכל אירוע
- ✅ מדריך למשתמש מובנה (כפתור ? בראש המסך)

---

## 🗄️ מידע על בסיס הנתונים / Database Information

**סוג בסיס הנתונים**: SQLite3

המערכת משתמשת ב-**SQLite** - בסיס נתונים קל משקל בקובץ אחד.

- **קובץ הדאטה**: `backend/event_system.db`
- **יתרונות**:
  - אין צורך בהתקנת שרת SQL נפרד
  - קל להעתקה וגיבוי (קובץ אחד)
  - מהיר ויעיל
  - עובד לחלוטין ללא חיבור לאינטרנט
  
- **טבלאות עיקריות**:
  - `users` - משתמשים והרשאות
  - `events` - אירועים ותקלות
  - `event_files` - קבצים מצורפים
  - `status_history` - היסטוריית שינויי סטטוס
  - `audit_log` - יומן שינויים מלא לכל שדה
  - `email_list` - רשימת תפוצה
  - `email_notifications` - העדפות התראות לכל משתמש

---

## 📦 מבנה הפרויקט / Project Structure

```
event-management-system/
│
├── .vscode/                          # VS Code settings
│
├── backend/                          # Backend server
│   ├── __pycache__/                  # Python cache (auto-generated)
│   ├── uploads/                      # Uploaded files (auto-created)
│   ├── app.py                        # Flask API
│   ├── database.py                   # Database management
│   ├── email_notifications.py        # Email & scheduler logic
│   ├── event_system.db               # SQLite database (auto-created)
│   ├── fix_database.py               # Database migration utility
│   ├── import_excel.py               # Import existing data
│   └── reports.py                    # Excel reports
│
├── frontend/                         # Frontend assets folder
├── static/                           # Static files (CSS, images, etc.)
├── templates/                        # HTML templates
├── uploads/                          # Root-level uploads
│
├── venv/                             # Virtual environment
│
├── app.js                            # Frontend JavaScript
├── index.html                        # Main UI
├── main.py                           # ⭐ DESKTOP APP LAUNCHER
├── README.md                         # This file
├── requirements.txt                  # Python dependencies
└── Run_App.bat                       # ⭐ DOUBLE-CLICK TO RUN!
```

---

## 🚀 התקנה ראשונית / Initial Setup

### שלב 1: הורד את הקבצים

**אופציה א': דרך Git**
```bash
git clone https://github.com/YOUR_ORGANIZATION/event-management-system.git
cd event-management-system
```

**אופציה ב': הורד ZIP**
- הורד את כל הקבצים
- חלץ לתיקייה במחשב
- פתח את התיקייה

### שלב 2: ודא שיש Python

```bash
python --version
```

אם אין Python, הורד מ: https://www.python.org/downloads/

### שלב 3: התקן את התלויות

```bash
python -m venv venv

# Windows:
venv\Scripts\activate
# Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

### שלב 4: אתחל את בסיס הנתונים

```bash
cd backend
python database.py
```

### שלב 5: (אופציונלי) ייבא נתונים קיימים

```bash
python import_excel.py
```

---

## 🎮 הפעלת המערכת / Running the System

### ⭐ הדרך הפשוטה ביותר:

**לחץ פעמיים על: `Run_App.bat`**

---

## 👥 ניהול משתמשים / User Management

### משתמש ברירת מחדל:
- **שם**: Admin
- **תפקיד**: אדמין
- **אימייל**: admin@example.com

### סוגי תפקידים והרשאות:

| פעולה | אדמין | תכנון | פיתוח |
|---|---|---|---|
| יצירת אירוע | ✅ | ✅ | ❌ |
| עריכת פרטי אירוע בסיסיים | ✅ (כל השדות אופציונליים) | ✅ | ❌ |
| עדכון סטטוס ופירוט סטטוס | ✅ | ❌ | ✅ |
| עדכון סיווג האירוע | ✅ | ✅ | ✅ |
| עדכון הערות נוספות | ✅ | ✅ | ✅ |
| עדכון לו"ז | ✅ | ✅ | ✅ |
| הקצאת גורם אחראי | ✅ | ❌ | ✅ |
| עדכון הצעת מחיר | ✅ | ❌ | ✅ |
| מחיקת אירוע | ✅ | ✅ | ❌ |
| ניהול משתמשים | ✅ | ❌ | ❌ |
| ניתוח וגרפים | ✅ | ❌ | ❌ |
| הפקת דוח Excel | ✅ | ✅ | ✅ |
| צפייה בהיסטוריית שינויים | ✅ | ✅ | ✅ |

> 💡 **הערה חשובה לאדמינים:** כל שדות הטופס הם **אופציונליים** לאדמינים — ניתן לשמור אירוע עם כל שדה חלקי.

---

## 🖥️ ממשק המשתמש / UI Features

### כפתור עזרה
לחיצה על כפתור **?** בפינה הימנית העליונה של הכותרת פותחת מדריך מובנה הכולל:
- הסבר על המערכת
- טבלת הרשאות לפי תפקיד
- הסבר על כל שדה בטופס
- רשימת הסטטוסים
- טיפים לשימוש

### תכונות עיקריות
- **חיפוש חופשי** — לפי תמצית, מערכת, פירוט או לקוח
- **מיון** — לפי מספר אירוע, תאריך, לו"ז, עדיפות
- **סינון עמודות** — לחיצה על כותרת עמודה (▼)
- **כרטיסי סטטיסטיקה** — לחיצה מסננת את הטבלה
- **האירועים שלי** — מסנן לפי גורם אחראי
- **היסטוריית שינויים** — כל שינוי בכל שדה מתועד
- **שחזור מחיקות** — אירועים שנמחקו ניתן לשחזר
- **אירועים באיחור** — שורות מסומנות באדום אוטומטית
- **הפקת דוח Excel** — אירועים פעילים/מעודכנים ב-7 ימים אחרונים

---

## 🔄 סטטוסים אפשריים

| סטטוס | משמעות |
|---|---|
| אירוע חדש | פתיחת אירוע — טרם טופל |
| בטיפול | הטיפול בעיצומו |
| בהכנת הצעת מחיר | מוכן הצעת מחיר ללקוח |
| בפיתוח | הועבר לצוות פיתוח |
| בבדיקת איכות של פיתוח | נבדק לפני שחרור |
| ממתין לאישור הצעת מחיר | ממתין לתשובת לקוח |
| בבדיקת תחנת תכנון | נבדק על ידי תחנת תכנון |
| הושלם הטיפול | ✅ סגור — לא מוצג בברירת מחדל |
| בהקפאה | ⏸ מוקפא — לא מוצג בברירת מחדל |
| טופל חלקית | טיפול חלקי בוצע |

---

## ✨ תכונות מתקדמות / Advanced Features

### 📋 יומן שינויים (Audit Log)
כל שינוי בכל שדה נשמר אוטומטית בטבלת `audit_log`.
- מי שינה, מה שינה, מאיזה ערך לאיזה ערך, ומתי
- ניתן לצפות בהיסטוריה המלאה דרך כפתור **📜 היסטוריה** בחלון הפרטים
- פעולות מעוקבות: יצירה, עדכון, מחיקה, שחזור

### 🪵 יומן שגיאות (Error Log)
כל שגיאת שרת נכתבת אוטומטית לקובץ:
```
backend/logs/app.log
```

### 📧 התראות אימייל
- שינוי סטטוס
- יצירת אירוע חדש
- הקצאת גורם אחראי
- אירועים באיחור (יומי — 08:00)
- דוח שבועי (ראשון — 08:00)

---

## 🌐 מעבר לשרת חברה / Moving to a Company Server

### ⚠️ שלב 1: עדכון כתובת השרת ב-app.js — חובה!

פתח את `app.js` ועדכן את **שורה 2**:

```javascript
// לפני:
const API_URL = 'http://localhost:5000/api';

// אחרי — החלף עם ה-IP האמיתי של השרת:
const API_URL = 'http://192.168.1.100:5000/api';
```

> 💡 לאיתור ה-IP: הרץ `ipconfig` ב-CMD וחפש "IPv4 Address"

### שלב 2: הגדרת שליחת אימיילים (אופציונלי)

פתח את `backend/email_notifications.py` ומלא:

```python
SMTP_CONFIG = {
    "host":       "",   # כתובת שרת המייל
    "from_email": "",   # כתובת השולח
    "username":   "",   # שם משתמש SMTP
    "password":   "",   # סיסמת SMTP
}
```

---

## 📦 בניית קובץ התקנה / Building an .exe

```bat
build.bat
```

התוצאה: `dist\EventManagementSystem\EventManagementSystem.exe`

> ⚠️ יש לשתף את **כל התיקייה** `dist\EventManagementSystem\` ולא רק את ה-.exe

---

## 🔒 גיבוי הנתונים / Data Backup

**קבצים חשובים לגיבוי:**
```
backend/event_system.db      ← כל הנתונים
backend/uploads/             ← קבצים מועלים
```

```bash
copy backend\event_system.db backup\event_system_%date%.db
xcopy backend\uploads backup\uploads /E /I
```



## מבנה מערכת 

┌──────────────────────────────────────────────────────────────────────────────┐
│                               USER OPENS APP                                 │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                          main.py → Flask (port 5000)
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (index.html + app.js)                       │
│  Functions: loadUsers(), loadEventsReadOnly(), openNewEventModal(),          │
│             openEditModal(), saveEvent(), deleteEvent(), uploadFile()        │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                               GET /api/users
                                      │
                                      ▼
┌─────────────────────────────── ROLE DECISION ────────────────────────────────┐
│                                                                              │
│     Development (status + files only)                                        │
│     Planning (create/edit/delete)                                            │
│     Admin (full access)                                                      │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                                      ▼
                               GET /api/events
                                      │
                                      ▼
┌──────────────────────────────── MAIN DASHBOARD ──────────────────────────────┐
│  • Event table                                                               │
│  • Filter / Search                                                           │
│  • My Events toggle                                                          │
│  • Click row → Event Detail                                                  │
└──────────────────────────────────────────────────────────────────────────────┘

═══════════════════════════════════════════════════════════════════════════════
                            EVENT OPERATIONS FLOW
═══════════════════════════════════════════════════════════════════════════════

[ CREATE EVENT ]
───────────────────────────────────────────────────────────────────────────────
User clicks "Create"
        │
        ▼
openNewEventModal()
        │
        ▼
POST /api/events
        │
        ▼
┌──────────────────────── BACKEND: Event Engine ───────────────────────────────┐
│ • Insert into events (SQLite)                                                │
│ • log_event_action(event_id, "created")                                      │
│ • notify_event_created()                                                     │
└──────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
Reload Event List


[ EDIT EVENT ]
───────────────────────────────────────────────────────────────────────────────
User clicks "Edit"
        │
        ▼
GET /api/events/<id>
        │
        ▼
openEditModal(id)
        │
        ▼
PUT /api/events/<id>
        │
        ▼
┌──────────────────────── BACKEND: Update Logic ───────────────────────────────┐
│ • Compare old vs new values                                                  │
│ • Update DB                                                                  │
│ • log_event_action(..., "updated")                                           │
│                                                                              │
│   IF status changed        → notify_status_changed()                         │
│   IF responsible assigned  → notify_assignment()                             │
└──────────────────────────────────────────────────────────────────────────────┘
        │
        ▼
UI Refresh


[ DELETE / RESTORE ]
───────────────────────────────────────────────────────────────────────────────
Delete:
PUT → set is_deleted = 1
        │
        ├── log_event_action(..., "deleted")
        ▼
Removed from active list

Restore:
POST /api/events/<id>/restore
        │
        ├── is_deleted = 0
        └── log_event_action(..., "restored")


═══════════════════════════════════════════════════════════════════════════════
                               FILE FLOW
═══════════════════════════════════════════════════════════════════════════════

Upload:
User selects file
        │
        ▼
POST /api/events/<event_id>/files
        │
        ▼
┌──────────────────────── BACKEND: File Engine ────────────────────────────────┐
│ • Save to /uploads/{event_id}/                                               │
│ • Insert metadata into event_files                                           │
└──────────────────────────────────────────────────────────────────────────────┘

Preview:
GET /api/files/<file_id>/view
        │
        ▼
┌──────────────────────── File Conversion Logic ───────────────────────────────┐
│ PDF/Image → Base64                                                           │
│ Excel      → pandas → HTML table                                             │
│ DOCX       → convert to HTML                                                 │
│ TXT        → plain text                                                      │
│ Other      → fallback to download                                            │
└──────────────────────────────────────────────────────────────────────────────┘

Download:
GET /api/files/<file_id>/download
        │
        ▼
Binary streamed to client


═══════════════════════════════════════════════════════════════════════════════
                           NOTIFICATION SYSTEM
═══════════════════════════════════════════════════════════════════════════════

Immediate Triggers:
───────────────────────────────────────────────────────────────────────────────
Event Created      → notify_event_created()      → send_email()
Status Changed     → notify_status_changed()     → send_email()
Assignment         → notify_assignment()         → send_email()

send_email():
    • Build EmailMessage
    • smtplib SSL (465) OR TLS (587)
    • Login (if configured)
    • Send


Scheduled Flow:
───────────────────────────────────────────────────────────────────────────────
Scheduler (APScheduler / schedule)
        │
        ▼
Weekly Job
        │
        ▼
generate_weekly_excel_report()
        │
        ├── Query events (last 7 days)
        ├── pandas → Excel (BytesIO)
        ▼
send_weekly_report()
        └── Attach Excel → send_email()


═══════════════════════════════════════════════════════════════════════════════
                               REPORT FLOW
═══════════════════════════════════════════════════════════════════════════════

Manual Download:
User clicks "Download Report"
        │
        ▼
GET /api/reports/excel
        │
        ▼
Backend:
    • Query DB
    • Generate Excel
    • Stream file


═══════════════════════════════════════════════════════════════════════════════
                                 DATA LAYER
═══════════════════════════════════════════════════════════════════════════════

SQLite (event_system.db)
    ├── events
    ├── users
    ├── audit_log
    ├── event_files
    ├── email_notifications
    └── email_list

File Storage:
    /uploads/{event_id}/files


═══════════════════════════════════════════════════════════════════════════════
                          COMPLETE CLICK PIPELINE
═══════════════════════════════════════════════════════════════════════════════

User Action
    ↓
Frontend JS Function
    ↓
Fetch → Flask Route
    ↓
Business Logic
    ├── SQLite DB Operation
    ├── Audit Log Entry
    ├── Conditional Email Trigger
    ├── File Handling (if applicable)
    └── Report Generation (if applicable)
    ↓
Response (JSON / File)
    ↓
UI Update
---

## 🐛 פתרון בעיות / Troubleshooting

| בעיה | פתרון |
|---|---|
| "Python לא מוכר" | התקן Python + סמן "Add to PATH" |
| "Module not found" | `pip install -r requirements.txt` |
| "Port 5000 in use" | שנה ל-`port=5001` ב-app.py |
| לא מצליח להתחבר מרחוק | בדוק חומת אש, IP ב-app.js, Port 5000 פתוח |
| שדות חסומים לאדמין | רענן את הדף ובחר שוב את המשתמש |

---

## 📞 תמיכה / Support

- בעיות טכניות: בדוק `backend/logs/app.log`
- שאלות שימוש: פנה למנהל המערכת

---

## 📄 רישיון / License

© 2026 Geoda.co.il - All Rights Reserved

---

**נוצר על ידי**: טל בן אריה 
**תאריך יצירה**: פברואר 2026  
**גרסה**: 1.1.0