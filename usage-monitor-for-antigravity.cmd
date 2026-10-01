@echo off
rem Start Usage Monitor for Antigravity on Windows
if exist "%~dp0dist\UsageMonitorForAntigravity.exe" (
    start "" "%~dp0dist\UsageMonitorForAntigravity.exe" %*
) else (
    python -m usage_monitor_for_antigravity %*
)
