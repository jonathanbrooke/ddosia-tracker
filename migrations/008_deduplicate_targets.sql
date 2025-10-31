-- Deduplication Analysis and Cleanup Script
-- Run this to see stats, then execute the DELETE to clean up

-- Step 1: Check current duplicate statistics
\echo '=== DEDUPLICATION ANALYSIS ==='
\echo ''
\echo 'Total targets:'
SELECT COUNT(*) as total_targets FROM targets;

\echo ''
\echo 'Duplicate groups (same normalized_host in same file):'
SELECT COUNT(*) as duplicate_groups
FROM (
    SELECT file_id, normalized_host, COUNT(*) as cnt
    FROM targets
    GROUP BY file_id, normalized_host
    HAVING COUNT(*) > 1
) dups;

\echo ''
\echo 'Total duplicate records to remove:'
SELECT SUM(cnt - 1) as duplicates_to_remove
FROM (
    SELECT file_id, normalized_host, COUNT(*) as cnt
    FROM targets
    GROUP BY file_id, normalized_host
    HAVING COUNT(*) > 1
) dups;

\echo ''
\echo 'Top 20 most duplicated domains:'
SELECT 
    normalized_host,
    COUNT(*) as total_occurrences,
    COUNT(DISTINCT file_id) as files_affected,
    ARRAY_AGG(DISTINCT host ORDER BY host) as variants
FROM targets
GROUP BY normalized_host
HAVING COUNT(*) > 10
ORDER BY total_occurrences DESC
LIMIT 20;

\echo ''
\echo '=== READY TO DEDUPLICATE ==='
\echo 'This will keep the first occurrence (lowest ID) of each domain per file.'
\echo 'Press Ctrl+C to cancel, or continue to execute the DELETE...'
\echo ''

-- Step 2: Actually perform deduplication
-- Keeps the first (lowest ID) occurrence per file+normalized_host
WITH duplicates AS (
    SELECT 
        id,
        file_id,
        normalized_host,
        ROW_NUMBER() OVER (
            PARTITION BY file_id, normalized_host 
            ORDER BY id ASC
        ) as rn
    FROM targets
),
to_delete AS (
    SELECT id 
    FROM duplicates 
    WHERE rn > 1
)
DELETE FROM targets 
WHERE id IN (SELECT id FROM to_delete);

-- Step 3: Show results
\echo ''
\echo '=== DEDUPLICATION COMPLETE ==='
\echo ''
\echo 'Remaining targets:'
SELECT COUNT(*) as total_targets FROM targets;

\echo ''
\echo 'Remaining duplicates (should be 0):'
SELECT COUNT(*) as remaining_duplicates
FROM (
    SELECT file_id, normalized_host, COUNT(*) as cnt
    FROM targets
    GROUP BY file_id, normalized_host
    HAVING COUNT(*) > 1
) dups;

-- Vacuum to reclaim space
VACUUM ANALYZE targets;
\echo ''
\echo '✓ Done! Table vacuumed and analyzed.'
