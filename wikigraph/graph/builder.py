"""NetworkX graph construction — article nodes, wikilink edges, and helper nodes.

Builds a graph from enriched article data with three connection types:
wikilinks, shared categories, and shared named entities. Helper nodes
for categories and entities serve as visual intermediaries.
"""
import collections

from ..analyzer.clustering import assign_cluster


HELPER_COLOR = "#b0b0b0"


def build_graph_nodes(articles, G):
    """Add article nodes to the graph with cluster assignments and metadata."""
    for a in articles:
        a["cluster"] = assign_cluster(a.get("categories", []), a.get("summary", ""))
        G.add_node(a["id"], **a, type="article")


def add_wikilink_edges(articles, article_ids, G):
    """Add edges for direct wikilinks between top 100 articles.

    Links are identified by matching outgoing links from each article's
    MediaWiki data against the set of target article IDs.
    """
    link_weight = collections.defaultdict(int)
    for a in articles:
        for link in a.get("links", []):
            if link in article_ids and link != a["id"]:
                pair = tuple(sorted([a["id"], link]))
                link_weight[pair] += 1

    for (s, t), w in link_weight.items():
        G.add_edge(s, t, weight=min(w, 3), type="wikilink")
    return len(link_weight)


def add_category_helpers(articles, article_ids, G, min_cat_share=3):
    """Add helper nodes for categories shared by min_cat_share articles.

    Helper node IDs are prefixed with 'cat:'. Edges connect each helper
    to all articles sharing that category. Helps visually group articles
    by theme (e.g., "2026 films", "UFC fighters").
    """
    all_cats = collections.defaultdict(list)
    for a in articles:
        for cat in a.get("categories", []):
            all_cats[cat].append(a["id"])

    for cat, aids in all_cats.items():
        if len(aids) >= min_cat_share:
            hid = f"cat:{cat}"
            G.add_node(hid, type="helper", helper_type="category",
                       label=cat, size=3, color=HELPER_COLOR)
            for aid in aids:
                G.add_edge(hid, aid, weight=1, type="category")


def add_entity_helpers(articles, entity_map, G, min_entity_share=3):
    """Add helper nodes for named entities shared by min_entity_share articles.

    Helper node IDs are prefixed with 'ent:'. Filters out:
    - Entities whose normalized name matches an article title
    - Entities in the blacklist (nationalities, generic terms)
    - Single-word entities that are common given names
    """
    from ..analyzer.ner import normalize_entity

    article_ids = {a["id"] for a in articles}
    article_title_set = {a["title"].lower() for a in articles}

    entity_blacklist = {"american", "british", "indian", "canadian", "australian",
                        "brazilian", "french", "german", "italian", "spanish",
                        "chinese", "japanese", "russian", "african", "european",
                        "english", "scottish", "mexican", "dutch", "swiss",
                        "jewish", "muslim", "christian", "hispanic", "latino",
                        "asian", "african american", "black", "white",
                        "male", "female", "human", "people", "man", "woman",
                        "new york", "london", "paris", "los angeles",
                        "january", "february", "march", "april", "may", "june",
                        "july", "august", "september", "october", "november", "december",
                        "world war ii", "the", "a", "an", "one", "two", "first", "second"}

    common_names = {"michael", "jackson", "john", "james", "robert", "william",
        "david", "richard", "joseph", "thomas", "charles", "george", "donald",
        "henry", "edward", "ronald", "paul", "brian", "kevin", "jason", "jeff",
        "ryan", "jacob", "gary", "nicholas", "eric", "stephen", "larry", "raymond",
        "mary", "patricia", "jennifer", "linda", "barbara", "elizabeth", "susan",
        "jessica", "sarah", "karen", "nancy", "betty", "margaret", "lisa",
        "sandra", "ashley", "dorothy", "kimberly", "donna", "emily", "carol",
        "michelle", "amanda", "melissa", "deborah", "stephanie", "rebecca",
        "sharon", "anna", "taylor", "alex", "tyler", "daniel", "matthew",
        "andrew", "joshua", "chris", "sam", "ben", "steve", "mike", "tom",
        "dick", "harry", "joe", "jack", "king", "queen", "prince", "lord",
        "jake", "nate", "mike", "tony", "eddie", "matt", "brad", "chad", "bill"}

    for entity, aids in entity_map.items():
        norm_entity = normalize_entity(entity)
        if norm_entity.lower() in article_title_set:
            continue
        if norm_entity.lower() in entity_blacklist:
            continue
        if " " not in norm_entity and norm_entity.lower() in common_names:
            continue
        matched = [a for a in aids if a in article_ids]
        if len(matched) >= min_entity_share:
            hid = f"ent:{entity}"
            G.add_node(hid, type="helper", helper_type="entity",
                       label=entity, size=2, color=HELPER_COLOR)
            for aid in matched:
                G.add_edge(hid, aid, weight=1, type="entity")
