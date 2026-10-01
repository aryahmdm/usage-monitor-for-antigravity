# Usage Monitor for Antigravity v0.1.0 🚀

The first public release of **Usage Monitor for Antigravity** — a lightweight, zero-configuration system tray application designed to monitor your **Google Antigravity (`agy`)** rate limits, token allowances, and reset timers in real time.

---

## ✨ Key Features

- **Real-Time System Tray Icon**:
  - Live progress display showing your current quota percentage.
  - Dynamic color-coded thresholds (Green -> Orange -> Red) indicating approaching limits.
  - Hover tooltip displaying exact remaining utilization and reset schedules.

- **Multi-Model Quota Monitoring**:
  - **Gemini Quotas**: Tracks 5-hour rolling sessions (Gemini Flash) and weekly model allowances (Gemini Pro).
  - **Claude / 3P Models**: Live tracking of Anthropic Claude and 3rd-party models within Google Antigravity.

- **Intelligent Multi-Tier Quota Resolution**:
  1. *Direct CLI Integration*: Queries local Antigravity CLI (`agy`) directly for precision quota figures.
  2. *Connect-RPC Language Server Probe*: Connects to the local Antigravity Language Server RPC when the IDE is running.
  3. *Local SQLite Telemetry*: Offline session tracking and step counting with rolling reset window projection.

- **Interactive Popup Dashboard**:
  - Left-click the tray icon to open a sleek, hardware-accelerated WebView2 dashboard.
  - View individual progress bars, exact reset timestamps, active session steps, and detected IDE installations.

- **Privacy & Security First**:
  - **100% Offline / Local Operation**: No telemetry, no external trackers, no analytics.
  - **Auditable**: Complete open-source codebase available for security inspection.
  - **No Plaintext Secret Storage**: Uses local environment variables or standard OS credentials.

- **Multilingual Support (i18n)**:
  - 13 bundled languages, including English and Bahasa Indonesia.

---

## 📦 Download & Quick Start

### Windows (Standalone Executable)

1. Download **`UsageMonitorForAntigravity.exe`** from the **Assets** section below.
2. Run `UsageMonitorForAntigravity.exe`. No installation or Python setup is required.
3. The application will immediately appear in your Windows notification tray.

> **Note on Windows SmartScreen**: Because this standalone binary is packaged with PyInstaller without an expensive corporate EV certificate, Windows SmartScreen may show an unrecognized app prompt. Click **More info → Run anyway**. You can verify and inspect the entire source code in this repository.

### Running from Source / Linux

Clone this repository and run with Python 3.10+:

```bash
git clone https://github.com/aryahmdm/usage-monitor-for-antigravity.git
cd usage-monitor-for-antigravity
python -m venv .venv
source .venv/bin/activate   # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m usage_monitor_for_antigravity
```

---

## 🛠️ Building Standalone Binary

To build the executable yourself from source:

```bash
python build.py
```

The resulting standalone executable will be located at `dist/UsageMonitorForAntigravity.exe`.

---

## 🙏 Credits & Attribution

- Ported, enhanced, and maintained for **Google Antigravity** by [Arya Maulana](https://github.com/aryahmdm).
- Originally created by [Jens Duttke](https://github.com/jens-duttke) as [Usage Monitor for Claude](https://github.com/jens-duttke/usage-monitor-for-claude).
- Released under the [MIT License](LICENSE).
