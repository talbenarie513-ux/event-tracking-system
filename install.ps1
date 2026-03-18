# ============================================================
# install.ps1 — התקנה מלאה של מערכת ניהול אירועים
# מריצים פעם אחת על מחשב שרת נקי (ללא Python, ללא כלום)
#
# הרצה:
#   קליק ימני על install.ps1 → "Run with PowerShell"
#   או מ-PowerShell:  Set-ExecutionPolicy Bypass -Scope Process; .\install.ps1
# ============================================================

$Host.UI.RawUI.WindowTitle = "התקנת מערכת ניהול אירועים"

# ── צבעים לפלט ────────────────────────────────────────────────
function Write-Step  { param($n,$t) Write-Host "`n[$n] $t" -ForegroundColor Cyan }
function Write-OK    { param($t)    Write-Host "  ✔  $t"  -ForegroundColor Green }
function Write-Warn  { param($t)    Write-Host "  ⚠  $t"  -ForegroundColor Yellow }
function Write-Fail  { param($t)    Write-Host "  ✘  $t"  -ForegroundColor Red }

function Exit-Install {
    param($msg)
    Write-Fail $msg
    Write-Host "`nההתקנה נעצרה. לחץ Enter לסגירה..." -ForegroundColor Red
    Read-Host | Out-Null
    exit 1
}

# ── כותרת ─────────────────────────────────────────────────────
Clear-Host
Write-Host "============================================================" -ForegroundColor Magenta
Write-Host "   מערכת ניהול אירועים — תכנון ופיתוח" -ForegroundColor Magenta
Write-Host "   התקנה אוטומטית מלאה" -ForegroundColor Magenta
Write-Host "============================================================" -ForegroundColor Magenta

# ── בדוק שהסקריפט רץ מתיקיית הפרויקט ───────────────────────
if (-not (Test-Path "main.py")) {
    Exit-Install "הסקריפט חייב לרוץ מתוך תיקיית הפרויקט (שם שנמצא main.py)"
}
$ProjectDir = (Get-Location).Path
Write-OK "תיקיית פרויקט: $ProjectDir"

# ============================================================
# שלב 1 — Python
# ============================================================
Write-Step "1/6" "בודק Python..."

$pythonCmd = $null

# נסה לאתר python / python3 ב-PATH
foreach ($cmd in @("python","python3")) {
    try {
        $ver = & $cmd --version 2>&1
        if ($ver -match "Python 3\.(\d+)\.(\d+)") {
            $minor = [int]$Matches[1]
            $patch = [int]$Matches[2]
            if ($minor -eq 13 -and $patch -eq 9) {
                $pythonCmd = $cmd
                Write-OK "נמצא: $ver"
                break
            } else {
                Write-Warn "נמצא $ver — נדרשת בדיוק 3.13.9. מוריד גרסה נכונה..."
            }
        }
    } catch {}
}

# Python לא נמצא או ישן מדי — הורד והתקן
if (-not $pythonCmd) {
    Write-Host "  מוריד Python 3.13.9 (64-bit)..." -ForegroundColor Yellow

    $pyInstaller = "$env:TEMP\python_installer.exe"
    $pyUrl       = "https://www.python.org/ftp/python/3.13.9/python-3.13.9-amd64.exe"

    try {
        [Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12
        Invoke-WebRequest -Uri $pyUrl -OutFile $pyInstaller -UseBasicParsing
    } catch {
        Exit-Install "הורדת Python נכשלה. בדוק חיבור אינטרנט ונסה שוב.`n$_"
    }

    Write-Host "  מתקין Python (PrependPath=1)..." -ForegroundColor Yellow
    # /quiet — ללא GUI  |  PrependPath=1 — מוסיף ל-PATH  |  Include_pip=1
    $proc = Start-Process -FilePath $pyInstaller `
        -ArgumentList "/quiet InstallAllUsers=1 PrependPath=1 Include_pip=1 Include_test=0" `
        -Wait -PassThru

    if ($proc.ExitCode -ne 0) {
        Exit-Install "התקנת Python נכשלה (exit code $($proc.ExitCode))"
    }
    Remove-Item $pyInstaller -ErrorAction SilentlyContinue

    # רענן PATH בסשן הנוכחי
    $env:PATH = [System.Environment]::GetEnvironmentVariable("PATH","Machine") + ";" +
                [System.Environment]::GetEnvironmentVariable("PATH","User")

    # בדוק שוב
    try {
        $ver = & python --version 2>&1
        Write-OK "Python הותקן בהצלחה: $ver"
        $pythonCmd = "python"
    } catch {
        Exit-Install "Python הותקן אך עדיין לא נמצא ב-PATH. אנא הפעל מחדש את המחשב ורוץ שוב."
    }
}

# ============================================================
# שלב 2 — venv
# ============================================================
Write-Step "2/6" "יוצר סביבת Python וירטואלית..."

if (Test-Path "venv\Scripts\activate.ps1") {
    Write-OK "venv כבר קיים — דולגת."
} else {
    & $pythonCmd -m venv venv
    if ($LASTEXITCODE -ne 0) { Exit-Install "יצירת venv נכשלה." }
    Write-OK "venv נוצרה."
}

# ── הפעל את ה-venv ────────────────────────────────────────────
& "venv\Scripts\Activate.ps1"
if ($LASTEXITCODE -ne 0) { Exit-Install "הפעלת venv נכשלה." }
Write-OK "venv פעיל."

# ============================================================
# שלב 3 — pip + תלויות
# ============================================================
Write-Step "3/6" "מתקין תלויות (requirements.txt)..."

if (-not (Test-Path "requirements.txt")) {
    Exit-Install "לא נמצא requirements.txt בתיקיית הפרויקט."
}

& python -m pip install --upgrade pip --quiet
& pip install -r requirements.txt
if ($LASTEXITCODE -ne 0) { Exit-Install "התקנת תלויות נכשלה. בדוק חיבור אינטרנט." }
Write-OK "כל התלויות הותקנו."

# ============================================================
# שלב 4 — בסיס נתונים
# ============================================================
Write-Step "4/6" "מאתחל בסיס נתונים..."

$dbPath = "backend\event_system.db"
if (Test-Path $dbPath) {
    Write-OK "DB כבר קיים ב-$dbPath — לא נדרס."
} else {
    Push-Location "backend"
    $result = & python -c "from database import Database; Database(); print('OK')" 2>&1
    Pop-Location
    if ($result -notmatch "OK") {
        Exit-Install "אתחול DB נכשל:`n$result"
    }
    Write-OK "בסיס נתונים נוצר."
}

# ── צור תיקיית uploads אם לא קיימת ──────────────────────────
$uploadsPath = "backend\uploads"
if (-not (Test-Path $uploadsPath)) {
    New-Item -ItemType Directory -Path $uploadsPath | Out-Null
    Write-OK "תיקיית uploads נוצרה."
}

# ============================================================
# שלב 5 — חומת אש
# ============================================================
Write-Step "5/6" "פותח פורט 5000 בחומת האש..."

$ruleName = "EventManagementSystem-Port5000"
$existing = Get-NetFirewallRule -DisplayName $ruleName -ErrorAction SilentlyContinue
if ($existing) {
    Write-OK "כלל חומת אש כבר קיים."
} else {
    try {
        New-NetFirewallRule `
            -DisplayName $ruleName `
            -Direction Inbound `
            -Action Allow `
            -Protocol TCP `
            -LocalPort 5000 `
            -Description "Allow inbound TCP port 5000 for Event Management System" | Out-Null
        Write-OK "פורט 5000 נפתח."
    } catch {
        Write-Warn "פתיחת פורט נכשלה — ייתכן שנדרשות הרשאות מנהל (Administrator)."
        Write-Warn "הרץ שוב בתור Administrator כדי לתקן."
    }
}

# ============================================================
# שלב 6 — זיהוי IP של השרת
# ============================================================
Write-Step "6/6" "מזהה כתובת IP של מחשב זה..."

$ip = (Get-NetIPAddress -AddressFamily IPv4 |
       Where-Object { $_.IPAddress -notmatch "^127\." -and $_.PrefixOrigin -ne "WellKnown" } |
       Select-Object -First 1).IPAddress

if ($ip) {
    Write-OK "כתובת IP: $ip"

    # ── עדכן אוטומטי את app.js ────────────────────────────────
    $appJsPath = "app.js"
    if (Test-Path $appJsPath) {
        $content     = Get-Content $appJsPath -Raw -Encoding UTF8
        $newContent  = $content -replace "http://localhost:5000/api", "http://${ip}:5000/api"
        $newContent  = $newContent -replace "http://127\.0\.0\.1:5000/api", "http://${ip}:5000/api"
        # עדכן רק אם יש שינוי — לא דורס ללא סיבה
        if ($newContent -ne $content) {
            Set-Content $appJsPath $newContent -Encoding UTF8
            Write-OK "app.js עודכן אוטומטית עם ה-IP החדש."
        } else {
            Write-OK "app.js כבר מכיל את ה-IP הנכון."
        }
    }

    # ── עדכן אוטומטי את launcher.py ──────────────────────────
    $launcherPath = "launcher.py"
    if (Test-Path $launcherPath) {
        $content    = Get-Content $launcherPath -Raw -Encoding UTF8
        $newContent = $content -replace "http://192\.168\.1\.XXX:5000", "http://${ip}:5000"
        $newContent = $newContent -replace "http://localhost:5000",      "http://${ip}:5000"
        if ($newContent -ne $content) {
            Set-Content $launcherPath $newContent -Encoding UTF8
            Write-OK "launcher.py עודכן אוטומטית."
        } else {
            Write-OK "launcher.py כבר מכיל את ה-IP הנכון."
        }
    }
} else {
    Write-Warn "לא הצלחתי לזהות IP אוטומטית."
    Write-Warn "עדכן ידנית ב-app.js וב-launcher.py."
}

# ============================================================
# סיום
# ============================================================
Write-Host "`n============================================================" -ForegroundColor Green
Write-Host "   ✔  ההתקנה הושלמה בהצלחה!" -ForegroundColor Green
Write-Host "============================================================" -ForegroundColor Green

Write-Host @"

 הצעדים הבאים:

 1. הפעל את השרת:
    לחץ פעמיים על  Run_App.bat

 2. בנה .exe ללקוחות:
    לחץ פעמיים על  build_client.bat
    (אחר כך שלח את תיקיית dist\EventManagementSystem\ לכל משתמש)

 כתובת גישה מהרשת:
    http://${ip}:5000

"@ -ForegroundColor White

Write-Host "לחץ Enter לסגירה..." -ForegroundColor Gray
Read-Host | Out-Null