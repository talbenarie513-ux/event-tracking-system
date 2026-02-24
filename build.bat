@echo off
title Building Event Management System...
cls

echo.
echo ================================
echo   Building .exe — please wait
echo ================================
echo.

REM Activate virtual environment
call venv\Scripts\activate

REM Install PyInstaller if not already installed
pip install pyinstaller --quiet

REM Clean previous build
if exist build rmdir /s /q build
if exist dist  rmdir /s /q dist

REM Run PyInstaller with the spec file
pyinstaller main.spec

echo.
echo ================================
if exist dist\EventManagementSystem\EventManagementSystem.exe (
    echo   SUCCESS! Your .exe is ready at:
    echo   dist\EventManagementSystem\
    echo.
    echo   Share the entire folder:
    echo   dist\EventManagementSystem\
    echo ================================
) else (
    echo   BUILD FAILED — check errors above
    echo ================================
)
echo.
pause