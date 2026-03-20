#!/usr/bin/env python3
"""
Launch Search Engine Web Interface
====================================
Starts a local Django development server.

Usage:
    python run_web.py              # Starts on http://127.0.0.1:8000
    python run_web.py 8080         # Starts on http://127.0.0.1:8080

Prerequisites:
    1. pip install django
    2. python run_crawler.py --max-pages 50
    3. python build_index.py
"""

import os
import sys


def main():
    # Set Django settings module
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "web_settings")

    # Add current directory to path
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

    # Check prerequisites
    db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "database", "search_engine.db")
    if not os.path.exists(db_path):
        print("ERROR: No database found!")
        print("Run these commands first:")
        print("  python run_crawler.py --max-pages 50")
        print("  python build_index.py")
        sys.exit(1)

    # Check Django is installed
    try:
        import django
    except ImportError:
        print("ERROR: Django is not installed!")
        print("Run: pip install django")
        sys.exit(1)

    # Get port from command line
    port = sys.argv[1] if len(sys.argv) > 1 else "8000"

    print("=" * 60)
    print("  SEARCH ENGINE — Web Interface")
    print("=" * 60)
    print(f"  Open your browser: http://127.0.0.1:{port}")
    print(f"  Press Ctrl+C to stop the server")
    print("=" * 60)

    # Start Django server
    from django.core.management import execute_from_command_line
    execute_from_command_line(["manage.py", "runserver", f"0.0.0.0:{port}", "--noreload"])


if __name__ == "__main__":
    main()
