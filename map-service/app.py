import os
import psycopg2
import psycopg2.extras
from datetime import datetime, timezone
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS

app = Flask(__name__, static_folder="static")
CORS(app)

DB_DSN = os.getenv("DATABASE_URL", "postgresql://postgres:postgres@postgres:5432/ddosia")

def get_conn():
    return psycopg2.connect(DB_DSN, cursor_factory=psycopg2.extras.RealDictCursor)

def parse_date(s):
    try:
        return datetime.fromisoformat(s).date()
    except Exception:
        return None

@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")

@app.route("/health")
def health_page():
    return send_from_directory(app.static_folder, "health.html")

@app.route("/api/tld")
def tld_aggregate():
    """
    Query params:
      from=YYYY-MM-DD
      to=YYYY-MM-DD
      min_count=int (optional)
    Returns: [{tld, lat, lon, count}, ...]
    """
    qs_from = request.args.get("from")
    qs_to = request.args.get("to")
    
    try:
        min_count = int(request.args.get("min_count", "0"))
    except ValueError:
        return jsonify({"error": "min_count must be a valid integer"}), 400

    if not qs_from or not qs_to:
        return jsonify({
            "error": "provide from and to parameters in YYYY-MM-DD"
        }), 400

    d_from = parse_date(qs_from)
    d_to = parse_date(qs_to)
    if not d_from or not d_to:
        return jsonify({"error": "invalid date format"}), 400

    # inclusive to the end of d_to day - use UTC timezone to match database
    ts_from = datetime.combine(d_from, datetime.min.time()).replace(tzinfo=timezone.utc)
    ts_to = datetime.combine(d_to, datetime.max.time()).replace(tzinfo=timezone.utc)

    sql = """
    SELECT
      lower(regexp_replace(t.normalized_host, '.*\\.', '')) AS tld,
      COALESCE(g.lat, 0.0) AS lat,
      COALESCE(g.lon, 0.0) AS lon,
      COUNT(*) AS cnt
    FROM targets t
    JOIN files f ON t.file_id = f.id
    LEFT JOIN tld_geo g
      ON lower(regexp_replace(t.normalized_host, '.*\\.', '')) = g.tld
    WHERE f.fetched_at >= %(from)s AND f.fetched_at <= %(to)s
      AND (t.normalized_host IS NOT NULL AND t.normalized_host <> '')
    GROUP BY lower(regexp_replace(t.normalized_host, '.*\\.', '')), g.lat, g.lon
    ORDER BY cnt DESC
    """
    params = {"from": ts_from, "to": ts_to}
    rows = []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    results = []
    for r in rows:
        tld = r["tld"] or "unknown"
        if r["cnt"] < min_count:
            continue
        results.append({"tld": tld, "lat": float(r["lat"]), "lon": float(r["lon"]), "count": int(r["cnt"])})

    return jsonify(results)

@app.route("/api/tld/available-range")
def available_range():
    """Return earliest and latest fetched_at dates to initialize the slider."""
    sql = "SELECT MIN(fetched_at) AS min_ts, MAX(fetched_at) AS max_ts FROM files"
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
                if not row or not row["min_ts"]:
                    return jsonify({"min": None, "max": None})
                return jsonify({
                    "min": row["min_ts"].date().isoformat(),
                    "max": row["max_ts"].date().isoformat()
                })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/last-update")
def last_update():
    """Return the most recent DDoSia file timestamp."""
    sql = """
        SELECT MAX(fetched_at) AS last_update
        FROM files
        WHERE fetched_at IS NOT NULL
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql)
                row = cur.fetchone()
                if not row or not row["last_update"]:
                    return jsonify({"last_update": None})
                return jsonify({
                    "last_update": row["last_update"].isoformat(),
                    "last_update_relative": format_relative_time(row["last_update"])
                })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


def format_relative_time(dt):
    """Format datetime as relative time (e.g., '2 hours ago')."""
    from datetime import timezone
    
    now = datetime.now(timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    
    diff = now - dt
    seconds = diff.total_seconds()
    
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        minutes = int(seconds / 60)
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"
    elif seconds < 86400:
        hours = int(seconds / 3600)
        return f"{hours} hour{'s' if hours != 1 else ''} ago"
    elif seconds < 604800:
        days = int(seconds / 86400)
        return f"{days} day{'s' if days != 1 else ''} ago"
    else:
        weeks = int(seconds / 604800)
        return f"{weeks} week{'s' if weeks != 1 else ''} ago"


@app.route("/api/country")
def country_aggregate():
    """
    Query params:
      from=YYYY-MM-DD
      to=YYYY-MM-DD
      min_count=int (optional)
    Returns: [{country, count}, ...]
    """
    qs_from = request.args.get("from")
    qs_to = request.args.get("to")
    
    try:
        min_count = int(request.args.get("min_count", "0"))
    except ValueError:
        return jsonify({"error": "min_count must be a valid integer"}), 400

    if not qs_from or not qs_to:
        return jsonify({
            "error": "provide from and to parameters in YYYY-MM-DD"
        }), 400

    d_from = parse_date(qs_from)
    d_to = parse_date(qs_to)
    if not d_from or not d_to:
        return jsonify({"error": "invalid date format"}), 400

    ts_from = datetime.combine(d_from, datetime.min.time()).replace(tzinfo=timezone.utc)
    ts_to = datetime.combine(d_to, datetime.max.time()).replace(tzinfo=timezone.utc)

    sql = """
    SELECT
      COALESCE(t.country, 'unknown') AS country,
      COUNT(*) AS cnt
    FROM targets t
    JOIN files f ON t.file_id = f.id
    WHERE f.fetched_at >= %(from)s AND f.fetched_at <= %(to)s
      AND (t.normalized_host IS NOT NULL AND t.normalized_host <> '')
    GROUP BY COALESCE(t.country, 'unknown')
    ORDER BY cnt DESC
    """
    params = {"from": ts_from, "to": ts_to}
    rows = []
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    results = []
    for r in rows:
        if r["cnt"] < min_count:
            continue
        results.append({"country": r["country"], "count": int(r["cnt"])})
    return jsonify(results)

@app.route("/api/domains")
def domains_list():
    """
    Returns domains aggregated with country and count.
    Query params:
      from=YYYY-MM-DD
      to=YYYY-MM-DD
      limit=int (optional, default 1000, max 10000)
    """
    qs_from = request.args.get("from")
    qs_to = request.args.get("to")
    
    try:
        limit = min(int(request.args.get("limit", "1000")), 10000)
    except ValueError:
        return jsonify({"error": "limit must be a valid integer"}), 400

    if not qs_from or not qs_to:
        return jsonify({
            "error": "provide from and to parameters in YYYY-MM-DD"
        }), 400

    d_from = parse_date(qs_from)
    d_to = parse_date(qs_to)
    if not d_from or not d_to:
        return jsonify({"error": "invalid date format"}), 400

    ts_from = datetime.combine(d_from, datetime.min.time()).replace(tzinfo=timezone.utc)
    ts_to = datetime.combine(d_to, datetime.max.time()).replace(tzinfo=timezone.utc)

    sql = """
    SELECT
      t.normalized_host AS domain,
      lower(regexp_replace(t.normalized_host, '.*\\.', '')) AS tld,
      COALESCE(t.country, 'unknown') AS country,
      COUNT(*) AS cnt
    FROM targets t
    JOIN files f ON t.file_id = f.id
    WHERE f.fetched_at >= %(from)s AND f.fetched_at <= %(to)s
      AND (t.normalized_host IS NOT NULL AND t.normalized_host <> '')
    GROUP BY t.normalized_host,
             lower(regexp_replace(t.normalized_host, '.*\\.', '')),
             COALESCE(t.country, 'unknown')
    ORDER BY cnt DESC
    LIMIT %(limit)s
    """
    params = {"from": ts_from, "to": ts_to, "limit": limit}

    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    results = [
        {
            "domain": r["domain"],
            "tld": r["tld"],
            "country": r["country"],
            "count": int(r["cnt"])
        }
        for r in rows
    ]
    return jsonify(results)


@app.route("/api/events")
def geopolitical_events():
    """
    Get geopolitical events within a date range from the database.
    Query params:
      from=YYYY-MM-DD
      to=YYYY-MM-DD
      source=curated|gdelt|both (default: both)
    Returns: [{date, title, description, category, countries, severity, source}]
    """
    qs_from = request.args.get("from")
    qs_to = request.args.get("to")
    source_filter = request.args.get("source", "both")
    
    if not qs_from or not qs_to:
        return jsonify({"error": "provide from and to parameters"}), 400
    
    d_from = parse_date(qs_from)
    d_to = parse_date(qs_to)
    if not d_from or not d_to:
        return jsonify({"error": "invalid date format"}), 400
    
    # Build SQL query based on source filter
    sql = """
        SELECT event_date, title, description, category, severity, source, 
               countries, url
        FROM events
        WHERE event_date >= %s AND event_date <= %s
    """
    params = [d_from, d_to]
    
    if source_filter in ["curated", "gdelt"]:
        sql += " AND source = %s"
        params.append(source_filter)
    
    sql += " ORDER BY event_date DESC, source ASC"
    
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                cur.execute(sql, params)
                rows = cur.fetchall()
    except Exception as e:
        return jsonify({"error": str(e)}), 500
    
    events = []
    for row in rows:
        events.append({
            "date": row["event_date"].isoformat(),
            "title": row["title"],
            "description": row["description"] or "",
            "category": row["category"],
            "severity": row["severity"] or "medium",
            "source": row["source"],
            "countries": row["countries"] or [],
            "url": row.get("url", "")
        })
    
    return jsonify(events)


@app.route("/api/health/overview")
def health_overview():
    """
    Get overall system health status including:
    - Database connectivity
    - Recent data imports
    - TLD mapping coverage
    - Data quality metrics
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Database status
                db_status = {"status": "healthy", "timestamp": datetime.now(timezone.utc).isoformat()}
                
                # Recent imports (today only)
                cur.execute("""
                    SELECT COUNT(*) as file_count, MAX(fetched_at) as last_import
                    FROM files
                    WHERE fetched_at >= CURRENT_DATE
                """)
                import_row = cur.fetchone()
                
                # TLD mapping coverage (today's data)
                cur.execute("""
                    SELECT 
                        COUNT(DISTINCT CASE WHEN country IS NOT NULL THEN normalized_host END) as mapped_hosts,
                        COUNT(DISTINCT CASE WHEN country IS NULL AND normalized_host IS NOT NULL THEN normalized_host END) as unmapped_hosts,
                        COUNT(DISTINCT normalized_host) as total_hosts
                    FROM targets
                    WHERE normalized_host IS NOT NULL AND normalized_host != ''
                        AND file_id IN (SELECT id FROM files WHERE fetched_at >= CURRENT_DATE)
                """)
                tld_row = cur.fetchone()
                
                # Data quality - null/empty hosts (today's data)
                cur.execute("""
                    SELECT 
                        COUNT(*) as total_targets,
                        COUNT(CASE WHEN normalized_host IS NULL OR normalized_host = '' THEN 1 END) as missing_hosts,
                        COUNT(CASE WHEN ip IS NULL THEN 1 END) as missing_ips
                    FROM targets
                    WHERE file_id IN (SELECT id FROM files WHERE fetched_at >= CURRENT_DATE)
                """)
                quality_row = cur.fetchone()
                
                # Recent errors/duplicates (today's data)
                cur.execute("""
                    SELECT COUNT(*) as duplicate_count
                    FROM (
                        SELECT normalized_host, file_id, COUNT(*) as cnt
                        FROM targets
                        WHERE file_id IN (SELECT id FROM files WHERE fetched_at >= CURRENT_DATE)
                        GROUP BY normalized_host, file_id
                        HAVING COUNT(*) > 1
                    ) dupes
                """)
                dup_row = cur.fetchone()
                
                return jsonify({
                    "database": db_status,
                    "imports": {
                        "files_today": import_row["file_count"],
                        "last_import": import_row["last_import"].isoformat() if import_row["last_import"] else None,
                        "status": "healthy" if import_row["file_count"] > 0 else "warning"
                    },
                    "tld_mapping": {
                        "mapped_hosts": tld_row["mapped_hosts"],
                        "unmapped_hosts": tld_row["unmapped_hosts"],
                        "total_hosts": tld_row["total_hosts"],
                        "coverage_percent": round((tld_row["mapped_hosts"] / tld_row["total_hosts"] * 100) if tld_row["total_hosts"] > 0 else 0, 2),
                        "status": "healthy" if tld_row["unmapped_hosts"] < tld_row["total_hosts"] * 0.1 else "warning"
                    },
                    "data_quality": {
                        "total_targets": quality_row["total_targets"],
                        "missing_hosts": quality_row["missing_hosts"],
                        "missing_ips": quality_row["missing_ips"],
                        "quality_percent": round(((quality_row["total_targets"] - quality_row["missing_hosts"]) / quality_row["total_targets"] * 100) if quality_row["total_targets"] > 0 else 0, 2),
                        "duplicates": dup_row["duplicate_count"],
                        "status": "healthy" if quality_row["missing_hosts"] < quality_row["total_targets"] * 0.05 else "warning"
                    }
                })
    except Exception as e:
        return jsonify({
            "database": {"status": "error", "error": str(e)},
            "imports": {"status": "error"},
            "tld_mapping": {"status": "error"},
            "data_quality": {"status": "error"}
        }), 500


@app.route("/api/health/docker")
def health_docker():
    """
    Check Docker container health via database activity.
    Since we can't access Docker API directly from Flask, we infer health from DB activity.
    """
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Downloader health - check for today's file downloads
                cur.execute("""
                    SELECT COUNT(*) as recent_files, MAX(processed_at) as last_activity
                    FROM files
                    WHERE processed_at >= CURRENT_DATE
                """)
                downloader = cur.fetchone()
                
                # Processor health - check for today's target processing
                cur.execute("""
                    SELECT COUNT(*) as recent_targets, MAX(f.processed_at) as last_activity
                    FROM targets t
                    JOIN files f ON t.file_id = f.id
                    WHERE f.processed_at >= CURRENT_DATE
                """)
                processor = cur.fetchone()
                
                # Map updater health - check for today's country updates
                cur.execute("""
                    SELECT 
                        COUNT(CASE WHEN country IS NOT NULL THEN 1 END) as mapped_count,
                        COUNT(*) as total_count
                    FROM targets
                    WHERE file_id IN (SELECT id FROM files WHERE processed_at >= CURRENT_DATE)
                """)
                map_worker = cur.fetchone()
                
                # GDELT worker health - check for today's events
                cur.execute("""
                    SELECT COUNT(*) as recent_events, MAX(created_at) as last_activity
                    FROM events
                    WHERE created_at >= CURRENT_DATE AND source = 'gdelt'
                """)
                gdelt = cur.fetchone()
                
                return jsonify({
                    "downloader": {
                        "status": "healthy" if downloader["recent_files"] > 0 else "idle",
                        "recent_files": downloader["recent_files"],
                        "last_activity": downloader["last_activity"].isoformat() if downloader["last_activity"] else None
                    },
                    "processor": {
                        "status": "healthy" if processor["recent_targets"] > 0 else "idle",
                        "recent_targets": processor["recent_targets"],
                        "last_activity": processor["last_activity"].isoformat() if processor["last_activity"] else None
                    },
                    "map_updater": {
                        "status": "healthy" if map_worker["mapped_count"] > 0 else "idle",
                        "mapped_count": map_worker["mapped_count"],
                        "total_count": map_worker["total_count"]
                    },
                    "gdelt_worker": {
                        "status": "healthy" if gdelt["recent_events"] > 0 else "idle",
                        "recent_events": gdelt["recent_events"],
                        "last_activity": gdelt["last_activity"].isoformat() if gdelt["last_activity"] else None
                    }
                })
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/health/issues")
def health_issues():
    """
    Get detailed list of current issues and warnings.
    """
    issues = []
    
    try:
        with get_conn() as conn:
            with conn.cursor() as cur:
                # Check for unmapped TLDs (today's data)
                cur.execute("""
                    SELECT 
                        lower(regexp_replace(normalized_host, '.*\\.', '')) as tld,
                        COUNT(*) as count
                    FROM targets
                    WHERE country IS NULL 
                        AND normalized_host IS NOT NULL 
                        AND normalized_host != ''
                        AND file_id IN (SELECT id FROM files WHERE fetched_at >= CURRENT_DATE)
                    GROUP BY lower(regexp_replace(normalized_host, '.*\\.', ''))
                    ORDER BY count DESC
                    LIMIT 20
                """)
                unmapped_tlds = cur.fetchall()
                
                if unmapped_tlds:
                    issues.append({
                        "type": "tld_mapping",
                        "severity": "warning",
                        "message": f"{len(unmapped_tlds)} TLDs without country mapping (today)",
                        "details": [{"tld": row["tld"], "count": row["count"]} for row in unmapped_tlds]
                    })
                
                # Check for targets with missing normalized_host (today's data)
                cur.execute("""
                    SELECT COUNT(*) as count
                    FROM targets
                    WHERE (normalized_host IS NULL OR normalized_host = '')
                        AND file_id IN (SELECT id FROM files WHERE fetched_at >= CURRENT_DATE)
                """)
                missing_hosts = cur.fetchone()
                
                if missing_hosts["count"] > 0:
                    issues.append({
                        "type": "data_quality",
                        "severity": "error",
                        "message": f"{missing_hosts['count']} targets with missing normalized_host (today)",
                        "details": {"count": missing_hosts["count"]}
                    })
                
                # Check for old data (no imports today)
                cur.execute("""
                    SELECT MAX(fetched_at) as last_import, COUNT(*) as today_count
                    FROM files
                    WHERE fetched_at >= CURRENT_DATE
                """)
                import_check = cur.fetchone()
                
                if import_check["today_count"] == 0:
                    cur.execute("SELECT MAX(fetched_at) as last_import FROM files")
                    last_import = cur.fetchone()
                    if last_import["last_import"]:
                        hours_since = (datetime.now(timezone.utc) - last_import["last_import"].replace(tzinfo=timezone.utc)).total_seconds() / 3600
                        issues.append({
                            "type": "import",
                            "severity": "warning" if hours_since < 6 else "error",
                            "message": f"No data imported today (last import {int(hours_since)}h ago)",
                            "details": {"hours_since": int(hours_since), "last_import": last_import["last_import"].isoformat()}
                        })
                
                # Check for duplicate targets (today's data)
                cur.execute("""
                    SELECT COUNT(*) as dup_groups, SUM(cnt - 1) as extra_records
                    FROM (
                        SELECT normalized_host, file_id, COUNT(*) as cnt
                        FROM targets
                        WHERE file_id IN (SELECT id FROM files WHERE fetched_at >= CURRENT_DATE)
                        GROUP BY normalized_host, file_id
                        HAVING COUNT(*) > 1
                    ) dupes
                """)
                duplicates = cur.fetchone()
                
                if duplicates["dup_groups"] and duplicates["dup_groups"] > 0:
                    issues.append({
                        "type": "data_quality",
                        "severity": "warning",
                        "message": f"{duplicates['extra_records']} duplicate target records",
                        "details": {"duplicate_groups": duplicates["dup_groups"], "extra_records": duplicates["extra_records"]}
                    })
                
                return jsonify({
                    "total_issues": len(issues),
                    "issues": issues
                })
    except Exception as e:
        return jsonify({"error": str(e)}), 500



if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
