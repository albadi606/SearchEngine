"""
URL Frontier
=============
Manages the queue of URLs waiting to be crawled.

Now supports:
- Per-domain politeness delays (e.g., 10s for UN, 1s for Wikipedia)
- Blocked path checking from robots.txt rules
- URL normalization for deduplication
"""

import time
import logging
from urllib.parse import urlparse
from collections import defaultdict
from typing import Optional

from deduplicator import URLNormalizer

logger = logging.getLogger(__name__)


class URLFrontier:
    """
    Manages URL scheduling and politeness for the crawler.
    
    Key features:
    - Per-domain delay: respects Crawl-delay from robots.txt
    - Blocked paths: skips URLs that robots.txt disallows
    - URL normalization: deduplicates similar URLs
    """

    def __init__(self, config: dict):
        self.max_depth = config.get("max_depth", 3)
        self.default_delay = config.get("politeness_delay", 1.0)
        self.allowed_domains = set(config.get("allowed_domains", []))
        self.skip_extensions = set(config.get("skip_extensions", []))
        self.respect_robots = config.get("respect_robots_txt", True)

        # Per-domain delays (from robots.txt Crawl-delay directives)
        self.domain_delays = config.get("domain_delays", {})

        # Blocked paths per domain (from robots.txt Disallow rules)
        self.blocked_paths = config.get("blocked_paths", {})

        # URL normalizer for deduplication
        self._normalizer = URLNormalizer()

        # Track when we last accessed each domain
        self._domain_last_access: dict[str, float] = defaultdict(float)

        # Set of all normalized URLs we've ever seen
        self._seen_urls: set[str] = set()

    def should_crawl(self, url: str, depth: int) -> bool:
        """
        Decide if a URL should be added to the frontier.
        
        Checks:
        1. Not already seen (normalized)
        2. Within depth limit
        3. Allowed domain
        4. Not in blocked paths (robots.txt)
        5. Not a file we don't want
        6. Valid URL format
        """
        # Normalize first
        normalized = self._normalizer.normalize(url)

        # Already seen?
        if normalized in self._seen_urls:
            return False

        # Too deep?
        if depth > self.max_depth:
            return False

        # Parse the URL
        parsed = urlparse(normalized)

        # Must be HTTP(S)
        if parsed.scheme not in ("http", "https"):
            return False

        # Check domain restrictions
        if self.allowed_domains:
            if parsed.netloc not in self.allowed_domains:
                return False

        # Check blocked paths (from robots.txt)
        if self._is_path_blocked(parsed.netloc, parsed.path):
            return False

        # Skip unwanted file types
        path_lower = parsed.path.lower()
        for ext in self.skip_extensions:
            if path_lower.endswith(ext):
                return False

        # Skip URLs that are too long
        if len(normalized) > 500:
            return False

        return True

    def _is_path_blocked(self, domain: str, path: str) -> bool:
        """
        Check if a URL path is blocked by robots.txt rules.
        
        Example:
            domain = "developer.mozilla.org"
            path = "/api/some-endpoint"
            blocked_paths = ["/api/", "/media"]
            → Returns True (path starts with /api/)
        """
        if domain not in self.blocked_paths:
            return False

        path_lower = path.lower()
        for blocked in self.blocked_paths[domain]:
            if path_lower.startswith(blocked.lower()):
                return True

        return False

    def mark_seen(self, url: str):
        """Mark a URL as seen (uses normalized form)."""
        normalized = self._normalizer.normalize(url)
        self._seen_urls.add(normalized)

    def is_seen(self, url: str) -> bool:
        """Check if we've already seen this URL."""
        normalized = self._normalizer.normalize(url)
        return normalized in self._seen_urls

    def wait_for_politeness(self, domain: str):
        """
        Wait the correct delay for this specific domain.
        
        Uses per-domain delays from config:
        - www.un.int → 10 seconds (robots.txt requires it)
        - en.wikipedia.org → 1 second
        - Omani news sites → 2 seconds (extra polite)
        """
        # Get the delay for this domain (fall back to default)
        delay = self.domain_delays.get(domain, self.default_delay)

        last_access = self._domain_last_access[domain]
        elapsed = time.time() - last_access

        if elapsed < delay:
            wait_time = delay - elapsed
            logger.debug(f"Politeness delay: waiting {wait_time:.1f}s for {domain}")
            time.sleep(wait_time)

        self._domain_last_access[domain] = time.time()

    def extract_domain(self, url: str) -> str:
        """Extract the domain from a URL."""
        return urlparse(url).netloc

    def filter_new_urls(self, urls: list[dict], current_depth: int) -> list[dict]:
        """Filter discovered URLs, keeping only crawlable ones."""
        new_urls = []
        next_depth = current_depth + 1

        for link in urls:
            url = link["url"]
            if self.should_crawl(url, next_depth):
                self.mark_seen(url)
                new_urls.append({
                    "url": self._normalizer.normalize(url),
                    "domain": self.extract_domain(url),
                    "depth": next_depth,
                    "anchor_text": link.get("anchor_text", ""),
                })

        logger.debug(
            f"Filtered {len(urls)} URLs → {len(new_urls)} new crawlable URLs"
        )
        return new_urls

    def get_stats(self) -> dict:
        return {
            "total_urls_seen": len(self._seen_urls),
            "domains_tracked": len(self._domain_last_access),
        }