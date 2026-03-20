"""
URL Configuration
=================
Maps URLs to views. Now includes API endpoint for autocomplete.
"""

from django.urls import path
from web_views import search_view, home_view, stats_view, autocomplete_view

urlpatterns = [
    path("", home_view, name="home"),
    path("search/", search_view, name="search"),
    path("stats/", stats_view, name="stats"),
    path("api/autocomplete/", autocomplete_view, name="autocomplete"),
]
