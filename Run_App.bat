@echo off
title Event Management System
cls

echo.
echo ================================
echo   Event Management System
echo   Starting...
echo ================================
echo.

REM Activate virtual environment
call venv\Scripts\activate

REM Run the desktop application
python main.py

pause