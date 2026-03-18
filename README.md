# מערכת ניהול אירועים - תכנון ופיתוח
## Event Management System - Planning & Development

---

## 📋 תיאור המערכת / System Description

אפליקציית ווב לניהול ומעקב אחר אירועים, תקלות ופניות פיתוח.
המערכת רצה על מחשב שרת אחד — משתמשים אחרים מתחברים דרך הדפדפן.

A web-based application for tracking bugs and development requests.
Runs on one server machine — other users connect via browser.

---

## 🎯 תכונות עיקריות / Key Features

- ✅ ניהול אירועים מלא (יצירה, עריכה, מחיקה רכה ושחזור)
- ✅ 3 רמות הרשאות: אדמין, תכנון, פיתוח
- ✅ הרשאות שדות לפי תפקיד ולפי משתמש בנפרד
- ✅ מעקב אחר סטטוס ולו"ז
- ✅ התראות על איחורים
- ✅ העלאת קבצים עם תצוגה מקדימה
- ✅ ניתוח נתונים וגרפים (אדמין בלבד)
- ✅ ייצוא דוחות Excel
- ✅ יומן שינויים מלא (Audit Log) לכל אירוע
- ✅ הערות פנימיות לכל אירוע
- ✅ התראות אימייל (חמישה סוגי התראות)
- ✅ תמיכה במשתמשים מרובים דרך רשת פנימית
- ✅ ממשק עברי RTL
- ✅ עובד ללא אינטרנט (מקומי)
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

> ⚠️ יש שני קבצי `event_system.db` — אחד ב-root ואחד ב-`backend/`. שניהם קיימים וזה בסדר. המערכת משתמשת בזה שב-`backend/`. אם תעביר לשרת חדש, `install.ps1` יעביר את זה שב-root ל-`backend/` אוטומטית אם צריך.

**טבלאות עיקריות**:
- `users` — משתמשים והרשאות
- `events` — אירועים ותקלות
- `event_files` — קבצים מצורפים
- `status_history` — היסטוריית שינויי סטטוס
- `audit_log` — יומן שינויים מלא לכל שדה
- `event_comments` — הערות פנימיות
- `field_permissions` — הרשאות שדות לפי תפקיד
- `user_field_permissions` — הרשאות שדות לפי משתמש
- `email_notifications` — העדפות התראות לכל משתמש
- `email_list` — רשימת תפוצה
- `user_last_seen` — מעקב כניסה אחרונה

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
│   ├── event_system.db               # ⭐ SQLite database — the real one used by the system
│   └── reports.py                    # Generates formatted Excel reports
│
├── venv/                             # Virtual environment (created during setup)
│
├── app.js                            # Frontend JavaScript — all UI logic and API calls
├── index.html                        # Main UI — the full single-page interface
├── main.py                           # ⭐ Server launcher — starts Flask
├── event_system.db                   # Root-level DB copy (both are fine — see note above)
├── install.ps1                       # ⭐ Full installation logic (run by START_INSTALL.bat)
├── START_INSTALL.bat                 # ⭐ Double-click to install everything on a new server
├── Run_App.bat                       # ⭐ Double-click to start the server after installation
├── README.md                         # This file
└── requirements.txt                  # Python package dependencies
```

> ⚠️ **הערה:** כל הקבצים המצורפים נשמרים בתוך `backend/uploads/` — לא בתיקיית ה-root.

---

פלת בזה

### שלב 1 — העתק את הפרויקט
העתק את כל תיקיית הפרויקט למחשב השרת החדש.
**אל תעתיק את תיקיית `venv/`** — היא תיווצר מחדש אוטומטית.

### שלב 2 — הרץ את ההתקנה
לחץ פעמיים על **`START_INSTALL.bat`**

הסקריפט עושה הכל אוטומטית:
1. מוריד ומתקין **Python 3.13.9** אם לא קיים (או אם הגרסה שגויה)
2. יוצר **venv** ומפעיל אותו
3. מתקין את כל **requirements.txt**
4. בודק אם יש `event_system.db` ב-root — מעביר ל-`backend/` אם צריך
5. יוצר תיקיית **uploads/** אם לא קיימת
6. פותח **פורט 5000** בחומת האש
7. מזהה את **ה-IP** אוטומטית ומעדכן `app.js`
8. מפעיל את השרת לאחר ההתקנה

### שלב 3 — גישה מהרשת
לאחר ההתקנה, משתמשים אחרים מתחברים דרך הדפדפן:
```
http://SERVER_IP:5000
```
אין צורך ב-.exe, אין צורך בהתקנה אצל המשתמשים — רק דפדפן.

---

## 🎮 הפעלת המערכת / Running the System

### ⭐ הדרך הפשוטה ביותר:
לחץ פעמיים על **`Run_App.bat`**

### או מה-CMD:
```cmd
cd C:\path\to\project
venv\Scripts\activate
python main.py
```

> 💡 **למה לא לחץ פעמיים על main.py?**
> כי double-click פותח את הקובץ לעריכה — לא מריץ אותו בסביבה הנכונה.
> `Run_App.bat` מפעיל את ה-venv ואז מריץ את main.py בצורה הנכונה.

---

## 🌐 שימוש עם מספר משתמשים / Multi-User Setup

המערכת תומכת במספר משתמשים בו-זמנית דרך רשת פנימית (LAN/WiFi משרדי).
יש מחשב אחד שמשמש **שרת** — שאר המשתמשים מתחברים דרך הדפדפן.

### איך זה עובד

```
SERVER MACHINE                    CLIENT MACHINES
──────────────────                ──────────────────────────
Run_App.bat                       Any browser
      │                                     │
Flask on port 5000       ◄─── HTTP ─────────┘
      │                     http://192.168.1.XXX:5000
event_system.db
backend/uploads/
```

- ה**שרת** מריץ את Flask, מחזיק את הדאטהבייס וכל הקבצים
- כל **משתמש** פותח דפדפן ומנווט לכתובת ה-IP של השרת
- אם השרת כבוי — אף אחד לא יכול להיכנס

---

## 🔧 שינוי פורט / Changing the Port

אם פורט 5000 תפוס, שנה ב-**5 מקומות**:

| קובץ | מה לשנות |
|---|---|
| `main.py` | `app.run(host='0.0.0.0', port=5000, ...)` |
| `main.py` | `requests.get('http://127.0.0.1:5000/api/files/...')` |
| `main.py` | `requests.get('http://127.0.0.1:5000/api/reports/excel')` |
| `app.js` | `const API_URL = 'http://localhost:5000/api'` |
| `install.ps1` | `-LocalPort 5000` (firewall rule) |

**דוגמה — מעבר לפורט 5001:**
```python
# main.py
app.run(host='0.0.0.0', port=5001, ...)
requests.get('http://127.0.0.1:5001/api/files/...')
requests.get('http://127.0.0.1:5001/api/reports/excel')
```
```javascript
// app.js
const API_URL = 'http://localhost:5001/api';
```
```powershell
# install.ps1
-LocalPort 5001
```

---

## 🌍 שינוי כתובת IP של השרת / Changing the Server IP

אם ה-IP של השרת השתנה, שנה ב-**מקום אחד בלבד**:

| קובץ | מה לשנות |
|---|---|
| `app.js` | `const API_URL = 'http://OLD_IP:5000/api'` → `'http://NEW_IP:5000/api'` |

> 💡 `install.ps1` מזהה ומעדכן את ה-IP **אוטומטית** בכל הרצה — כך שאם תריץ שוב את `START_INSTALL.bat` על השרת החדש, הוא יעדכן את `app.js` בעצמו.

**עדכון ידני אם צריך:**
```javascript
// app.js — שורה 1
const API_URL = 'http://192.168.1.XXX:5000/api';  // החלף XXX בIP האמיתי
```

**כיצד למצוא את ה-IP של השרת:**
```cmd
ipconfig
```
חפש **IPv4 Address** — לדוגמה: `192.168.1.105`

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
install.ps1
START_INSTALL.bat
Run_App.bat
```

> ⚠️ **אל תעתיק** את `venv/` — היא תיווצר מחדש ע"י `START_INSTALL.bat`

### שלב 2 — הרץ את ההתקנה על השרת החדש
לחץ פעמיים על `START_INSTALL.bat` — הכל אוטומטי כולל עדכון ה-IP.

---

## 👥 ניהול משתמשים / User Management

### משתמש ברירת מחדל (התקנה חדשה):
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

## 🔄 סטטוסים אפשריים / Event Statuses

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

### 📧 התראות אימייל
לפני שליחת מיילים, ערוך את `backend/email_notifications.py`:
```python
SMTP_CONFIG = {
    "host":       "mail.geoda.co.il",    # כתובת שרת המייל
    "from_email": "noreply@geoda.co.il", # כתובת השולח
    "username":   "noreply@geoda.co.il", # שם משתמש
    "password":   "YOUR_PASSWORD",       # סיסמה
    "port":       587,
    "use_tls":    True,
}
```
כל עוד השדות ריקים — המערכת רצה ב**stub mode** (מיילים מודפסים לקונסול בלבד).

סוגי התראות:
- שינוי סטטוס
- יצירת אירוע חדש
- הקצאת גורם אחראי
- אירועים באיחור (יומי — 08:00)
- דוח שבועי (ראשון — 08:00)

---

## 🔒 גיבוי ושחזור נתונים / Backup & Restore

### יצירת גיבוי
**קבצים חשובים לגיבוי:**
```
backend/event_system.db      ← כל הנתונים
backend/uploads/             ← קבצים מועלים
```

```cmd
copy backend\event_system.db backup\event_system_%date%.db
xcopy backend\uploads backup\uploads /E /I
```

### שחזור מגיבוי
1. **עצור את השרת** — סגור את חלון `Run_App.bat`
2. **החלף את קובץ הדאטהבייס:**
```cmd
copy backup\event_system_DATE.db backend\event_system.db
```
3. **החלף את תיקיית הקבצים המצורפים (אם צריך):**
```cmd
xcopy backup\uploads backend\uploads /E /I /Y
```
4. **הפעל מחדש את השרת** — הרץ `Run_App.bat`

> ✅ SQLite הוא קובץ אחד בלבד — שחזור הוא פשוט החלפת קובץ

---

## ⚠️ מגבלות ואבטחה ידועות / Known Limitations & Security

### 🔑 אין מערכת התחברות (Login)
המערכת **אינה מוגנת בסיסמה**. בחירת המשתמש מהרשימה מבוססת על אמון בלבד. יש לוודא שהרשת הפנימית מאובטחת וש הגישה לשרת מוגבלת לאנשים מורשים.

### 🔐 סיסמת אימייל בטקסט גלוי
בקובץ `backend/email_notifications.py`, הסיסמה נשמרת ישירות בקוד.
- אל תשתמש בסיסמה ראשית של החברה — צור סיסמת אפליקציה ייעודית
- שמור את קבצי הקוד פרטיים

### 🔢 סיכון כפל מזהים (Duplicate ID)
אם שני משתמשים יוצרים אירוע באותה שנייה בדיוק, שניהם עלולים לקבל את אותו ה-ID. נדיר בצוות קטן.

### 📊 מגבלות SQLite
מתאים לצוותים קטנים (עד ~20 משתמשים במקביל). לצוות גדול — שקול מעבר ל-PostgreSQL.

---

## 🐛 פתרון בעיות / Troubleshooting

| בעיה | פתרון |
|---|---|
| Python לא נמצא | `START_INSTALL.bat` מתקין אוטומטית |
| "Module not found" | הרץ שוב את `START_INSTALL.bat` |
| "Port 5000 in use" | שנה פורט ב-5 המקומות המפורטים למעלה |
| משתמש רואה דף ריק | השרת לא רץ — הרץ `Run_App.bat` |
| לא מצליח להתחבר מרחוק | בדוק IP ב-`app.js`, ופורט 5000 פתוח בחומת האש |
| שדות חסומים לאדמין | רענן את הדף ובחר שוב את המשתמש |

### ⚠️ דגשים חשובים למולטי-יוזר

| נושא | פרטים |
|---|---|
| השרת חייב לרוץ | לפני שמשתמש פותח את הדפדפן, השרת חייב לרוץ |
| אותה רשת | כל המשתמשים חייבים להיות באותה רשת (LAN/WiFi משרדי) |
| שינוי IP | אם ה-IP של השרת השתנה — יש לעדכן `app.js` ולהפעיל מחדש |
| גישה מבחוץ | המערכת מיועדת לרשת פנימית בלבד — לא לגישה מהאינטרנט |

---

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

## 🗺️ מבנה וקשרי הקבצים במערכת / System Architecture

```
═══════════════════════════════════════════════════════════════════
                        הפעלת המערכת
═══════════════════════════════════════════════════════════════════

  START_INSTALL.bat  (פעם אחת בלבד — שרת חדש)
       │
       ▼
  install.ps1
  ├── Python 3.13.9
  ├── venv + requirements.txt
  ├── מעביר event_system.db ל-backend/ אם צריך
  ├── פותח פורט 5000
  └── מזהה IP ומעדכן app.js
       │
       ▼
  Run_App.bat  (כל פעם שרוצים להפעיל)
       │
       ▼
  main.py
  ├── מפעיל Flask בthread נפרד (port 5000, host 0.0.0.0)
  └── מפעיל email scheduler

═══════════════════════════════════════════════════════════════════
                      שרת Flask (Backend)
═══════════════════════════════════════════════════════════════════

  backend/app.py  (כל ה-API Routes)
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
            │         └──► backend/event_system.db
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
            │    ├── trigger_new_event()        ── נקרא מ-app.py בעת יצירת אירוע
            │    ├── trigger_status_change()    ── נקרא מ-app.py בעת עדכון סטטוס
            │    ├── trigger_responsible_assigned() ── נקרא מ-app.py בעת הקצאת אחראי
            │    ├── send_overdue_notifications() ── Scheduler: כל יום 08:00
            │    └── send_weekly_report()       ── Scheduler: כל ראשון 08:00
            │              └──► backend/reports.py
            │                   └── generate_excel_report()
            │                       ├── נקרא מ-app.py (כפתור "הפקת דוח")
            │                       └── נקרא מ-email_notifications.py (דוח שבועי)
            │
            └──► backend/uploads/
                 └── uploads/{event_id}/{timestamp}_{filename}

═══════════════════════════════════════════════════════════════════
                     ממשק המשתמש (Frontend)
═══════════════════════════════════════════════════════════════════

  משתמשים מתחברים דרך דפדפן: http://SERVER_IP:5000
       │
       ▼
  index.html  (כל ה-HTML + CSS של הממשק)
       │
       └── טוען ──► app.js
                    ├── loadUsers()              ── /api/users
                    ├── loadEvents()             ── /api/events
                    ├── handleEventSubmit()      ── /api/events POST/PUT
                    ├── openFile() / downloadFile() ── /api/files
                    ├── loadPermissions()        ── /api/user-permissions
                    ├── showAnalysisModal()      ── Chart.js גרפים
                    ├── generateReport()         ── /api/reports/excel
                    └── showAdminPanel()         ── ניהול משתמשים/הרשאות

═══════════════════════════════════════════════════════════════════
              תלויות Python (requirements.txt)
═══════════════════════════════════════════════════════════════════

  Flask          ── שרת ה-API
  flask-cors     ── מאפשר גישת CORS
  openpyxl       ── קריאת/כתיבת .xlsx
  xlsxwriter     ── יצירת דוחות Excel
  xlrd           ── קריאת .xls ישן
  python-docx    ── קריאת .docx
  pywebview      ── (נשמר ב-requirements, לא בשימוש פעיל)
  apscheduler    ── Scheduler לתזכורות מייל
  Werkzeug       ── כלי עזר ל-Flask
  requests       ── HTTP מ-main.py
```

---

## 📞 תמיכה / Support

- בעיות טכניות: בדוק פלט הקונסול של `Run_App.bat`
- שאלות שימוש: פנה למנהל המערכת

---

## 📄 רישיון / License

© 2026 Geoda.co.il - All Rights Reserved

---

**נוצר על ידי**: טל בן אריה
**תאריך יצירה**: פברואר 2026
**גרסה**: 1.0.0