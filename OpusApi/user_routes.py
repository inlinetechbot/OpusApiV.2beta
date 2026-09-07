"""
user_routes.py — User-facing token management endpoints.

    POST /api/token/generate   — create a new token for a Telegram user
    GET  /api/token/list        — list a user's tokens
    POST /api/token/revoke      — revoke one of the user's own tokens

Force-join verification (must join 2 Telegram channels before a token
can be generated) is checked here but the actual Telegram-API
membership check is wired up in a later step — until then,
joined_channels is accepted as given by the caller. This keeps the
endpoint shape stable so the landing page can be built against it now.
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from OpusApi import config
from OpusApi.database import supabase_client

router = APIRouter(prefix="/api/token", tags=["tokens"])


class GenerateTokenRequest(BaseModel):
    telegram_id: int
    telegram_username: str | None = None
    joined_channels: bool = False  # real check added in the force-join step


class RevokeTokenRequest(BaseModel):
    telegram_id: int
    token: str


class AdminGenerateUnlimitedRequest(BaseModel):
    admin_key: str
    label: str | None = None  # optional note, e.g. "for MyBot"


def _require_supabase():
    if not supabase_client.is_configured():
        raise HTTPException(
            status_code=503,
            detail="Token system not yet configured — SUPABASE_URL/SUPABASE_KEY missing.",
        )


def _require_admin(admin_key: str):
    if not config.ADMIN_KEY or admin_key != config.ADMIN_KEY:
        raise HTTPException(status_code=403, detail="Invalid admin key")


@router.post("/generate")
async def generate_user_token(body: GenerateTokenRequest):
    _require_supabase()

    if not body.joined_channels:
        raise HTTPException(
            status_code=403,
            detail=(
                "Please join both required channels before generating a token: "
                f"@{config.FORCE_JOIN_CHANNEL_1 or '(channel 1 not set)'} and "
                f"@{config.FORCE_JOIN_CHANNEL_2 or '(channel 2 not set)'}"
            ),
        )

    await supabase_client.upsert_user(body.telegram_id, body.telegram_username, True)

    token_row = await supabase_client.create_token(body.telegram_id)
    if not token_row:
        raise HTTPException(status_code=500, detail="Failed to create token")

    return {
        "status": "success",
        "token": token_row["token"],
        "expires_at": token_row["expires_at"],
        "request_limit": token_row["request_limit"],
        "base_url": config.BASE_URL,
        "usage": f"{config.BASE_URL}/stream/{{video_id}}?type=audio&token={token_row['token']}",
    }


@router.get("/list")
async def list_user_tokens(telegram_id: int):
    _require_supabase()
    tokens = await supabase_client.get_tokens_for_user(telegram_id)
    return {"status": "success", "tokens": tokens}


@router.post("/revoke")
async def revoke_user_token(body: RevokeTokenRequest):
    _require_supabase()

    token_row = await supabase_client.get_token(body.token)
    if not token_row:
        raise HTTPException(status_code=404, detail="Token not found")
    if token_row["telegram_id"] != body.telegram_id:
        raise HTTPException(status_code=403, detail="This token doesn't belong to you")

    ok = await supabase_client.revoke_token(body.token)
    if not ok:
        raise HTTPException(status_code=500, detail="Failed to revoke token")

    return {"status": "success", "message": "Token revoked"}


@router.post("/admin/generate-unlimited")
async def admin_generate_unlimited_token(body: AdminGenerateUnlimitedRequest):
    """Admin-only: create a token with no expiry and no request limit.
    Not tied to a real Telegram user — uses telegram_id=0 as a
    reserved marker for admin-issued tokens."""
    _require_admin(body.admin_key)
    _require_supabase()

    ADMIN_MARKER_ID = 0
    await supabase_client.upsert_user(ADMIN_MARKER_ID, body.label or "admin-issued", True)

    token_row = await supabase_client.create_token(ADMIN_MARKER_ID, unlimited=True)
    if not token_row:
        raise HTTPException(status_code=500, detail="Failed to create token")

    return {
        "status": "success",
        "token": token_row["token"],
        "unlimited": True,
        "label": body.label,
    }
