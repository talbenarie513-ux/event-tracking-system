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