# Privacy Policy

**Usage Monitor for Antigravity** is a local desktop application that monitors your Google Antigravity (`agy`) quota and rate limits.
It runs on Windows and Linux.

> [!NOTE]
> **Attribution**: This project is adapted and forked from the original [Usage Monitor for Claude](https://github.com/jens-duttke/usage-monitor-for-claude) by [Jens Duttke](https://github.com/jens-duttke).

## Data Collection

This application does **not** collect, store, or transmit any personal data.

## Communication & Quota Retrieval

The application communicates with the local Antigravity CLI (`agy -p "/quota"`) and Antigravity endpoints to retrieve real-time quota and tier information for your account. No telemetry or analytics connections are made.

The server certificate is verified against the system certificate store, the same store your browser uses.

## Credentials

The application uses your existing local Antigravity / Gemini CLI session. Quota queries are run locally against the Antigravity CLI. No credentials or passwords are ever logged, stored elsewhere, copied, or transmitted to any third party.

## Local Storage

All usage data is kept in memory only and discarded when the application closes. An optional settings file (`usage-monitor-settings.json`) is read-only. The complete list of what the application changes on your system follows - there is nothing else.

**On Windows** no files are written at all. Two values are written to the registry, both under `HKEY_CURRENT_USER`:

- `Software\Classes\AppUserModelId\Antigravity.UsageMonitor` - the display name and icon shown in the header of the application's notifications. Re-registered on every start.
- `Software\Microsoft\Windows\CurrentVersion\Run` - the autostart entry (`UsageMonitorForAntigravity`). Written only when you enable autostart from the tray menu, removed when you disable it again.

**On Linux** the registry has no equivalent, so the same two concerns need files:

- `~/.config/autostart/usage-monitor-for-antigravity.desktop` - the autostart entry. Written only when you enable autostart from the tray menu, removed when you disable it again.
- `$XDG_RUNTIME_DIR/usage-monitor-for-antigravity.lock` - a lock file that prevents a second instance from running. It holds the process id and version, is created with owner-only permissions (`0600`), and lives in the session's runtime directory, which the system clears at logout.

Monitoring a secondary account (`--config-dir`) adds a suffix to those names, so each account gets its own entry.

## Third-Party Services

The application does not integrate with any analytics, tracking, advertising, or telemetry services.
