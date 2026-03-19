#!/bin/bash
# Move to the directory where this script is stored
cd "$(dirname "$0")"

echo "======================================================="
echo "  ZKTeco MB10 Attendance Sync - macOS/Linux Runner"
echo "======================================================="

while true; do
    clear
    echo "======================================================="
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Starting Attendance Sync (Polling Mode)"
    echo "======================================================="

    # Step 1: Activate the Virtual Environment
    source venv/bin/activate

    # Step 2: Run the Python Script
    python daily_live.py

    # Step 3: Error Handling / Auto-Restart
    echo ""
    echo "-------------------------------------------------------"
    echo "[!] Connection lost or Script exited at $(date '+%H:%M:%S')"
    echo "[!] Restarting in 10 seconds... (Press Ctrl+C to cancel)"
    echo "-------------------------------------------------------"
    sleep 10
done
