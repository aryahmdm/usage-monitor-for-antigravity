"""
Formatting
===========

Pure functions for formatting usage data: time-until-reset strings,
elapsed period percentages, credit amounts, status lines, and tooltip text.
"""
from __future__ import annotations

import locale as _locale
from datetime import datetime, timedelta, timezone
from typing import Any

from .i18n import T
from .settings import CURRENCY_SYMBOL, TIME_FORMAT, TOOLTIP_FIELDS, _SYSTEM_CURRENCY_SYMBOL

__all__ = [
    'divider_positions', 'elapsed_pct', 'expand_popup_fields', 'field_period', 'format_credits',
    'format_tooltip', 'is_active_quota', 'parse_field_name', 'popup_label', 'time_until', 'tooltip_label',
]

PERIOD_5H = 5 * 3600
PERIOD_7D = 7 * 24 * 3600

_NUMBER_WORDS = {
    'one': 1, 'two': 2, 'three': 3, 'four': 4, 'five': 5, 'six': 6,
    'seven': 7, 'eight': 8, 'nine': 9, 'ten': 10, 'eleven': 11, 'twelve': 12,
}
_UNIT_SUFFIXES = {'hour': 'h', 'day': 'd'}
_TITLE_CASE_EXCEPTIONS = {'oauth': 'OAuth', 'api': 'API', 'ai': 'AI', '3p': '3P', 'gpt': 'GPT'}
_CURRENCY_SYMBOLS = {
    'USD': '$', 'EUR': '€', 'GBP': '£', 'JPY': '¥', 'CNY': '¥',
    'INR': '₹', 'KRW': '₩', 'BRL': 'R$', 'CAD': 'CA$', 'AUD': 'A$', 'CHF': 'CHF',
}

_ANTIGRAVITY_SHORT_LABELS = {
    'gemini_5h': 'Gemini 5h',
    'gemini_weekly': 'Gemini Wk',
    'claude_5h': 'Claude 5h',
    'claude_weekly': 'Claude Wk',
    'gemini_flash': 'Gemini 5h',
    'gemini_pro': 'Gemini Wk',
    'claude_session': 'Claude 5h',
    'session': 'Session',
    'daily': 'Daily',
}

_ANTIGRAVITY_FULL_LABELS = {
    'gemini_5h': 'Gemini Models (5-Hour)',
    'gemini_weekly': 'Gemini Models (Weekly)',
    'claude_5h': 'Claude & GPT Models (5-Hour)',
    'claude_weekly': 'Claude & GPT Models (Weekly)',
    'gemini_flash': 'Gemini Models (5-Hour)',
    'gemini_pro': 'Gemini Models (Weekly)',
    'claude_session': 'Claude & GPT Models (5-Hour)',
    'session': 'Antigravity Session',
    'daily': 'Daily Turns',
}

_ALIAS_KEYS = frozenset({'gemini_flash', 'gemini_pro', 'claude_session'})


def parse_field_name(field: str) -> tuple[int, str, str | None] | None:
    """Parse an API field name into its numeric, unit, and variant components."""
    parts = field.split('_', 2)
    if len(parts) < 2:
        return None

    number = _NUMBER_WORDS.get(parts[0])
    unit = parts[1]
    if number is None or unit not in _UNIT_SUFFIXES:
        return None

    variant = parts[2] if len(parts) > 2 else None
    return (number, unit, variant)


def _title_case_variant(text: str) -> str:
    """Title-case a variant string, respecting abbreviation exceptions."""
    return ' '.join(_TITLE_CASE_EXCEPTIONS.get(w.lower(), w.title()) for w in text.split('_'))


def tooltip_label(field: str) -> str:
    """Generate a short tooltip label from an API field name."""
    if field in _ANTIGRAVITY_SHORT_LABELS:
        return _ANTIGRAVITY_SHORT_LABELS[field]

    parsed = parse_field_name(field)
    if parsed is None:
        return _title_case_variant(field)

    number, unit, variant = parsed
    label = f'{number}{_UNIT_SUFFIXES[unit]}'
    if variant:
        label += f' {_title_case_variant(variant)}'
    return label


def popup_label(field: str) -> str:
    """Generate a popup bar label from an API field name using i18n templates."""
    if field in _ANTIGRAVITY_FULL_LABELS:
        return _ANTIGRAVITY_FULL_LABELS[field]

    parsed = parse_field_name(field)
    if parsed is None:
        return _title_case_variant(field)

    number, unit, variant = parsed
    if variant:
        suffix = _title_case_variant(variant)
    elif unit == 'hour':
        suffix = f'{number}hr'
    else:
        suffix = f'{number} {unit}'

    template_key = 'session_label' if unit == 'hour' else 'weekly_label'
    return T[template_key].format(suffix=suffix)


def field_period(field: str) -> int | None:
    """Return the period duration in seconds for a field, or None if unknown."""
    if '5h' in field or 'flash' in field or 'session' in field:
        return PERIOD_5H
    if 'weekly' in field or 'pro' in field or '7d' in field:
        return PERIOD_7D

    parsed = parse_field_name(field)
    if parsed is None:
        return None

    number, unit, _ = parsed
    if unit == 'hour':
        return number * 3600
    if unit == 'day':
        return number * 24 * 3600
    return None


def is_active_quota(field: str, entry: Any) -> bool:
    """Return True if a usage entry is a quota that applies to the account."""
    if not isinstance(entry, dict) or entry.get('utilization') is None:
        return False

    if field in (
        'gemini_5h', 'gemini_weekly', 'claude_5h', 'claude_weekly',
        'gemini_flash', 'gemini_pro', 'claude_session', 'session', 'daily'
    ):
        return True

    return bool(entry.get('resets_at')) or parse_field_name(field) is not None or bool(entry.get('from_account_limits'))


def _field_sort_key(field: str) -> tuple[int, int, int, str]:
    """Sort key for default field ordering."""
    order_map = {
        'gemini_5h': 0,
        'gemini_weekly': 1,
        'claude_5h': 2,
        'claude_weekly': 3,
        'gemini_flash': 4,
        'gemini_pro': 5,
        'claude_session': 6,
        'session': 7,
    }
    if field in order_map:
        return (0, order_map[field], 0, field)

    parsed = parse_field_name(field)
    if parsed is None:
        return (2, 0, 0, field)

    number, unit, variant = parsed
    unit_order = 0 if unit == 'hour' else 1
    variant_order = 0 if variant is None else 1
    return (unit_order, number, variant_order, variant or '')


def expand_popup_fields(popup_fields: list[str], usage_data: dict[str, Any]) -> list[str]:
    """Expand a popup_fields setting into concrete field names based on API data."""
    available = {
        key for key, value in usage_data.items()
        if isinstance(value, dict) and is_active_quota(key, value)
    }

    result: list[str] = []
    seen: set[str] = set()

    for field in popup_fields:
        if field == '*':
            candidates = available
            if any(k in available for k in ('gemini_5h', 'gemini_weekly', 'claude_5h', 'claude_weekly')):
                candidates = {k for k in available if k not in _ALIAS_KEYS}
            remaining = sorted((f for f in candidates if f not in seen), key=_field_sort_key)
            for f in remaining:
                seen.add(f)
                result.append(f)
        elif field in available and field not in seen:
            seen.add(field)
            result.append(field)

    return result


def elapsed_pct(resets_at: str, period_seconds: int) -> float | None:
    """Return elapsed percentage of a usage period, or None if not calculable."""
    if not resets_at or period_seconds <= 0:
        return None

    try:
        reset = datetime.fromisoformat(resets_at)
        now = datetime.now(timezone.utc)
        remaining = (reset - now).total_seconds()
        elapsed = period_seconds - remaining

        return max(0.0, min(100.0, elapsed / period_seconds * 100))
    except Exception:
        return None


def divider_positions(resets_at: str, period_seconds: int) -> list[float]:
    """Return relative positions (0.0-1.0) of divider marks within a usage period."""
    if not resets_at or period_seconds <= 0:
        return []

    try:
        reset = datetime.fromisoformat(resets_at)
        start = reset - timedelta(seconds=period_seconds)

        if period_seconds <= PERIOD_5H:
            return [i / 5 for i in range(1, 5)]

        positions: list[float] = []
        day = start.replace(hour=0, minute=0, second=0, microsecond=0) + timedelta(days=1)
        while day < reset:
            offset = (day - start).total_seconds()
            pos = offset / period_seconds
            if 0 < pos < 1:
                positions.append(pos)
            day += timedelta(days=1)

        return positions
    except Exception:
        return []


def _format_clock(when: datetime, clock_24h: bool) -> str:
    """Format a local time as a 24-hour ('14:30') or 12-hour ('2:30 PM') clock string."""
    if clock_24h:
        return when.strftime('%H:%M')
    return when.strftime('%I:%M %p').lstrip('0')


def time_until(iso_str: str, clock_24h: bool | None = None) -> str:
    """Return human-readable reset time."""
    if clock_24h is None:
        clock_24h = TIME_FORMAT == '24h'

    if not iso_str:
        return ''

    try:
        reset = datetime.fromisoformat(iso_str)
        now = datetime.now(timezone.utc)
        diff = reset - now
        total_seconds = diff.total_seconds()

        if total_seconds < 60:
            return T['resets_imminent'] if total_seconds > -60 else ''

        total_min = int(total_seconds / 60)
        reset_local = reset.astimezone()
        today = datetime.now().date()
        if reset_local.second >= 30:
            reset_local = reset_local.replace(second=0) + timedelta(minutes=1)
        else:
            reset_local = reset_local.replace(second=0)
        reset_date = reset_local.date()
        time_str = _format_clock(reset_local, clock_24h)

        if reset_date == today:
            if total_min >= 60:
                duration = T['duration_hm'].format(h=total_min // 60, m=total_min % 60)
            else:
                duration = T['duration_m'].format(m=max(1, total_min))
            return T['resets_in'].format(duration=duration, clock=time_str)

        tomorrow = today + timedelta(days=1)
        if reset_date == tomorrow:
            return T['resets_tomorrow'].format(clock=time_str)

        days_ahead = (reset_date - today).days
        if days_ahead < 7:
            day_name = T['weekdays'][reset_local.weekday()]
            return T['resets_weekday'].format(day=day_name, clock=time_str)

        return f'{reset_local.strftime("%b %d")}, {time_str}'
    except Exception:
        return ''


def _target_currency_symbol(currency: str | None) -> str:
    """Return the currency symbol to display."""
    if CURRENCY_SYMBOL is not None:
        return CURRENCY_SYMBOL
    if currency:
        return _CURRENCY_SYMBOLS.get(currency.upper(), currency.upper())
    return _SYSTEM_CURRENCY_SYMBOL


def format_credits(minor_units: float, currency: str | None = None, decimal_places: int | None = None) -> str:
    """Format a minor-unit amount as a localized currency string."""
    places = decimal_places if decimal_places is not None else 2
    amount = minor_units / (10 ** places)
    symbol = _target_currency_symbol(currency)

    try:
        formatted = _locale.currency(amount, grouping=True)
        if symbol != _SYSTEM_CURRENCY_SYMBOL and _SYSTEM_CURRENCY_SYMBOL:
            formatted = formatted.replace(_SYSTEM_CURRENCY_SYMBOL, symbol).strip()
        return formatted
    except (ValueError, _locale.Error):
        if symbol:
            return f'{symbol}\u00a0{amount:.{places}f}'
        return f'{amount:.{places}f}'


def format_tooltip(data: dict[str, Any]) -> str:
    """Format usage data as short tooltip text.

    Windows tray limits tooltips to 127 characters. To stay safely under
    that ceiling, reset countdowns are dynamically omitted (starting with
    inactive 0% quotas, then secondary quotas) when necessary.
    """
    if 'error' in data:
        if data.get('auth_error'):
            return f"{T['auth_expired_label']}\n{T['auth_expired_short']}"
        error = data['error']
        server_msg = data.get('server_message')
        if server_msg:
            error += f' {server_msg}'
        res = f"{T['error_label']}\n{error[:80]}"
        return res[:127]

    matched_entries: list[tuple[str, dict[str, Any]]] = []
    for key in TOOLTIP_FIELDS:
        entry = data.get(key)
        if isinstance(entry, dict) and entry.get('utilization') is not None:
            matched_entries.append((key, entry))

    if not matched_entries:
        for key, entry in data.items():
            if isinstance(entry, dict) and entry.get('utilization') is not None:
                matched_entries.append((key, entry))

    def _assemble(mode: str) -> str:
        out = [T['tooltip_title']]
        for key, entry in matched_entries:
            short = tooltip_label(key)
            pct = f"{entry['utilization']:.0f}%"
            util = entry.get('utilization', 0) or 0
            reset = time_until(entry.get('resets_at', ''))
            line = f'{short}: {pct}'
            if mode == 'all' and reset:
                line += f' ({reset})'
            elif mode == 'active_only' and util > 0 and reset:
                line += f' ({reset})'
            elif mode == 'primary_only' and key == matched_entries[0][0] and util > 0 and reset:
                line += f' ({reset})'
            out.append(line)
        return '\n'.join(out)

    for mode in ('all', 'active_only', 'primary_only', 'none'):
        text = _assemble(mode)
        if len(text) <= 127:
            return text

    return text[:127]
