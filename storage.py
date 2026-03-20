"""
Crawler Storage
===============
Handles all database operations for the crawler.
Now includes image_url storage for search result thumbnails.
"""

import os
import sqlite3
import logging
from typing import Optional
from datetime import datetime

logger = logging.getLogger(__name__)


class CrawlerStorage:
    """Manages SQLite database for storing crawled pages and metadata."""

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.conn: Optional[sqlite3.Connection] = None

    def connect(self):
        os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._init_schema()
        self._migrate()
        logger.info(f"Database connected: {self.db_path}")

    def _init_schema(self):
        from config import SCHEMA_PATH
        with open(SCHEMA_PATH, "r") as f:
            self.conn.executescript(f.read())
        self.conn.commit()

    def _migrate(self):
        """Add new columns to existing databases without losing data."""
        try:
            self.conn.execute("SELECT image_url FROM pages LIMIT 1")
        except sqlite3.OperationalError:
            logger.info("Migrating database: adding image_url column...")
            self.conn.execute("ALTER TABLE pages ADD COLUMN image_url TEXT DEFAULT ''")
            self.conn.commit()

    def close(self):
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed.")

    # ─── Page Operations ─────────────────────────────────────────

    def save_page(self, url: str, domain: str, title: str, raw_html: str,
                  clean_text: str, word_count: int, status_code: int,
                  content_type: str, crawl_depth: int, image_url: str = "") -> bool:
        try:
            self.conn.execute(
                """INSERT OR IGNORE INTO pages 
                    (url, domain, title, raw_html, clean_text, word_count,
                     status_code, content_type, crawl_depth, image_url)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (url, domain, title, raw_html, clean_text, word_count,
                 status_code, content_type, crawl_depth, image_url),
            )
            self.conn.commit()
            return True
        except sqlite3.Error as e:
            logger.error(f"Failed to save page {url}: {e}")
            return False

    def page_exists(self, url: str) -> bool:
        cursor = self.conn.execute("SELECT 1 FROM pages WHERE url = ? LIMIT 1", (url,))
        return cursor.fetchone() is not None

    def get_page_count(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM pages")
        return cursor.fetchone()[0]

    # ─── Link Operations ─────────────────────────────────────────

    def save_links_batch(self, links: list[tuple[str, str, str]]):
        try:
            self.conn.executemany(
                "INSERT OR IGNORE INTO links (source_url, target_url, anchor_text) VALUES (?, ?, ?)",
                links,
            )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Batch link save failed: {e}")

    def get_link_count(self) -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM links")
        return cursor.fetchone()[0]

    # ─── Frontier Operations ─────────────────────────────────────

    def add_to_frontier(self, url: str, domain: str, depth: int, priority: float = 0.5):
        try:
            self.conn.execute(
                "INSERT OR IGNORE INTO frontier (url, domain, depth, priority) VALUES (?, ?, ?, ?)",
                (url, domain, depth, priority),
            )
        except sqlite3.Error:
            pass

    def add_to_frontier_batch(self, urls: list[tuple[str, str, int, float]]):
        try:
            self.conn.executemany(
                "INSERT OR IGNORE INTO frontier (url, domain, depth, priority) VALUES (?, ?, ?, ?)",
                urls,
            )
            self.conn.commit()
        except sqlite3.Error as e:
            logger.error(f"Batch frontier insert failed: {e}")

    def get_next_urls(self, limit: int = 10) -> list[dict]:
        cursor = self.conn.execute(
            """SELECT id, url, domain, depth FROM frontier
            WHERE status = 'pending'
            ORDER BY priority DESC, depth ASC
            LIMIT ?""",
            (limit,),
        )
        rows = cursor.fetchall()

        if rows:
            ids = [row["id"] for row in rows]
            placeholders = ",".join("?" * len(ids))
            self.conn.execute(
                f"UPDATE frontier SET status = 'crawling' WHERE id IN ({placeholders})", ids,
            )
            self.conn.commit()

        return [dict(row) for row in rows]

    def mark_frontier_done(self, url: str):
        self.conn.execute("UPDATE frontier SET status = 'done' WHERE url = ?", (url,))

    def mark_frontier_failed(self, url: str):
        self.conn.execute("UPDATE frontier SET status = 'failed' WHERE url = ?", (url,))

    def get_frontier_count(self, status: str = "pending") -> int:
        cursor = self.conn.execute("SELECT COUNT(*) FROM frontier WHERE status = ?", (status,))
        return cursor.fetchone()[0]

    # ─── Statistics ──────────────────────────────────────────────

    def start_crawl_session(self) -> int:
        cursor = self.conn.execute(
            "INSERT INTO crawl_stats (start_time) VALUES (?)",
            (datetime.now().isoformat(),),
        )
        self.conn.commit()
        return cursor.lastrowid

    def end_crawl_session(self, session_id: int):
        self.conn.execute(
            """UPDATE crawl_stats 
            SET end_time = ?, total_pages = ?, total_links = ?, status = 'completed'
            WHERE id = ?""",
            (datetime.now().isoformat(), self.get_page_count(),
             self.get_link_count(), session_id),
        )
        self.conn.commit()

    def get_stats(self) -> dict:
        return {
            "total_pages": self.get_page_count(),
            "total_links": self.get_link_count(),
            "frontier_pending": self.get_frontier_count("pending"),
            "frontier_done": self.get_frontier_count("done"),
            "frontier_failed": self.get_frontier_count("failed"),
        }