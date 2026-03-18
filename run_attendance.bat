@echo off
:: Set the title of the command window
title Attendance Sync - Shop A

:: Step 1: Activate the Virtual Environment
:: Assumes your venv folder is named 'venv' in the same directory
call venv\Scripts\activate

:loop
echo [%date% %time%] Starting Attendance Sync for MB10...

:: Step 2: Run the Python Script
:: Use 'python' or 'python3' depending on your PC's installation
python daily_live.py

:: If the script reaches here, it means it crashed or was closed
echo.
echo -------------------------------------------------------
echo [!] Script stopped or Connection lost at %time%
echo [!] Restarting in 10 seconds... (Press Ctrl+C to cancel)
echo -------------------------------------------------------
timeout /t 10

:: Step 3: Loop back to the start
goto loop