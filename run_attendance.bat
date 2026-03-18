@echo off
:: Move to the directory where this .bat file is stored
cd /d %~dp0

title Attendance Sync - %cd%

:loop
cls
echo =======================================================
echo [%date% %time%] Starting Attendance Sync (Polling Mode)
echo =======================================================

:: Step 1: Activate the Virtual Environment
call venv\Scripts\activate

:: Step 2: Run the Python Script
python daily_live.py

:: Step 3: Error Handling
echo.
echo -------------------------------------------------------
echo [!] Connection lost or Script closed at %time%
echo [!] Restarting in 10 seconds... (Press Ctrl+C to cancel)
echo -------------------------------------------------------
timeout /t 10

goto loop