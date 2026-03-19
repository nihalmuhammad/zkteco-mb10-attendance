"""
test_live.py – Live capture test for ZKTeco MB10.

Reads device IP from config.json (same source as the main script).
Run this on macOS/Linux to verify the device connection before
starting the full sync.

Usage:
    python test_live.py
"""

import json
import sys
from datetime import datetime
from zk import ZK

CONFIG_FILE = 'config.json'


def load_config():
    try:
        with open(CONFIG_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"❌ {CONFIG_FILE} not found. Create it first (see README).")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"❌ {CONFIG_FILE} is invalid JSON: {e}")
        sys.exit(1)


def test_live_capture():
    config      = load_config()
    device_ip   = config.get('device_ip', '192.168.8.201')
    device_port = config.get('device_port', 4370)

    zk   = ZK(device_ip, port=device_port, timeout=10, force_udp=True)
    conn = None

    try:
        print(f"--- Live Capture Test: Connecting to {device_ip}:{device_port} ---")
        conn = zk.connect()
        print("✅ Connected! Listening for finger punches...")
        print("👉 Please punch a finger on the device now.")
        print("-" * 50)

        for attendance in conn.live_capture():
            if attendance is not None:
                now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                punch_label = "Punch-IN" if attendance.punch == 0 else "Punch-OUT"
                print(f"🚀 [LIVE] {now}")
                print(f"   User ID  : {attendance.user_id}")
                print(f"   Punch    : {punch_label}")
                print("-" * 30)
                sys.stdout.flush()

    except KeyboardInterrupt:
        print("\n🛑 Test stopped by user.")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if conn:
            conn.disconnect()
            print("🔌 Connection closed.")


if __name__ == "__main__":
    test_live_capture()