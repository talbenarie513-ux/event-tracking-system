@echo off
title מערכת ניהול אירועים — שרת
chcp 65001 > nul
cls

echo.
echo ================================
echo   Event Management System
echo   Starting server...
echo ================================
echo.

REM Activate virtual environment
call venv\Scripts\activate

REM Start the Flask server (browser-based, no desktop window)
python main.py

pause