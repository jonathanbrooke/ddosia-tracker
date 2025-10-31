-- Add normalized_host column to store deduplicated domain names
ALTER TABLE targets ADD COLUMN IF NOT EXISTS normalized_host TEXT;

-- Create function to normalize hostnames
CREATE OR REPLACE FUNCTION normalize_hostname(hostname TEXT) RETURNS TEXT AS $$
BEGIN
    -- Remove www. prefix, convert to lowercase, trim whitespace
    RETURN LOWER(TRIM(regexp_replace(hostname, '^www\.', '', 'i')));
END;
$$ LANGUAGE plpgsql IMMUTABLE;

-- Populate normalized_host for existing records
UPDATE targets 
SET normalized_host = normalize_hostname(host)
WHERE normalized_host IS NULL;

-- Create index on normalized_host for fast lookups
CREATE INDEX IF NOT EXISTS idx_targets_normalized_host 
ON targets(normalized_host);

-- Create index on file_id + normalized_host for deduplication
CREATE INDEX IF NOT EXISTS idx_targets_file_normalized 
ON targets(file_id, normalized_host);

-- Add comment
COMMENT ON COLUMN targets.normalized_host IS 
'Normalized domain name: lowercase, www. prefix removed, for deduplication';
