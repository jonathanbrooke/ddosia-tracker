-- Create extension and tables for DDoSia files
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

CREATE TABLE IF NOT EXISTS files (
  id              SERIAL PRIMARY KEY,
  filename        TEXT NOT NULL UNIQUE,
  fetched_at      TIMESTAMP WITH TIME ZONE,
  sha256          TEXT,
  size_bytes      BIGINT,
  processed_at    TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS randoms (
  id           BIGSERIAL PRIMARY KEY,
  file_id      INT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  name         TEXT NOT NULL,
  remote_id    TEXT,
  digit        BOOLEAN,
  upper        BOOLEAN,
  lower        BOOLEAN,
  min_value    INT,
  max_value    INT
);

CREATE TABLE IF NOT EXISTS targets (
  id           BIGSERIAL PRIMARY KEY,
  file_id      INT NOT NULL REFERENCES files(id) ON DELETE CASCADE,
  target_id    TEXT,
  request_id   TEXT,
  host         TEXT,
  ip           INET,
  type         TEXT,
  method       TEXT,
  port         INT,
  use_ssl      BOOLEAN,
  path         TEXT,
  body         JSONB,
  headers      JSONB
);

CREATE INDEX IF NOT EXISTS idx_targets_file_request ON targets(file_id, request_id);
CREATE INDEX IF NOT EXISTS idx_randoms_file ON randoms(file_id);