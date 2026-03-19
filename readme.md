# ZKTeco MB10 — Live Attendance Sync

Polls the MB10 fingerprint device every 10 seconds and writes punch events to Google Sheets in real-time.

---

## ✨ Features

- **Smart IN/OUT logic** — first punch after shop open hour = `IN`, rest = `OUT`
- **2-minute cooldown** — ignores accidental double-taps
- **Crash-safe state** — persists to `state.json`, no duplicate sheet rows after a restart
- **Date-based midnight reset** — reliably resets at midnight, never misses the window
- **Full deduplication** — each unique punch (user + timestamp) is written exactly once
- **Auto-restart runner** — `.bat` (Windows) / `.sh` (macOS/Linux) keeps the sync alive 24/7

---

## 📁 Project Structure

```
mb10-attendance/
├── daily_live.py          # ▶ Main sync script
├── test_live.py           # 🔌 Device connection test
├── config.json            # ⚙️  Shop settings (IP, sheet name, hours)
├── credentials.json       # 🔑 Google Service Account key — NOT in git, add manually
├── state.json             # 🔄 Auto-generated runtime state — NOT in git
├── requirements.txt       # Python dependencies
├── run_attendance.bat     # 🪟 Windows production runner
├── run_attendance.sh      # 🍎 macOS / Linux production runner
└── .gitignore
```

> **`credentials.json` and `state.json` are in `.gitignore`** and will never be pushed to GitHub.

---

## 🖥️ Shop PC Setup (do this once per machine)

### Step 1 — Install Python

Download and install **Python 3.8+** from https://www.python.org/downloads/

> ✅ On Windows, tick **"Add Python to PATH"** during install.

---

### Step 2 — Pull the Repository

**Windows (Command Prompt):**
```cmd
git clone https://github.com/nihalmuhammad/zkteco-mb10-attendance.git
cd zkteco-mb10-attendance
```

**macOS / Linux (Terminal):**
```bash
git clone https://github.com/nihalmuhammad/zkteco-mb10-attendance.git
cd zkteco-mb10-attendance
```

> If the repo was already cloned, just run `git pull` inside the folder to get latest updates.

---

### Step 3 — Create Virtual Environment & Install Dependencies

**Windows:**
```cmd
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

---

### Step 4 — Add the Google Credentials File

Copy `credentials.json` (Google Service Account key) into the project root folder. This file is **not in the repository** — you must transfer it manually (USB, email, etc.).

The file must be named exactly:
```
credentials.json
```

It should look like this (structure check):
```json
{
  "type": "service_account",
  "project_id": "...",
  "private_key_id": "...",
  "private_key": "-----BEGIN RSA PRIVATE KEY-----\n...",
  "client_email": "...@....iam.gserviceaccount.com"
}
```

---

### Step 5 — Verify `config.json`

Open `config.json` and confirm the settings are correct for this shop:

```json
{
    "device_ip": "192.168.8.201",
    "spreadsheet_name": "Live_Attendance",
    "worksheet_name": "newdoor",
    "shop_start_hour": 8,
    "cooldown_minutes": 2,
    "check_interval_seconds": 10
}
```

| Key | Description |
|---|---|
| `device_ip` | Local IP of the MB10 on this shop's network |
| `spreadsheet_name` | Exact name of the Google Spreadsheet |
| `worksheet_name` | Tab name inside the spreadsheet |
| `shop_start_hour` | Hour (24h) after which first punch = **IN** |
| `cooldown_minutes` | Minimum gap between two punches from same user |
| `check_interval_seconds` | How often to poll the device |

---

### Step 6 — Test the Device Connection

```bash
python test_live.py       # macOS/Linux
python test_live.py       # Windows
```

Tap a finger on the MB10. You should see:
```
✅ Connected! Listening for finger punches...
🚀 [LIVE] 2026-03-19 09:15:33
   User ID  : vijin
   Punch    : Punch-IN
```

Press `Ctrl+C` to stop the test.

---

### Step 7 — Run in Production

**🪟 Windows** — double-click:
```
run_attendance.bat
```

**🍎 macOS / Linux:**
```bash
chmod +x run_attendance.sh   # only needed once
./run_attendance.sh
```

The runner activates the venv, starts the sync, and **auto-restarts it within 10 seconds** if it ever crashes.

---

### ✅ Optional: Auto-start on PC Boot (Windows)

So the sync starts automatically every morning without manual action:

1. Press `Win + R` → type `shell:startup` → press Enter
2. Right-click → **New → Shortcut**
3. Browse to `run_attendance.bat` in the project folder
4. Click Finish

The sync will now launch automatically every time Windows boots.

---

## 📊 Google Sheet Structure

The script appends one row per punch. Set up your worksheet with this header row:

| A | B | C | D |
|---|---|---|---|
| Date | User ID | Time | Status |
| `2026-03-19` | `vijin` | `09:15:33` | `IN` |
| `2026-03-19` | `vijin` | `17:42:10` | `OUT` |

---

## 🔄 Updating the Script on Shop PCs

When a new version is pushed to GitHub, simply run inside the project folder:

```cmd
git pull
```

No reinstall needed — `config.json` and `credentials.json` are untouched by git pull.

---

## 🐛 Troubleshooting

| Problem | Fix |
|---|---|
| `ConnectionError` on ZK device | Check `device_ip` in `config.json`; ensure PC and MB10 are on the same network |
| `Google Sheets Connection Failed: invalid_grant` | Replace `credentials.json` with a fresh key from Google Cloud Console |
| `Google Sheets Connection Failed: APIError` | Ensure the Service Account email has **Editor** access to the spreadsheet |
| Logs not appearing in sheet | Check `shop_start_hour` — punches before that hour are still recorded as OUT |
| Duplicate rows after restart | Delete `state.json` and restart — it will rebuild cleanly |
| `ModuleNotFoundError` | Run `pip install -r requirements.txt` with the venv activated |
