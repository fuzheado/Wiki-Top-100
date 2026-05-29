#!/usr/bin/env python3
"""Backward-compatible entry point. All logic lives in wikigraph.*.

This file exists so existing scripts and imports continue to work
without changes. New code should import from the wikigraph package
directly:

    from wikigraph import build_graph, latest_available_date
"""
from wikigraph.pipeline import build_graph, latest_available_date, main
from wikigraph.config import CACHE_DIR

# Re-export everything the test suite imports
from wikigraph.analyzer.categories import is_meaningful_category, MAINT_CAT_PATTERNS
from wikigraph.analyzer.clustering import assign_cluster, TOPIC_KEYWORDS, CLUSTER_COLORS
from wikigraph.analyzer.ner import normalize_entity, extract_entities
from wikigraph.graph.builder import (
    build_graph_nodes, add_wikilink_edges,
    add_category_helpers, add_entity_helpers, HELPER_COLOR,
)
from wikigraph.graph.serializers import serialize_graph
from wikigraph.cache import _cache_get, _cache_set
from wikigraph.sources.hatnote import fetch_json, fetch_top100, SKIP_PREFIXES
from wikigraph.enricher.mw_api import fetch_single_metadata, fetch_all_metadata
from wikigraph.config import _load_dotenv, _is_valid_ua, HEADERS


if __name__ == "__main__":
    main()
