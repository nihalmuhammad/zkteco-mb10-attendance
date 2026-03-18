from zk import ZK
from datetime import datetime
import sys

# --- CONFIG ---
DEVICE_IP = '192.168.8.201'  # Change to your MB10's Local IP
DEVICE_PORT = 4370

def test_mac_live():
    # force_udp=True often works better on Mac networks
    zk = ZK(DEVICE_IP, port=DEVICE_PORT, timeout=10, force_udp=True)
    conn = None
    
    try:
        print(f"--- Mac Terminal Test: Connecting to {DEVICE_IP} ---")
        conn = zk.connect()
        print("✅ Connected! System is now listening...")
        print("👉 Please punch your finger on the device now...")
        print("-" * 50)

        # Start live capture loop
        for attendance in conn.live_capture():
            if attendance is not None:
                now = datetime.now().strftime("%I:%M:%S %p")
                print(f"🚀 [LIVE EVENT] Time: {now}")
                print(f"   User ID: {attendance.user_id}")
                print(f"   Type: {'Punch-In' if attendance.punch == 0 else 'Punch-Out'}")
                print("-" * 30)
                # Ensure the terminal prints immediately
                sys.stdout.flush() 
                
    except KeyboardInterrupt:
        print("\nStopping test...")
    except Exception as e:
        print(f"❌ Error: {e}")
    finally:
        if conn:
            conn.disconnect()
            print("Connection closed.")

if __name__ == "__main__":
    test_mac_live()