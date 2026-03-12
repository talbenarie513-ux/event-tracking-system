@echo off
:: @echo off — hides each command from being printed to the console, keeps output clean

title Building Client Launcher...
:: sets the CMD window title bar text so it's clear what this window is doing

cls
:: clears the screen before printing our banner so there's no clutter

echo.
echo ================================
echo   Building Client .exe
echo   Please wait...
echo ================================
echo.

REM ── IMPORTANT: Read before running ───────────────────────────────────────
REM This script builds the .exe that you send to each user.
REM Before running this, make sure you have:
REM   1. Edited launcher.py and set the correct server IP in SERVER_URL
REM   2. A working venv folder with pywebview installed:
REM         python -m venv venv
REM         venv\Scripts\activate
REM         pip install pywebview pyinstaller
REM ─────────────────────────────────────────────────────────────────────────

REM ── STEP 1: Activate virtual environment ─────────────────────────────────
REM The venv contains pywebview and pyinstaller which are needed for the build.
REM "call" is used instead of just running the script directly so this .bat
REM continues executing after activation (without "call" it would stop here).
call venv\Scripts\activate

REM ── STEP 2: Install PyInstaller if not already installed ─────────────────
REM PyInstaller converts launcher.py into a standalone .exe with all dependencies bundled.
REM --quiet suppresses the pip output so the console doesn't get flooded.
REM ⚠️ PyInstaller is intentionally NOT in requirements.txt — it's only needed
REM    for building the .exe, not for running the system normally.
pip install pyinstaller --quiet

REM ── STEP 3: Delete previous build output ─────────────────────────────────
REM PyInstaller creates two folders:
REM   "build" = temporary work files used during the build process (can be deleted after)
REM   "dist"  = the final output — contains the .exe and everything it needs to run
REM Deleting them before building ensures no leftover files from a previous build cause issues.
REM /s = include all subfolders, /q = quiet mode (no confirmation prompts)
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

REM ── STEP 4: Build the .exe from launcher.py ──────────────────────────────
REM PyInstaller reads launcher.py and packages it + pywebview into a self-contained folder.
REM
REM Flag explanations:
REM   --onedir   = output is a FOLDER (more reliable than --onefile on most machines)
REM                the folder contains the .exe + supporting DLLs and libraries
REM   --windowed = do NOT show a black CMD console window when the user opens the app
REM                without this flag a console window would flash open behind the app window
REM   --name     = sets the name of the output folder and the .exe file
REM                result will be: dist\EventManagementSystem\EventManagementSystem.exe
REM
REM ⚠️ This only bundles launcher.py — it does NOT include Flask, the database,
REM    or any backend files. Those stay on the server machine.
pyinstaller --onedir --windowed --name "EventManagementSystem" launcher.py

REM ── STEP 5: Print success or failure message ─────────────────────────────
REM Checks if the .exe was actually created — if yes, print success instructions.
REM If no, print a failure message so you know to check the errors above.
echo.
echo ================================
if exist dist\EventManagementSystem\EventManagementSystem.exe (
    echo   SUCCESS! Client .exe is ready at:
    echo   dist\EventManagementSystem\
    echo.
    echo   Next steps:
    echo   1. Zip the entire dist\EventManagementSystem\ folder
    echo   2. Send the zip to each user
    echo   3. They unzip it and double-click EventManagementSystem.exe
    echo.
    echo   ⚠️  Send the whole FOLDER, not just the .exe file
    echo   ⚠️  The server must be running before users open the app
    echo   ⚠️  If the server IP changes, update launcher.py and rebuild
    echo ================================
) else (
    echo   BUILD FAILED — check errors above
    echo.
    echo   Common causes:
    echo   - launcher.py has a syntax error
    echo   - pywebview is not installed in venv
    echo   - pyinstaller is not installed
    echo   - SERVER_URL in launcher.py was not updated
    echo ================================
)
echo.
pause
:: pause keeps the window open so you can read the result before it closes