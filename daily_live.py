import json
import time
from datetime import datetime, timedelta, timezone
from zk import ZK
import gspread
from oauth2client.service_account import ServiceAccountCredentials

JSON_KEYFILE = 'credentials.json'
RIYADH_TZ = timezone(timedelta(hours=3))
CHECK_INTERVAL = 10 

def start_polling_sync():
    # 1. Load Local Config from JSON
    try:
        with open(JSON_KEYFILE, 'r') as f:
            config = json.load(f)
        
        DEVICE_IP = config.get('device_ip')
        SHEET_NAME = config.get('spreadsheet_name')
        WORKSHEET_NAME = config.get('worksheet_name', 'Sheet2')
        START_HOUR = config.get('shop_start_hour', 8)
        
        print(f"🚀 Initializing: {DEVICE_IP} -> {SHEET_NAME} ({WORKSHEET_NAME})")
    except Exception as e:
        print(f"❌ Error loading {JSON_KEYFILE}: {e}")
        return

    # 2. Connect to Google Sheets
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEYFILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
    except Exception as e:
        print(f"❌ Google Sheets Connection Failed: {e}")
        return

    zk = ZK(DEVICE_IP, port=4370, timeout=15, force_udp=True)
    
    # Memory for "First Punch of the Day" logic
    punched_in_today = set() 
    last_processed_time = datetime.now(RIYADH_TZ) - timedelta(minutes=1)

    while True:
        try:
            now = datetime.now(RIYADH_TZ)
            
            # Reset daily 'IN' list at Midnight
            if now.hour == 0 and now.minute == 0:
                punched_in_today.clear()

            conn = zk.connect()
            logs = conn.get_attendance()
            
            if logs:
                for log in logs:
                    log_time = log.timestamp.replace(tzinfo=RIYADH_TZ)
                    
                    if log_time > last_processed_time:
                        user_id = str(log.user_id)
                        
                        # LOGIC: First punch after Start Hour = IN, others = OUT
                        if log_time.hour >= START_HOUR and user_id not in punched_in_today:
                            status = "IN"
                            punched_in_today.add(user_id)
                        else:
                            status = "OUT"

                        row = [log_time.strftime('%Y-%m-%d %H:%M:%S'), user_id, status]
                        sheet.append_row(row)
                        print(f"✅ {status}: User {user_id} at {log_time.strftime('%H:%M:%S')}")
                        last_processed_time = log_time
            
            conn.disconnect()
        except Exception as e:
            print(f"⚠️ Connection loop issue: {e}")
        
        time.sleep(CHECK_INTERVAL)

if __name__ == "__main__":
    start_polling_sync()