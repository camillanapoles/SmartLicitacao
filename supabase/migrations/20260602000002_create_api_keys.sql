-- Datalake API Self-Service — api_keys table (#1372)
-- Phase 1: Core infrastructure for API key management.
--
-- api_key_hash: SHA-256 hex digest of the plaintext key.
-- The plaintext key is returned ONCE at creation time and never stored.
-- revoked_at: soft-delete. Non-null means the key is revoked.
-- last_used_at: updated on each authenticated request for audit trail.

CREATE TABLE public.api_keys (
    id              UUID         PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id         UUID         NOT NULL REFERENCES profiles(id) ON DELETE CASCADE,
    key_hash        TEXT         NOT NULL UNIQUE,
    name            TEXT         NOT NULL DEFAULT '',
    revoked_at      TIMESTAMPTZ,
    last_used_at    TIMESTAMPTZ,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- Index for user-specific listing (GET /v1/api-keys)
CREATE INDEX idx_api_keys_user_id ON api_keys(user_id);

-- Index for key hash lookup (middleware validation — hot path)
CREATE INDEX idx_api_keys_key_hash ON api_keys(key_hash) WHERE revoked_at IS NULL;

-- RLS: users can only see their own keys
ALTER TABLE public.api_keys ENABLE ROW LEVEL SECURITY;

CREATE POLICY "Users can view own api keys"
    ON public.api_keys FOR SELECT
    USING (auth.uid() = user_id);

CREATE POLICY "Users can insert own api keys"
    ON public.api_keys FOR INSERT
    WITH CHECK (auth.uid() = user_id);

CREATE POLICY "Users can update own api keys"
    ON public.api_keys FOR UPDATE
    USING (auth.uid() = user_id);

-- Note: No DELETE policy — keys are soft-deleted via revoked_at.
-- service_role bypasses RLS for all operations (Supabase default).
