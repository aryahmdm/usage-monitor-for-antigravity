"""
Antigravity CLI
================

Discovers Antigravity / Gemini CLI installations on the system and provides
token refresh.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

from .platforms import no_window_kwargs
from .settings import CLI_COMMAND


def _discover_cli_path() -> Path:
    """Discover the Antigravity CLI binary path (agy)."""
    found = shutil.which('agy')
    if found:
        path = Path(found)
        if path.suffix.lower() == '.ps1':
            for ext in ('.cmd', '.exe'):
                alt = path.with_suffix(ext)
                if alt.is_file():
                    return alt
        return path

    localappdata = os.environ.get('LOCALAPPDATA')
    if localappdata:
        candidate = Path(localappdata) / 'agy' / 'bin' / 'agy.exe'
        if candidate.is_file():
            return candidate

    found_claude = shutil.which('claude')
    if found_claude:
        return Path(found_claude)

    return Path.home() / 'AppData' / 'Local' / 'agy' / 'bin' / 'agy.exe'


# Resolved at import time. The CLI path doesn't move during runtime.
CLAUDE_CLI_PATH = _discover_cli_path()
ANTIGRAVITY_CLI_PATH = CLAUDE_CLI_PATH

_EXTENSION_DIRS: list[tuple[str, Path]] = [
    ('VS Code', Path.home() / '.vscode' / 'extensions'),
    ('VS Code Insiders', Path.home() / '.vscode-insiders' / 'extensions'),
    ('Cursor', Path.home() / '.cursor' / 'extensions'),
    ('Windsurf', Path.home() / '.windsurf' / 'extensions'),
]
_EXTENSION_PREFIXES = ('google.', 'gemini', 'antigravity')

CHANGELOG_URL = 'https://antigravity.google/docs'
PROJECT_URL = 'https://github.com/jens-duttke/usage-monitor-for-claude'

__all__ = [
    'CLAUDE_CLI_PATH', 'ANTIGRAVITY_CLI_PATH', 'CHANGELOG_URL', 'PROJECT_URL',
    'ClaudeInstallation', 'AntigravityInstallation', 'RefreshResult',
    'cli_version', 'find_installations', 'refresh_token',
]

_version_cache: dict[Path, tuple[float, str]] = {}
_command_version_cache: dict[tuple[str, ...], str] = {}


@dataclass
class ClaudeInstallation:
    """A discovered CLI or IDE installation."""

    name: str
    version: str
    path: Path


AntigravityInstallation = ClaudeInstallation


@dataclass
class RefreshResult:
    """Result of a token refresh / update invocation."""

    success: bool
    updated: bool
    old_version: str
    new_version: str
    error: str


def find_installations() -> list[ClaudeInstallation]:
    """Discover Antigravity CLI and extension installations on the system."""
    results: list[ClaudeInstallation] = []

    # Native CLI (agy)
    if CLAUDE_CLI_PATH.is_file():
        version = cli_version(CLAUDE_CLI_PATH)
        if version:
            results.append(ClaudeInstallation('Antigravity CLI', version, CLAUDE_CLI_PATH))

    # Configured commands
    for name, command in CLI_COMMAND.items():
        version = _command_version(command)
        if version:
            results.append(ClaudeInstallation(name, version, Path(command[-1])))

    # IDE extensions
    for ide_name, ext_dir in _EXTENSION_DIRS:
        try:
            if not ext_dir.is_dir():
                continue

            for entry in ext_dir.iterdir():
                matching_prefix = next((p for p in _EXTENSION_PREFIXES if entry.name.startswith(p)), None)
                if not matching_prefix:
                    continue

                remainder = entry.name[len(matching_prefix):]
                match = re.search(r'(\d+\.\d+\.\d+)', remainder)
                version = match.group(1) if match else 'installed'
                results.append(ClaudeInstallation(f'{ide_name} ({entry.name.split("-")[0]})', version, entry))
        except OSError:
            continue

    return results


def refresh_token() -> RefreshResult:
    """Refresh the Google OAuth token and check for CLI updates."""
    from .api import refresh_google_oauth_token

    curr_version = cli_version(CLAUDE_CLI_PATH) if CLAUDE_CLI_PATH.is_file() else ''

    # First perform Google OAuth refresh
    auth_refreshed = refresh_google_oauth_token()

    # Try agy update if executable exists
    if CLAUDE_CLI_PATH.is_file() and 'agy' in CLAUDE_CLI_PATH.name.lower():
        try:
            proc = _run_cli([str(CLAUDE_CLI_PATH), 'update'], timeout=30)
            output = (proc.stdout or '') + (proc.stderr or '')
            new_version = cli_version(CLAUDE_CLI_PATH)
            updated = bool(new_version and curr_version and new_version != curr_version)
            return RefreshResult(
                success=True,
                updated=updated,
                old_version=curr_version,
                new_version=new_version or curr_version,
                error='',
            )
        except Exception:
            pass

    if auth_refreshed:
        return RefreshResult(
            success=True,
            updated=False,
            old_version=curr_version,
            new_version=curr_version,
            error='',
        )

    return RefreshResult(
        success=False,
        updated=False,
        old_version=curr_version,
        new_version=curr_version,
        error='Token refresh failed',
    )


def cli_version(path: Path) -> str:
    """Run ``agy --version`` and return the version string, or ``''``."""
    try:
        mtime = path.stat().st_mtime
        cached = _version_cache.get(path)
        if cached and cached[0] == mtime:
            return cached[1]

        proc = _run_cli([str(path), '--version'], timeout=10)
        version = _parse_version(proc.stdout)
        _version_cache[path] = (mtime, version)
        return version
    except Exception:
        return ''


def _command_version(command: list[str]) -> str:
    """Run ``<command> --version`` and return the version string, or ``''``."""
    key = tuple(command)
    cached = _command_version_cache.get(key)
    if cached is not None:
        return cached

    try:
        proc = _run_cli([*command, '--version'], timeout=10)
    except Exception:
        return ''

    version = _parse_version(proc.stdout)
    _command_version_cache[key] = version
    return version


def _run_cli(command: list[str], timeout: int) -> subprocess.CompletedProcess[str]:
    """Run a CLI command and capture its output as UTF-8 text."""
    proc = subprocess.run(
        command,
        capture_output=True, text=True, encoding='utf-8', errors='replace',
        timeout=timeout, **no_window_kwargs(),
    )

    if proc.stdout is None or proc.stderr is None:
        raise OSError(f'Command stream lost: {command[0]}')

    return proc


def _parse_version(stdout: str) -> str:
    """Extract a version string like '1.2.7' from CLI output."""
    match = re.search(r'(\d+\.\d+\.\d+)', stdout)
    return match.group(1) if match else stdout.strip().split()[-1] if stdout.strip() else ''
