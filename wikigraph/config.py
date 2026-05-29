"""Configuration management via environment variables and .env file.

Loads settings at module import time. All constants are available for
direct import by other modules.
"""
import os
import re
from pathlib import Path


def _load_dotenv():
    """Load .env file if present, populating os.environ (does not override)."""
    env_path = Path(".env")
    if env_path.exists():
        for line in env_path.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key, val = key.strip(), val.strip().strip("\"'")
            os.environ.setdefault(key, val)


def _is_valid_ua(ua):
    """Check if a User-Agent string appears Wikimedia-compliant (has contact info).

    Wikimedia requires User-Agent strings to include a way to contact the
    developer — either an email address or a project URL. Returns True if
    the string contains an email or http(s) URL.
    """
    return bool(re.search(r'[^@\s]+@[^@\s]+\.[^@\s]+|https?://\S+', ua))


# Load .env at import time (matches original build_graph.py behaviour)
_load_dotenv()


HATNOTE_URL = os.environ.get("WIKI_HATNOTE_URL",
    "https://top.hatnote.com/en/wikipedia/{year}/{month}/{day}.json")
MW_API = os.environ.get("WIKI_MW_API",
    "https://en.wikipedia.org/w/api.php")
_DEFAULT_UA = "WikiTop100Viz/1.0 (contact: andrew.lih@gmail.com)"
HEADERS = {"User-Agent": os.environ.get("WIKI_USER_AGENT", _DEFAULT_UA)}
MAX_CONCURRENT = int(os.environ.get("WIKI_MAX_CONCURRENT", "3"))
CACHE_DIR = os.environ.get("WIKI_CACHE_DIR", ".cache")
HATNOTE_CACHE_TTL = int(os.environ.get("WIKI_HATNOTE_CACHE_TTL", "86400"))  # 24h
MW_CACHE_TTL = int(os.environ.get("WIKI_MW_CACHE_TTL", "604800"))  # 7d
