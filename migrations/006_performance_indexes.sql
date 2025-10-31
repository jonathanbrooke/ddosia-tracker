-- Add performance indexes for commonly queried columns
CREATE INDEX IF NOT EXISTS idx_files_fetched_at ON files(fetched_at);
CREATE INDEX IF NOT EXISTS idx_targets_host ON targets(host);
CREATE INDEX IF NOT EXISTS idx_targets_country ON targets(country);
CREATE INDEX IF NOT EXISTS idx_targets_effective_tld ON targets(effective_tld);
