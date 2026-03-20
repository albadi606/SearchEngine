#!/usr/bin/env python3
"""
Search Engine — Command Line Search
====================================
Search through your crawled and indexed pages!

Usage:
    python search.py "search query"
    python search.py                          # Interactive mode

Examples:
    python search.py "search engine"
    python search.py "machne lerning"         # Tests spell correction
"""

import sys
import os
import argparse
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DATABASE
from indexer import InvertedIndex


def display_results(search_result: dict, query: str):
    """Display search results in a clean format."""
    results = search_result.get("results", [])
    suggestion = search_result.get("suggestion")

    if suggestion:
        print(f"\n  💡 Did you mean: \"{suggestion}\"?")

    if not results:
        print(f"\n  No results found for \"{query}\"")
        print(f"  Try different keywords or run the crawler with more pages.")
        return

    print(f"\n  Found {len(results)} results for \"{query}\"")
    print(f"  {'─' * 60}")

    for r in results:
        print(f"\n  {r['rank']}. {r['title']}")
        print(f"     Score: {r['score']}  |  Words: {r['word_count']}")
        print(f"     URL: {r['url']}")
        print(f"     {r['snippet']}")

    print(f"\n  {'─' * 60}\n")


def interactive_mode(index: InvertedIndex):
    """Interactive search loop."""
    print("\n" + "=" * 60)
    print("  SEARCH ENGINE — Interactive Mode")
    print("=" * 60)
    print("  Type your search query and press Enter.")
    print("  Type 'quit' or 'exit' to stop.")
    print("  Type 'stats' to see index statistics.")
    print("=" * 60)

    while True:
        try:
            query = input("\n  Search > ").strip()
        except (KeyboardInterrupt, EOFError):
            print("\n  Goodbye!")
            break

        if not query:
            continue
        if query.lower() in ("quit", "exit", "q"):
            print("  Goodbye!")
            break
        if query.lower() == "stats":
            stats = index.get_stats()
            print(f"\n  Documents indexed : {stats.get('total_docs', '?')}")
            print(f"  Unique terms      : {stats.get('unique_terms', '?')}")
            print(f"  Total tokens      : {stats.get('total_tokens', '?')}")
            continue

        search_result = index.search(query, top_k=10)
        display_results(search_result, query)


def main():
    logging.basicConfig(level=logging.WARNING)

    parser = argparse.ArgumentParser(description="Search your crawled pages")
    parser.add_argument("query", nargs="?", default=None)
    parser.add_argument("--top", type=int, default=10)
    args = parser.parse_args()

    db_path = DATABASE["path"]
    if not os.path.exists(db_path):
        print("No database found. Run these commands first:")
        print("  python run_crawler.py --max-pages 50")
        print("  python build_index.py")
        sys.exit(1)

    index = InvertedIndex(db_path)
    index.connect()

    row = index.conn.execute(
        "SELECT value FROM index_meta WHERE key = 'total_docs'"
    ).fetchone()
    if not row:
        print("Index not built yet. Run: python build_index.py")
        index.close()
        sys.exit(1)

    if args.query:
        search_result = index.search(args.query, top_k=args.top)
        display_results(search_result, args.query)
    else:
        interactive_mode(index)

    index.close()


if __name__ == "__main__":
    main()
