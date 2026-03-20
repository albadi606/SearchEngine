-- Search Engine Database Schema
-- Phase 1: Crawler Storage (with image support)

CREATE TABLE IF NOT EXISTS pages (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT UNIQUE NOT NULL,
    domain          TEXT NOT NULL,
    title           TEXT,
    raw_html        TEXT,
    clean_text      TEXT,
    word_count      INTEGER DEFAULT 0,
    status_code     INTEGER,
    content_type    TEXT,
    crawl_depth     INTEGER DEFAULT 0,
    image_url       TEXT DEFAULT '',
    crawled_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS links (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    source_url      TEXT NOT NULL,
    target_url      TEXT NOT NULL,
    anchor_text     TEXT,
    discovered_at   TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_url, target_url)
);

CREATE TABLE IF NOT EXISTS frontier (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    url             TEXT UNIQUE NOT NULL,
    domain          TEXT NOT NULL,
    depth           INTEGER DEFAULT 0,
    priority        REAL DEFAULT 0.5,
    status          TEXT DEFAULT 'pending',
    added_at        TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS crawl_stats (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    total_pages     INTEGER DEFAULT 0,
    total_links     INTEGER DEFAULT 0,
    start_time      TIMESTAMP,
    end_time        TIMESTAMP,
    status          TEXT DEFAULT 'running'
);

CREATE INDEX IF NOT EXISTS idx_pages_url ON pages(url);
CREATE INDEX IF NOT EXISTS idx_pages_domain ON pages(domain);
CREATE INDEX IF NOT EXISTS idx_frontier_status ON frontier(status);
CREATE INDEX IF NOT EXISTS idx_frontier_domain ON frontier(domain);
CREATE INDEX IF NOT EXISTS idx_links_source ON links(source_url);
CREATE INDEX IF NOT EXISTS idx_links_target ON links(target_url);