"""
config.py — Central place for all environment-driven settings.

Everything here is read from .env (via python-dotenv, loaded once at
import time). Nothing in this file should be hardcoded — if a value
needs to change per-deployment, it belongs in .env, not in code.
"""

import os
from dotenv import load_dotenv

load_dotenv()

# ── Server ────────────────────────────────────────────────────
PORT = int(os.environ.get("PORT", 8080))

# Public base URL of this deployment, e.g. https://opusmusicapi-nf2e.onrender.com
# Used for building absolute links (docs, landing page, token endpoints).
# No trailing slash.
BASE_URL = os.environ.get("BASE_URL", "http://localhost:8080").rstrip("/")

# ── Disk cache ────────────────────────────────────────────────
MIN_FREE_MB = int(os.environ.get("MIN_FREE_MB", 500))

# ── Proxy pool (OPTIONAL) ─────────────────────────────────────
# Comma-separated "host:port:user:pass" entries. Leave empty/unset to
# run without any proxy — the app works fine either way. Add this the
# moment YouTube starts blocking the server's IP; no code change needed.
_RAW_PROXIES = [p.strip() for p in os.environ.get("PROXIES", "").split(",") if p.strip()]


def _parse_proxy(raw: str) -> str:
    """Convert 'host:port:user:pass' into a yt-dlp/curl-style proxy URL."""
    host, port, user, pwd = raw.split(":")
    return f"http://{user}:{pwd}@{host}:{port}"


PROXIES = [_parse_proxy(p) for p in _RAW_PROXIES]

# ── Turso (song cache) ───────────────────────────────────────
TURSO_DATABASE_URL = os.environ.get("TURSO_DATABASE_URL")
TURSO_AUTH_TOKEN = os.environ.get("TURSO_AUTH_TOKEN")

# ── Supabase (users / tokens / request logs) ─────────────────
# Filled in later once the Supabase project exists — safe to be None
# until then; the auth/admin modules that need it will check.
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# ── Admin access ──────────────────────────────────────────────
ADMIN_KEY = os.environ.get("ADMIN_KEY")

# ── Fixed/permanent tokens (OPTIONAL) ─────────────────────────
# Comma-separated list of tokens that are always valid, never expire,
# and have no request limit. Meant for your own testing/personal bots —
# not for regular end users (those get Supabase-issued tokens with
# expiry + request limits, added in a later step).
FIXED_TOKENS = [t.strip() for t in os.environ.get("FIXED_TOKENS", "").split(",") if t.strip()]

# ── Token limits (for the upcoming multi-user token system) ──
TOKEN_EXPIRY_DAYS = int(os.environ.get("TOKEN_EXPIRY_DAYS", 28))
TOKEN_REQUEST_LIMIT = int(os.environ.get("TOKEN_REQUEST_LIMIT", 200))

# ── Force-join channels (placeholders — fill in when ready) ──
FORCE_JOIN_CHANNEL_1 = os.environ.get("FORCE_JOIN_CHANNEL_1", "")
FORCE_JOIN_CHANNEL_2 = os.environ.get("FORCE_JOIN_CHANNEL_2", "")

# ── Telegram Bot (used to verify real channel membership) ─────
# This bot MUST be an admin in both FORCE_JOIN_CHANNEL_1 and
# FORCE_JOIN_CHANNEL_2, otherwise getChatMember calls will fail.
BOT_TOKEN = os.environ.get("BOT_TOKEN", "")
