# Usage Monitor for Antigravity v0.1.1 🛠️

Maintenance and bug-fix release addressing a console window flicker issue on Windows during quota updates and background refreshes.

---

## 📋 Full Changelog & Detailed Notes

### 🐛 Bug Fixes: Suppress Transient Console Window Flash (Windows 11)
- **Problem**: 
  - Every time the application polled or refreshed for quota updates (via `agy -p /quota` CLI or `netstat.exe` Connect-RPC port discovery), a black command prompt / terminal window would briefly pop up on the screen for a fraction of a second.
  - On Windows 11 with modern console host (*Windows Terminal* / `OpenConsole.exe`), background subprocesses spawned by GUI applications were triggering an interactive window allocation because standard input was unredirected and window visibility flags were incomplete.
- **Root Cause & Fixes Implemented**:
  - **`usage_monitor_for_antigravity/platforms/win32.py`**:
    - Re-architected `no_window_kwargs()` to supply both `creationflags = subprocess.CREATE_NO_WINDOW` (`0x08000000`) and a properly configured `subprocess.STARTUPINFO` object with `dwFlags |= subprocess.STARTF_USESHOWWINDOW` and `wShowWindow = subprocess.SW_HIDE` (`0`).
    - Introduced a cached singleton `_no_window_startupinfo` to optimize execution performance and eliminate repetitive `STARTUPINFO` object creation on every poll tick.
  - **`usage_monitor_for_antigravity/api.py`**:
    - Standardized all `subprocess.run` and `subprocess.check_output` calls (`_fetch_agy_cli_quota` and `_find_listening_ports`) to use `**no_window_kwargs()`.
    - Explicitly passed `stdin=subprocess.DEVNULL` to disconnect standard input from the system console host, ensuring completely silent background execution.
  - **`usage_monitor_for_antigravity/antigravity_cli.py`**, **`command.py`**, & **`__main__.py`**:
    - Added `stdin=subprocess.DEVNULL` to all remaining subprocess and Popen calls (`_run_cli`, user event commands, and app restart routines).
    - Fixed error dialog titles to accurately display `"Usage Monitor for Antigravity"`.

---

### 📦 Maintenance & Build
- Bumped application package version to `0.1.1` (`usage_monitor_for_antigravity/__init__.py`).
- Bumped Windows PE version information to `0.1.1.0` (`version_info.py`).
- Updated download links in `README.md` and release documentation in `RELEASE_NOTES.md`.
- Updated test suites in `tests/test_platforms_win32.py` and verified all 613 unit tests pass.
- Rebuilt standalone executable using PyInstaller (`dist/UsageMonitorForAntigravity.exe`).

---

## 💾 Downloads & Installation

- **Windows**: Download **`UsageMonitorForAntigravity.exe`** from the **Assets** section below. Portable single-executable, zero setup required.
- **Source / Linux**: Clone repository and run `python -m usage_monitor_for_antigravity`.
