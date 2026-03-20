"""
Search Engine Configuration
===========================
Multi-source search engine with 11 verified domains.

All domains below have been manually verified via robots.txt
to allow educational crawling on their article/content pages.

Sources:
    - Wikipedia (general knowledge)
    - MDN Web Docs (web/security documentation)
    - Python Docs (Python documentation)
    - Times of Oman (Omani news)
    - Oman Observer (Omani news)
    - Muscat Daily (Omani news)
    - Visit Oman (tourism)
    - Oman Air (airline)
    - Experience Oman (tourism/culture)
    - Oman Info (government portal)
    - UN Mission of Oman (international)
"""

import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# ─── Crawler Settings ────────────────────────────────────────────────
CRAWLER = {
    # Seed URLs — starting points across all verified sources
    "seed_urls": [
        # ── Wikipedia (general knowledge) ──
        "https://en.wikipedia.org/wiki/Web_search_engine",
        "https://en.wikipedia.org/wiki/Cybersecurity",
        "https://en.wikipedia.org/wiki/Machine_learning",
        "https://en.wikipedia.org/wiki/Artificial_intelligence",
        "https://en.wikipedia.org/wiki/Computer_network",
        "https://en.wikipedia.org/wiki/Information_retrieval",
        "https://en.wikipedia.org/wiki/Oman",
        "https://en.wikipedia.org/wiki/Muscat,_Oman",

        # ── MDN Web Docs (tech/security) ──
        "https://developer.mozilla.org/en-US/docs/Web/HTTP",
        "https://developer.mozilla.org/en-US/docs/Web/Security",
        "https://developer.mozilla.org/en-US/docs/Web/JavaScript",
        "https://developer.mozilla.org/en-US/docs/Learn/Server-side/Django",

        # ── Python Docs ──
        "https://docs.python.org/3/tutorial/index.html",
        "https://docs.python.org/3/library/index.html",

        # ── Times of Oman (news) ──
        "https://timesofoman.com/",

        # ── Oman Observer (news) ──
        "https://www.omanobserver.om/",

        # ── Muscat Daily (news) ──
        "https://www.muscatdaily.com/",

        # ── Visit Oman (tourism) ──
        "https://visitoman.om/",

        # ── Oman Air ──
        "https://www.omanair.com/",

        # ── Experience Oman (culture/tourism) ──
        "https://experienceoman.om/",

        # ── Oman Info (government portal) ──
        "https://www.omaninfo.om/",

        # ── UN Mission of Oman ──
        "https://www.un.int/oman/",
    ],

    "max_pages": 200,
    "max_depth": 3,

    # Default politeness delay (overridden per-domain below)
    "politeness_delay": 1.0,

    "max_concurrent_requests": 5,
    "request_timeout": 15,
    "user_agent": "SearchEngineBot/1.0 (Educational Project by Mohammed Al-Badi; +https://github.com/albadi606/SearchEngine)",
    "respect_robots_txt": True,

    # ── Allowed Domains ──────────────────────────────────────────
    # Only crawl within these domains (verified via robots.txt)
    "allowed_domains": [
        "en.wikipedia.org",
        "developer.mozilla.org",
        "docs.python.org",
        "timesofoman.com",
        "www.omanobserver.om",
        "www.muscatdaily.com",
        "visitoman.om",
        "www.omanair.com",
        "experienceoman.om",
        "www.omaninfo.om",
        "www.un.int",
    ],

    # ── Per-Domain Politeness Delays ─────────────────────────────
    # Some sites require longer delays (from their robots.txt)
    "domain_delays": {
        "www.un.int": 10.0,          # robots.txt specifies Crawl-delay: 10
        "en.wikipedia.org": 1.0,
        "developer.mozilla.org": 1.0,
        "docs.python.org": 1.0,
        "timesofoman.com": 2.0,      # Be extra polite to news sites
        "www.omanobserver.om": 2.0,
        "www.muscatdaily.com": 2.0,
        "visitoman.om": 2.0,
        "www.omanair.com": 2.0,
        "experienceoman.om": 2.0,
        "www.omaninfo.om": 2.0,
    },

    # ── Blocked Paths Per Domain ─────────────────────────────────
    # Paths that robots.txt says to avoid
    "blocked_paths": {
        "developer.mozilla.org": ["/api/", "/media"],
        "docs.python.org": ["/dev", "/release", "/2/", "/2.", "/3.0/", "/3.1/",
                            "/3.2/", "/3.3/", "/3.4/", "/3.5/", "/3.6/",
                            "/3.7/", "/3.8/"],
        "timesofoman.com": ["/ajax/", "/search", "/article.php", "/login-mgt",
                            "/archive/", "/widget/"],
        "www.omanobserver.om": ["/ajax/", "/search", "/article.php", "/login-mgt",
                                "/archive/", "/widget/"],
        "www.un.int": ["/includes/", "/misc/", "/modules/", "/profiles/",
                       "/scripts/", "/themes/", "/admin/", "/search/",
                       "/user/register/", "/user/password/", "/user/login/"],
    },

    # File extensions to skip
    "skip_extensions": [
        ".jpg", ".jpeg", ".png", ".gif", ".svg", ".webp",
        ".pdf", ".doc", ".docx", ".xls", ".xlsx",
        ".zip", ".tar", ".gz", ".rar",
        ".mp3", ".mp4", ".avi", ".mov",
        ".css", ".js", ".json", ".xml",
    ],
}

# ─── Database Settings ───────────────────────────────────────────────
DATABASE = {
    "path": os.path.join(BASE_DIR, "database", "search_engine.db"),
}

SCHEMA_PATH = os.path.join(BASE_DIR, "database", "schema.sql")

# ─── Search Optimization Settings ────────────────────────────────────
SEARCH = {
    "max_edit_distance": 2,
    "min_suggestion_freq": 2,
    "autocomplete_limit": 7,
    "enable_spell_correction": True,
}

# ─── Logging Settings ────────────────────────────────────────────────
LOGGING = {
    "level": "INFO",
    "format": "%(asctime)s | %(levelname)-8s | %(name)-20s | %(message)s",
    "date_format": "%Y-%m-%d %H:%M:%S",
}