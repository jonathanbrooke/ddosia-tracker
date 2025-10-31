import os
import re
import json
import time
import hashlib
import logging
from pathlib import Path
from datetime import datetime, timezone
import psycopg2
import psycopg2.extras

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("processor")

# DB connection from env
DB_DSN = os.getenv("DATABASE_URL") or os.getenv("DB_DSN") or "postgresql://postgres:postgres@postgres:5432/ddosia"

DOWNLOAD_DIR = Path(os.getenv("DOWNLOAD_DIR", "/app/data/downloads"))  # keep for compatibility
PENDING_DIR = DOWNLOAD_DIR.parent / "pending"
PROCESSED_DIR = DOWNLOAD_DIR.parent / "processed"

# regex to capture timestamp at filename start
TS_RE = re.compile(r'^(?P<ts>(?:\d{2}-\d{2}-\d{4}_\d{2}-\d{2}-\d{2})|(?:\d{4}-\d{2}-\d{2}_\d{2}-\d{2}-\d{2}))')

def parse_timestamp_from_filename(name: str):
    m = TS_RE.match(name)
    if not m:
        return None
    ts = m.group("ts")
    for fmt in ("%d-%m-%Y_%H-%M-%S", "%Y-%m-%d_%H-%M-%S"):
        try:
            # return timezone-aware UTC timestamp
            dt = datetime.strptime(ts, fmt)
            return dt.replace(tzinfo=timezone.utc)
        except Exception:
            continue
    return None

def sha256(path: Path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(64*1024), b""):
            h.update(chunk)
    return h.hexdigest()


def normalize_hostname(hostname: str) -> str:
    """
    Normalize hostname for deduplication:
    - Convert to lowercase
    - Remove 'www.' prefix
    - Strip whitespace
    """
    if not hostname:
        return None
    normalized = hostname.strip().lower()
    if not normalized:  # After stripping, check if empty
        return None
    if normalized.startswith('www.'):
        normalized = normalized[4:]  # Remove 'www.'
    return normalized if normalized else None


def connect():
    return psycopg2.connect(DB_DSN, cursor_factory=psycopg2.extras.RealDictCursor)

def _validate_records(records, expected_len, name):
    bad = [r for r in records if not isinstance(r, (list, tuple)) or len(r) != expected_len]
    if bad:
        logger.error("Skipping %d malformed %s records (expected %d values each). Example: %r", len(bad), name, expected_len, bad[:2])
    good = [r for r in records if isinstance(r, (list, tuple)) and len(r) == expected_len]
    return good

def process_file(conn, filepath: Path):
    filename = filepath.name
    logger.info("Processing %s", filename)
    ts = parse_timestamp_from_filename(filename)
    file_sha = sha256(filepath)
    size = filepath.stat().st_size

    with conn.cursor() as cur:
        # idempotent insert/update for files table
        cur.execute("""
            INSERT INTO files (filename, fetched_at, sha256, size_bytes, processed_at)
            VALUES (%s, %s, %s, %s, NOW())
            ON CONFLICT (filename) DO UPDATE
              SET sha256 = EXCLUDED.sha256,
                  size_bytes = EXCLUDED.size_bytes,
                  fetched_at = COALESCE(files.fetched_at, EXCLUDED.fetched_at),
                  processed_at = NOW()
            RETURNING id
        """, (filename, ts, file_sha, size))
        row = cur.fetchone()
        file_id = row['id']

        # If the file was already processed and hashes match, skip reprocessing targets/randoms
        cur.execute("SELECT sha256, size_bytes FROM files WHERE id = %s", (file_id,))
        existing = cur.fetchone()
        if existing and existing['sha256'] == file_sha and existing['size_bytes'] == size:
            cur.execute("SELECT 1 FROM targets WHERE file_id = %s LIMIT 1", (file_id,))
            if cur.fetchone():
                logger.info("File %s already ingested, skipping", filename)
                conn.commit()  # persist the files row update from above
                return

    # load JSON (outside transaction to avoid long locks)
    try:
        with open(filepath, "r", encoding="utf-8") as fh:
            data = json.load(fh)
    except Exception as e:
        logger.error("Failed to parse JSON %s: %s", filepath, e)
        return

    randoms = data.get("randoms", []) or []
    targets = data.get("targets", []) or []

    # perform inserts and commit explicitly (avoid nested conn context)
    try:
        with conn.cursor() as cur:
            if randoms:
                records = []
                for r in randoms:
                    records.append((
                        file_id,
                        r.get("name"),
                        r.get("id"),
                        bool(r.get("digit")) if r.get("digit") is not None else None,
                        bool(r.get("upper")) if r.get("upper") is not None else None,
                        bool(r.get("lower")) if r.get("lower") is not None else None,
                        r.get("min"),
                        r.get("max"),
                    ))
                records = _validate_records(records, 8, "randoms")
                if records:
                    psycopg2.extras.execute_batch(cur,
                        """
                        INSERT INTO randoms (file_id, name, remote_id, digit, upper, lower, min_value, max_value)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        records, page_size=200
                    )
                    logger.info("Inserted %d randoms for %s", len(records), filename)

            if targets:
                # Deduplicate targets by normalized_host within this file
                seen_hosts = set()
                t_records = []
                duplicates_skipped = 0
                
                for t in targets:
                    host = t.get("host")
                    normalized = normalize_hostname(host)
                    
                    # Skip targets with no valid hostname
                    if not normalized:
                        continue
                    
                    # Skip if we've already seen this normalized host in this file
                    if normalized in seen_hosts:
                        duplicates_skipped += 1
                        continue
                    
                    seen_hosts.add(normalized)
                    
                    ip = t.get("ip")
                    ip_val = ip if ip else None
                    t_records.append((
                        file_id,
                        t.get("target_id"),
                        t.get("request_id"),
                        host,
                        normalized,
                        ip_val,
                        t.get("type"),
                        t.get("method"),
                        t.get("port"),
                        bool(t.get("use_ssl")) if t.get("use_ssl") is not None else None,
                        t.get("path"),
                        psycopg2.extras.Json(t.get("body")) if t.get("body") is not None else None,
                        psycopg2.extras.Json(t.get("headers")) if t.get("headers") is not None else None
                    ))
                
                t_records = _validate_records(t_records, 13, "targets")
                if t_records:
                    psycopg2.extras.execute_batch(cur,
                        """
                        INSERT INTO targets
                        (file_id,target_id,request_id,host,normalized_host,ip,type,method,port,use_ssl,path,body,headers)
                        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                        """,
                        t_records, page_size=200
                    )
                    logger.info("Inserted %d targets for %s (%d duplicates skipped)", 
                                len(t_records), filename, duplicates_skipped)

        conn.commit()
    except Exception:
        conn.rollback()
        logger.exception("Failed inserting records for %s", filename)
        raise

def main_loop(poll_interval=None):
    if poll_interval is None:
        poll_interval = int(os.getenv("PROCESSOR_POLL_INTERVAL", "10"))
    error_retry_delay = int(os.getenv("PROCESSOR_ERROR_RETRY_DELAY", "30"))
    
    logger.info("Starting processor; pending=%s", PENDING_DIR)
    PENDING_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    while True:
        try:
            with connect() as conn:
                files = sorted(PENDING_DIR.glob("*.json"))
                for f in files:
                    # skip "last.json" — it's typically a duplicate of the most recent timestamped file
                    if f.name.lower() == "last.json":
                        logger.info("Skipping last.json and moving to processed: %s", f.name)
                        try:
                            PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
                            f.replace(PROCESSED_DIR / f.name)
                        except Exception:
                            logger.exception("Failed to move last.json to processed: %s", f)
                        continue

                    try:
                        process_file(conn, f)
                        # move to processed after success
                        target = PROCESSED_DIR / f.name
                        try:
                            target.parent.mkdir(parents=True, exist_ok=True)
                            f.replace(target)
                        except Exception:
                            logger.exception("Failed to move %s to processed", f)
                    except Exception:
                        logger.exception("Processing failed for %s", f)
            time.sleep(poll_interval)
        except Exception:
            logger.exception("Main loop error, sleeping %ds", error_retry_delay)
            time.sleep(error_retry_delay)


if __name__ == "__main__":
    main_loop()
