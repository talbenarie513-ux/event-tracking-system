@echo off
title התקנת מערכת ניהול אירועים
chcp 65001 > nul

:: הרץ את install.ps1 עם הרשאות מנהל
PowerShell -NoProfile -ExecutionPolicy Bypass -Command ^
    "Start-Process PowerShell -ArgumentList '-NoProfile -ExecutionPolicy Bypass -File ""%~dp0install.ps1""' -Verb RunAs -Wait"

:: כשההתקנה מסתיימת — הפעל את השרת
call "%~dp0Run_App.bat"