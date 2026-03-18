# ZKTeco MB10 Attendance Sync

A robust Python-based live attendance synchronization system that captures punches from ZKTeco MB10 devices and pushes them to Google Sheets in real-time. 

## ✨ Features
* **Live Capture:** Records punches the instant a finger touches the sensor.
* **Smart In/Out Logic:** Automatically labels the first punch of the day as `PUNCH-IN` and the second as `PUNCH-OUT`.
* **2-Minute Cooldown:** Prevents accidental double-taps from creating duplicate entries.
* **Timezone Locked:** Uses Riyadh Time (UTC+3) for all logging, regardless of local PC settings.
* **Shop-Specific Start Times:** Configurable opening hours to filter out early/late-night testing.

## 🛠️ Prerequisites
1. **Python 3.8+** installed on the host PC.
2. **Static IP** assigned to the MB10 device on the local network.
3. **Google Cloud Project** with Sheets and Drive APIs enabled.

## 🚀 Installation

### 1. Clone the Repository
```bash
git clone [https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git](https://github.com/YOUR_USERNAME/YOUR_REPO_NAME.git)
cd mb10-attendance
2. Setup Virtual EnvironmentmacOS/Linux:Bashpython3 -m venv venv
source venv/bin/activate
Windows:Bashpython -m venv venv
venv\Scripts\activate
3. Install DependenciesBashpip install -r requirements.txt
4. Add CredentialsPlace your credentials.json file (Service Account Key) into the root folder. Note: Ensure this file is listed in your .gitignore.⚙️ ConfigurationOpen daily_live.py and update the following variables for the specific shop:VariableDescriptionDEVICE_IPLocal IP of the MB10 (e.g., 192.168.8.201)SHEET_NAMEThe name of your Google SpreadsheetWORKSHEET_NAMEThe specific tab name (e.g., newdoor)SHOP_START_HOUROpening hour in 24h format (e.g., 8 for 8 AM)📊 Google Sheet StructureThe script expects (and will verify) the following columns in the worksheet:Column A: Date (YYYY-MM-DD)Column B: User IDColumn C: Punch Time (HH:MM:SS AM/PM)Column D: Type (PUNCH-IN / PUNCH-OUT)🖥️ Running the ScriptTo start the live sync:Bashpython daily_live.py
