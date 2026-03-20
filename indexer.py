"""
Inverted Index
==============
The core data structure that makes search possible.

An inverted index flips the normal mapping:
    Normal:   "Document → What words are in it?"
    Inverted: "Word → Which documents contain it?"

Now includes:
- TF-IDF search ranking
- Spell correction ("Did you mean...?")
- Autocomplete suggestions
- Content deduplication awareness
"""

import os
import sys
import json
import math
import time
import sqlite3
import logging
from typing import Optional

from tokenizer import Tokenizer
from spell_correct import SpellCorrector, Autocomplete

logger = logging.getLogger(__name__)


class InvertedIndex:
    """
    Builds and queries an inverted index from crawled pages.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path
        self.tokenizer = Tokenizer()
        self.conn: Optional[sqlite3.Connection] = None

        # Smart search features
        self.spell_corrector = SpellCorrector(db_path)
        self.autocomplete = Autocomplete(db_path)

        # Stats
        self.total_docs = 0
        self.total_tokens = 0

    def connect(self):
        """Open database and create index tables."""
        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self._create_tables()

    def _create_tables(self):
        """Create the inverted index tables."""
        self.conn.executescript("""
            CREATE TABLE IF NOT EXISTS inverted_index (
                token       TEXT NOT NULL,
                page_id     INTEGER NOT NULL,
                frequency   INTEGER NOT NULL,
                positions   TEXT,
                PRIMARY KEY (token, page_id)
            );

            CREATE TABLE IF NOT EXISTS doc_stats (
                page_id         INTEGER PRIMARY KEY,
                url             TEXT NOT NULL,
                title           TEXT,
                total_tokens    INTEGER,
                unique_tokens   INTEGER,
                indexed_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );

            CREATE TABLE IF NOT EXISTS index_meta (
                key     TEXT PRIMARY KEY,
                value   TEXT
            );

            -- Indexes for fast lookup
            CREATE INDEX IF NOT EXISTS idx_inverted_token 
                ON inverted_index(token);
            CREATE INDEX IF NOT EXISTS idx_inverted_page 
                ON inverted_index(page_id);
        """)
        self.conn.commit()

    def build(self):
        """
        Build the inverted index from all crawled pages.
        Reads every page, tokenizes it, and populates the index.
        """
        logger.info("=" * 60)
        logger.info("  BUILDING INVERTED INDEX")
        logger.info("=" * 60)

        start_time = time.time()

        # Clear old index data
        self.conn.execute("DELETE FROM inverted_index")
        self.conn.execute("DELETE FROM doc_stats")
        self.conn.commit()

        # Get all crawled pages
        cursor = self.conn.execute(
            "SELECT id, url, title, clean_text FROM pages WHERE clean_text IS NOT NULL"
        )
        pages = cursor.fetchall()
        total_pages = len(pages)

        if total_pages == 0:
            logger.warning("No pages found in database. Run the crawler first!")
            return

        logger.info(f"  Indexing {total_pages} pages...")

        batch_index = []
        batch_stats = []

        for i, page in enumerate(pages, 1):
            page_id = page["id"]
            url = page["url"]
            title = page["title"] or "Untitled"
            text = page["clean_text"]

            # Tokenize: title repeated for extra weight
            full_text = f"{title} {title} {text}"
            result = self.tokenizer.tokenize(full_text)

            for token, freq in result.term_frequencies.items():
                positions = result.token_positions.get(token, [])
                positions_json = json.dumps(positions[:20])
                batch_index.append((token, page_id, freq, positions_json))

            batch_stats.append((
                page_id, url, title,
                result.token_count, result.unique_count
            ))

            self.total_tokens += result.token_count

            if i % 10 == 0 or i == total_pages:
                logger.info(f"  [{i}/{total_pages}] Indexed: {title[:50]}")

        # Bulk insert
        logger.info("  Writing index to database...")

        self.conn.executemany(
            """INSERT OR REPLACE INTO inverted_index 
               (token, page_id, frequency, positions)
               VALUES (?, ?, ?, ?)""",
            batch_index,
        )

        self.conn.executemany(
            """INSERT OR REPLACE INTO doc_stats 
               (page_id, url, title, total_tokens, unique_tokens)
               VALUES (?, ?, ?, ?, ?)""",
            batch_stats,
        )

        # Save global stats
        self.total_docs = total_pages
        unique_terms = self.conn.execute(
            "SELECT COUNT(DISTINCT token) FROM inverted_index"
        ).fetchone()[0]

        self.conn.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
            ("total_docs", str(total_pages)),
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
            ("total_tokens", str(self.total_tokens)),
        )
        self.conn.execute(
            "INSERT OR REPLACE INTO index_meta (key, value) VALUES (?, ?)",
            ("unique_terms", str(unique_terms)),
        )

        self.conn.commit()

        elapsed = time.time() - start_time

        logger.info(f"\n{'=' * 60}")
        logger.info(f"  INDEX COMPLETE")
        logger.info(f"{'=' * 60}")
        logger.info(f"  Documents indexed : {total_pages}")
        logger.info(f"  Unique terms      : {unique_terms:,}")
        logger.info(f"  Total postings    : {len(batch_index):,}")
        logger.info(f"  Time elapsed      : {elapsed:.1f}s")
        logger.info(f"{'=' * 60}")

        # Pre-load spell corrector vocabulary
        logger.info("  Loading spell correction vocabulary...")
        self.spell_corrector.load_vocabulary()

    def search(self, query: str, top_k: int = 10) -> dict:
        """
        Search the index with TF-IDF ranking + smart features.

        Returns dict with:
        - results: ranked list of matching pages
        - suggestion: spell correction suggestion (or None)
        - query_tokens: processed query tokens
        """
        # Tokenize the query
        query_tokens = self.tokenizer.tokenize_query(query)

        # Check spelling
        suggestion = self.spell_corrector.correct(query)

        if not query_tokens:
            # If no tokens, try the suggestion
            if suggestion:
                query_tokens = self.tokenizer.tokenize_query(suggestion)
            if not query_tokens:
                return {"results": [], "suggestion": suggestion, "query_tokens": []}

        # Get total document count
        row = self.conn.execute(
            "SELECT value FROM index_meta WHERE key = 'total_docs'"
        ).fetchone()
        total_docs = int(row["value"]) if row else 1

        # TF-IDF scoring
        doc_scores = {}

        for token in query_tokens:
            cursor = self.conn.execute(
                "SELECT page_id, frequency FROM inverted_index WHERE token = ?",
                (token,),
            )
            postings = cursor.fetchall()

            if not postings:
                continue

            doc_freq = len(postings)
            idf = math.log(total_docs / doc_freq) if doc_freq > 0 else 0

            for posting in postings:
                page_id = posting["page_id"]
                tf = posting["frequency"]
                tf_normalized = 1 + math.log(tf) if tf > 0 else 0
                score = tf_normalized * idf

                if page_id not in doc_scores:
                    doc_scores[page_id] = 0.0
                doc_scores[page_id] += score

        if not doc_scores:
            return {"results": [], "suggestion": suggestion, "query_tokens": query_tokens}

        # Sort by score
        ranked = sorted(doc_scores.items(), key=lambda x: -x[1])[:top_k]

        # Fetch page details
        results = []
        for page_id, score in ranked:
            row = self.conn.execute(
                """SELECT p.url, p.title, p.clean_text, p.image_url, d.total_tokens
                   FROM pages p 
                   JOIN doc_stats d ON p.id = d.page_id
                   WHERE p.id = ?""",
                (page_id,),
            ).fetchone()

            if row:
                snippet = self._generate_snippet(row["clean_text"], query_tokens)
                results.append({
                    "rank": len(results) + 1,
                    "score": round(score, 4),
                    "title": row["title"],
                    "url": row["url"],
                    "snippet": snippet,
                    "word_count": row["total_tokens"],
                    "image_url": row["image_url"] or "",
                })

        return {
            "results": results,
            "suggestion": suggestion,
            "query_tokens": query_tokens,
        }

    def get_autocomplete(self, prefix: str, limit: int = 7) -> list[dict]:
        """Get autocomplete suggestions for a prefix."""
        return self.autocomplete.suggest(prefix, limit)

    def _generate_snippet(self, text: str, query_tokens: list[str],
                          max_length: int = 200) -> str:
        """Generate a search result snippet around query terms."""
        text_lower = text.lower()

        best_pos = -1
        for token in query_tokens:
            pos = text_lower.find(token)
            if pos != -1 and (best_pos == -1 or pos < best_pos):
                best_pos = pos

        if best_pos == -1:
            return text[:max_length] + "..." if len(text) > max_length else text

        start = max(0, best_pos - 60)
        end = min(len(text), start + max_length)
        snippet = text[start:end].strip()

        if start > 0:
            snippet = "..." + snippet
        if end < len(text):
            snippet = snippet + "..."

        return snippet

    def get_stats(self) -> dict:
        """Get index statistics."""
        stats = {}
        cursor = self.conn.execute("SELECT key, value FROM index_meta")
        for row in cursor:
            stats[row["key"]] = row["value"]

        cursor = self.conn.execute(
            """SELECT token, COUNT(*) as doc_count, SUM(frequency) as total_freq
               FROM inverted_index
               GROUP BY token
               ORDER BY doc_count DESC
               LIMIT 20"""
        )
        stats["top_terms"] = [
            {"token": r["token"], "doc_count": r["doc_count"], "total_freq": r["total_freq"]}
            for r in cursor
        ]

        return stats

    def close(self):
        if self.conn:
            self.conn.close()