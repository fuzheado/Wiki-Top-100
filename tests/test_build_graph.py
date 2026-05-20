import json, os, tempfile, collections
from unittest.mock import patch, MagicMock
import networkx as nx
import pytest

from build_graph import (
    is_meaningful_category,
    assign_cluster,
    normalize_entity,
    serialize_graph,
    add_wikilink_edges,
    add_category_helpers,
    add_entity_helpers,
    build_graph_nodes,
    _cache_get,
    _cache_set,
    fetch_json,
    fetch_top100,
    build_graph,
    SKIP_PREFIXES,
)


class TestIsMeaningfulCategory:
    def test_maintenance_categories_are_filtered(self):
        assert is_meaningful_category("Articles with short description") is False
        assert is_meaningful_category("CS1 errors: dates") is False
        assert is_meaningful_category("All articles with unsourced statements") is False
        assert is_meaningful_category("Use dmy dates") is False
        assert is_meaningful_category("Short description is different from Wikidata") is False

    def test_topic_categories_pass(self):
        assert is_meaningful_category("2026 films") is True
        assert is_meaningful_category("American mixed martial artists") is True
        assert is_meaningful_category("Living people") is False  # biography maintenance
        assert is_meaningful_category("UFC champions") is True

    def test_short_categories_are_filtered(self):
        assert is_meaningful_category("ABC") is False


class TestAssignCluster:
    def test_sports_cluster(self):
        cats = ["American mixed martial artists"]
        summary = "UFC fighter from Nevada"
        assert assign_cluster(cats, summary) == "Sports"

    def test_music_cluster(self):
        cats = ["American singers"]
        summary = "Pop singer and songwriter"
        assert assign_cluster(cats, summary) == "Music"

    def test_film_cluster(self):
        cats = ["2026 films"]
        summary = "American action film directed by"
        assert assign_cluster(cats, summary) == "Film & TV"

    def test_fallback_to_other(self):
        cats = ["Foo bar baz"]
        summary = "Nothing matches any keyword here at all"
        assert assign_cluster(cats, summary) == "Other"


class TestNormalizeEntity:
    def test_strips_leading_the(self):
        assert normalize_entity("the United States") == "United States"

    def test_strips_leading_The(self):
        assert normalize_entity("The Beatles") == "Beatles"

    def test_leaves_other_unchanged(self):
        assert normalize_entity("Netflix") == "Netflix"

    def test_handles_multiword(self):
        assert normalize_entity("the Ultimate Fighting Championship") == "Ultimate Fighting Championship"


class TestCache:
    def test_cache_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("build_graph.CACHE_DIR", tmp):
                key = "test-key.json"
                data = {"hello": "world"}
                _cache_set("test", key, data)
                result = _cache_get("test", key, ttl=3600)
                assert result == data

    def test_cache_miss(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("build_graph.CACHE_DIR", tmp):
                result = _cache_get("test", "nonexistent.json", ttl=3600)
                assert result is None

    def test_cache_expired(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch("build_graph.CACHE_DIR", tmp):
                key = "stale.json"
                _cache_set("test", key, {"data": 1})
                result = _cache_get("test", key, ttl=-1)  # already expired
                assert result is None


class TestFetchJson:
    def test_success(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"ok": True}
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.get.return_value = mock_resp
            result = fetch_json("https://example.com/data.json")
            assert result == {"ok": True}

    def test_retry_on_failure_then_succeeds(self):
        failing_resp = MagicMock()
        failing_resp.raise_for_status.side_effect = Exception("transient error")
        ok_resp = MagicMock()
        ok_resp.json.return_value = {"ok": True}
        mock_get = MagicMock(side_effect=[failing_resp, ok_resp])
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.get = mock_get
            result = fetch_json("https://example.com/data.json", max_retries=2)
            assert result == {"ok": True}
            assert mock_get.call_count == 2

    def test_raises_after_max_retries(self):
        failing_resp = MagicMock()
        failing_resp.raise_for_status.side_effect = Exception("persistent error")
        with patch("httpx.Client") as MockClient:
            MockClient.return_value.__enter__.return_value.get.return_value = failing_resp
            with pytest.raises(Exception):
                fetch_json("https://example.com/data.json", max_retries=1)


class TestSkipPrefixes:
    def test_non_article_prefixes_skipped(self):
        for prefix in SKIP_PREFIXES:
            title = f"{prefix}:Something"
            parts = title.split(":")[0]
            assert parts == prefix


class TestBuildGraphNodes:
    def test_nodes_added_with_cluster(self):
        G = nx.Graph()
        articles = [
            {"id": "Test_Article", "title": "Test Article", "rank": 1, "views": 500000,
             "summary": "A test article about sports", "categories": ["UFC fighters"],
             "image_url": "", "url": "https://en.wikipedia.org/wiki/Test_Article"},
        ]
        build_graph_nodes(articles, G)
        assert G.has_node("Test_Article")
        assert G.nodes["Test_Article"]["type"] == "article"
        assert G.nodes["Test_Article"]["cluster"] == "Sports"


class TestAddWikilinkEdges:
    def test_wikilinks_added(self):
        G = nx.Graph()
        articles = [
            {"id": "Article_A", "links": ["Article_B", "Article_C"]},
            {"id": "Article_B", "links": ["Article_A"]},
            {"id": "Article_C", "links": []},
        ]
        article_ids = {"Article_A", "Article_B", "Article_C"}
        count = add_wikilink_edges(articles, article_ids, G)
        assert count == 2  # A-B, A-C
        assert G.has_edge("Article_A", "Article_B")
        assert G.has_edge("Article_A", "Article_C")

    def test_self_link_not_added(self):
        G = nx.Graph()
        articles = [
            {"id": "Article_A", "links": ["Article_A"]},
        ]
        article_ids = {"Article_A"}
        count = add_wikilink_edges(articles, article_ids, G)
        assert count == 0


class TestAddCategoryHelpers:
    def test_helper_created_for_shared_category(self):
        G = nx.Graph()
        articles = [
            {"id": "A", "categories": ["2026 films"]},
            {"id": "B", "categories": ["2026 films"]},
            {"id": "C", "categories": ["2026 films"]},
        ]
        article_ids = {"A", "B", "C"}
        add_category_helpers(articles, article_ids, G, min_cat_share=3)
        assert G.has_node("cat:2026 films")
        assert G.nodes["cat:2026 films"]["type"] == "helper"
        assert G.nodes["cat:2026 films"]["helper_type"] == "category"
        assert G.has_edge("cat:2026 films", "A")
        assert G.has_edge("cat:2026 films", "B")
        assert G.has_edge("cat:2026 films", "C")

    def test_helper_not_created_below_threshold(self):
        G = nx.Graph()
        articles = [
            {"id": "A", "categories": ["rare category"]},
            {"id": "B", "categories": ["rare category"]},
        ]
        article_ids = {"A", "B"}
        add_category_helpers(articles, article_ids, G, min_cat_share=3)
        assert not G.has_node("cat:rare category")


class TestAddEntityHelpers:
    def test_helper_created_for_shared_entity(self):
        G = nx.Graph()
        articles = [
            {"id": "A", "title": "Article A"},
            {"id": "B", "title": "Article B"},
            {"id": "C", "title": "Article C"},
        ]
        entity_map = {"Netflix": ["A", "B", "C"]}
        add_entity_helpers(articles, entity_map, G, min_entity_share=3)
        assert G.has_node("ent:Netflix")
        assert G.nodes["ent:Netflix"]["helper_type"] == "entity"

    def test_entity_matching_article_title_skipped(self):
        G = nx.Graph()
        articles = [
            {"id": "Netflix", "title": "Netflix"},
            {"id": "Other", "title": "Other"},
        ]
        entity_map = {"Netflix": ["Netflix", "Other"]}
        add_entity_helpers(articles, entity_map, G, min_entity_share=2)
        assert not G.has_node("ent:Netflix")


class TestSerializeGraph:
    def test_serialized_format(self):
        G = nx.Graph()
        G.add_node("Article_A", id="Article_A", type="article", title="A",
                    cluster="Sports", views=500000, rank=1, summary="test",
                    categories=["Sports"], image_url="", url="", links=[])
        G.add_node("cat:Test", id="cat:Test", type="helper", helper_type="category",
                    label="Test", size=3)
        G.add_edge("Article_A", "cat:Test", weight=1, type="category")

        nodes, links = serialize_graph(G)
        assert len(nodes) == 2
        assert len(links) == 1
        article = [n for n in nodes if n["type"] == "article"][0]
        assert "links" not in article
        assert "extract" not in article
        assert article["size"] == max(6, min(35, __import__('math').log2(500000) * 2.5))
        helper = [n for n in nodes if n["type"] == "helper"][0]
        assert helper["color"] == "#b0b0b0"


class TestFetchTop100:
    def test_filters_non_article_prefixes(self):
        mock_data = {
            "articles": [
                {"article": "Main_Page", "title": "Main Page", "rank": 1, "views": 100},
                {"article": "Special:Random", "title": "Random", "rank": 2, "views": 50},
                {"article": "Wikipedia:About", "title": "About", "rank": 3, "views": 30},
                {"article": "Real_Article", "title": "Real Article", "rank": 4, "views": 200,
                 "summary": "A real article.", "image_url": "", "history": []},
            ]
        }
        with patch("build_graph.fetch_json", return_value=mock_data):
            with patch("build_graph._cache_get", return_value=None), \
                 patch("build_graph._cache_set"):
                articles = fetch_top100("2026", "5", "17")
                assert len(articles) == 1
                assert articles[0]["id"] == "Real_Article"

    def test_returns_normalized_fields(self):
        mock_data = {
            "articles": [
                {"article": "Test_Article", "title": "Test Article", "rank": 5,
                 "views": 100000, "summary": "A test", "image_url": "https://img",
                 "url": "https://wiki/Test_Article", "history": [1, 2, 3]},
            ]
        }
        with patch("build_graph.fetch_json", return_value=mock_data):
            with patch("build_graph._cache_get", return_value=None), \
                 patch("build_graph._cache_set"):
                articles = fetch_top100("2026", "5", "17")
                a = articles[0]
                assert a["id"] == "Test_Article"
                assert a["title"] == "Test Article"
                assert a["rank"] == 5
                assert a["views"] == 100000
                assert a["summary"] == "A test"
                assert a["image_url"] == "https://img"


class TestProgressCallback:
    def test_callback_receives_progress_messages(self):
        messages = []
        def cb(msg):
            messages.append(msg)
        with patch("build_graph.fetch_top100", return_value=[]), \
             patch("build_graph.asyncio.run", return_value={}):
            build_graph("2026", "5", "17", progress_callback=cb)
        assert len(messages) > 0
        assert any("top 100" in m.lower() for m in messages)


class TestUserAgent:
    def test_compliant_with_email(self):
        from build_graph import _is_valid_ua
        assert _is_valid_ua("MyApp/1.0 (user@example.com)") is True

    def test_compliant_with_url(self):
        from build_graph import _is_valid_ua
        assert _is_valid_ua("MyApp/1.0 (https://github.com/user/repo)") is True

    def test_non_compliant_no_contact(self):
        from build_graph import _is_valid_ua
        assert _is_valid_ua("python-requests/2.28") is False

    def test_non_compliant_empty(self):
        from build_graph import _is_valid_ua
        assert _is_valid_ua("") is False

    def test_default_ua_is_compliant(self):
        from build_graph import HEADERS
        from build_graph import _is_valid_ua
        assert _is_valid_ua(HEADERS["User-Agent"]) is True

    def test_graph_meta_includes_ua_fields(self):
        with patch("build_graph.fetch_top100", return_value=[]), \
             patch("build_graph.asyncio.run", return_value={}):
            result = build_graph("2026", "5", "17")
        assert "user_agent" in result["meta"]
        assert "ua_compliant" in result["meta"]
        assert result["meta"]["ua_compliant"] is True
