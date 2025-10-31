-- helper table for TLD -> representative lat/lon
CREATE TABLE IF NOT EXISTS tld_geo (
  tld TEXT PRIMARY KEY,
  country TEXT,
  lat DOUBLE PRECISION,
  lon DOUBLE PRECISION
);

INSERT INTO tld_geo (tld, country, lat, lon) VALUES
('us', 'United States', 38.9072, -77.0369),
('uk', 'United Kingdom', 51.5074, -0.1278),
('de', 'Germany', 52.5200, 13.4050),
('fr', 'France', 48.8566, 2.3522),
('ru', 'Russia', 55.7558, 37.6173),
('cn', 'China', 39.9042, 116.4074),
('com', 'Commercial', 20.0, 0.0),
('net', 'Network', 20.0, 0.0),
('org', 'Organization', 20.0, 0.0),
('ip', 'IP', 0.0, 0.0)
ON CONFLICT (tld) DO NOTHING;

-- recreate materialized view that aggregates targets by day + tld
DROP MATERIALIZED VIEW IF EXISTS view_tld_daily;
CREATE MATERIALIZED VIEW view_tld_daily AS
SELECT
  date_trunc('day', f.fetched_at)::date AS day,
  lower(regexp_replace(t.host, '.*\\.', '')) AS tld,
  COALESCE(g.lat, 0.0) AS lat,
  COALESCE(g.lon, 0.0) AS lon,
  COUNT(*) AS cnt
FROM targets t
JOIN files f ON t.file_id = f.id
LEFT JOIN tld_geo g ON lower(regexp_replace(t.host, '.*\\.', '')) = g.tld
WHERE f.fetched_at IS NOT NULL
  AND (t.host IS NOT NULL AND t.host <> '')
GROUP BY date_trunc('day', f.fetched_at)::date,
         lower(regexp_replace(t.host, '.*\\.', '')),
         g.lat, g.lon;

-- add index to speed queries by day
CREATE INDEX IF NOT EXISTS idx_view_tld_daily_day ON view_tld_daily(day);