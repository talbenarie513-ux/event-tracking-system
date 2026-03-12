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
- ✅ תמיכה במשתמשים מרובים דרך רשת פנימית

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
│   ├── uploads/                      # Uploaded files storage (auto-created at runtime)
│   ├── app.py                        # Flask API — all routes and endpoints
│   ├── database.py                   # Database manager — creates and manages all tables
│   ├── email_notifications.py        # Email sending logic and scheduled jobs
│   ├── event_system.db               # SQLite database file — contains all data (auto-created)
│   ├── fix_database.py               # One-time utility to wipe and re-import data from Excel
│   ├── import_excel.py               # Imports existing data from an Excel file into the database
│   └── reports.py                    # Generates formatted Excel reports
│
├── venv/                             # Virtual environment (created during setup)
│
├── app.js                            # Frontend JavaScript — all UI logic and API calls
├── index.html                        # Main UI — the full single-page interface
├── main.py                           # ⭐ SERVER launcher — starts Flask + opens desktop window
├── launcher.py                       # ⭐ CLIENT launcher — opens desktop window pointed at server
├── README.md                         # This file
├── requirements.txt                  # Python package dependencies
├── Run_App.bat                       # ⭐ SERVER: double-click to start the server
├── build.bat                         # Builds the SERVER into a standalone .exe
└── build_client.bat                  # ⭐ CLIENT: builds the client launcher into a .exe to send to users
```

> ⚠️ **הערה:** כל הקבצים המצורפים נשמרים בתוך `backend/uploads/` — לא בתיקיית ה-root.

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

## 🌐 שימוש עם מספר משתמשים / Multi-User Setup

המערכת תומכת במספר משתמשים בו-זמנית דרך רשת פנימית (LAN/WiFi משרדי).
יש מחשב אחד שמשמש **שרת** — שאר המשתמשים מתחברים אליו.

### איך זה עובד

```
SERVER MACHINE                    CLIENT MACHINES
──────────────────                ──────────────────────────
Run_App.bat                       EventManagementSystem.exe
      │                                     │
Flask on port 5000                 pywebview window
      │                                     │
event_system.db          ◄─── HTTP ─────────┘
backend/uploads/            192.168.1.XXX:5000
```

- ה**שרת** מריץ את Flask, מחזיק את הדאטהבייס וכל הקבצים
- כל **משתמש** פותח חלון דסקטופ שמתחבר לשרת דרך הרשת
- אם השרת כבוי — אף אחד לא יכול להיכנס

---

### שלב 1 — הגדר את השרת

על מחשב השרת, הרץ `ipconfig` ב-CMD ואתר את **IPv4 Address**:
```
IPv4 Address: 192.168.1.XXX   ← זה ה-IP שתצטרך
```

ודא שפורט 5000 פתוח בחומת האש:
```bat
netsh advfirewall firewall add rule name="EventSystem" dir=in action=allow protocol=TCP localport=5000
```

הרץ את השרת:
```bat
Run_App.bat
```

---

### שלב 2 — עדכן את כתובת השרת ב-app.js

פתח את `app.js` ועדכן את **שורה 1**:
```javascript
// לפני:
const API_URL = 'http://localhost:5000/api';

// אחרי — החלף עם ה-IP האמיתי של השרת:
const API_URL = 'http://192.168.1.XXX:5000/api';
```

> ⚠️ שלב זה חובה — בלעדיו המשתמשים יראו את הממשק אך לא יוכלו לטעון נתונים

---

### שלב 3 — בנה את ה-.exe ללקוחות

#### launcher.py
קובץ זה רץ על מחשב **המשתמש** (לא השרת).
הוא פותח חלון דסקטופ שמתחבר לשרת — ללא Flask, ללא דאטהבייס.

לפני הבנייה, ערוך את `launcher.py` ועדכן את ה-IP:
```python
SERVER_URL = 'http://192.168.1.XXX:5000'  # ← שנה ל-IP האמיתי
```

#### build_client.bat
קובץ זה בונה את `launcher.py` לקובץ `.exe` שאפשר לשלוח לכל משתמש.
מריצים אותו **פעם אחת בלבד** על מחשב השרת:

```bat
build_client.bat
```

התוצאה תופיע ב:
```
dist\EventManagementSystem\
└── EventManagementSystem.exe   ← זה מה שמשלחים למשתמשים
```

---

### שלב 4 — שלח למשתמשים

1. **דחוס** את התיקייה `dist\EventManagementSystem\` לקובץ ZIP
2. **שלח** את ה-ZIP לכל משתמש
3. המשתמש **מחלץ** את התיקייה לכל מקום במחשב שלו
4. המשתמש **לוחץ פעמיים** על `EventManagementSystem.exe` — זהו!

> ✅ אין צורך ב-Python, אין התקנות, אין הגדרות — רק לפתוח את ה-.exe

---

### ⚠️ דגשים חשובים למולטי-יוזר

| נושא | פרטים |
|---|---|
| השרת חייב לרוץ | לפני שמשתמש פותח את ה-.exe, השרת חייב לרוץ |
| אותה רשת | כל המשתמשים חייבים להיות באותה רשת (LAN/WiFi משרדי) |
| שינוי IP | אם ה-IP של השרת השתנה — יש לעדכן `launcher.py` ולבנות מחדש |
| שליחת תיקייה שלמה | יש לשלוח את כל התיקייה `EventManagementSystem\` ולא רק את ה-.exe |

---

## 🔄 מעבר לשרת אחר / Moving to a Different Server

### שלב 1 — העתק קבצים לשרת החדש

קבצים חיוניים להעתקה:
```
backend/
├── app.py
├── database.py
├── email_notifications.py
├── reports.py
├── event_system.db        ← כל הנתונים שלך
└── uploads/               ← כל הקבצים המצורפים

index.html
app.js
main.py
requirements.txt
Run_App.bat
launcher.py
build_client.bat
```

### שלב 2 — התקן Python והתלויות בשרת החדש
```bat
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

### שלב 3 — עדכן IP ב-app.js ו-launcher.py
```javascript
// app.js שורה 1:
const API_URL = 'http://NEW_SERVER_IP:5000/api';
```
```python
# launcher.py:
SERVER_URL = 'http://NEW_SERVER_IP:5000'
```

### שלב 4 — פתח פורט 5000 בחומת האש
```bat
netsh advfirewall firewall add rule name="EventSystem" dir=in action=allow protocol=TCP localport=5000
```

### שלב 5 — בנה .exe חדש ושלח למשתמשים
```bat
build_client.bat
```
אחרי הבנייה — שלח את `dist\EventManagementSystem\` לכל המשתמשים מחדש.

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
- **כרטיסי סטטיסטיקה** — לחיצה על כרטיס מסננת את הטבלה
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
| בבדיקת תחום תכנון | נבדק על ידי תחנת תכנון |
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

## 📦 בניית קובץ התקנה / Building .exe Files

### בניית .exe לשרת
```bat
build.bat
```
התוצאה: `dist\EventManagementSystem\EventManagementSystem.exe`

### בניית .exe ללקוחות
```bat
build_client.bat
```
התוצאה: `dist\EventManagementSystem\EventManagementSystem.exe`

> ⚠️ שני הקבצים מייצרים תיקייה בשם `EventManagementSystem` — הרץ אותם בנפרד
> ויש לשתף את **כל התיקייה** ולא רק את ה-.exe

---

## 🔒 גיבוי ושחזור נתונים / Backup & Restore

### יצירת גיבוי
**קבצים חשובים לגיבוי:**
```
backend/event_system.db      ← כל הנתונים
backend/uploads/             ← קבצים מועלים
```

```bash
copy backend\event_system.db backup\event_system_%date%.db
xcopy backend\uploads backup\uploads /E /I
```

### שחזור מגיבוי
אם משהו השתבש ויש צורך לחזור לגיבוי קודם:

1. **עצור את השרת** — סגור את חלון `Run_App.bat`
2. **החלף את קובץ הדאטהבייס:**
```bash
copy backup\event_system_DATE.db backend\event_system.db
```
3. **החלף את תיקיית הקבצים המצורפים (אם צריך):**
```bash
xcopy backup\uploads backend\uploads /E /I /Y
```
4. **הפעל מחדש את השרת** — הרץ `Run_App.bat`

> ✅ SQLite הוא קובץ אחד בלבד — שחזור הוא פשוט החלפת קובץ

---

## מבנה מערכת

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                               USER OPENS APP                                 │
│              (double-clicks EventManagementSystem.exe)                       │
└──────────────────────────────────────────────────────────────────────────────┘
                                      │
                    ┌─────────────────┴──────────────────┐
                    │                                    │
             SERVER MACHINE                     CLIENT MACHINES
             main.py → Flask                    launcher.py
             port 5000                          pywebview window
                    │                                    │
                    └─────────────── HTTP ───────────────┘
                                192.168.1.XXX:5000
                                      │
                                      ▼
┌──────────────────────────────────────────────────────────────────────────────┐
│                         FRONTEND (index.html + app.js)                       │
│  Functions: loadUsers(), loadEventsReadOnly(), openNewEventModal(),          │
│             openEditModal(), saveEvent(), deleteEvent(), uploadFile()...     │
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
```
## סרטוט מערכת 
## 🗺️ מבנה וקשרי הקבצים במערכת

═══════════════════════════════════════════════════════════════════
                        הפעלת המערכת
═══════════════════════════════════════════════════════════════════

  Run_App.bat
       │
       ▼
  main.py  ──────────────────────────────────────────────────────┐
  (מרכז השליטה)                                                   │
       │                                                          │
       ├── מפעיל Flask בthread נפרד                              │
       ├── מפעיל email scheduler                                  │
       └── פותח חלון pywebview ──► http://127.0.0.1:5000         │
                                                                  │
═══════════════════════════════════════════════════════════════════
                      שרת Flask (Backend)
═══════════════════════════════════════════════════════════════════
                                                                  │
  backend/app.py  ◄─────────────────────────────────────────────┘
  (כל ה-API Routes)
       │
       ├── /api/events         ── CRUD אירועים
       ├── /api/users          ── ניהול משתמשים
       ├── /api/files          ── העלאה/הורדה/תצוגה
       ├── /api/permissions    ── הרשאות לפי תפקיד
       ├── /api/user-permissions ── הרשאות לפי משתמש
       ├── /api/stats          ── סטטיסטיקות
       ├── /api/reports/excel  ── הפקת דוח
       └── /api/comments       ── הערות פנימיות
            │
            ├──► backend/database.py
            │    (מנהל SQLite — יוצר טבלאות, מאתחל הרשאות)
            │         │
            │         └──► backend/event_system.db  ◄── כל הנתונים
            │              ┌─────────────────────────────────┐
            │              │  users                          │
            │              │  events                         │
            │              │  event_files                    │
            │              │  audit_log                      │
            │              │  status_history                 │
            │              │  event_comments                 │
            │              │  field_permissions              │
            │              │  user_field_permissions         │
            │              │  email_notifications            │
            │              │  user_last_seen                 │
            │              │  email_list                     │
            │              └─────────────────────────────────┘
            │
            ├──► backend/email_notifications.py
            │    (שליחת מיילים + Scheduler)
            │    ├── trigger_new_event()        ── נקרא מ-app.py בעת יצירת אירוע
            │    ├── trigger_status_change()    ── נקרא מ-app.py בעת עדכון סטטוס
            │    ├── trigger_responsible_assigned() ── נקרא מ-app.py בעת הקצאת אחראי
            │    ├── send_overdue_notifications() ── Scheduler: כל יום 08:00
            │    └── send_weekly_report()       ── Scheduler: כל ראשון 08:00
            │              │
            │              └──► backend/reports.py
            │                   (בונה קובץ Excel עם xlsxwriter)
            │                   └── generate_excel_report()
            │                       ├── נקרא מ-app.py (כפתור "הפקת דוח")
            │                       └── נקרא מ-email_notifications.py (דוח שבועי)
            │
            └──► backend/uploads/
                 (קבצים מצורפים — מאורגנים לפי event_id)
                 └── uploads/{event_id}/{timestamp}_{filename}

═══════════════════════════════════════════════════════════════════
                     ממשק המשתמש (Frontend)
═══════════════════════════════════════════════════════════════════

  index.html  ◄── נטען מהשרת על ידי הדפדפן / pywebview
  (כל ה-HTML + CSS של הממשק)
       │
       └── טוען ──► app.js
                    (כל לוגיקת הלקוח)
                    ├── loadUsers()              ── /api/users
                    ├── loadEvents()             ── /api/events
                    ├── handleEventSubmit()      ── /api/events POST/PUT
                    ├── openFile() / downloadFile() ── /api/files
                    ├── loadPermissions()        ── /api/user-permissions
                    ├── showAnalysisModal()      ── Chart.js גרפים
                    ├── generateReport()         ── /api/reports/excel
                    └── showAdminPanel()         ── ניהול משתמשים/הרשאות

═══════════════════════════════════════════════════════════════════
                 משתמשי רשת (Multi-User)
═══════════════════════════════════════════════════════════════════

  build_client.bat
       │
       ▼
  launcher.py  ──► EventManagementSystem.exe
  (נשלח לכל משתמש)      (חלון pywebview)
       │                       │
       └───────────────────────┘
                    │
                    │  HTTP (רשת פנימית)
                    ▼
             192.168.1.XXX:5000
             (שרת Flask על מחשב השרת)

═══════════════════════════════════════════════════════════════════
              כלי עזר חד-פעמיים (One-time utilities)
═══════════════════════════════════════════════════════════════════

  fix_database.py
  ├── מוחק את כל הנתונים
  └── קורא ל-import_excel.py

  import_excel.py
  └── קורא מקובץ Excel ומכניס נתונים ל-event_system.db
      (מדלג על ID כפולים — בטוח להרצה על DB קיים)

═══════════════════════════════════════════════════════════════════
              תלויות Python (requirements.txt)
═══════════════════════════════════════════════════════════════════

  Flask          ── שרת ה-API
  flask-cors     ── מאפשר גישת CORS
  openpyxl       ── קריאת/כתיבת .xlsx
  xlsxwriter     ── יצירת דוחות Excel
  xlrd           ── קריאת .xls ישן
  python-docx    ── קריאת .docx
  pywebview      ── חלון דסקטופ
  apscheduler    ── Scheduler לתזכורות מייל
  Werkzeug       ── כלי עזר ל-Flask
  requests       ── HTTP מ-DownloadAPI ב-main.py

---

## 🐛 פתרון בעיות / Troubleshooting

| בעיה | פתרון |
|---|---|
| "Python לא מוכר" | התקן Python + סמן "Add to PATH" |
| "Module not found" | `pip install -r requirements.txt` |
| "Port 5000 in use" | שנה ל-`port=5001` ב-app.py |
| לא מצליח להתחבר מרחוק | בדוק חומת אש, IP ב-app.js ו-launcher.py, Port 5000 פתוח |
| משתמש רואה דף ריק | השרת לא רץ — הרץ `Run_App.bat` על מחשב השרת |
| שדות חסומים לאדמין | רענן את הדף ובחר שוב את המשתמש |
| ה-.exe של הלקוח נפתח אך אין נתונים | עדכן את SERVER_URL ב-`launcher.py` ובנה מחדש |

### כיצד לבדוק אם השרת פועל

**שיטה 1 — בדוק את חלון ה-CMD:**
חפש חלון CMD פתוח עם הכותרת "Event Management System".
אם החלון סגור — השרת לא פועל. הרץ `Run_App.bat` מחדש.

**שיטה 2 — פתח דפדפן:**
על כל מחשב ברשת, הקלד בדפדפן:
```
http://SERVER_IP:5000
```
- ✅ רואה את הממשק = השרת פועל
- ❌ שגיאת חיבור = השרת לא פועל או IP שגוי

---

## ⚠️ מגבלות ואבטחה ידועות / Known Limitations & Security

### 🔑 אין מערכת התחברות (Login)
המערכת **אינה מוגנת בסיסמה**. כל מי שפותח את ה-.exe ונמצא באותה רשת יכול להיכנס ולהתחזות לכל משתמש — בחירת המשתמש מהרשימה מבוססת על אמון בלבד, לא אימות אמיתי. יש לוודא שה-.exe מופץ רק לאנשים מורשים ושהרשת הפנימית מאובטחת.

### 🔐 סיסמת אימייל בטקסט גלוי
בקובץ `backend/email_notifications.py`, סיסמת ה-SMTP נשמרת ישירות בקוד:
```python
SMTP_CONFIG = {
    "password": "YOUR_PASSWORD_HERE",  # ← כל מי שיש לו גישה לקוד יכול לראות את הסיסמה
}
```
**מה לעשות:**
- אל תשתמש בסיסמה ראשית של החברה — צור סיסמת אפליקציה ייעודית
- שמור את קבצי הקוד פרטיים ואל תעלה אותם ל-GitHub ציבורי
- בגרסה עתידית ניתן לעבור למשתני סביבה (environment variables) במקום טקסט גלוי

### 🔢 סיכון כפל מזהים (Duplicate ID)
בקובץ `backend/app.py`, הפונקציה `get_next_available_id()` מוצאת את ה-ID הגבוה ביותר ומוסיפה 1.
אם שני משתמשים יוצרים אירוע **באותה שנייה בדיוק**, שניהם יקבלו את אותו ה-ID ואחד מהם ייכשל.
זה נדיר בצוות קטן אך כדאי לדעת שזה קיים.

### 📊 מגבלות SQLite
SQLite מתאים לצוותים קטנים (עד ~20 משתמשים במקביל). הוא אינו מתוכנן לכתיבות רבות בו-זמנית. אם המערכת תגדל לצוות גדול — מומלץ לשקול מעבר ל-PostgreSQL או MySQL.

---

## ⚠️ נתיבים קשיחים בקוד / Hardcoded Paths

שני קבצים מכילים נתיבים מוחלטים שמצביעים למחשב הפיתוח המקורי.
אם תריץ אותם ללא עדכון — הם יכשלו עם שגיאת "file not found".

Two files contain absolute paths pointing to the original development machine.
Running them without updating will fail with a "file not found" error.

### fix_database.py

```python
# שורה שצריך לעדכן / Line to update:
excel_path = r'C:\Users\tal_ba\Documents\...\חוברת1.xlsx'

# שנה ל-נתיב של קובץ ה-Excel שלך / Change to your own Excel file path:
excel_path = r'C:\YOUR_PATH\your_file.xlsx'
```

> ⚠️ קובץ זה **מוחק את כל הנתונים** לפני הייבוא מחדש.
> הרץ אותו רק בהגדרה ראשונית או כשברצונך לאפס את הדאטהבייס לחלוטין.
>
> This file **deletes all existing data** before re-importing.
> Only run it during initial setup or when you intentionally want to reset the database.

### import_excel.py

```python
# שורה שצריך לעדכן / Line to update:
excel_path = r'C:\Users\tal_ba\Documents\...\חוברת1.xlsx'

# שנה ל-נתיב של קובץ ה-Excel שלך / Change to your own Excel file path:
excel_path = r'C:\YOUR_PATH\your_file.xlsx'
```

> ✅ קובץ זה בטוח יותר — הוא מייבא נתונים מבלי למחוק את הקיים (מדלג על ID-ים כפולים).
>
> This file is safer — it imports without deleting existing data (skips duplicate IDs).

---

**כלל אצבע:** אם תראה שגיאת `FileNotFoundError` עם נתיב שמתחיל ב-`C:\Users\tal_ba\` —
זה אחד משני הקבצים האלה. עדכן את `excel_path` בסוף הקובץ הרלוונטי ונסה שוב.

**Rule of thumb:** If you see a `FileNotFoundError` with a path starting with `C:\Users\tal_ba\` —
it's one of these two files. Update the `excel_path` at the bottom of the relevant file and try again.


## 📞 תמיכה / Support

- בעיות טכניות: בדוק `backend/logs/app.log`
- שאלות שימוש: פנה למנהל המערכת

---

## 📄 רישיון / License

© 2026 Geoda.co.il - All Rights Reserved

---

**נוצר על ידי**: טל בן אריה  
**תאריך יצירה**: פברואר 2026  
**גרסה**: 1.0.0