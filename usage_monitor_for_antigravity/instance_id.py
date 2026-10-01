"""
Instance Identity
==================

Derives a per-instance identifier from the effective Antigravity config
directory so multiple monitor instances can coexist, each guarding its own
single-instance mutex and autostart registry entry.

This module must stay free of imports from ``api`` or ``settings`` -
it is used before config directories are finalized in ``__main__``.
"""
from __future__ import annotations

import hashlib
import os
import re
from pathlib import Path

__all__ = ['config_dir_suffix', 'effective_config_dir', 'is_default_config_dir', 'parse_config_dir']


def parse_config_dir(argv: list[str]) -> str | None:
    """Extract the ``--config-dir`` value from command-line arguments.

    Supports both ``--config-dir=PATH`` and ``--config-dir PATH`` forms.
    Surrounding quotes and a stray trailing quote (left by cmd.exe when
    the path ends with a backslash, e.g. ``--config-dir="C:\\dir\\"``)
    are stripped.  Environment variables (``%USERPROFILE%``) and a
    leading ``~`` are expanded, so the flag works the same from cmd.exe,
    PowerShell, and shortcut targets.

    Parameters
    ----------
    argv : list[str]
        Argument list, typically ``sys.argv``.

    Returns
    -------
    str | None
        The cleaned path value, or ``None`` if the flag is absent or
        has no value.
    """
    value = None
    for index, arg in enumerate(argv):
        if arg.startswith('--config-dir='):
            value = arg.split('=', 1)[1]
        elif arg == '--config-dir' and index + 1 < len(argv):
            value = argv[index + 1]

    if value is None:
        return None

    value = value.strip().strip('"').rstrip('\\/')
    if not value:
        return None

    # A bare drive letter left by the rstrip ('D:') is a drive-relative path
    # (the current directory on that drive) - restore the root separator.
    if re.fullmatch(r'[A-Za-z]:', value):
        value += '\\'

    return str(Path(os.path.expandvars(value)).expanduser())


def effective_config_dir() -> Path:
    """Return the resolved Antigravity config directory currently in effect."""
    custom = os.environ.get('GEMINI_HOME') or os.environ.get('ANTIGRAVITY_CONFIG_DIR') or os.environ.get('CLAUDE_CONFIG_DIR')
    base = Path(custom) if custom else Path.home() / '.gemini'
    return base.resolve()


def is_default_config_dir() -> bool:
    """Return True when the effective config dir is the default ``~/.gemini``."""
    default = (Path.home() / '.gemini').resolve()
    return os.path.normcase(str(effective_config_dir())) == os.path.normcase(str(default))


def config_dir_suffix() -> str:
    """Return a per-instance suffix for kernel object and registry names.

    Empty for the default ``~/.gemini`` directory, otherwise an underscore
    plus a short hash of the resolved, case-normalized directory path.
    """
    if is_default_config_dir():
        return ''

    normalized = os.path.normcase(str(effective_config_dir()))
    return '_' + hashlib.sha1(normalized.encode('utf-8')).hexdigest()[:12]
