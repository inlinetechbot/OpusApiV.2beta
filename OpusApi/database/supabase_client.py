"""
database/supabase_client.py — Users, tokens, and request-logs, backed
by Supabase (Postgres).

Every function here checks config.SUPABASE_URL/SUPABASE_KEY first and
returns a safe "not configured" result if they're unset — so the rest
of the app works fine even before the Supabase project exists. Once
those env vars are filled in, everything activates automatically; no
code change needed.
"""

import time
import uuid
import datetime
from supabase import create_client, Client

from OpusApi import config

_client: Client | None = None
_client_checked = False


def get_client() -> Client | None:
    """Lazily create the Supabase client. Returns None if not configured."""
    global _client, _client_checked
    if _client_checked:
        return _client
    _client_checked = True
    if config.SUPABASE_URL and config.SUPABASE_KEY:
        _client = create_client(config.SUPABASE_URL, config.SUPABASE_KEY)
    return _client


def is_configured() -> bool:
    return get_client() is not None


# ── Users ─────────────────────────────────────────────────────

async def upsert_user(telegram_id: int, telegram_username: str | None, joined_channels: bool) -> None:
    client = get_client()
    if not client:
        return
    client.table("users").upsert({
        "telegram_id": telegram_id,
        "telegram_username": telegram_username,
        "joined_channels": joined_channels,
    }, on_conflict="telegram_id").execute()


async def get_user(telegram_id: int) -> dict | None:
    client = get_client()
    if not client:
        return None
    result = client.table("users").select("*").eq("telegram_id", telegram_id).limit(1).execute()
    return result.data[0] if result.data else None


# ── Tokens ────────────────────────────────────────────────────

def _new_token_string() -> str:
    return f"OpusUser{uuid.uuid4().hex}"


async def create_token(telegram_id: int, unlimited: bool = False) -> dict | None:
    """Create a new token for a user. Returns the created row, or None
    if Supabase isn't configured."""
    client = get_client()
    if not client:
        return None

    now = datetime.datetime.now(datetime.timezone.utc)
    expires_at = now + datetime.timedelta(days=config.TOKEN_EXPIRY_DAYS)
    token_str = _new_token_string()

    row = {
        "token": token_str,
        "telegram_id": telegram_id,
        "status": "active",
        "request_count": 0,
        "request_limit": config.TOKEN_REQUEST_LIMIT,
        "is_unlimited": unlimited,
        "expires_at": expires_at.isoformat(),
    }
    result = client.table("tokens").insert(row).execute()
    return result.data[0] if result.data else None


async def get_token(token: str) -> dict | None:
    client = get_client()
    if not client:
        return None
    result = client.table("tokens").select("*").eq("token", token).limit(1).execute()
    return result.data[0] if result.data else None


async def get_tokens_for_user(telegram_id: int) -> list[dict]:
    client = get_client()
    if not client:
        return []
    result = client.table("tokens").select("*").eq("telegram_id", telegram_id).order("created_at", desc=True).execute()
    return result.data or []


async def revoke_token(token: str) -> bool:
    client = get_client()
    if not client:
        return False
    now = datetime.datetime.now(datetime.timezone.utc).isoformat()
    result = client.table("tokens").update({
        "status": "revoked",
        "revoked_at": now,
    }).eq("token", token).execute()
    return bool(result.data)


async def set_token_status(token: str, status: str) -> bool:
    """status: 'active' | 'blocked' | 'revoked' — used by the admin panel."""
    client = get_client()
    if not client:
        return False
    result = client.table("tokens").update({"status": status}).eq("token", token).execute()
    return bool(result.data)


async def increment_request_count(token: str) -> None:
    client = get_client()
    if not client:
        return
    # Supabase's python client doesn't support atomic increment directly
    # via .update(), so read-then-write. Request volume per single
    # token is low enough that the race window here is not a concern.
    row = await get_token(token)
    if not row:
        return
    client.table("tokens").update({
        "request_count": row["request_count"] + 1
    }).eq("token", token).execute()


async def list_all_tokens() -> list[dict]:
    """Used by the admin panel."""
    client = get_client()
    if not client:
        return []
    result = client.table("tokens").select("*").order("created_at", desc=True).execute()
    return result.data or []


# ── Request logs ──────────────────────────────────────────────

async def log_request(token: str, telegram_id: int | None, endpoint: str, video_id: str | None, status: str) -> None:
    client = get_client()
    if not client:
        return
    client.table("request_logs").insert({
        "token": token,
        "telegram_id": telegram_id,
        "endpoint": endpoint,
        "video_id": video_id,
        "status": status,
    }).execute()


async def get_request_logs(limit: int = 100) -> list[dict]:
    """Used by the admin panel."""
    client = get_client()
    if not client:
        return []
    result = client.table("request_logs").select("*").order("created_at", desc=True).limit(limit).execute()
    return result.data or []


async def get_request_count_last_24h() -> int:
    client = get_client()
    if not client:
        return 0
    cutoff = (datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)).isoformat()
    result = client.table("request_logs").select("id", count="exact").gte("created_at", cutoff).execute()
    return result.count or 0
