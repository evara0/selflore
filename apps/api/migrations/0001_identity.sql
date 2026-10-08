CREATE TABLE app.schema_migrations (
    version text PRIMARY KEY,
    checksum_sha256 char(64) NOT NULL CHECK (checksum_sha256 ~ '^[0-9a-f]{64}$'),
    applied_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.users (
    id uuid PRIMARY KEY,
    username varchar(32) NOT NULL UNIQUE
        CHECK (username ~ '^[a-z][a-z0-9_-]{2,31}$'),
    password_hash text NOT NULL,
    role text NOT NULL DEFAULT 'member' CHECK (role IN ('member', 'admin')),
    is_active boolean NOT NULL DEFAULT true,
    created_at timestamptz NOT NULL DEFAULT now(),
    updated_at timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE app.auth_sessions (
    id uuid PRIMARY KEY,
    user_id uuid NOT NULL REFERENCES app.users(id),
    token_hash bytea NOT NULL UNIQUE CHECK (octet_length(token_hash) = 32),
    csrf_token text NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now(),
    expires_at timestamptz NOT NULL,
    revoked_at timestamptz,
    CHECK (expires_at > created_at)
);
CREATE INDEX auth_sessions_user_expiry_idx ON app.auth_sessions (user_id, expires_at);
CREATE INDEX auth_sessions_active_idx ON app.auth_sessions (user_id) WHERE revoked_at IS NULL;

CREATE TABLE app.auth_login_throttle (
    bucket_key char(64) PRIMARY KEY CHECK (bucket_key ~ '^[0-9a-f]{64}$'),
    failed_count integer NOT NULL DEFAULT 0 CHECK (failed_count >= 0),
    window_started_at timestamptz NOT NULL DEFAULT now(),
    blocked_until timestamptz,
    updated_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX auth_login_throttle_updated_idx ON app.auth_login_throttle (updated_at);

CREATE TABLE app.account_audit (
    id uuid PRIMARY KEY,
    actor_user_id uuid REFERENCES app.users(id),
    target_user_id uuid NOT NULL REFERENCES app.users(id),
    action text NOT NULL CHECK (action IN ('bootstrap', 'created', 'activated', 'deactivated', 'role_changed')),
    role_before text CHECK (role_before IS NULL OR role_before IN ('member', 'admin')),
    role_after text CHECK (role_after IS NULL OR role_after IN ('member', 'admin')),
    is_active_before boolean,
    is_active_after boolean,
    created_at timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX account_audit_target_created_idx ON app.account_audit (target_user_id, created_at);
