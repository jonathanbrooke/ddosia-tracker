"""
GDELT worker:
- Fetches geopolitical events from GDELT API for dates with DDoSia data
- Processes one date at a time to respect API rate limits
- Filters for English language articles
- Stores up to 5 key events per day
Run on a schedule; idempotent.
"""
import os
import time
import logging
import psycopg2
import psycopg2.extras
import requests

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("gdelt-worker")

DB_DSN = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/ddosia"
)


def get_conn():
    return psycopg2.connect(
        DB_DSN,
        cursor_factory=psycopg2.extras.RealDictCursor
    )


def fetch_gdelt_events(conn):
    """
    Fetch GDELT events for dates where we have DDoSia data but no GDELT events.
    Strategy:
    1. First tries to fill recent dates (last 30 days)
    2. Then fills one older historical date per run
    3. Marks dates as processed even if no English events found
    """
    # Check if we have any processed marker
    with conn.cursor() as cur:
        # Create a simple table to track which dates we've attempted
        cur.execute("""
            CREATE TABLE IF NOT EXISTS gdelt_processed_dates (
                process_date DATE PRIMARY KEY,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                events_found INTEGER DEFAULT 0
            )
        """)
    
    # Find dates where we have DDoSia files but haven't processed GDELT yet
    with conn.cursor() as cur:
        # First priority: recent dates (last 30 days)
        cur.execute("""
            SELECT DISTINCT DATE(f.fetched_at) as ddos_date
            FROM files f
            WHERE DATE(f.fetched_at) >= CURRENT_DATE - INTERVAL '30 days'
            AND NOT EXISTS (
                SELECT 1 FROM gdelt_processed_dates g
                WHERE g.process_date = DATE(f.fetched_at)
            )
            ORDER BY ddos_date DESC
            LIMIT 1
        """)
        
        result = cur.fetchone()
        is_recent = True
        
        # If no recent dates, get one older historical date
        if not result:
            cur.execute("""
                SELECT DISTINCT DATE(f.fetched_at) as ddos_date
                FROM files f
                WHERE NOT EXISTS (
                    SELECT 1 FROM gdelt_processed_dates g
                    WHERE g.process_date = DATE(f.fetched_at)
                )
                ORDER BY ddos_date DESC
                LIMIT 1
            """)
            result = cur.fetchone()
            is_recent = False
        
        if not result:
            logger.info("All DDoSia dates have been processed for GDELT")
            return
        
        target_date = result['ddos_date']
    
    date_type = "recent" if is_recent else "historical"
    logger.info(f"Fetching GDELT events for {target_date} ({date_type})")
    
    events_found = 0
    
    # Get configuration from environment
    gdelt_query = os.getenv("GDELT_QUERY", "Ukraine war")
    gdelt_timeout = int(os.getenv("GDELT_TIMEOUT", "30"))
    gdelt_languages = os.getenv("GDELT_LANGUAGES", "eng").lower()
    max_events_per_day = int(os.getenv("GDELT_MAX_EVENTS_PER_DAY", "5"))
    
    try:
        url = "https://api.gdeltproject.org/api/v2/doc/doc"
        params = {
            "query": gdelt_query,
            "mode": "artlist",
            "maxrecords": "100",
            "format": "json",
            "startdatetime": target_date.strftime("%Y%m%d") + "000000",
            "enddatetime": target_date.strftime("%Y%m%d") + "235959"
        }
        
        response = requests.get(url, params=params, timeout=gdelt_timeout)
        if response.status_code != 200:
            logger.warning(
                f"GDELT API returned status {response.status_code}"
            )
            # Mark as processed even on error to avoid retry loops
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO gdelt_processed_dates (process_date, events_found)
                    VALUES (%s, 0)
                    ON CONFLICT (process_date) DO NOTHING
                """, (target_date,))
            return
        
        data = response.json()
        articles = data.get("articles", [])
        
        if not articles:
            logger.info(f"No GDELT articles found for {target_date}")
            # Mark as processed
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO gdelt_processed_dates (process_date, events_found)
                    VALUES (%s, 0)
                """, (target_date,))
            return
        
        logger.info(
            f"Retrieved {len(articles)} articles from GDELT "
            f"for {target_date}"
        )
        
        with conn.cursor() as cur:
            inserted = 0
            english_count = 0
            
            for article in articles:
                # Stop if we have enough events
                if inserted >= max_events_per_day:
                    logger.info(
                        f"Reached limit of {max_events_per_day} events "
                        f"for {target_date}"
                    )
                    break
                
                try:
                    seendate = article.get("seendate", "")
                    if len(seendate) < 8:
                        continue
                    
                    # Check if article language is English
                    language = article.get("language", "").lower()
                    title = article.get("title", "")[:200]
                    
                    # Filter by configured languages
                    if gdelt_languages and language != "english":
                        continue
                    
                    english_count += 1
                    evt_date = (
                        f"{seendate[0:4]}-"
                        f"{seendate[4:6]}-"
                        f"{seendate[6:8]}"
                    )
                    domain = article.get("domain", "news")
                    url_link = article.get("url", "")
                    
                    cur.execute("""
                        INSERT INTO events
                        (event_date, title, description, category,
                         severity, source, url)
                        VALUES (%s, %s, %s, 'gdelt', 'medium', 'gdelt', %s)
                        ON CONFLICT (event_date, title, source) DO NOTHING
                    """, (evt_date, title, f"Source: {domain}", url_link))
                    
                    if cur.rowcount > 0:
                        inserted += 1
                        events_found += 1
                        
                except Exception as e:
                    logger.warning(f"Failed to insert GDELT event: {e}")
            
            # Mark date as processed
            cur.execute("""
                INSERT INTO gdelt_processed_dates (process_date, events_found)
                VALUES (%s, %s)
                ON CONFLICT (process_date)
                DO UPDATE SET events_found = EXCLUDED.events_found
            """, (target_date, events_found))
            
            if inserted >= max_events_per_day:
                logger.info(
                    f"✓ Inserted {inserted} GDELT events for {target_date} "
                    f"({english_count} English from {len(articles)} total)"
                )
            elif inserted > 0:
                logger.info(
                    f"⚠ Found {inserted} English events for {target_date} "
                    f"(max {max_events_per_day})"
                )
            else:
                logger.info(
                    f"⚠ No English events found for {target_date} "
                    f"({len(articles)} non-English articles)"
                )
    
    except Exception as e:
        logger.error(f"Error fetching GDELT events: {e}")
        # Mark as processed to avoid infinite retry
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO gdelt_processed_dates (process_date, events_found)
                VALUES (%s, 0)
                ON CONFLICT (process_date) DO NOTHING
            """, (target_date,))


def main():
    logger.info("GDELT worker starting...")
    request_delay = int(os.getenv("GDELT_REQUEST_DELAY", "7"))
    
    conn = get_conn()
    try:
        with conn:
            fetch_gdelt_events(conn)
    except Exception:
        logger.exception("Failed to fetch GDELT events")
        return 1
    finally:
        conn.close()
    
    logger.info("GDELT worker completed successfully")
    logger.info("Waiting %ds before next check", request_delay)
    time.sleep(request_delay)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
