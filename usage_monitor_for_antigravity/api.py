"""
API Client for Antigravity
===========================

Reads Google / Antigravity OAuth credentials and communicates with
Antigravity Language Server, Cloud Code API, agy CLI, and local telemetry databases.

Handles Google OAuth token reading and automatic refreshing.
"""
from __future__ import annotations

import base64
import datetime
import glob
import json
import logging
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import requests
import urllib3
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

try:
    import truststore
except ImportError:
    truststore = None

from .i18n import T
from .instance_id import effective_config_dir
from .platforms import no_window_kwargs

log = logging.getLogger(__name__)

__all__ = [
    'API_URL_USAGE', 'API_URL_PROFILE', 'API_URL_PREPAID_CREDITS',
    'ANTIGRAVITY_CONFIG_DIR', 'ANTIGRAVITY_CREDENTIALS',
    'CLAUDE_CONFIG_DIR', 'CLAUDE_CREDENTIALS',
    'read_access_token', 'refresh_google_oauth_token', 'api_headers',
    'fetch_usage', 'fetch_profile', 'fetch_prepaid_credits',
]

# Config & Credentials paths
ANTIGRAVITY_CONFIG_DIR = effective_config_dir()
ANTIGRAVITY_CREDENTIALS = ANTIGRAVITY_CONFIG_DIR / 'oauth_creds.json'

# Aliases for backward-compatibility with callers
CLAUDE_CONFIG_DIR = ANTIGRAVITY_CONFIG_DIR
CLAUDE_CREDENTIALS = ANTIGRAVITY_CREDENTIALS

# OAuth Client ID & Secret for Gemini / Antigravity CLI (configurable via env or credentials file)
OAUTH_CLIENT_ID = os.environ.get('ANTIGRAVITY_CLIENT_ID', '')
OAUTH_CLIENT_SECRET = os.environ.get('ANTIGRAVITY_CLIENT_SECRET', '')
GOOGLE_OAUTH_TOKEN_URL = 'https://oauth2.googleapis.com/token'

# Cloud Code / Antigravity endpoints
API_URL_USAGE = 'https://cloudcode-pa.googleapis.com/v1internal:retrieveUserQuota'
API_URL_PROFILE = 'https://cloudcode-pa.googleapis.com/v1internal:loadCodeAssist'
API_URL_PREPAID_CREDITS = ''

_agy_quota_cache: dict[str, Any] = {'time': 0.0, 'data': {}}


def _read_credentials_file() -> dict[str, Any] | None:
    """Read the OAuth credentials JSON from ~/.gemini/oauth_creds.json."""
    if not ANTIGRAVITY_CREDENTIALS.exists():
        return None
    try:
        content = ANTIGRAVITY_CREDENTIALS.read_text(encoding='utf-8').strip()
        if not content:
            return None
        return json.loads(content)
    except Exception as exc:
        log.warning('Could not read credentials file: %s', exc)
        return None


def refresh_google_oauth_token() -> bool:
    """Refresh the Google OAuth access token using the refresh_token.

    Returns True if successfully refreshed and credentials file was updated."""
    creds = _read_credentials_file() or {}

    refresh_token_val = creds.get('refresh_token')
    client_id = creds.get('client_id') or OAUTH_CLIENT_ID or os.environ.get('ANTIGRAVITY_CLIENT_ID', '')
    client_secret = creds.get('client_secret') or OAUTH_CLIENT_SECRET or os.environ.get('ANTIGRAVITY_CLIENT_SECRET', '')

    # Try creds first if client_id and client_secret are provided
    if client_id and client_secret and refresh_token_val:
        try:
            payload = {
                'client_id': client_id,
                'client_secret': client_secret,
                'refresh_token': refresh_token_val,
                'grant_type': 'refresh_token',
            }
            resp = requests.post(GOOGLE_OAUTH_TOKEN_URL, data=payload, timeout=10)
            if resp.status_code == 200:
                token_data = resp.json()
                new_access_token = token_data.get('access_token')
                expires_in = token_data.get('expires_in', 3600)
                id_token = token_data.get('id_token')
                if new_access_token:
                    creds['access_token'] = new_access_token
                    creds['token'] = new_access_token
                    creds['expiry'] = int(time.time()) + int(expires_in)
                    if id_token:
                        creds['id_token'] = id_token
                    ANTIGRAVITY_CREDENTIALS.write_text(json.dumps(creds, indent=2), encoding='utf-8')
                    log.info('Successfully refreshed Antigravity Google OAuth token')
                    return True
        except Exception as exc:
            log.debug('Google OAuth token refresh via creds failed: %s', exc)

    # Fallback to antigravity-acp token configuration if available
    acp_file = ANTIGRAVITY_CONFIG_DIR / 'antigravity-acp' / 'acp_token.json'
    if acp_file.exists():
        try:
            acp_data = json.loads(acp_file.read_text(encoding='utf-8').strip())
            c_id = acp_data.get('client_id')
            c_sec = acp_data.get('client_secret')
            r_tok = acp_data.get('refresh_token')
            t_uri = acp_data.get('token_uri') or GOOGLE_OAUTH_TOKEN_URL
            if c_id and c_sec and r_tok:
                resp = requests.post(
                    t_uri,
                    data={
                        'client_id': c_id,
                        'client_secret': c_sec,
                        'refresh_token': r_tok,
                        'grant_type': 'refresh_token',
                    },
                    timeout=10,
                )
                if resp.status_code == 200:
                    token_data = resp.json()
                    new_access_token = token_data.get('access_token')
                    expires_in = token_data.get('expires_in', 3600)
                    id_token = token_data.get('id_token')
                    if new_access_token:
                        creds['access_token'] = new_access_token
                        creds['token'] = new_access_token
                        creds['expiry'] = int(time.time()) + int(expires_in)
                        if id_token:
                            creds['id_token'] = id_token
                        ANTIGRAVITY_CREDENTIALS.write_text(json.dumps(creds, indent=2), encoding='utf-8')
                        log.info('Successfully refreshed Antigravity Google OAuth token via ACP credentials')
                        return True
        except Exception as exc:
            log.debug('Google OAuth token refresh via ACP failed: %s', exc)

    return False


def read_access_token() -> str | None:
    """Read the Google OAuth access token from ~/.gemini/oauth_creds.json.

    Automatically refreshes if expired."""
    creds = _read_credentials_file()
    if not creds:
        # Check ACP token as fallback
        acp_file = ANTIGRAVITY_CONFIG_DIR / 'antigravity-acp' / 'acp_token.json'
        if acp_file.exists():
            refresh_google_oauth_token()
            creds = _read_credentials_file()
        if not creds:
            return None

    expiry = creds.get('expiry')
    if not expiry and creds.get('expiry_date'):
        expiry = int(creds['expiry_date']) // 1000

    if expiry and isinstance(expiry, (int, float)):
        # If expired or expiring within 60 seconds, refresh
        if time.time() > (expiry - 60):
            if refresh_google_oauth_token():
                creds = _read_credentials_file() or {}

    token = creds.get('access_token') or creds.get('token')
    return token if isinstance(token, str) and token.strip() else None


def api_headers() -> dict[str, str]:
    """Return standard headers for API calls using Antigravity OAuth bearer token."""
    token = read_access_token()
    if not token:
        return {}

    return {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
        'Content-Type': 'application/json',
        'User-Agent': 'antigravity-monitor/1.0',
    }


def fetch_profile() -> dict[str, Any] | None:
    """Extract user profile information from loadCodeAssist or id_token."""
    token = read_access_token()
    email = None
    plan = 'Google AI Pro'

    # Try fast loadCodeAssist for exact plan name
    if token:
        try:
            req = requests.post(
                API_URL_PROFILE,
                headers={
                    'Authorization': f'Bearer {token}',
                    'Content-Type': 'application/json',
                    'User-Agent': 'Antigravity/1.2.13',
                },
                json={},
                timeout=5,
            )
            if req.status_code == 200:
                data = req.json()
                paid = data.get('paidTier') or {}
                curr = data.get('currentTier') or {}
                plan = paid.get('name') or curr.get('name') or plan
        except Exception:
            pass

    # Extract email from id_token
    creds = _read_credentials_file()
    if creds:
        id_token = creds.get('id_token')
        if id_token and isinstance(id_token, str):
            try:
                parts = id_token.split('.')
                if len(parts) >= 2:
                    payload_str = parts[1] + '=' * (-len(parts[1]) % 4)
                    jwt_data = json.loads(base64.urlsafe_b64decode(payload_str))
                    email = jwt_data.get('email')
            except Exception:
                pass

    if not email:
        accounts_file = ANTIGRAVITY_CONFIG_DIR / 'google_accounts.json'
        if accounts_file.exists():
            try:
                acc_data = json.loads(accounts_file.read_text(encoding='utf-8'))
                email = acc_data.get('active')
            except Exception:
                pass

    if not email and not token and not creds:
        return None

    email = email or 'Google User'
    return {
        'email': email,
        'display_name': email,
        'name': email,
        'account': {
            'email': email,
        },
        'organization': {
            'name': 'Google Antigravity',
            'organization_type': plan,
            'uuid': None,
        },
        'tier': plan,
    }


def fetch_prepaid_credits(org_uuid: Any) -> dict[str, Any] | None:
    """Antigravity does not use Anthropic prepaid credits."""
    return None


def _fetch_agy_cli_quota(force: bool = False) -> dict[str, Any] | None:
    """Deprecated: agy CLI prompt execution is not a quota endpoint.

    Running ``agy -p /quota`` triggers non-interactive agent turns, which
    spawns browser OAuth authorization popups when the CLI agent session is unauthenticated,
    and starts background MCP child processes. Live quota is resolved cleanly
    via local Antigravity Language Server RPC or SQLite telemetry tracking.
    """
    return None


def _find_listening_ports() -> list[int]:
    """Find local TCP ports listening on 127.0.0.1 on Windows, prioritizing Antigravity IDE/LSP."""
    if sys.platform == 'win32':
        try:
            import ctypes
            import ctypes.wintypes
            import socket

            iphlpapi = ctypes.windll.iphlpapi
            kernel32 = ctypes.windll.kernel32
            AF_INET = 2
            TCP_TABLE_OWNER_PID_ALL = 5
            MIB_TCP_STATE_LISTEN = 2

            class MIB_TCPROW_OWNER_PID(ctypes.Structure):
                _fields_ = [
                    ('dwState', ctypes.wintypes.DWORD),
                    ('dwLocalAddr', ctypes.wintypes.DWORD),
                    ('dwLocalPort', ctypes.wintypes.DWORD),
                    ('dwRemoteAddr', ctypes.wintypes.DWORD),
                    ('dwRemotePort', ctypes.wintypes.DWORD),
                    ('dwOwningPid', ctypes.wintypes.DWORD),
                ]

            size = ctypes.wintypes.DWORD(0)
            iphlpapi.GetExtendedTcpTable(None, ctypes.byref(size), True, AF_INET, TCP_TABLE_OWNER_PID_ALL, 0)
            buf = (ctypes.c_byte * size.value)()
            if iphlpapi.GetExtendedTcpTable(buf, ctypes.byref(size), True, AF_INET, TCP_TABLE_OWNER_PID_ALL, 0) == 0:
                num_entries = ctypes.cast(buf, ctypes.POINTER(ctypes.wintypes.DWORD)).contents.value
                row_size = ctypes.sizeof(MIB_TCPROW_OWNER_PID)
                offset = ctypes.sizeof(ctypes.wintypes.DWORD)
                candidate_ports: list[int] = []
                other_ports: list[int] = []
                for i in range(num_entries):
                    row = MIB_TCPROW_OWNER_PID.from_buffer(buf, offset + i * row_size)
                    if row.dwState == MIB_TCP_STATE_LISTEN:
                        if row.dwLocalAddr in (0, 0x0100007F):
                            port = socket.ntohs(row.dwLocalPort & 0xFFFF)
                            pid = row.dwOwningPid
                            h = kernel32.OpenProcess(0x1000, False, pid)  # PROCESS_QUERY_LIMITED_INFORMATION
                            name = ''
                            if h:
                                buf_name = ctypes.create_unicode_buffer(1024)
                                sz = ctypes.wintypes.DWORD(1024)
                                if kernel32.QueryFullProcessImageNameW(h, 0, buf_name, ctypes.byref(sz)):
                                    name = buf_name.value.lower()
                                kernel32.CloseHandle(h)
                            if any(k in name for k in ('antigravity', 'language_server', 'code', 'cursor', 'windsurf', 'zed')):
                                candidate_ports.append(port)
                            else:
                                other_ports.append(port)
                return candidate_ports if candidate_ports else other_ports
        except Exception as exc:
            log.debug('GetExtendedTcpTable failed, falling back to netstat: %s', exc)

    try:
        system_root = os.environ.get('SystemRoot') or os.environ.get('WINDIR') or r'C:\Windows'
        netstat_path = os.path.join(system_root, 'System32', 'netstat.exe')
        bin_to_run = netstat_path if os.path.exists(netstat_path) else 'netstat'

        out = subprocess.check_output(
            [bin_to_run, '-ano', '-p', 'tcp'],
            stdin=subprocess.DEVNULL,
            shell=False,
            text=True,
            errors='ignore',
            **no_window_kwargs(),
        )
        ports = set()
        for line in out.splitlines():
            line = line.strip()
            if 'LISTENING' in line and ('127.0.0.1:' in line or '[::1]:' in line):
                parts = line.split()
                if len(parts) >= 2:
                    match = re.search(r':(\d+)\b', parts[1])
                    if match:
                        ports.add(int(match.group(1)))
        return sorted(ports)
    except Exception:
        return []


def _probe_local_antigravity_rpc() -> dict[str, Any] | None:
    """Probe local Antigravity Language Server Connect-RPC endpoints."""
    ports = _find_listening_ports()
    if not ports:
        return None

    payload = {
        'metadata': {
            'ideName': 'antigravity',
            'extensionName': 'antigravity',
            'ideVersion': 'unknown',
            'locale': 'en',
        }
    }
    headers = {
        'Content-Type': 'application/json',
        'Connect-Protocol-Version': '1',
    }
    token = read_access_token()
    if token:
        headers['Authorization'] = f'Bearer {token}'

    # Probe up to 5 prioritized candidate ports
    for port in ports[:5]:
        for scheme in ('http', 'https'):
            url = f'{scheme}://127.0.0.1:{port}/exa.language_server_pb.LanguageServerService/RetrieveUserQuotaSummary'
            try:
                resp = requests.post(url, json=payload, headers=headers, timeout=0.2, verify=False)
                if resp.status_code == 200:
                    data = resp.json()
                    groups = (data.get('response') or {}).get('groups') or []
                    buckets: dict[str, Any] = {}
                    for g in groups:
                        for b in g.get('buckets', []):
                            buckets[b.get('bucketId')] = b

                    if buckets:
                        usage: dict[str, Any] = {}
                        if 'gemini-5h' in buckets:
                            rem = buckets['gemini-5h'].get('remainingFraction', 1.0)
                            usage['gemini_5h'] = {
                                'utilization': round((1.0 - rem) * 100.0, 1),
                                'remaining': round(rem * 100.0, 1),
                                'resets_at': buckets['gemini-5h'].get('resetTime'),
                            }
                            usage['gemini_flash'] = usage['gemini_5h']
                        if 'gemini-weekly' in buckets:
                            rem = buckets['gemini-weekly'].get('remainingFraction', 1.0)
                            usage['gemini_weekly'] = {
                                'utilization': round((1.0 - rem) * 100.0, 1),
                                'remaining': round(rem * 100.0, 1),
                                'resets_at': buckets['gemini-weekly'].get('resetTime'),
                            }
                            usage['gemini_pro'] = usage['gemini_weekly']
                        if '3p-5h' in buckets:
                            rem = buckets['3p-5h'].get('remainingFraction', 1.0)
                            usage['claude_5h'] = {
                                'utilization': round((1.0 - rem) * 100.0, 1),
                                'remaining': round(rem * 100.0, 1),
                                'resets_at': buckets['3p-5h'].get('resetTime'),
                            }
                            usage['claude_session'] = usage['claude_5h']
                        if '3p-weekly' in buckets:
                            rem = buckets['3p-weekly'].get('remainingFraction', 1.0)
                            usage['claude_weekly'] = {
                                'utilization': round((1.0 - rem) * 100.0, 1),
                                'remaining': round(rem * 100.0, 1),
                                'resets_at': buckets['3p-weekly'].get('resetTime'),
                            }
                        if usage:
                            return usage
            except Exception:
                pass

    return None


def _fetch_local_sqlite_telemetry() -> dict[str, Any] | None:
    """Calculate session and activity statistics from local SQLite conversation history."""
    try:
        summary_db = ANTIGRAVITY_CONFIG_DIR / 'antigravity-cli' / 'conversation_summaries.db'
        if not summary_db.exists():
            return None

        conn = sqlite3.connect(summary_db, timeout=2)
        c = conn.cursor()
        c.execute('SELECT COUNT(*), SUM(step_count) FROM conversation_summaries')
        total_convs, total_steps = c.fetchone()
        total_convs = total_convs or 0
        total_steps = total_steps or 0

        # Today's steps
        today_iso = datetime.date.today().isoformat()
        c.execute('SELECT SUM(step_count) FROM conversation_summaries WHERE last_modified_time >= ?', (today_iso,))
        today_steps = c.fetchone()[0] or 0

        # Recent model check
        recent_model = 'gemini-3.8-flash'
        convs_dir = ANTIGRAVITY_CONFIG_DIR / 'antigravity-cli' / 'conversations'
        if convs_dir.exists():
            db_files = sorted(convs_dir.glob('*.db'), key=lambda p: p.stat().st_mtime, reverse=True)
            if db_files:
                try:
                    c2 = sqlite3.connect(db_files[0], timeout=2)
                    cur2 = c2.cursor()
                    cur2.execute('SELECT data FROM gen_metadata ORDER BY idx DESC LIMIT 3')
                    for row in cur2.fetchall():
                        m = re.findall(rb'gemini-[a-zA-Z0-9.-]+|claude-[a-zA-Z0-9.-]+', row[0])
                        if m:
                            recent_model = m[0].decode('utf-8')
                            break
                    c2.close()
                except Exception:
                    pass

        conn.close()

        # Rolling 5-hour reset window
        now = datetime.datetime.now(datetime.timezone.utc)
        reset_time = (now + datetime.timedelta(hours=4)).isoformat()
        weekly_reset = (now + datetime.timedelta(days=6)).isoformat()

        # Normalize utilization
        flash_pct = min(100.0, round((today_steps / 200.0) * 100.0, 1))
        pro_pct = min(100.0, round((today_steps / 50.0) * 100.0, 1))

        return {
            'gemini_5h': {
                'utilization': flash_pct,
                'remaining': round(100.0 - flash_pct, 1),
                'resets_at': reset_time,
                'model_id': recent_model,
            },
            'gemini_weekly': {
                'utilization': pro_pct,
                'remaining': round(100.0 - pro_pct, 1),
                'resets_at': weekly_reset,
                'model_id': 'gemini-3.1-pro',
            },
            'claude_5h': {
                'utilization': 0.0,
                'remaining': 100.0,
                'resets_at': reset_time,
            },
            'claude_weekly': {
                'utilization': 0.0,
                'remaining': 100.0,
                'resets_at': weekly_reset,
            },
            'gemini_flash': {
                'utilization': flash_pct,
                'resets_at': reset_time,
            },
            'gemini_pro': {
                'utilization': pro_pct,
                'resets_at': weekly_reset,
            },
            'session': {
                'utilization': flash_pct,
                'resets_at': reset_time,
                'steps': today_steps,
            },
        }
    except Exception as exc:
        log.debug('Local SQLite telemetry reading failed: %s', exc)
        return None


def fetch_usage() -> dict[str, Any]:
    """Fetch usage data for Antigravity / Gemini & Claude models.

    Multi-tier resolution:
    1. Local Antigravity Language Server Connect RPC (when IDE is running).
    2. Local SQLite telemetry tracking (offline / CLI conversations).
    3. Fallback default active window.
    """
    token = read_access_token()
    if not token and not ANTIGRAVITY_CREDENTIALS.exists():
        return {'error': T.get('no_token', 'No Antigravity credentials found. Sign in via agy.')}

    # Tier 1: Local Antigravity Language Server RPC probe
    local_rpc = _probe_local_antigravity_rpc()
    if local_rpc:
        return local_rpc

    # Tier 2: Local SQLite telemetry tracking
    local_usage = _fetch_local_sqlite_telemetry()
    if local_usage:
        return local_usage

    # Fallback default active window
    now = datetime.datetime.now(datetime.timezone.utc)
    reset_5h = (now + datetime.timedelta(hours=5)).isoformat()
    reset_7d = (now + datetime.timedelta(days=7)).isoformat()
    return {
        'gemini_5h': {
            'utilization': 0.0,
            'remaining': 100.0,
            'resets_at': reset_5h,
        },
        'gemini_weekly': {
            'utilization': 0.0,
            'remaining': 100.0,
            'resets_at': reset_7d,
        },
        'claude_5h': {
            'utilization': 0.0,
            'remaining': 100.0,
            'resets_at': reset_5h,
        },
        'claude_weekly': {
            'utilization': 0.0,
            'remaining': 100.0,
            'resets_at': reset_7d,
        },
        'gemini_flash': {
            'utilization': 0.0,
            'resets_at': reset_5h,
        },
        'gemini_pro': {
            'utilization': 0.0,
            'resets_at': reset_7d,
        },
    }
