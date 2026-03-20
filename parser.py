"""
HTML Parser
============
Extracts clean text, links, and images from raw HTML pages.

Now extracts:
- Page title
- Clean text content
- All hyperlinks
- Thumbnail/main image URL (for search result display)
- Meta description
"""

import re
import logging
from urllib.parse import urljoin, urlparse
from typing import NamedTuple

from bs4 import BeautifulSoup

logger = logging.getLogger(__name__)


class ParsedPage(NamedTuple):
    title: str
    clean_text: str
    word_count: int
    links: list[dict]
    meta_description: str
    image_url: str          # NEW: main image for this page


class HTMLParser:
    """
    Parses raw HTML to extract meaningful content.
    Strips navigation, scripts, footers, and other noise.
    """

    NOISE_TAGS = [
        "script", "style", "noscript", "iframe", "svg",
        "nav", "footer", "header", "aside", "form",
    ]

    CONTENT_TAGS = ["article", "main", "section"]

    def parse(self, html: str, base_url: str) -> ParsedPage:
        soup = BeautifulSoup(html, "lxml")

        title = self._extract_title(soup)
        clean_text = self._extract_text(soup)
        word_count = len(clean_text.split())
        links = self._extract_links(soup, base_url)
        meta_desc = self._extract_meta_description(soup)
        image_url = self._extract_image(soup, base_url)

        return ParsedPage(
            title=title,
            clean_text=clean_text,
            word_count=word_count,
            links=links,
            meta_description=meta_desc,
            image_url=image_url,
        )

    def _extract_title(self, soup: BeautifulSoup) -> str:
        if soup.title and soup.title.string:
            return soup.title.string.strip()
        h1 = soup.find("h1")
        if h1:
            return h1.get_text(strip=True)
        return "Untitled"

    def _extract_text(self, soup: BeautifulSoup) -> str:
        soup_copy = BeautifulSoup(str(soup), "lxml")

        for tag_name in self.NOISE_TAGS:
            for tag in soup_copy.find_all(tag_name):
                tag.decompose()

        main_content = None
        for tag_name in self.CONTENT_TAGS:
            main_content = soup_copy.find(tag_name)
            if main_content:
                break

        target = main_content or soup_copy.find("body") or soup_copy
        raw_text = target.get_text(separator=" ", strip=True)
        clean = self._clean_text(raw_text)
        return clean

    def _clean_text(self, text: str) -> str:
        text = re.sub(r"\s+", " ", text)
        text = re.sub(r"[^\w\s.,;:!?'\"\-()[\]{}@#$%&*/+=<>~`\u0600-\u06FF]", "", text)
        return text.strip()

    def _extract_links(self, soup: BeautifulSoup, base_url: str) -> list[dict]:
        links = []
        seen_urls = set()

        for a_tag in soup.find_all("a", href=True):
            href = a_tag["href"].strip()

            if href.startswith(("#", "mailto:", "javascript:", "tel:")):
                continue

            absolute_url = urljoin(base_url, href)
            parsed = urlparse(absolute_url)
            normalized = parsed._replace(fragment="").geturl()

            if normalized in seen_urls:
                continue
            seen_urls.add(normalized)

            if parsed.scheme not in ("http", "https"):
                continue

            anchor_text = a_tag.get_text(strip=True)[:200]

            links.append({
                "url": normalized,
                "anchor_text": anchor_text,
            })

        return links

    def _extract_meta_description(self, soup: BeautifulSoup) -> str:
        meta = soup.find("meta", attrs={"name": "description"})
        if meta and meta.get("content"):
            return meta["content"].strip()[:500]
        return ""

    def _extract_image(self, soup: BeautifulSoup, base_url: str) -> str:
        """
        Extract the main/representative image from the page.
        
        Priority:
        1. og:image meta tag (most reliable — used by social media)
        2. twitter:image meta tag
        3. First content image that's large enough
        """
        # Try og:image first (Open Graph)
        og = soup.find("meta", attrs={"property": "og:image"})
        if og and og.get("content"):
            return og["content"].strip()

        # Try twitter:image
        tw = soup.find("meta", attrs={"name": "twitter:image"})
        if tw and tw.get("content"):
            return tw["content"].strip()

        # Fallback: find first reasonable content image
        # Look inside main content area
        content = soup.find("article") or soup.find("main") or soup.find("body")
        if content:
            for img in content.find_all("img", src=True):
                src = img.get("src", "")
                # Skip tiny icons, logos, badges
                width = img.get("width", "")
                height = img.get("height", "")

                # Skip obviously small images
                try:
                    if width and int(width) < 100:
                        continue
                    if height and int(height) < 100:
                        continue
                except (ValueError, TypeError):
                    pass

                # Skip common non-content images
                src_lower = src.lower()
                skip_patterns = [
                    "icon", "logo", "badge", "button", "arrow",
                    "spacer", "pixel", "tracking", "1x1",
                    "emoji", "flag", "edit", "lock",
                ]
                if any(p in src_lower for p in skip_patterns):
                    continue

                # Make absolute
                absolute = urljoin(base_url, src)
                return absolute

        return ""