"""File-based JSON cache with configurable TTL.

Two-layer cache (hatnote, mw) used by the pipeline to avoid redundant
API calls on repeated builds for the same date.
"""
import json
import time
from pathlib import Path

from .config import CACHE_DIR


def _cache_get(cache_type, key, ttl):
    """Load cached JSON if fresh, else return None."""
    path = Path(CACHE_DIR, cache_type, key)
    if not path.exists():
        return None
    if time.time() - path.stat().st_mtime > ttl:
        return None
    with open(path) as f:
        return json.load(f)


def _cache_set(cache_type, key, data):
    """Save JSON to cache, creating directories as needed."""
    path = Path(CACHE_DIR, cache_type, key)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        json.dump(data, f)
