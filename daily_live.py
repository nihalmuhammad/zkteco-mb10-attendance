import gspread
from oauth2client.service_account import ServiceAccountCredentials
from zk import ZK
from datetime import datetime, timedelta, timezone
import sys

# --- CONFIG ---
DEVICE_IP = '192.168.8.201' 
SHEET_NAME = 'Live_Attendance'
WORKSHEET_NAME = 'newdoor'
JSON_KEYFILE = 'credentials.json'
SHOP_START_HOUR = 8 

# Riyadh Timezone (UTC+3)
RIYADH_TZ = timezone(timedelta(hours=3))

def start_live_sync():
    try:
        scope = ["https://spreadsheets.google.com/feeds", "https://www.googleapis.com/auth/drive"]
        creds = ServiceAccountCredentials.from_json_keyfile_name(JSON_KEYFILE, scope)
        client = gspread.authorize(creds)
        sheet = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
        print(f"✅ Connected to Sheet: {SHEET_NAME} -> {WORKSHEET_NAME}")
    except Exception as e:
        print(f"❌ Google Sheets Error: {e}")
        return

    zk = ZK(DEVICE_IP, port=4370, timeout=10, force_udp=True)
    conn = None
    
    try:
        conn = zk.connect()
        print(f"✅ Live Tracking Active. Tracking IN and OUT.")

        for attendance in conn.live_capture():
            if attendance is not None:
                # Use Riyadh Time
                now_riyadh = datetime.now(RIYADH_TZ)
                
                if now_riyadh.hour >= SHOP_START_HOUR:
                    today_str = str(now_riyadh.date())
                    uid = str(attendance.user_id).strip()
                    
                    # 1. Fetch current data to COUNT entries for this user today
                    try:
                        all_rows = sheet.get_all_values()
                        # Count how many rows match today's date AND this user's ID
                        user_punches_today = [row for row in all_rows if row[0] == today_str and str(row[1]).strip() == uid]
                        punch_count = len(user_punches_today)
                    except Exception as e:
                        print(f"Error reading sheet: {e}")
                        punch_count = 0

                    punch_time_str = now_riyadh.strftime("%I:%M:%S %p")

                    # 2. DECISION LOGIC
                    if punch_count == 0:
                        # No record yet? This is the PUNCH-IN
                        sheet.append_row([today_str, uid, punch_time_str, "PUNCH-IN"])
                        print(f"🚀 [IN] User {uid} recorded at {punch_time_str}")
                    
                    elif punch_count == 1:
                        # One record exists? This is the PUNCH-OUT
                        # Ensure at least 2 minutes passed since the IN (prevent double-taps)
                        last_punch_str = user_punches_today[0][2]
                        last_time = datetime.strptime(f"{today_str} {last_punch_str}", "%Y-%m-%d %I:%M:%S %p").replace(tzinfo=RIYADH_TZ)
                        
                        if (now_riyadh - last_time).total_seconds() > 120:
                            sheet.append_row([today_str, uid, punch_time_str, "PUNCH-OUT"])
                            print(f"🚪 [OUT] User {uid} recorded at {punch_time_str}")
                        else:
                            print(f"⚠️  [WAIT] User {uid} scanned too soon after IN. (2-min cooldown)")
                    
                    else:
                        # Already has an IN and an OUT
                        print(f"ℹ️  [DONE] User {uid} already has IN & OUT for today.")
                
                sys.stdout.flush()

    except KeyboardInterrupt:
        print("\nStopping...")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if conn:
            conn.disconnect()

if __name__ == "__main__":
    start_live_sync()