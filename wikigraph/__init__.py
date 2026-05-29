"""wikigraph — build connection graphs from Wikipedia/Wikimedia data.

Package modules:
    config      — environment variable and .env configuration
    cache       — file-based JSON cache with TTL
    sources     — data source plugins (Hatnote API, article lists, etc.)
    enricher    — MediaWiki API async batch enrichment
    analyzer    — NER, category filtering, and topic clustering
    graph       — NetworkX graph construction and serialization
    pipeline    — main build_graph() orchestration and CLI entry point
"""
from .pipeline import build_graph, latest_available_date, main
from .config import CACHE_DIR
