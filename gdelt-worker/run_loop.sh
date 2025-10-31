#!/bin/bash
# GDELT worker loop - runs hourly to fetch news articles
# Limits to 5 articles per day

echo "GDELT worker loop starting..."
INTERVAL_SECONDS=${GDELT_POLL_INTERVAL_SECONDS:-3600}  # Default: 1 hour (3600 seconds)
echo "Will check for new dates every ${INTERVAL_SECONDS}s (hourly)"
echo ""

while true; do
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Running GDELT worker..."
    
    python worker.py
    EXIT_CODE=$?
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✓ Worker completed successfully"
    else
        echo "[$(date '+%Y-%m-%d %H:%M:%S')] ✗ Worker failed with exit code $EXIT_CODE"
    fi
    
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] Sleeping for ${INTERVAL_SECONDS}s..."
    echo ""
    
    sleep ${INTERVAL_SECONDS}
done
