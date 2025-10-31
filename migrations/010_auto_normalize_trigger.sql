-- Add database trigger to automatically normalize hosts on insert/update
-- This ensures normalized_host is ALWAYS populated, even if the application code fails

-- Create or replace the trigger function
CREATE OR REPLACE FUNCTION auto_normalize_host()
RETURNS TRIGGER AS $$
BEGIN
    -- If normalized_host is NULL or empty, populate it from host
    IF NEW.normalized_host IS NULL OR NEW.normalized_host = '' THEN
        NEW.normalized_host := normalize_hostname(NEW.host);
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Drop trigger if it exists (idempotent)
DROP TRIGGER IF EXISTS trigger_auto_normalize_host ON targets;

-- Create trigger that fires before INSERT or UPDATE
CREATE TRIGGER trigger_auto_normalize_host
    BEFORE INSERT OR UPDATE ON targets
    FOR EACH ROW
    EXECUTE FUNCTION auto_normalize_host();

-- Backfill any existing NULL or empty normalized_host values
UPDATE targets 
SET normalized_host = normalize_hostname(host)
WHERE normalized_host IS NULL OR normalized_host = '';

COMMENT ON TRIGGER trigger_auto_normalize_host ON targets IS 
'Automatically populates normalized_host from host if NULL or empty';
