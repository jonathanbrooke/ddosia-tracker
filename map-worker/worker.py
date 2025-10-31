"""
Map-updater worker:
- Loads mapping JSON (MAPPING_FILE)
- Upserts into tld_geo
- Updates targets.country and targets.country_iso from tld_geo in a single set-based SQL
- Loads curated geopolitical events into events table
Run once or on a schedule; idempotent.
"""
import os
import json
import logging
import time
from pathlib import Path
import psycopg2
import psycopg2.extras

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s"
)
logger = logging.getLogger("map-updater")

DB_DSN = os.getenv(
    "DATABASE_URL",
    "postgresql://postgres:postgres@postgres:5432/ddosia"
)
MAPPING_FILE = os.getenv(
    "MAPPING_FILE",
    "/app/mappings/tld_to_country.json"
)


def get_conn():
    return psycopg2.connect(
        DB_DSN,
        cursor_factory=psycopg2.extras.RealDictCursor
    )

def load_mapping(path):
    p = Path(path)
    if not p.exists():
        logger.error("Mapping file not found: %s", path)
        return {}
    with p.open("r", encoding="utf-8") as fh:
        return json.load(fh)

def upsert_tld_geo(conn, mapping):
    pairs = []
    for tld, meta in mapping.items():
        country = meta.get("country")
        iso2 = meta.get("iso2")
        pairs.append((tld.lower(), country, iso2))
    if not pairs:
        logger.info("No mappings to upsert")
        return
    with conn.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS tld_geo (tld text PRIMARY KEY, country text, lat double precision, lon double precision, iso2 text);")
        psycopg2.extras.execute_batch(cur,
            """
            INSERT INTO tld_geo (tld, country, iso2)
            VALUES (%s, %s, %s)
            ON CONFLICT (tld) DO UPDATE
              SET country = EXCLUDED.country,
                  iso2 = EXCLUDED.iso2
            """,
            pairs, page_size=200
        )
    logger.info("Upserted %d tld_geo rows", len(pairs))

def apply_mapping_to_targets(conn):
    """
    Use a set-based UPDATE to apply country/iso2 from tld_geo to targets by extracting TLD from host.
    This version overwrites previous values unconditionally for matched rows.
    """
    sql = """
    WITH mapped AS (
      SELECT t.id AS target_id,
             g.country AS new_country,
             g.iso2 AS new_iso2
      FROM targets t
      JOIN files f ON t.file_id = f.id
      JOIN tld_geo g ON lower(regexp_replace(t.host, '.*\\.', '')) = g.tld
      WHERE t.host IS NOT NULL AND t.host <> ''
    )
    UPDATE targets tgt
    SET country = m.new_country,
        country_iso = m.new_iso2
    FROM mapped m
    WHERE tgt.id = m.target_id;
    """
    with conn.cursor() as cur:
        cur.execute(sql)
        updated = cur.rowcount
    logger.info("Updated %d targets with country mapping (overwrite mode)", updated)


def load_curated_events(conn):
    """Load curated events from JSON file into the events table."""
    events_file = Path("/app/mappings/geopolitical_events.json")
    if not events_file.exists():
        logger.warning("Curated events file not found")
        return
    
    try:
        with events_file.open("r", encoding="utf-8") as f:
            data = json.load(f)
        
        events = data.get("events", [])
        if not events:
            logger.info("No curated events to load")
            return
        
        with conn.cursor() as cur:
            inserted = 0
            for evt in events:
                try:
                    cur.execute("""
                        INSERT INTO events 
                        (event_date, title, description, category, severity, source, countries)
                        VALUES (%s, %s, %s, %s, %s, 'curated', %s)
                        ON CONFLICT (event_date, title, source) DO NOTHING
                    """, (
                        evt["date"],
                        evt["title"],
                        evt.get("description", ""),
                        evt.get("category", "political"),
                        evt.get("severity", "medium"),
                        evt.get("countries", [])
                    ))
                    if cur.rowcount > 0:
                        inserted += 1
                except Exception as e:
                    logger.warning(f"Failed to insert curated event: {e}")
        
        logger.info(f"Loaded {inserted} new curated events (total: {len(events)})")
    except Exception as e:
        logger.error(f"Error loading curated events: {e}")


def main():
    poll_interval = int(os.getenv("MAP_UPDATER_POLL_INTERVAL", "300"))
    error_retry_delay = int(os.getenv("MAP_UPDATER_ERROR_RETRY_DELAY", "30"))
    
    mapping = load_mapping(MAPPING_FILE)
    if not mapping:
        logger.error("No mapping loaded; exiting")
        return 1

    # Run continuously with periodic updates
    while True:
        try:
            conn = get_conn()
            try:
                with conn:
                    # Update TLD mappings
                    upsert_tld_geo(conn, mapping)
                    apply_mapping_to_targets(conn)
                    
                    # Load curated events
                    load_curated_events(conn)
            except Exception:
                logger.exception("Failed to update mappings")
            finally:
                conn.close()
            
            logger.info(
                "Map updater cycle completed, sleeping %ds",
                poll_interval
            )
            time.sleep(poll_interval)
        except KeyboardInterrupt:
            logger.info("Shutting down map updater")
            break
        except Exception:
            logger.exception("Unexpected error in main loop")
            time.sleep(error_retry_delay)
    
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
