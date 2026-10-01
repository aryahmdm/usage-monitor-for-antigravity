"""
Build Script
=============

Builds a standalone EXE for Usage Monitor for Antigravity using PyInstaller and code
signs it when a certificate is configured.

Signing is optional. Without a `signing.env` beside this script the build
produces the same unsigned EXE it always did, so anyone who clones the
repository can build it. That file is git-ignored and holds no secret: the
token's PIN is never stored, signtool asks the token for it on every run.

Usage:
    python build.py

Produces:
    dist/UsageMonitorForAntigravity.exe
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).parent
DIST = ROOT / 'dist'
SPEC = ROOT / 'usage_monitor_for_antigravity.spec'
SIGNING_CONFIG = ROOT / 'signing.env'


def build() -> None:
    """Run PyInstaller to produce the standalone EXE, then sign it when configured."""
    print('Starting PyInstaller build ...')
    cmd = [sys.executable, '-m', 'PyInstaller', '--clean', '--noconfirm', str(SPEC)]
    subprocess.check_call(cmd, cwd=str(ROOT))

    exe = DIST / 'UsageMonitorForAntigravity.exe'
    if not exe.exists():
        print('\nBuild failed - EXE not found.')
        sys.exit(1)

    _sign(exe)

    size_mb = exe.stat().st_size / (1024 * 1024)
    print(f'\nBuild successful!  {exe}  ({size_mb:.1f} MB)')


def _sign(exe: Path) -> None:
    """
    Code sign the executable in place and verify what came out.

    A build without `signing.env` returns immediately. A configured signature
    that fails stops the build instead of leaving an unsigned EXE behind, which
    would otherwise reach a release page looking finished.

    A failed attempt is repeated against the fallback timestamp server when one
    is configured, because the cause is not knowable here: a mistyped PIN fails
    exactly like a timestamp server that did not answer, and a second try costs
    one more PIN prompt. Neither message therefore names a cause - signtool's
    own output on stdout is what says why.
    """
    config = _read_signing_config()
    if not config:
        return

    signtool = _signtool()
    thumbprint = config['SIGNING_THUMBPRINT']
    timestamp_urls = [config['SIGNING_TIMESTAMP_URL']]
    fallback = config.get('SIGNING_FALLBACK_TIMESTAMP_URL')
    if fallback:
        timestamp_urls.append(fallback)

    for i, timestamp_url in enumerate(timestamp_urls):
        attempt = f' (attempt {i + 1}/{len(timestamp_urls)})' if len(timestamp_urls) > 1 else ''
        print(f'\nCode signing {exe.name}{attempt} ...')
        cmd = [
            str(signtool), 'sign',
            '/fd', 'sha256',
            '/sha1', thumbprint,
            '/tr', timestamp_url,
            '/td', 'sha256',
            str(exe),
        ]
        result = subprocess.run(cmd)
        if result.returncode == 0:
            print('\nVerifying signature ...')
            verify = subprocess.run([str(signtool), 'verify', '/pa', str(exe)])
            if verify.returncode != 0:
                print('\nSignature verification failed.')
                sys.exit(1)
            return

    print('\nCode signing failed.')
    sys.exit(1)


def _read_signing_config() -> dict[str, str] | None:
    """
    Read the local `signing.env` file.

    Returns
    -------
    dict[str, str] | None
        The configuration, or `None` when no `signing.env` exists.
    """
    if not SIGNING_CONFIG.is_file():
        return None

    config: dict[str, str] = {}
    for line in SIGNING_CONFIG.read_text(encoding='utf-8').splitlines():
        line = line.strip()
        if not line or line.startswith('#'):
            continue
        key, sep, value = line.partition('=')
        if sep:
            config[key.strip()] = value.strip().strip('"').strip("'")

    for key in ('SIGNING_THUMBPRINT', 'SIGNING_TIMESTAMP_URL'):
        if not config.get(key):
            print(f'{SIGNING_CONFIG.name}: {key} is missing or empty')
            sys.exit(1)

    return config


def _signtool() -> Path:
    """
    Locate the newest 64-bit signtool.exe among the installed Windows SDKs.

    Returns
    -------
    Path
        The signtool to sign with.
    """
    program_files = [os.environ.get('ProgramFiles(x86)'), os.environ.get('ProgramFiles')]
    candidates: list[tuple[tuple[int, ...], Path]] = []
    for base in program_files:
        if not base:
            continue

        root = Path(base) / 'Windows Kits' / '10' / 'bin'
        if not root.is_dir():
            continue

        for entry in root.iterdir():
            tool = entry / 'x64' / 'signtool.exe'
            if tool.is_file():
                candidates.append((_sdk_version(entry.name), tool))\

    if not candidates:
        print('signtool.exe not found - install the Windows SDK signing tools.')
        sys.exit(1)

    return max(candidates)[1]


def _sdk_version(name: str) -> tuple[int, ...]:
    """Sort key for an SDK directory name such as `10.0.19041.0`; anything else sorts last."""
    parts = name.split('.')
    if not all(part.isdigit() for part in parts):
        return (0,)

    return tuple(int(part) for part in parts)


if __name__ == '__main__':
    build()

_signing_config = _read_signing_config
