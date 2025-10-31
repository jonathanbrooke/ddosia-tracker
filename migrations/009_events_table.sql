-- Create events table for geopolitical events
CREATE TABLE IF NOT EXISTS events (
    id SERIAL PRIMARY KEY,
    event_date DATE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    category TEXT NOT NULL,
    severity TEXT,
    source TEXT NOT NULL DEFAULT 'curated',
    countries TEXT[],
    url TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(event_date, title, source)
);

CREATE INDEX idx_events_date ON events(event_date);
CREATE INDEX idx_events_source ON events(source);
CREATE INDEX idx_events_category ON events(category);

-- Insert curated events from the JSON file
-- This will be done by the map-worker script
