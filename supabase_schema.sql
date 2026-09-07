-- ═══════════════════════════════════════════════════════════
-- OpusMusicApi — Supabase schema (users / tokens / request_logs)
-- Run this once in your Supabase project's SQL Editor
-- (Dashboard → SQL Editor → New query → paste → Run)
-- ═══════════════════════════════════════════════════════════

-- Telegram users who have generated a token
CREATE TABLE IF NOT EXISTS users (
    id              BIGSERIAL PRIMARY KEY,
    telegram_id     BIGINT UNIQUE NOT NULL,
    telegram_username TEXT,
    joined_channels BOOLEAN NOT NULL DEFAULT FALSE,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- API tokens — one row per token. A user can have multiple tokens
-- over time (old ones expire/get revoked, new ones get generated).
CREATE TABLE IF NOT EXISTS tokens (
    id              BIGSERIAL PRIMARY KEY,
    token           TEXT UNIQUE NOT NULL,
    telegram_id     BIGINT NOT NULL REFERENCES users(telegram_id),
    status          TEXT NOT NULL DEFAULT 'active',   -- active | revoked | blocked | expired
    request_count   INTEGER NOT NULL DEFAULT 0,
    request_limit   INTEGER NOT NULL DEFAULT 200,
    is_unlimited    BOOLEAN NOT NULL DEFAULT FALSE,    -- true only for admin-generated tokens
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    expires_at      TIMESTAMPTZ NOT NULL,
    revoked_at      TIMESTAMPTZ
);

CREATE INDEX IF NOT EXISTS idx_tokens_token ON tokens(token);
CREATE INDEX IF NOT EXISTS idx_tokens_telegram_id ON tokens(telegram_id);

-- One row per API request — powers the admin panel's usage view.
CREATE TABLE IF NOT EXISTS request_logs (
    id              BIGSERIAL PRIMARY KEY,
    token           TEXT NOT NULL,
    telegram_id     BIGINT,
    endpoint        TEXT NOT NULL,       -- e.g. "/stream", "/download"
    video_id        TEXT,
    status          TEXT,                -- "success" | "error"
    created_at      TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_request_logs_token ON request_logs(token);
CREATE INDEX IF NOT EXISTS idx_request_logs_created_at ON request_logs(created_at);
