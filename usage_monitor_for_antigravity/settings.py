"""
Settings
=========

Centralizes all user-tunable constants.  Structural constants (API URLs,
registry keys, file paths) remain in their respective modules.

Loads an optional ``usage-monitor-settings.json`` to let users override
any constant.  Search order:

1. ``$ANTIGRAVITY_CONFIG_DIR/usage-monitor-settings.json`` (if set and different from ``~/.gemini/``)
2. Next to the executable (frozen) or project root (source)
3. ``~/.gemini/usage-monitor-settings.json``

The app never creates this file - users place it manually.
"""
from __future__ import annotations

import json
import locale as _locale
import sys
from pathlib import Path

from .instance_id import effective_config_dir, is_default_config_dir
from .platforms import show_warning_box, system_time_format

__all__ = [
    'ALERT_EXTRA_USAGE_SPENT', 'ALERT_TIME_AWARE', 'ALERT_TIME_AWARE_BELOW',
    'BAR_BG', 'BAR_DIVIDER', 'BAR_FG', 'BAR_FG_WARN', 'BAR_MARKER', 'BG',
    'CLI_COMMAND', 'COMPACT_HIDE', 'CURRENCY_SYMBOL',
    'FG', 'FG_DIM', 'FG_HEADING', 'FG_LINK',
    'ICON_DARK', 'ICON_FIELDS', 'ICON_LIGHT', 'ICON_STYLE', 'IDLE_INTERVAL', 'IDLE_PAUSE',
    'LANGUAGE', 'MAX_BACKOFF', 'NOTIFY_CLAUDE_UPDATE', 'NOTIFY_ANTIGRAVITY_UPDATE',
    'ON_RESET_COMMAND', 'ON_STARTUP_COMMAND', 'ON_THRESHOLD_COMMAND', 'QUICK_ACTION_COMMAND',
    'POLL_ERROR', 'POLL_FAST', 'POLL_FAST_EXTRA', 'POLL_INTERVAL',
    'POPUP_FIELDS', 'SETTINGS_FILENAME', 'TIME_FORMAT', 'TOOLTIP_FIELDS',
    'get_alert_thresholds',
]

SETTINGS_FILENAME = 'usage-monitor-settings.json'

_NUMERIC_BOUNDS: dict[str, int] = {
    'poll_interval': 1,
    'poll_fast': 1,
    'poll_fast_extra': 1,
    'poll_error': 1,
    'max_backoff': 1,
    'idle_pause': 0,
    'idle_interval': 1,
}
_COLOR_KEYS = frozenset({'bg', 'fg', 'fg_dim', 'fg_heading', 'fg_link', 'bar_bg', 'bar_fg', 'bar_fg_warn', 'bar_divider', 'bar_marker'})
_ICON_KEYS = frozenset({'icon_light', 'icon_dark'})
_THRESHOLD_KEY_PREFIX = 'alert_thresholds_'
_PERCENT_KEYS = frozenset({'alert_time_aware_below'})
_STRING_KEYS = frozenset({'currency_symbol', 'language'})
_VALID_TIME_FORMATS = frozenset({'24h', '12h'})
_VALID_ICON_STYLES = frozenset({'number+bars', 'numbers'})
_COMMAND_KEYS = frozenset({
    'quick_action_command', 'on_double_click_command', 'on_reset_command', 'on_startup_command', 'on_threshold_command',
})
_BOOL_KEYS = frozenset({'alert_time_aware', 'notify_claude_update', 'notify_antigravity_update'})
_STRING_LIST_KEYS = frozenset({'tooltip_fields', 'compact_hide'})
_WILDCARD_STRING_LIST_KEYS = frozenset({'popup_fields'})
_VALID_BAR_MODES = frozenset({'utilization', 'overage'})


def _quick_action_command(settings: dict) -> list[str]:
    """Resolve the quick action, accepting its former name as an alias."""
    if 'quick_action_command' in settings:
        return settings['quick_action_command']

    return settings.get('on_double_click_command', [])


def _load_settings() -> dict:
    """Read the first ``usage-monitor-settings.json`` found, or return ``{}``."""
    if getattr(sys, 'frozen', False):
        app_dir = Path(sys.executable).parent
    else:
        app_dir = Path(__file__).resolve().parent.parent

    home_gemini = Path.home() / '.gemini'

    search_paths = []
    if not is_default_config_dir():
        search_paths.append(effective_config_dir() / SETTINGS_FILENAME)
    search_paths.append(app_dir / SETTINGS_FILENAME)
    search_paths.append(home_gemini / SETTINGS_FILENAME)

    for path in search_paths:
        if path.is_file():
            try:
                text = path.read_text(encoding='utf-8-sig').strip()
                if not text:
                    return {}
                data = json.loads(text)
                if not isinstance(data, dict):
                    raise ValueError(f'Expected a JSON object, got {type(data).__name__}')
                return _validate(data, path)
            except (json.JSONDecodeError, ValueError) as exc:
                show_warning_box(
                    f'Invalid JSON in settings file:\n{path}\n\n{exc}',
                    'Usage Monitor for Antigravity - Settings Error',
                )
                return {}
            except OSError:
                return {}

    return {}


def _valid_rgba(value: object) -> bool:
    """Return True if *value* is a list of exactly 4 integers in 0–255."""
    return (
        isinstance(value, list) and len(value) == 4
        and all(isinstance(c, int) and not isinstance(c, bool) and 0 <= c <= 255 for c in value)
    )


def _validate(data: dict, path: Path) -> dict:
    """Drop entries with invalid types or values and show a MessageBox listing errors."""
    errors: list[str] = []
    drop: list[str] = []

    for key, value in data.items():
        if key in _NUMERIC_BOUNDS:
            min_val = _NUMERIC_BOUNDS[key]
            if isinstance(value, bool) or not isinstance(value, int):
                errors.append(f'  {key}: expected an integer, got {type(value).__name__}')
                drop.append(key)
            elif value < min_val:
                errors.append(f'  {key}: must be >= {min_val}, got {value}')
                drop.append(key)

        elif key in _COLOR_KEYS:
            if not isinstance(value, str):
                errors.append(f'  {key}: expected a color string, got {type(value).__name__}')
                drop.append(key)

        elif key.startswith(_THRESHOLD_KEY_PREFIX):
            if not isinstance(value, list):
                errors.append(f'  {key}: expected an array, got {type(value).__name__}')
                drop.append(key)
            else:
                bad = [v for v in value if isinstance(v, bool) or not isinstance(v, (int, float)) or not (1 <= v <= 100)]
                if bad:
                    errors.append(f'  {key}: all values must be numbers between 1 and 100')
                    drop.append(key)
                else:
                    data[key] = sorted(set(value))

        elif key == 'alert_extra_usage_spent':
            if not isinstance(value, list):
                errors.append(f'  {key}: expected an array, got {type(value).__name__}')
                drop.append(key)
            else:
                bad = [v for v in value if isinstance(v, bool) or not isinstance(v, (int, float)) or v <= 0]
                if bad:
                    errors.append(f'  {key}: all values must be numbers greater than 0')
                    drop.append(key)
                else:
                    data[key] = sorted(set(value))

        elif key in _PERCENT_KEYS:
            if isinstance(value, bool) or not isinstance(value, (int, float)):
                errors.append(f'  {key}: expected a number, got {type(value).__name__}')
                drop.append(key)
            elif not (1 <= value <= 100):
                errors.append(f'  {key}: must be between 1 and 100, got {value}')
                drop.append(key)

        elif key in _STRING_KEYS:
            if not isinstance(value, str):
                errors.append(f'  {key}: expected a string, got {type(value).__name__}')
                drop.append(key)

        elif key == 'time_format':
            if value not in _VALID_TIME_FORMATS:
                errors.append(f'  {key}: must be "24h" or "12h", got {value!r}')
                drop.append(key)

        elif key == 'icon_style':
            if value not in _VALID_ICON_STYLES:
                errors.append(f'  {key}: must be "number+bars" or "numbers", got {value!r}')
                drop.append(key)

        elif key in _COMMAND_KEYS:
            if isinstance(value, str):
                data[key] = [value] if value.strip() else []
            elif isinstance(value, list):
                if any(not isinstance(item, str) or not item.strip() for item in value):
                    errors.append(f'  {key}: all items must be non-empty strings')
                    drop.append(key)
            else:
                errors.append(f'  {key}: expected a string or array of strings, got {type(value).__name__}')
                drop.append(key)

        elif key in _BOOL_KEYS:
            if not isinstance(value, bool):
                errors.append(f'  {key}: expected true or false, got {type(value).__name__}')
                drop.append(key)

        elif key in _STRING_LIST_KEYS:
            if not isinstance(value, list):
                errors.append(f'  {key}: expected an array, got {type(value).__name__}')
                drop.append(key)
            elif any(not isinstance(item, str) or not item for item in value):
                errors.append(f'  {key}: all entries must be non-empty strings')
                drop.append(key)
            else:
                seen: set[str] = set()
                deduped: list[str] = []
                for item in value:
                    if item not in seen:
                        seen.add(item)
                        deduped.append(item)
                data[key] = deduped

        elif key in _WILDCARD_STRING_LIST_KEYS:
            if not isinstance(value, list):
                errors.append(f'  {key}: expected an array, got {type(value).__name__}')
                drop.append(key)
            elif any(not isinstance(item, str) or not item for item in value):
                errors.append(f'  {key}: all entries must be non-empty strings')
                drop.append(key)
            elif value.count('*') > 1:
                errors.append(f'  {key}: "*" may appear at most once')
                drop.append(key)
            else:
                seen_wc: set[str] = set()
                deduped_wc: list[str] = []
                for item in value:
                    if item == '*' or item not in seen_wc:
                        seen_wc.add(item)
                        deduped_wc.append(item)
                data[key] = deduped_wc

        elif key == 'icon_fields':
            if not isinstance(value, list):
                errors.append(f'  {key}: expected an array, got {type(value).__name__}')
                drop.append(key)
            elif len(value) != 2:
                errors.append(f'  {key}: expected exactly 2 entries, got {len(value)}')
                drop.append(key)
            elif any(not isinstance(item, str) or not item for item in value):
                errors.append(f'  {key}: all entries must be non-empty strings')
                drop.append(key)
            else:
                invalid_modes = [
                    item for item in value
                    if ':' in item and item.split(':', 1)[1] not in _VALID_BAR_MODES
                ]
                if invalid_modes:
                    errors.append(
                        f'  {key}: unknown bar mode in: {", ".join(invalid_modes)}'
                        f' (valid: {", ".join(sorted(_VALID_BAR_MODES))})'
                    )
                    drop.append(key)

        elif key in _ICON_KEYS:
            if not isinstance(value, dict):
                errors.append(f'  {key}: expected an object, got {type(value).__name__}')
                drop.append(key)
            else:
                bad = [k for k, v in value.items() if not _valid_rgba(v)]
                for k in bad:
                    errors.append(f'  {key}.{k}: expected [R, G, B, A] with integers 0–255')
                    del value[k]

        elif key == 'cli_command':
            if not isinstance(value, dict):
                errors.append(f'  {key}: expected an object mapping a name to a command array, got {type(value).__name__}')
                drop.append(key)
            else:
                invalid = False
                for name, command in value.items():
                    if not name.strip():
                        errors.append(f'  {key}: names must be non-empty strings')
                        invalid = True
                        break
                    if not isinstance(command, list) or not command or any(not isinstance(item, str) or not item.strip() for item in command):
                        errors.append(f'  {key}.{name}: expected a non-empty array of non-empty strings')
                        invalid = True
                        break
                if invalid:
                    drop.append(key)

    for key in drop:
        del data[key]

    if errors:
        show_warning_box(
            f'Invalid values in settings file:\n{path}\n\n' + '\n'.join(errors),
            'Usage Monitor for Antigravity - Settings Error',
        )

    return data


def _icon_colors(key: str, defaults: dict[str, tuple]) -> dict[str, tuple]:
    """Merge icon color overrides from settings, converting JSON arrays to tuples."""
    overrides = _S.get(key, {})
    return {k: tuple(overrides[k]) if k in overrides else v for k, v in defaults.items()}


_S = _load_settings()

# Polling intervals (seconds)
POLL_INTERVAL = _S.get('poll_interval', 180)
POLL_FAST = _S.get('poll_fast', 120)
POLL_FAST_EXTRA = _S.get('poll_fast_extra', 2)
POLL_ERROR = _S.get('poll_error', 30)
MAX_BACKOFF = _S.get('max_backoff', 900)
IDLE_PAUSE = _S.get('idle_pause', 300)
IDLE_INTERVAL = _S.get('idle_interval', 900)

# Popup theme
BG = _S.get('bg', '#1e1e1e')
FG = _S.get('fg', '#cccccc')
FG_DIM = _S.get('fg_dim', '#888888')
FG_HEADING = _S.get('fg_heading', '#ffffff')
FG_LINK = _S.get('fg_link', '#4a9eff')
BAR_BG = _S.get('bar_bg', '#333333')
BAR_FG = _S.get('bar_fg', '#4a9eff')
BAR_FG_WARN = _S.get('bar_fg_warn', '#e05050')
BAR_DIVIDER = _S.get('bar_divider', '#000c')
BAR_MARKER = _S.get('bar_marker', '#fffc')

# Tray icon colors
ICON_LIGHT = _icon_colors('icon_light', {\
    'fg': (255, 255, 255, 255),
    'fg_half': (255, 255, 255, 80),
    'fg_dim': (255, 255, 255, 140),
    'fg_warn': (224, 80, 80, 255),
})
ICON_DARK = _icon_colors('icon_dark', {
    'fg': (0, 0, 0, 255),
    'fg_half': (0, 0, 0, 80),
    'fg_dim': (0, 0, 0, 140),
    'fg_warn': (224, 80, 80, 255),
})

# Tray icon fields: Gemini 5-hour and Gemini Weekly
ICON_FIELDS: list[str] = _S.get('icon_fields', ['gemini_5h', 'gemini_weekly'])

# Tray icon layout: 'number+bars' shows the top field's percentage above two
# usage bars, 'numbers' shows both fields as two stacked percentages
ICON_STYLE: str = _S.get('icon_style', 'number+bars')

# Tooltip fields
TOOLTIP_FIELDS: list[str] = _S.get('tooltip_fields', ['gemini_5h', 'gemini_weekly', 'claude_5h', 'claude_weekly'])

# Popup fields
POPUP_FIELDS: list[str] = _S.get('popup_fields', ['*'])

# Sections and usage bars hidden while the popup is pinned (compact view)
COMPACT_HIDE: list[str] = _S.get('compact_hide', [])

# Alert thresholds
ALERT_TIME_AWARE: bool = _S.get('alert_time_aware', True)
ALERT_TIME_AWARE_BELOW: float = _S.get('alert_time_aware_below', 90)

# Notify when a background token refresh installs a new Antigravity CLI version
NOTIFY_CLAUDE_UPDATE: bool = _S.get('notify_antigravity_update', _S.get('notify_claude_update', True))
NOTIFY_ANTIGRAVITY_UPDATE = NOTIFY_CLAUDE_UPDATE

# Currency

def _detect_currency_symbol() -> str:
    """Detect the system locale currency symbol for monetary formatting."""
    try:
        _locale.setlocale(_locale.LC_MONETARY, '')
        return _locale.localeconv().get('currency_symbol', '') or ''
    except _locale.Error:
        return ''


_SYSTEM_CURRENCY_SYMBOL = _detect_currency_symbol()
CURRENCY_SYMBOL: str | None = _S.get('currency_symbol')

# Language override
LANGUAGE: str = _S.get('language', '')

# Clock format for reset times: '24h' (e.g. 14:30) or '12h' (e.g. 2:30 PM)
_SYSTEM_TIME_FORMAT = system_time_format()
TIME_FORMAT: str = _S.get('time_format', _SYSTEM_TIME_FORMAT)

# Extra CLI command(s)
CLI_COMMAND: dict[str, list[str]] = _S.get('cli_command', {})

# Event commands
QUICK_ACTION_COMMAND: list[str] = _quick_action_command(_S)
ON_RESET_COMMAND: list[str] = _S.get('on_reset_command', [])
ON_STARTUP_COMMAND: list[str] = _S.get('on_startup_command', [])
ON_THRESHOLD_COMMAND: list[str] = _S.get('on_threshold_command', [])

_ALERT_THRESHOLDS: dict[str, list[float]] = {
    'gemini_5h': [50, 80, 95],
    'gemini_weekly': [80, 95],
    'claude_5h': [50, 80, 95],
    'claude_weekly': [80, 95],
    'gemini_flash': [50, 80, 95],
    'gemini_pro': [80, 95],
    'session': [50, 80, 95],
    'five_hour': [50, 80, 95],
    'seven_day': [95],
    'extra_usage': [50, 80, 95],
}

ALERT_EXTRA_USAGE_SPENT: list[float] = _S.get('alert_extra_usage_spent', [])


def get_alert_thresholds(variant_key: str) -> list[float]:
    """Return the alert thresholds for a usage variant."""
    exact_settings_key = f'{_THRESHOLD_KEY_PREFIX}{variant_key}'
    if exact_settings_key in _S:
        return _S[exact_settings_key]

    if variant_key in _ALERT_THRESHOLDS:
        return _ALERT_THRESHOLDS[variant_key]

    return []
