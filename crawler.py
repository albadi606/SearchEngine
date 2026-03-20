"""
Web Crawler Engine
==================
The main crawler that orchestrates fetching, parsing, and storing web pages.

Architecture:
                                    ┌──────────────┐
    Seed URLs ──► URL Frontier ──►  │   Crawler    │ ──► Storage (SQLite)
                    ▲               │   Engine     │
                    │               └──────┬───────┘
                    │                      │
                    └── New URLs ◄── HTML Parser

How it works:
1. Start with seed URLs in the frontier
2. Pick the next URL from the frontier
3. Fetch the page (respecting politeness rules)
4. Parse HTML → extract text + links
5. Store the page content in the database
6. Add new URLs to the frontier
7. Repeat until max_pages reached or frontier empty
"""

import time
import logging
from typing import Optional

import requests
from requests.exceptions import RequestException

from parser import HTMLParser
from storage import CrawlerStorage
from url_frontier import URLFrontier

logger = logging.getLogger(__name__)


class Crawler:
    """
    Main crawler engine.
    
    Usage:
        crawler = Crawler(config)
        crawler.start()
    """

    def __init__(self, config: dict, db_config: dict):
        self.config = config
        self.max_pages = config.get("max_pages", 100)
        self.timeout = config.get("request_timeout", 15)
        self.user_agent = config.get("user_agent", "SearchBot/1.0")

        # Initialize components
        self.storage = CrawlerStorage(db_config["path"])
        self.frontier = URLFrontier(config)
        self.parser = HTMLParser()

        # HTTP session for connection reuse (much faster)
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": self.user_agent,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "en-US,en;q=0.9,ar;q=0.8",
        })

        # Stats
        self.pages_crawled = 0
        self.pages_failed = 0
        self.start_time: Optional[float] = None

    def start(self):
        """
        Start the crawling process.
        This is the main entry point.
        """
        logger.info("=" * 60)
        logger.info("  CRAWLER STARTING")
        logger.info("=" * 60)
        logger.info(f"  Max pages  : {self.max_pages}")
        logger.info(f"  Max depth  : {self.config.get('max_depth', 3)}")
        logger.info(f"  Seed URLs  : {len(self.config.get('seed_urls', []))}")
        logger.info(f"  Domains    : {self.config.get('allowed_domains', ['any'])}")
        logger.info("=" * 60)

        self.start_time = time.time()

        # Connect to database
        self.storage.connect()
        session_id = self.storage.start_crawl_session()

        # Seed the frontier with initial URLs
        self._seed_frontier()

        try:
            # Main crawl loop
            self._crawl_loop()
        except KeyboardInterrupt:
            logger.info("\nCrawl interrupted by user (Ctrl+C)")
        except Exception as e:
            logger.error(f"Crawl failed with error: {e}", exc_info=True)
        finally:
            # Always save final stats and close cleanly
            self.storage.end_crawl_session(session_id)
            self._print_summary()
            self.session.close()
            self.storage.close()

    def _seed_frontier(self):
        """Add seed URLs to the frontier and database."""
        seed_urls = self.config.get("seed_urls", [])

        for url in seed_urls:
            domain = self.frontier.extract_domain(url)
            self.frontier.mark_seen(url)
            self.storage.add_to_frontier(url, domain, depth=0, priority=1.0)

        logger.info(f"Seeded frontier with {len(seed_urls)} URLs")

    def _crawl_loop(self):
        """
        Main crawl loop.
        Keeps fetching pages until we hit max_pages or run out of URLs.
        """
        while self.pages_crawled < self.max_pages:
            # Get next batch of URLs from the database frontier
            batch = self.storage.get_next_urls(limit=1)

            if not batch:
                logger.info("Frontier is empty — no more URLs to crawl.")
                break

            for item in batch:
                if self.pages_crawled >= self.max_pages:
                    break

                url = item["url"]
                depth = item["depth"]
                domain = item["domain"]

                # Respect politeness delay
                self.frontier.wait_for_politeness(domain)

                # Fetch and process the page
                success = self._process_url(url, depth)

                if success:
                    self.storage.mark_frontier_done(url)
                    self.pages_crawled += 1
                else:
                    self.storage.mark_frontier_failed(url)
                    self.pages_failed += 1

                # Progress update every 10 pages
                if self.pages_crawled % 10 == 0 and self.pages_crawled > 0:
                    self._print_progress()

    def _process_url(self, url: str, depth: int) -> bool:
        """
        Fetch a single URL, parse it, store results, and discover new links.
        
        Returns True if successful, False otherwise.
        """
        logger.info(f"[{self.pages_crawled + 1}/{self.max_pages}] Crawling: {url}")

        # Step 1: Fetch the page
        html, status_code, content_type = self._fetch(url)
        if html is None:
            return False

        # Step 2: Parse the HTML
        try:
            parsed = self.parser.parse(html, url)
        except Exception as e:
            logger.warning(f"Parse error for {url}: {e}")
            return False

        # Step 3: Store the page
        domain = self.frontier.extract_domain(url)
        self.storage.save_page(
            url=url,
            domain=domain,
            title=parsed.title,
            raw_html=html,
            clean_text=parsed.clean_text,
            word_count=parsed.word_count,
            status_code=status_code,
            content_type=content_type,
            crawl_depth=depth,
            image_url=parsed.image_url,
        )

        # Step 4: Store discovered links (the web graph)
        link_records = [
            (url, link["url"], link["anchor_text"])
            for link in parsed.links
        ]
        if link_records:
            self.storage.save_links_batch(link_records)

        # Step 5: Add new URLs to the frontier
        new_urls = self.frontier.filter_new_urls(parsed.links, depth)
        if new_urls:
            frontier_records = [
                (u["url"], u["domain"], u["depth"], 0.5)
                for u in new_urls
            ]
            self.storage.add_to_frontier_batch(frontier_records)

        logger.info(
            f"  ✓ \"{parsed.title[:50]}\" | "
            f"{parsed.word_count} words | "
            f"{len(parsed.links)} links | "
            f"{len(new_urls)} new URLs"
        )

        return True

    def _fetch(self, url: str) -> tuple[Optional[str], int, str]:
        """
        Fetch a URL and return (html, status_code, content_type).
        Returns (None, status_code, "") on failure.
        """
        try:
            response = self.session.get(
                url,
                timeout=self.timeout,
                allow_redirects=True,
                # Don't download huge files
                stream=True,
            )

            # Check content type — only process HTML pages
            content_type = response.headers.get("Content-Type", "")
            if "text/html" not in content_type.lower():
                logger.debug(f"  Skipping non-HTML: {content_type}")
                return None, response.status_code, content_type

            # Check response size (skip pages > 5MB)
            content_length = response.headers.get("Content-Length")
            if content_length and int(content_length) > 5 * 1024 * 1024:
                logger.debug(f"  Skipping oversized page: {content_length} bytes")
                return None, response.status_code, content_type

            # Read the content
            html = response.text

            if response.status_code != 200:
                logger.debug(f"  HTTP {response.status_code} for {url}")
                return None, response.status_code, content_type

            return html, response.status_code, content_type

        except RequestException as e:
            logger.warning(f"  Fetch error for {url}: {e}")
            return None, 0, ""

    def _print_progress(self):
        """Print current crawl progress."""
        elapsed = time.time() - self.start_time
        rate = self.pages_crawled / elapsed if elapsed > 0 else 0
        stats = self.storage.get_stats()

        logger.info(
            f"\n  ── Progress ──────────────────────────────\n"
            f"  Pages crawled : {self.pages_crawled}\n"
            f"  Pages failed  : {self.pages_failed}\n"
            f"  Links found   : {stats['total_links']}\n"
            f"  Frontier left : {stats['frontier_pending']}\n"
            f"  Crawl rate    : {rate:.1f} pages/sec\n"
            f"  Time elapsed  : {elapsed:.0f}s\n"
            f"  ──────────────────────────────────────────\n"
        )

    def _print_summary(self):
        """Print final crawl summary."""
        elapsed = time.time() - self.start_time if self.start_time else 0
        stats = self.storage.get_stats()

        logger.info(
            f"\n{'=' * 60}\n"
            f"  CRAWL COMPLETE\n"
            f"{'=' * 60}\n"
            f"  Pages crawled  : {stats['total_pages']}\n"
            f"  Pages failed   : {self.pages_failed}\n"
            f"  Total links    : {stats['total_links']}\n"
            f"  Frontier done  : {stats['frontier_done']}\n"
            f"  Frontier left  : {stats['frontier_pending']}\n"
            f"  Time elapsed   : {elapsed:.1f}s\n"
            f"  Avg speed      : {stats['total_pages'] / elapsed:.1f} pages/sec\n"
            f"{'=' * 60}"
        )