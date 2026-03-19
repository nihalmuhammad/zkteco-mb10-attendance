import json
import time
import os
from datetime import datetime, timedelta, timezone, date
from zk import ZK
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- File Paths ---
CONFIG_FILE = 'config.json'
CREDENTIALS_FILE = 'credentials.json'
STATE_FILE = 'state.json'

RIYADH_TZ = timezone(timedelta(hours=3))


# ─────────────────────────────────────────────
# State Persistence (crash-safe across restarts)
# ─────────────────────────────────────────────

def load_state():
    """Load persisted runtime state from disk.
    Returns a dict with:
      - last_date         : str  (YYYY-MM-DD) – used to detect day rollover
      - punched_in_today  : list – user IDs that have punched IN today
      - last_punch_times  : dict – user_id -> ISO timestamp of their last punch
      - processed_keys    : list – unique log keys already written to the sheet
    """
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
                # Ensure all expected keys exist (handles older state files)
                state.setdefault('last_date', '')
                state.setdefault('punched_in_today', [])
                state.setdefault('last_punch_times', {})
                state.setdefault('processed_keys', [])
                return state
        except Exception as e:
            print(f"⚠️  Could not read {STATE_FILE}, starting fresh: {e}")

    return {
        'last_date': '',
        'punched_in_today': [],
        'last_punch_times': {},
        'processed_keys': [],
    }


def save_state(state):
    """Persist current runtime state to disk atomically."""
    try:
        tmp_path = STATE_FILE + '.tmp'
        with open(tmp_path, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(tmp_path, STATE_FILE)  # atomic on POSIX and Windows
    except Exception as e:
        print(f"⚠️  Could not save state: {e}")


def reset_daily_state(state, today_str):
    """Clear per-day tracking when the date rolls over."""
    print(f"🔄 New day detected ({today_str}). Resetting daily punch state.")
    state['last_date'] = today_str
    state['punched_in_today'] = []
    state['last_punch_times'] = {}
    state['processed_keys'] = []   # clear old-day log keys too
    save_state(state)


# ─────────────────────────────────────────────
# Main Sync Loop
# ─────────────────────────────────────────────

def start_polling_sync():

    # 1. Load App Config (device IP, sheet name, etc.)
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

        DEVICE_IP        = config['device_ip']
        SHEET_NAME       = config['spreadsheet_name']
        WORKSHEET_NAME   = config.get('worksheet_name', 'Sheet2')
        START_HOUR       = config.get('shop_start_hour', 8)
        COOLDOWN_MINUTES = config.get('cooldown_minutes', 2)
        CHECK_INTERVAL   = config.get('check_interval_seconds', 10)

        print(f"🚀 Initializing: {DEVICE_IP} → {SHEET_NAME} ({WORKSHEET_NAME})")
        print(f"   Start Hour: {START_HOUR}:00 | Cooldown: {COOLDOWN_MINUTES} min | Poll: {CHECK_INTERVAL}s")
    except Exception as e:
        print(f"❌ Error loading {CONFIG_FILE}: {e}")
        return

    # 2. Connect to Google Sheets (uses Service Account key from credentials.json)
    try:
        scope = [
            "https://spreadsheets.google.com/feeds",
            "https://www.googleapis.com/auth/drive",
        ]
        creds  = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        sheet  = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
        print(f"✅ Google Sheets connected: '{SHEET_NAME}' → '{WORKSHEET_NAME}'")
    except Exception as e:
        print(f"❌ Google Sheets Connection Failed: {e}")
        return

    # 3. Load persisted state (survives crashes / restarts)
    state = load_state()
    punched_in_today  = set(state['punched_in_today'])
    last_punch_times  = {
        uid: datetime.fromisoformat(ts)
        for uid, ts in state['last_punch_times'].items()
    }
    processed_keys    = set(state['processed_keys'])

    # 4. Check for day rollover on startup
    today_str = datetime.now(RIYADH_TZ).date().isoformat()
    if state['last_date'] != today_str:
        reset_daily_state(state, today_str)
        punched_in_today = set()
        last_punch_times = {}
        processed_keys   = set()

    # 5. ZK device handle
    zk = ZK(DEVICE_IP, port=4370, timeout=15, force_udp=True)

    print("\n📡 Polling loop started. Press Ctrl+C to stop.\n")
    cooldown = timedelta(minutes=COOLDOWN_MINUTES)

    while True:
        try:
            now       = datetime.now(RIYADH_TZ)
            today_str = now.date().isoformat()

            # ── Day-rollover check (date-based, never misses midnight) ──
            if state['last_date'] != today_str:
                reset_daily_state(state, today_str)
                punched_in_today = set()
                last_punch_times = {}
                processed_keys   = set()

            # ── Fetch attendance log from device ──
            conn = zk.connect()
            logs = conn.get_attendance()
            conn.disconnect()

            if logs:
                # Sort chronologically so we process in order
                logs_sorted = sorted(logs, key=lambda l: l.timestamp)

                for log in logs_sorted:
                    log_time = log.timestamp.replace(tzinfo=RIYADH_TZ)

                    # Skip logs from previous days
                    if log_time.date().isoformat() != today_str:
                        continue

                    user_id = str(log.user_id)
                    log_key = f"{user_id}_{log_time.strftime('%Y-%m-%dT%H:%M:%S')}"

                    # ── Deduplication: skip already-processed logs ──
                    if log_key in processed_keys:
                        continue

                    # ── 2-Minute cooldown: skip accidental double-taps ──
                    if user_id in last_punch_times:
                        gap = log_time - last_punch_times[user_id]
                        if gap < cooldown:
                            print(f"⏭️  Skipped duplicate punch: User {user_id} "
                                  f"(only {int(gap.total_seconds())}s since last punch)")
                            processed_keys.add(log_key)   # mark so we don't re-check it
                            continue

                    # ── IN / OUT logic ──
                    if log_time.hour >= START_HOUR and user_id not in punched_in_today:
                        status = "IN"
                        punched_in_today.add(user_id)
                    else:
                        status = "OUT"

                    # ── Write to Google Sheet ──
                    date_str = log_time.strftime('%Y-%m-%d')
                    time_str = log_time.strftime('%I:%M:%S %p')
                    sheet.append_row([date_str, user_id, time_str, status])
                    print(f"✅ {status}: User {user_id} at {log_time.strftime('%Y-%m-%d %H:%M:%S')}")

                    # ── Update in-memory state ──
                    processed_keys.add(log_key)
                    last_punch_times[user_id] = log_time

                    # ── Persist state after every write ──
                    state['punched_in_today'] = list(punched_in_today)
                    state['last_punch_times'] = {
                        uid: ts.isoformat()
                        for uid, ts in last_punch_times.items()
                    }
                    state['processed_keys'] = list(processed_keys)
                    save_state(state)

        except KeyboardInterrupt:
            print("\n🛑 Stopped by user.")
            break
        except Exception as e:
            print(f"⚠️  Loop error: {e}")

        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    start_polling_sync()