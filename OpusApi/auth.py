"""
auth.py — Token validation, layered across three sources.

A request's token is checked, in order:
    1. Fixed/permanent tokens from .env (config.FIXED_TOKENS) — for
       your own testing/personal bots. Never expire, no request limit.
    2. Supabase user tokens — regular end users. Each has an expiry
       (config.TOKEN_EXPIRY_DAYS) and a request limit
       (config.TOKEN_REQUEST_LIMIT). Wired up in a later step; until
       the Supabase project exists, check_supabase_token() always
       returns None (not found), so this tier is a safe no-op.
    3. Temporary /download tokens — short-lived (5 min), video_id-bound
       tokens minted by the /download endpoint. Unchanged from before;
       still lives in main.py's TOKENS dict since it's request-scoped,
       not user-scoped.

Returning a small TokenInfo tells the caller what kind of token this
was, so /stream can decide whether to also check the temporary-token
video_id/expiry rules (only relevant for tier 3).
"""

from dataclasses import dataclass
from datetime import datetime, timezone

import aiohttp

from OpusApi import config
from OpusApi.database import supabase_client

# Membership statuses Telegram's getChatMember can return that count
# as "joined". "left" and "kicked" (banned) do not count.
_MEMBER_STATUSES = {"creator", "administrator", "member", "restricted"}


async def _is_member_of_channel(telegram_id: int, channel_username: str) -> bool:
    """Ask Telegram directly whether telegram_id is in channel_username.

    The bot (config.BOT_TOKEN) must be an admin of the channel or this
    call fails with a 400 from Telegram. Returns False on any failure
    (channel not set, bot not admin, user not found, network error,
    etc.) — fail closed, never assume membership.
    """
    if not config.BOT_TOKEN or not channel_username:
        return False

    chat_id = channel_username if channel_username.startswith("@") else f"@{channel_username}"
    url = f"https://api.telegram.org/bot{config.BOT_TOKEN}/getChatMember"

    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params={"chat_id": chat_id, "user_id": telegram_id},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                data = await resp.json()
    except (aiohttp.ClientError, TimeoutError):
        return False

    if not data.get("ok"):
        return False

    status = data.get("result", {}).get("status")
    return status in _MEMBER_STATUSES


async def verify_channels_joined(telegram_id: int) -> tuple[bool, list[str]]:
    """Check real membership in both force-join channels.

    Returns (all_joined, missing_channels) where missing_channels lists
    the @usernames the user still needs to join (empty if all_joined).
    """
    missing: list[str] = []

    for channel in (config.FORCE_JOIN_CHANNEL_1, config.FORCE_JOIN_CHANNEL_2):
        if not channel:
            continue  # channel not configured — nothing to check for this slot
        joined = await _is_member_of_channel(telegram_id, channel)
        if not joined:
            missing.append(channel)

    return (len(missing) == 0, missing)


@dataclass
class TokenInfo:
    kind: str          # "fixed" | "supabase" | "temporary"
    valid: bool
    reason: str = ""    # populated when valid=False, for error messages
    telegram_id: int | None = None


def check_fixed_token(token: str) -> bool:
    """Tier 1: permanent tokens from .env, no expiry/limit."""
    return token in config.FIXED_TOKENS


async def check_supabase_token(token: str) -> TokenInfo | None:
    """Tier 2: Supabase-backed user tokens.

    Returns None if Supabase isn't configured yet, or the token
    doesn't exist there — either way, the caller falls through to the
    next tier. If the token DOES exist in Supabase, this always
    returns a TokenInfo (valid=True/False) — it never falls through
    for a token Supabase actually recognizes, so a blocked/expired
    Supabase token can't accidentally succeed via a later tier.
    """
    if not supabase_client.is_configured():
        return None  # Supabase not set up yet — nothing to check.

    row = await supabase_client.get_token(token)
    if row is None:
        return None  # Not a Supabase token — let the caller check other tiers.

    if row["status"] == "revoked":
        return TokenInfo(kind="supabase", valid=False, reason="Token revoked")
    if row["status"] == "blocked":
        return TokenInfo(kind="supabase", valid=False, reason="Token blocked by admin")

    if not row["is_unlimited"]:
        expires_at = datetime.fromisoformat(row["expires_at"])
        if datetime.now(timezone.utc) > expires_at:
            return TokenInfo(kind="supabase", valid=False, reason="Token expired")

        if row["request_count"] >= row["request_limit"]:
            return TokenInfo(kind="supabase", valid=False, reason="Request limit reached for this token")

    # Valid — bump the usage counter (unlimited tokens are still
    # counted for visibility in the admin panel, just never blocked by it).
    await supabase_client.increment_request_count(token)

    return TokenInfo(kind="supabase", valid=True, telegram_id=row["telegram_id"])


def is_fixed_token(token: str) -> bool:
    """Convenience check used by /stream before falling through to the
    existing temporary-token logic."""
    return bool(token) and check_fixed_token(token)
