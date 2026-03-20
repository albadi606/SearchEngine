#!/usr/bin/env python3
"""
Crawl Inspector
===============
Utility script to inspect and analyze crawled data.
Run after crawling to see what you've collected.

Usage:
    python inspect_data.py
    python inspect_data.py --top 20
"""

import os
import sys
import sqlite3
import argparse

DB_PATH = os.path.join(os.path.dirname(__file__), "database", "search_engine.db")


def inspect(top_n: int = 10):
    """Print a summary of crawled data."""
    if not os.path.exists(DB_PATH):
        print("No database found. Run the crawler first: python run_crawler.py")
        sys.exit(1)

    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row

    # ─── Overview ────────────────────────────────────────────────────
    pages = conn.execute("SELECT COUNT(*) FROM pages").fetchone()[0]
    links = conn.execute("SELECT COUNT(*) FROM links").fetchone()[0]
    domains = conn.execute("SELECT COUNT(DISTINCT domain) FROM pages").fetchone()[0]
    avg_words = conn.execute("SELECT AVG(word_count) FROM pages").fetchone()[0] or 0

    print(f"\n{'=' * 60}")
    print(f"  CRAWL DATABASE SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total pages crawled  : {pages:,}")
    print(f"  Total links found    : {links:,}")
    print(f"  Unique domains       : {domains:,}")
    print(f"  Avg words per page   : {avg_words:,.0f}")
    print(f"  Database size        : {os.path.getsize(DB_PATH) / 1024 / 1024:.1f} MB")

    # ─── Top Pages by Word Count ─────────────────────────────────────
    print(f"\n  TOP {top_n} PAGES BY WORD COUNT")
    print(f"  {'─' * 55}")
    rows = conn.execute(
        "SELECT title, word_count, url FROM pages ORDER BY word_count DESC LIMIT ?",
        (top_n,),
    ).fetchall()
    for i, row in enumerate(rows, 1):
        title = row["title"][:45]
        print(f"  {i:3}. {title:<45}  {row['word_count']:>6} words")

    # ─── Domain Distribution ─────────────────────────────────────────
    print(f"\n  PAGES BY DOMAIN")
    print(f"  {'─' * 55}")
    rows = conn.execute(
        "SELECT domain, COUNT(*) as cnt FROM pages GROUP BY domain ORDER BY cnt DESC LIMIT ?",
        (top_n,),
    ).fetchall()
    for row in rows:
        print(f"  {row['domain']:<40}  {row['cnt']:>6} pages")

    # ─── Most Linked Pages ───────────────────────────────────────────
    print(f"\n  TOP {top_n} MOST LINKED-TO PAGES")
    print(f"  {'─' * 55}")
    rows = conn.execute(
        """
        SELECT target_url, COUNT(*) as inlinks 
        FROM links GROUP BY target_url 
        ORDER BY inlinks DESC LIMIT ?
        """,
        (top_n,),
    ).fetchall()
    for i, row in enumerate(rows, 1):
        url_short = row["target_url"][:50]
        print(f"  {i:3}. {url_short:<50}  {row['inlinks']:>4} links")

    # ─── Sample Text ─────────────────────────────────────────────────
    print(f"\n  SAMPLE CRAWLED TEXT (first page)")
    print(f"  {'─' * 55}")
    row = conn.execute(
        "SELECT title, clean_text FROM pages ORDER BY id LIMIT 1"
    ).fetchone()
    if row:
        print(f"  Title: {row['title']}")
        text_preview = row["clean_text"][:300]
        print(f"  Text:  {text_preview}...")

    print(f"\n{'=' * 60}\n")
    conn.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect crawled data")
    parser.add_argument("--top", type=int, default=10, help="Number of results to show")
    args = parser.parse_args()
    inspect(args.top)
