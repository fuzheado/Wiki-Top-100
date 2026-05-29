"""Async MediaWiki API enrichment — fetches categories, links, extracts, and page images.

Uses asyncio.Semaphore to cap concurrent requests (default 3) with
exponential backoff on retries. Results are cached to disk (7-day TTL).
"""
import asyncio
from urllib.parse import urlencode

import httpx

from ..config import HEADERS, MAX_CONCURRENT, MW_API, MW_CACHE_TTL
from ..cache import _cache_get, _cache_set


async def fetch_single_metadata(client, title, sem):
    """Fetch categories, outgoing links (ns=0 only), and intro extract for one article.

    Results are cached to disk (7-day TTL) to avoid redundant API calls.
    Uses an asyncio.Semaphore to cap concurrent requests. Retries up to 3 times
    with exponential backoff on failure. pllimit=500 is sufficient for each article.
    """
    cache_key = f"{title}.json"
    cached = _cache_get("mw", cache_key, MW_CACHE_TTL)
    if cached is not None:
        return title, cached

    async with sem:
        params = {
            "action": "query",
            "prop": "categories|links|extracts|pageimages",
            "titles": title,
            "format": "json",
            "cllimit": 200,
            "pllimit": 500,
            "exintro": 1,
            "explaintext": 1,
            "exchars": 800,
            "piprop": "thumbnail",
            "pithumbsize": 300,
        }
        url = f"{MW_API}?{urlencode(params)}"
        for attempt in range(3):
            try:
                resp = await client.get(url, timeout=15.0)
                resp.raise_for_status()
                data = resp.json()
                pages = data.get("query", {}).get("pages", {})
                for pid, info in pages.items():
                    if int(pid) < 0:
                        result = {"categories": [], "links": [], "extract": ""}
                        _cache_set("mw", cache_key, result)
                        return title, result
                    cats = []
                    for c in info.get("categories", []):
                        ct = c.get("title", "")
                        if ct.startswith("Category:"):
                            cats.append(ct[len("Category:"):])
                    links = []
                    for l in info.get("links", []):
                        if l.get("ns") == 0:
                            links.append(l.get("title", "").replace(" ", "_"))
                    extract = info.get("extract", "")
                    thumbnail = info.get("thumbnail", {})
                    page_image_url = thumbnail.get("source", "") if thumbnail else ""
                    result = {"categories": cats, "links": links, "extract": extract, "page_image_url": page_image_url}
                    _cache_set("mw", cache_key, result)
                    return title, result
            except Exception as e:
                delay = 0.5 * (2 ** attempt)
                if attempt < 2:
                    await asyncio.sleep(delay)
                else:
                    print(f"  Failed to fetch {title}: {e}")
                    return title, {"categories": [], "links": [], "extract": ""}
        return title, {"categories": [], "links": [], "extract": ""}


async def fetch_all_metadata(titles, max_concurrent=None, progress_callback=None, headers=None):
    """Fetch metadata for all articles concurrently with a concurrency limit.

    Reports progress via progress_callback after each article completes.
    Uses asyncio.as_completed to surface results incrementally.
    Returns a dict mapping article IDs to {categories, links, extract}.
    """
    if max_concurrent is None:
        max_concurrent = MAX_CONCURRENT
    if headers is None:
        headers = HEADERS
    sem = asyncio.Semaphore(max_concurrent)
    total = len(titles)
    async with httpx.AsyncClient(headers=HEADERS) as client:
        tasks = [fetch_single_metadata(client, t, sem) for t in titles]
        results = {}
        for i, coro in enumerate(asyncio.as_completed(tasks)):
            title, meta = await coro
            results[title] = meta
            if progress_callback and (i + 1) % 5 == 0:
                progress_callback(f"Fetched article metadata ({i + 1}/{total})")
            elif progress_callback and i == 0:
                progress_callback(f"Fetched article metadata ({i + 1}/{total})")
        return results
