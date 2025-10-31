-- Add a country column to targets (idempotent)
ALTER TABLE IF EXISTS targets
  ADD COLUMN IF NOT EXISTS country TEXT;

-- optional ISO code column for future use
ALTER TABLE IF EXISTS targets
  ADD COLUMN IF NOT EXISTS country_iso TEXT;

-- ensure tld_geo exists (previous migration does this, but safe)
CREATE TABLE IF NOT EXISTS tld_geo (
  tld TEXT PRIMARY KEY,
  country TEXT,
  lat DOUBLE PRECISION,
  lon DOUBLE PRECISION,
  iso2 TEXT
);