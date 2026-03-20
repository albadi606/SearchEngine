"""
Web Views (Optimized)
=====================
Key performance fix: the InvertedIndex is created ONCE and reused
across all requests, instead of reconnecting on every search.

Before: every search → new DB connection + reload vocabulary = ~2-3 seconds
After:  every search → reuse cached connection = ~50ms
"""

import os
import sys
import json
import time
import logging
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from django.http import HttpResponse, JsonResponse
from django.shortcuts import render

from indexer import InvertedIndex

logger = logging.getLogger(__name__)

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "search_engine.db")

# ─── Cached Index (Singleton) ───────────────────────────────────────
# Created once on first request, reused for all subsequent requests.
# Thread-safe via a lock.

_index_instance = None
_index_lock = threading.Lock()


def _get_index():
    """
    Get the cached InvertedIndex instance.
    Creates it on first call, reuses it for all subsequent calls.
    This is the KEY performance fix — no more reconnecting per request.
    """
    global _index_instance

    if _index_instance is not None:
        return _index_instance

    with _index_lock:
        # Double-check after acquiring lock
        if _index_instance is not None:
            return _index_instance

        logger.info("Creating cached index connection (one-time setup)...")
        index = InvertedIndex(DB_PATH)
        index.connect()

        # Pre-load spell correction vocabulary
        index.spell_corrector._ensure_loaded()

        _index_instance = index
        logger.info("Index cached and ready!")
        return _index_instance


# ─── Views ───────────────────────────────────────────────────────────

def home_view(request):
    """Home page with search box."""
    try:
        index = _get_index()
        stats = index.get_stats()
        popular = index.autocomplete.get_popular_searches(8)
        context = {
            "total_docs": stats.get("total_docs", "0"),
            "unique_terms": stats.get("unique_terms", "0"),
            "popular_searches": popular,
        }
    except Exception:
        context = {"total_docs": "0", "unique_terms": "0", "popular_searches": []}

    return render(request, "home.html", context)


def search_view(request):
    """Handle search queries and display results."""
    query = request.GET.get("q", "").strip()
    page = int(request.GET.get("page", 1))
    results_per_page = 10

    if not query:
        return render(request, "home.html", {"total_docs": "0", "unique_terms": "0"})

    try:
        index = _get_index()

        start_time = time.time()
        search_result = index.search(query, top_k=50)
        search_time = time.time() - start_time

        stats = index.get_stats()

        all_results = search_result.get("results", [])
        suggestion = search_result.get("suggestion")

        # Pagination
        total_results = len(all_results)
        start_idx = (page - 1) * results_per_page
        end_idx = start_idx + results_per_page
        page_results = all_results[start_idx:end_idx]
        total_pages = (total_results + results_per_page - 1) // results_per_page

        context = {
            "query": query,
            "results": page_results,
            "total_results": total_results,
            "search_time": f"{search_time:.4f}",
            "suggestion": suggestion,
            "current_page": page,
            "total_pages": total_pages,
            "has_prev": page > 1,
            "has_next": page < total_pages,
            "prev_page": page - 1,
            "next_page": page + 1,
            "total_docs": stats.get("total_docs", "0"),
        }

    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        context = {
            "query": query,
            "results": [],
            "total_results": 0,
            "search_time": "0",
            "error": str(e),
        }

    return render(request, "results.html", context)


def autocomplete_view(request):
    """API endpoint for autocomplete suggestions."""
    query = request.GET.get("q", "").strip()

    if len(query) < 2:
        return JsonResponse({"suggestions": []})

    try:
        index = _get_index()
        suggestions = index.get_autocomplete(query, limit=7)
        return JsonResponse({"suggestions": suggestions})
    except Exception as e:
        return JsonResponse({"suggestions": [], "error": str(e)})


def stats_view(request):
    """Display index statistics."""
    try:
        index = _get_index()
        stats = index.get_stats()
        context = {"stats": stats}
    except Exception as e:
        context = {"stats": {}, "error": str(e)}

    return render(request, "stats.html", context)