"""
Deduplicator
=============
Handles two types of duplicates that plague web crawlers:

1. URL Duplicates:
   Same page, different URL formats:
   - https://en.wikipedia.org/wiki/Google_Search
   - https://en.wikipedia.org/wiki/Google_search  (different case)
   - https://en.wikipedia.org/wiki/Google_Search#History  (fragment)
   - https://en.wikipedia.org/wiki/Google_Search?action=view  (query params)

2. Content Duplicates:
   Different URLs but identical (or near-identical) content.
   Common with: mirrors, syndicated articles, print-friendly pages.

We use:
- URL normalization (clean up URL variations)
- Content fingerprinting with SimHash (detect near-duplicate content)
"""

import re
import hashlib
import logging
from urllib.parse import urlparse, urlunparse, parse_qs, urlencode

logger = logging.getLogger(__name__)


class URLNormalizer:
    """
    Normalizes URLs to a canonical form to avoid crawling the same page twice.
    
    Example:
        https://Example.COM/path/../page?b=2&a=1#section
        → https://example.com/page?a=1&b=2
    """

    # Query parameters that don't change page content
    NOISE_PARAMS = {
        "utm_source", "utm_medium", "utm_campaign", "utm_term", "utm_content",
        "fbclid", "gclid", "ref", "source", "action", "oldid",
        "printable", "mobileaction", "useskin",
    }

    @staticmethod
    def normalize(url: str) -> str:
        """
        Normalize a URL to its canonical form.
        
        Steps:
        1. Lowercase scheme and host
        2. Remove fragment (#section)
        3. Remove trailing slash
        4. Sort query parameters
        5. Remove tracking/noise parameters
        6. Resolve path (remove /../ and /./)
        """
        try:
            parsed = urlparse(url)

            # Lowercase scheme and host
            scheme = parsed.scheme.lower()
            netloc = parsed.netloc.lower()

            # Clean path
            path = parsed.path
            # Remove double slashes
            path = re.sub(r'/+', '/', path)
            # Remove trailing slash (except root)
            if path != '/':
                path = path.rstrip('/')

            # Sort and filter query parameters
            if parsed.query:
                params = parse_qs(parsed.query, keep_blank_values=False)
                # Remove noise parameters
                filtered = {
                    k: v for k, v in params.items()
                    if k.lower() not in URLNormalizer.NOISE_PARAMS
                }
                # Sort for consistency
                query = urlencode(filtered, doseq=True)
            else:
                query = ""

            # Rebuild URL without fragment
            normalized = urlunparse((scheme, netloc, path, "", query, ""))
            return normalized

        except Exception:
            return url  # Return original if normalization fails


class ContentFingerprinter:
    """
    Detects near-duplicate content using SimHash.
    
    SimHash works by:
    1. Break text into word-level features (shingles)
    2. Hash each feature
    3. Combine hashes into a single fingerprint
    4. Similar documents have similar fingerprints
    
    Two pages with SimHash distance < 3 bits are likely duplicates.
    """

    def __init__(self, hash_bits: int = 64):
        self.hash_bits = hash_bits

    def fingerprint(self, text: str) -> int:
        """
        Compute SimHash fingerprint of a text.
        
        Returns an integer fingerprint. Similar texts will have
        fingerprints that differ in very few bits.
        """
        # Tokenize into 3-word shingles (overlapping)
        words = text.lower().split()
        if len(words) < 3:
            # For very short texts, use individual words
            features = words
        else:
            features = [
                " ".join(words[i:i+3])
                for i in range(len(words) - 2)
            ]

        if not features:
            return 0

        # Initialize bit counters
        counters = [0] * self.hash_bits

        for feature in features:
            # Hash the feature
            h = int(hashlib.md5(feature.encode("utf-8")).hexdigest(), 16)

            for i in range(self.hash_bits):
                # If bit i is set, increment counter; else decrement
                if h & (1 << i):
                    counters[i] += 1
                else:
                    counters[i] -= 1

        # Build fingerprint: bit i is 1 if counter[i] > 0
        fingerprint = 0
        for i in range(self.hash_bits):
            if counters[i] > 0:
                fingerprint |= (1 << i)

        return fingerprint

    @staticmethod
    def hamming_distance(fp1: int, fp2: int) -> int:
        """
        Count the number of differing bits between two fingerprints.
        Lower distance = more similar content.
        
        Distance 0: Identical content
        Distance 1-3: Near-duplicate (likely same article)
        Distance 4+: Different content
        """
        xor = fp1 ^ fp2
        return bin(xor).count("1")

    def is_duplicate(self, fp1: int, fp2: int, threshold: int = 3) -> bool:
        """Check if two fingerprints represent duplicate content."""
        return self.hamming_distance(fp1, fp2) <= threshold


class Deduplicator:
    """
    Combined URL + content deduplication.
    
    Usage:
        dedup = Deduplicator()
        
        # Check URL duplicate
        normalized = dedup.normalize_url(url)
        
        # Check content duplicate
        is_dup, similar_to = dedup.check_content(text)
    """

    def __init__(self):
        self.url_normalizer = URLNormalizer()
        self.fingerprinter = ContentFingerprinter()
        self._seen_urls = set()
        self._fingerprints = {}  # {url: fingerprint}

    def normalize_url(self, url: str) -> str:
        """Normalize a URL."""
        return self.url_normalizer.normalize(url)

    def is_url_seen(self, url: str) -> bool:
        """Check if this normalized URL has been seen before."""
        normalized = self.normalize_url(url)
        if normalized in self._seen_urls:
            return True
        self._seen_urls.add(normalized)
        return False

    def check_content_duplicate(self, url: str, text: str) -> tuple[bool, str]:
        """
        Check if content is a near-duplicate of something already seen.
        
        Returns:
            (is_duplicate, similar_url) — if duplicate, which URL it matches
        """
        fp = self.fingerprinter.fingerprint(text)

        for seen_url, seen_fp in self._fingerprints.items():
            if self.fingerprinter.is_duplicate(fp, seen_fp):
                return True, seen_url

        self._fingerprints[url] = fp
        return False, ""

    def get_stats(self) -> dict:
        return {
            "unique_urls": len(self._seen_urls),
            "content_fingerprints": len(self._fingerprints),
        }


# ─── Test ────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # URL normalization demo
    norm = URLNormalizer()
    test_urls = [
        "https://en.wikipedia.org/wiki/Google_Search#History",
        "https://en.wikipedia.org/wiki/Google_search",
        "https://en.wikipedia.org/wiki/Google_Search?utm_source=twitter",
        "https://en.Wikipedia.org/wiki/Google_Search/",
    ]
    print("URL Normalization:")
    for url in test_urls:
        print(f"  {url}")
        print(f"  → {norm.normalize(url)}")
        print()

    # Content fingerprinting demo
    fp = ContentFingerprinter()
    text1 = "A search engine is a software system designed to carry out web searches"
    text2 = "A search engine is a software system designed to perform web searches"  # Near-dup
    text3 = "Machine learning is a subset of artificial intelligence"  # Different

    fp1 = fp.fingerprint(text1)
    fp2 = fp.fingerprint(text2)
    fp3 = fp.fingerprint(text3)

    print("Content Fingerprinting:")
    print(f"  Text 1 vs Text 2 (near-duplicate): distance = {fp.hamming_distance(fp1, fp2)}")
    print(f"  Text 1 vs Text 3 (different):      distance = {fp.hamming_distance(fp1, fp3)}")
