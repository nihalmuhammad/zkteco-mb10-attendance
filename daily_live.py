import json
import time
import os
from datetime import datetime, timedelta, timezone, date
from zk import ZK
import gspread
from oauth2client.service_account import ServiceAccountCredentials

# --- File Paths ---
CONFIG_FILE     = 'config.json'
CREDENTIALS_FILE = 'credentials.json'
STATE_FILE      = 'state.json'

RIYADH_TZ = timezone(timedelta(hours=3))


# ─────────────────────────────────────────────
# State Persistence (crash-safe across restarts)
# ─────────────────────────────────────────────

def load_state():
    """Load persisted runtime state from disk.

    State fields:
      - last_date       : str  'YYYY-MM-DD' — for day-rollover detection
      - user_statuses   : dict  user_id -> last recorded status ('IN' / 'OUT')
      - last_punch_times: dict  user_id -> ISO timestamp of their last accepted punch
      - processed_keys  : list  unique 'userid_timestamp' keys already written to sheet
    """
    if os.path.exists(STATE_FILE):
        try:
            with open(STATE_FILE, 'r') as f:
                state = json.load(f)
            state.setdefault('last_date', '')
            state.setdefault('user_statuses', {})
            state.setdefault('last_punch_times', {})
            state.setdefault('processed_keys', [])
            return state
        except Exception as e:
            print(f"⚠️  Could not read {STATE_FILE}, starting fresh: {e}")

    return {
        'last_date':        '',
        'user_statuses':    {},
        'last_punch_times': {},
        'processed_keys':   [],
    }


def save_state(state):
    """Persist current runtime state to disk atomically."""
    try:
        tmp = STATE_FILE + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(state, f, indent=2)
        os.replace(tmp, STATE_FILE)
    except Exception as e:
        print(f"⚠️  Could not save state: {e}")


def reset_daily_state(state, today_str):
    """Reset all per-day tracking when the date rolls over at midnight."""
    print(f"🔄 New day ({today_str}) — resetting daily punch state.")
    state['last_date']        = today_str
    state['user_statuses']    = {}
    state['last_punch_times'] = {}
    state['processed_keys']   = []
    save_state(state)


# ─────────────────────────────────────────────
# Shift-Aware IN / OUT Toggle Logic
# ─────────────────────────────────────────────

def determine_status(user_id, log_time, user_statuses, start_hour):
    """
    Toggle-based shift logic:

      - If the user has NO record today (first punch of the day):
          → Only accepted as IN if time >= shop_start_hour.
          → Ignored (returns None) if punch is before start_hour.

      - If last recorded status was IN  → next punch = OUT  (leaving shift)
      - If last recorded status was OUT → next punch = IN   (starting new shift)

    This supports unlimited shift changes per day:
        Punch 1  →  IN   (morning shift starts)
        Punch 2  →  OUT  (morning shift ends)
        Punch 3  →  IN   (evening shift starts)
        Punch 4  →  OUT  (evening shift ends)
        ...
    """
    last_status = user_statuses.get(user_id)  # None if first punch today

    if last_status is None:
        # First punch of the day
        if log_time.hour < start_hour:
            return None  # too early — ignore (prevents accidental taps before open)
        return "IN"

    # Toggle
    return "OUT" if last_status == "IN" else "IN"


# ─────────────────────────────────────────────
# Main Sync Loop
# ─────────────────────────────────────────────

def start_polling_sync():

    # 1. Load App Config
    try:
        with open(CONFIG_FILE, 'r') as f:
            config = json.load(f)

        DEVICE_IP        = config['device_ip']
        DEVICE_PORT      = config.get('device_port', 4370)
        SHEET_NAME       = config['spreadsheet_name']
        WORKSHEET_NAME   = config.get('worksheet_name', 'Sheet2')
        START_HOUR       = config.get('shop_start_hour', 8)
        COOLDOWN_MINUTES = config.get('cooldown_minutes', 2)
        CHECK_INTERVAL   = config.get('check_interval_seconds', 10)

        print(f"🚀 Initializing: {DEVICE_IP} → {SHEET_NAME} ({WORKSHEET_NAME})")
        print(f"   Start Hour: {START_HOUR}:00 | Cooldown: {COOLDOWN_MINUTES} min | Poll: {CHECK_INTERVAL}s")
        print(f"   Mode: SHIFT TOGGLE (IN→OUT→IN→OUT per punch)")
    except Exception as e:
        print(f"❌ Error loading {CONFIG_FILE}: {e}")
        return

    # 2. Connect to Google Sheets
    try:
        scope  = ["https://spreadsheets.google.com/feeds",
                  "https://www.googleapis.com/auth/drive"]
        creds  = ServiceAccountCredentials.from_json_keyfile_name(CREDENTIALS_FILE, scope)
        client = gspread.authorize(creds)
        sheet  = client.open(SHEET_NAME).worksheet(WORKSHEET_NAME)
        print(f"✅ Google Sheets connected: '{SHEET_NAME}' → '{WORKSHEET_NAME}'")
    except Exception as e:
        print(f"❌ Google Sheets Connection Failed: {e}")
        return

    # 3. Load persisted state
    state = load_state()
    user_statuses    = state['user_statuses']
    last_punch_times = {
        uid: datetime.fromisoformat(ts)
        for uid, ts in state['last_punch_times'].items()
    }
    processed_keys = set(state['processed_keys'])

    # 4. Day-rollover check on startup
    today_str = datetime.now(RIYADH_TZ).date().isoformat()
    if state['last_date'] != today_str:
        reset_daily_state(state, today_str)
        user_statuses    = {}
        last_punch_times = {}
        processed_keys   = set()

    # 5. ZK device
    zk       = ZK(DEVICE_IP, port=DEVICE_PORT, timeout=15, force_udp=True)
    cooldown = timedelta(minutes=COOLDOWN_MINUTES)

    print("\n📡 Polling loop started. Press Ctrl+C to stop.\n")

    while True:
        try:
            now       = datetime.now(RIYADH_TZ)
            today_str = now.date().isoformat()

            # Day-rollover check every loop iteration
            if state['last_date'] != today_str:
                reset_daily_state(state, today_str)
                user_statuses    = {}
                last_punch_times = {}
                processed_keys   = set()

            # Fetch full attendance log from device
            conn = zk.connect()
            logs = conn.get_attendance()
            conn.disconnect()

            if logs:
                logs_sorted = sorted(logs, key=lambda l: l.timestamp)

                for log in logs_sorted:
                    log_time = log.timestamp.replace(tzinfo=RIYADH_TZ)

                    # Skip logs from previous days
                    if log_time.date().isoformat() != today_str:
                        continue

                    user_id = str(log.user_id)
                    log_key = f"{user_id}_{log_time.strftime('%Y-%m-%dT%H:%M:%S')}"

                    # ── Deduplication ──
                    if log_key in processed_keys:
                        continue

                    # ── 2-Minute cooldown ──
                    if user_id in last_punch_times:
                        gap = log_time - last_punch_times[user_id]
                        if gap < cooldown:
                            print(f"⏭️  Cooldown: User {user_id} "
                                  f"(only {int(gap.total_seconds())}s since last punch — skipped)")
                            processed_keys.add(log_key)
                            continue

                    # ── Shift toggle IN/OUT logic ──
                    status = determine_status(user_id, log_time, user_statuses, START_HOUR)

                    if status is None:
                        # Before shop open hour and no prior record — ignore
                        print(f"⏭️  Before start hour: User {user_id} at "
                              f"{log_time.strftime('%I:%M:%S %p')} — skipped")
                        processed_keys.add(log_key)
                        continue

                    # ── Write to Google Sheet ──
                    date_str = log_time.strftime('%Y-%m-%d')
                    time_str = log_time.strftime('%I:%M:%S %p')
                    sheet.append_row([date_str, user_id, time_str, status])
                    print(f"✅ {status:3}: User {user_id} at {log_time.strftime('%Y-%m-%d %I:%M:%S %p')}")

                    # ── Update in-memory state ──
                    user_statuses[user_id]    = status
                    last_punch_times[user_id] = log_time
                    processed_keys.add(log_key)

                    # ── Persist after every write ──
                    state['user_statuses']    = user_statuses
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