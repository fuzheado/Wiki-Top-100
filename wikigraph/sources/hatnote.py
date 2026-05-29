"""Hatnote API data source — fetches the daily top 100 Wikipedia articles.

Filters out non-article pages (Special:, Wikipedia:, Talk:, etc.).
Results are cached for 24 hours.
"""
import time
import httpx

from ..config import HEADERS, HATNOTE_URL, HATNOTE_CACHE_TTL
from ..cache import _cache_get, _cache_set


SKIP_PREFIXES = {"Special", "Wikipedia", "Talk", "User", "Help", "File", "Template",
                 "Category", "Portal", "Draft", "Module", "MediaWiki"}


def fetch_json(url, max_retries=2):
    """Fetch and parse JSON from a URL with a timeout, user-agent, and retries."""
    for attempt in range(max_retries + 1):
        try:
            with httpx.Client(headers=HEADERS, timeout=30.0) as client:
                resp = client.get(url)
                resp.raise_for_status()
                return resp.json()
        except Exception as e:
            if attempt < max_retries:
                time.sleep(0.5)
            else:
                raise


def fetch_top100(year, month, day):
    """Fetch the top 100 list from the Hatnote API (cached for 24h).

    Filters out Special:, Wikipedia:, Talk:, and other non-article pages.
    Returns a list of dicts with id, title, rank, views, summary, image_url, url.
    Article IDs use underscores (matching Wikipedia URL convention).
    """
    cache_key = f"{year}-{month}-{day}.json"
    cached = _cache_get("hatnote", cache_key, HATNOTE_CACHE_TTL)
    if cached is not None:
        return cached

    url = HATNOTE_URL.format(year=year, month=month, day=day)
    data = fetch_json(url)
    articles = []
    for a in data["articles"]:
        title = a["article"]
        prefix = title.split(":")[0]
        if prefix in SKIP_PREFIXES or title == "Main_Page":
            continue
        articles.append({
            "id": title.replace(" ", "_"),
            "title": a["title"],
            "rank": a["rank"],
            "views": a["views"],
            "summary": a.get("summary", ""),
            "image_url": a.get("image_url", ""),
            "url": a.get("url", f"https://en.wikipedia.org/wiki/{title}"),
            "history": a.get("history", []),
        })

    _cache_set("hatnote", cache_key, articles)
    return articles
