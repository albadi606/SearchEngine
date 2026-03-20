#!/usr/bin/env python3
"""
Search Engine - Web Crawler
============================
Run this script to start crawling!

Usage:
    python run_crawler.py                  # Use default config
    python run_crawler.py --max-pages 50   # Crawl 50 pages
    python run_crawler.py --seed https://en.wikipedia.org/wiki/Python_(programming_language)

Examples:
    # Quick test (10 pages)
    python run_crawler.py --max-pages 10

    # Crawl 200 Wikipedia pages starting from a specific topic
    python run_crawler.py --max-pages 200 --seed https://en.wikipedia.org/wiki/Cybersecurity
"""

import argparse
import logging
import sys
import os

# Make sure Python can find our modules in the same folder
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import CRAWLER, DATABASE, LOGGING
from crawler import Crawler


def setup_logging():
    """Configure logging for the crawler."""
    logging.basicConfig(
        level=getattr(logging, LOGGING["level"]),
        format=LOGGING["format"],
        datefmt=LOGGING["date_format"],
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler("crawler.log", encoding="utf-8"),
        ],
    )


def parse_args():
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Search Engine Web Crawler",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_crawler.py --max-pages 10          Quick test crawl
  python run_crawler.py --max-pages 200         Larger crawl
  python run_crawler.py --seed URL1 --seed URL2 Custom seed URLs
  python run_crawler.py --depth 5               Crawl deeper
        """,
    )
    parser.add_argument(
        "--max-pages", type=int, default=None,
        help=f"Maximum pages to crawl (default: {CRAWLER['max_pages']})",
    )
    parser.add_argument(
        "--depth", type=int, default=None,
        help=f"Maximum crawl depth (default: {CRAWLER['max_depth']})",
    )
    parser.add_argument(
        "--seed", action="append", default=None,
        help="Seed URL(s) to start crawling from (can specify multiple)",
    )
    parser.add_argument(
        "--delay", type=float, default=None,
        help=f"Politeness delay in seconds (default: {CRAWLER['politeness_delay']})",
    )
    parser.add_argument(
        "--domain", action="append", default=None,
        help="Restrict crawling to these domain(s) (can specify multiple)",
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    setup_logging()
    args = parse_args()

    # Override config with command-line arguments
    config = CRAWLER.copy()
    if args.max_pages is not None:
        config["max_pages"] = args.max_pages
    if args.depth is not None:
        config["max_depth"] = args.depth
    if args.seed is not None:
        config["seed_urls"] = args.seed
    if args.delay is not None:
        config["politeness_delay"] = args.delay
    if args.domain is not None:
        config["allowed_domains"] = args.domain

    # Create and start the crawler
    crawler = Crawler(config=config, db_config=DATABASE)
    crawler.start()

    print("\nDone! Check database/search_engine.db for results.")
    print("You can inspect it with: sqlite3 database/search_engine.db")
    print('  Try: SELECT title, word_count FROM pages ORDER BY word_count DESC LIMIT 10;')


if __name__ == "__main__":
    main()