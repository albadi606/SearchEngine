#!/usr/bin/env python3
"""
Build Inverted Index
====================
Run this AFTER crawling to build the searchable index.

Usage:
    python build_index.py

This reads all pages from the database, tokenizes them,
and creates the inverted index. Must be run before searching.
"""

import sys
import os
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DATABASE, LOGGING
from indexer import InvertedIndex


def setup_logging():
    logging.basicConfig(
        level=getattr(logging, LOGGING["level"]),
        format=LOGGING["format"],
        datefmt=LOGGING["date_format"],
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )


def main():
    setup_logging()

    db_path = DATABASE["path"]
    if not os.path.exists(db_path):
        print("No database found. Run the crawler first:")
        print("  python run_crawler.py --max-pages 50")
        sys.exit(1)

    # Build the index
    index = InvertedIndex(db_path)
    index.connect()
    index.build()

    # Show stats
    stats = index.get_stats()
    print(f"\nIndex Statistics:")
    print(f"  Documents  : {stats.get('total_docs', '?')}")
    print(f"  Unique terms: {stats.get('unique_terms', '?')}")
    print(f"  Total tokens: {stats.get('total_tokens', '?')}")

    print(f"\nTop 20 most common terms across all documents:")
    for term in stats.get("top_terms", []):
        print(f"  {term['token']:<25} in {term['doc_count']:>3} docs  ({term['total_freq']:>5}x total)")

    index.close()
    print("\nIndex built successfully! Now try:")
    print("  python search.py \"your search query\"")


if __name__ == "__main__":
    main()
