"""Backward compatibility alias for antigravity_cli."""
import shutil
import subprocess
from .antigravity_cli import *
from . import antigravity_cli as _agy

_command_version_cache = _agy._command_version_cache
_version_cache = _agy._version_cache
_run_cli = _agy._run_cli
_discover_cli_path = _agy._discover_cli_path
_EXTENSION_DIRS = _agy._EXTENSION_DIRS
_EXTENSION_PREFIXES = _agy._EXTENSION_PREFIXES
