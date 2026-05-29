"""Pipeline orchestration — the main build_graph() function.

Coordinates the full pipeline: fetch → enrich → analyze → build → export.
Can be called programmatically (from server.py) or via CLI.
"""
import json
import sys
import asyncio

import networkx as nx

from .config import _is_valid_ua, HEADERS, MAX_CONCURRENT
from .sources.hatnote import fetch_top100
from .enricher.mw_api import fetch_all_metadata
from .analyzer.categories import is_meaningful_category
from .analyzer.ner import extract_entities
from .graph.builder import (
    build_graph_nodes,
    add_wikilink_edges,
    add_category_helpers,
    add_entity_helpers,
)
from .graph.serializers import serialize_graph


def build_graph(year, month, day, min_entity_share=3, verbose=True,
                ignore_articles=None, progress_callback=None, user_agent=None):
    """Run the full pipeline: fetch → enrich → analyze → build → export.

    Returns the graph data dict with meta, nodes, and links keys.
    Can be called programmatically from server.py or as a CLI script.
    Accepts an optional progress_callback(msg) for streaming status updates.
    Accepts an optional user_agent override for MW API requests.
    """
    def log(msg):
        if verbose:
            print(msg)
        if progress_callback:
            progress_callback(msg)

    ua = user_agent or HEADERS["User-Agent"]
    if not _is_valid_ua(ua):
        log("WARNING: User-Agent may not be Wikimedia-compliant (no email or URL).")
        log("WARNING: Set WIKI_USER_AGENT env var or add .env file.")
        log("WARNING: Non-compliant User-Agent strings may be rate-limited by the MediaWiki API.")
    ua_ok = _is_valid_ua(ua)

    headers = {"User-Agent": ua}

    log(f"Fetching top 100 for {year}/{month}/{day}...")
    articles = fetch_top100(year, month, day)
    if ignore_articles:
        ignore_set = {a.lower().replace(" ", "_") for a in ignore_articles}
        ignore_titles = {a.lower() for a in ignore_articles}
        filtered = []
        for a in articles:
            if a["id"].lower() not in ignore_set and a["title"].lower() not in ignore_titles:
                filtered.append(a)
        removed = [a["title"] for a in articles if a not in filtered]
        log(f"Ignored {len(articles) - len(filtered)} articles: {', '.join(removed)}")
        articles = filtered
    log(f"Got {len(articles)} articles")

    titles = [a["id"] for a in articles]
    log("Fetching article metadata (async, 5 concurrent)...")
    metadata = asyncio.run(fetch_all_metadata(
        titles, max_concurrent=MAX_CONCURRENT,
        progress_callback=progress_callback, headers=headers))
    log(f"Got metadata for {len(metadata)} articles")

    failed_articles = []
    for a in articles:
        meta = metadata.get(a["id"], {})
        all_cats = meta.get("categories", [])
        a["categories"] = [c for c in all_cats if is_meaningful_category(c)]
        a["links"] = meta.get("links", [])
        a["extract"] = meta.get("extract", "")
        a["page_image_url"] = meta.get("page_image_url", "")
        if not all_cats and not a["links"] and len(a["extract"]) < 50:
            failed_articles.append(a["title"])

    meaningful_cat_count = sum(len(a["categories"]) for a in articles)
    link_count_total = sum(len(a["links"]) for a in articles)
    log(f"  {meaningful_cat_count} meaningful categories, {link_count_total} total links across all articles")

    log("Extracting named entities with spaCy...")
    texts = {}
    for a in articles:
        t = (a.get("summary", "") + " " + a.get("extract", "")).strip()
        if t:
            texts[a["id"]] = t
    entity_map, _ = extract_entities(texts)
    log(f"Found {len(entity_map)} unique named entities")

    log("Building graph...")
    G = nx.Graph()
    article_ids = {a["id"] for a in articles}

    build_graph_nodes(articles, G)
    n_wiki = add_wikilink_edges(articles, article_ids, G)
    log(f"  {n_wiki} direct wikilink edges between top 100 articles")

    add_category_helpers(articles, article_ids, G, min_cat_share=3)
    add_entity_helpers(articles, entity_map, G, min_entity_share=min_entity_share)

    nodes_data, links_data = serialize_graph(G)

    output = {
        "meta": {
            "date": f"{year}-{month}-{day}",
            "total_articles": len(articles),
            "total_nodes": len(nodes_data),
            "total_edges": len(links_data),
            "user_agent": ua,
            "ua_compliant": ua_ok,
            "failed_articles": failed_articles,
            "failed_count": len(failed_articles),
        },
        "nodes": nodes_data,
        "links": links_data,
    }

    if verbose:
        n_articles = sum(1 for n in nodes_data if n.get("type") == "article")
        n_helpers = sum(1 for n in nodes_data if n.get("type") == "helper")
        n_cat = sum(1 for n in nodes_data if n.get("helper_type") == "category")
        n_ent = sum(1 for n in nodes_data if n.get("helper_type") == "entity")
        n_wiki_e = sum(1 for l in links_data if l["type"] == "wikilink")
        n_cats = sum(1 for l in links_data if l["type"] == "category")
        n_ents = sum(1 for l in links_data if l["type"] == "entity")
        log(f"  {n_articles} articles + {n_helpers} helpers ({n_cat} categories, {n_ent} entities) = {len(nodes_data)} nodes")
        log(f"  {len(links_data)} edges ({n_wiki_e} wikilinks, {n_cats} cat, {n_ents} ent)")

    return output


def latest_available_date():
    """Walk backwards from today to find a date with Hatnote data."""
    from datetime import date, timedelta

    from .config import HATNOTE_URL
    from .sources.hatnote import fetch_json

    d = date.today()
    for _ in range(7):
        url = HATNOTE_URL.format(year=d.year, month=d.month, day=d.day)
        try:
            fetch_json(url)
            return str(d.year), str(d.month), str(d.day)
        except Exception:
            d -= timedelta(days=1)
    return "2026", "5", "18"


def main():
    """CLI entry point: builds graph and saves to a file."""
    year, month, day = sys.argv[1:4] if len(sys.argv) >= 4 else latest_available_date()
    out_file = sys.argv[4] if len(sys.argv) >= 5 else "graph_data.json"
    min_entity_share = int(sys.argv[5]) if len(sys.argv) >= 6 else 3

    output = build_graph(year, month, day, min_entity_share)

    with open(out_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"Graph saved to {out_file}")


if __name__ == "__main__":
    main()
