#!/usr/bin/env python3
"""Pipeline to build a connection graph from the top 100 Wikipedia articles.

Fetches the top 100 list from the Hatnote API, enriches each article with
categories, links, and intro text from the MediaWiki API, runs spaCy NER
on summaries, and builds a NetworkX graph exported as JSON for the D3.js
visualization in index.html.
"""
import json, sys, math, time, collections, re, asyncio
from urllib.parse import urlencode

import httpx
import networkx as nx

HATNOTE_URL = "https://top.hatnote.com/en/wikipedia/{year}/{month}/{day}.json"
MW_API = "https://en.wikipedia.org/w/api.php"
HEADERS = {"User-Agent": "WikiTop100Viz/1.0 (prototype; alih@example.com)"}

SKIP_PREFIXES = {"Special", "Wikipedia", "Talk", "User", "Help", "File", "Template",
                 "Category", "Portal", "Draft", "Module", "MediaWiki"}

MAINT_CAT_PATTERNS = [
    r'^articles?\s+(with|containing|needing|that\s+may|to\s+be|lacking|using)',
    r'^all\s+articles?\s+',
    r'^short\s+description',
    r'^cs1:?',
    r'^webarchive\s+template',
    r'^use\s+(dmy|mdy|British|American|Australian|Canadian)\s+dates?',
    r'^official\s+website',
    r'^track\s+variants?',
    r'^redirects?\b',
    r'^(good|featured)\s+articles?\b',
    r'^commons\s+category\s+link',
    r'^living\s+people\b',
    r'^biography\s+with\s+signature',
    r'^wikipedia\s+',
    r'^pages\s+(containing|using)',
    r'^template\s+',
    r'^album\s+chart',
    r'^interlanguage\s+link\s+template',
    r'^articles\s+with\s+(empty\s+)?(music\s+)?ratings?',
    r'\bdead\s+(external\s+)?links?\b',
    r'\bunsourced\s+statements\b',
    r'\bpotentially\s+dated\s+statements\b',
    r'\bself-references?\b',
    r'\bhCards?\b',
    r'\bhatnote\b',
    r'\bweasel-worded\b',
    r'\bpeacock\b',
    r'\btrivia\b',
    r'\boriginal\s+research\b',
    r'\bstyle\s+issues?\b',
    r'\bmultiple\s+issues\b',
    r'\breliable\s+references?\b',
    r'\blacking\s+sources\b',
    r'\bbot-generated\b',
    r'\bmerged?\b',
    r'\bexpanded?\b',
    r'\bcleanup\b',
    r'\bmaintenance\b',
    r'\bsubscription-only\b',
    r'\bpermanently\s+dead\b',
    r'\bAAR\b',
    r'\bsemi-protected\b',
    r'\bextended-confirmed-protected\b',
    r'\bprotected\s+pages?\b',
    r'\bmatches\s+wikidata\b',
    r'\bshort\s+description\s+is\s+different\b',
    r'\bTCMDb\b',
    r'\bAllMovie\b',
    r'\bRotten\s+Tomatoes\b',
    r'\bMetacritic\b',
    r'\bDouban\b',
    r'\bcalled\s+without\b',
    r'\bmanual\s+ref\b',
    r'^all\s+wikipedia\s+articles?\s+written\s+in\b',
    r'^use\s+\w+\s+english\b',
    r'\blogin\s+required\b',
    r'\bCite\s+Mojo\b',
    r'\bnot\s+in\s+wikidata\b',
    r'\bID\s+not\s+in\b',
    r'\bID\s+different\s+from\b',
    r'\bdifferent\s+from\s+wikidata\b',
    r'\bC-SPAN\b',
    r'\bappearing\s+on\s+C-SPAN\b',
    r'\bpages\s+needing\s+factual\s+verification\b',
]

TOPIC_KEYWORDS = {
    "Sports": {"sport", "athlete", "mma", "ufc", "boxing", "fighter", "football", "soccer",
               "nfl", "nba", "fifa", "olympic", "golf", "tennis", "rugby", "baseball",
               "basketball", "championship", "tournament", "coach", "player", "race",
               "grand prix", "heavyweight", "wrestling", "judoka", "martial arts",
               "bare-knuckle", "sportsmen", "sportswomen", "golfer", "mixed martial artists"},
    "Music": {"singer", "song", "album", "musician", "band", "eurovision", "concert",
              "rapper", "pop", "rock", "jazz", "vocal", "music", "orchestra", "guitar",
              "singer-songwriter", "beatles", "hip hop", "singers"},
    "Film & TV": {"film", "movie", "actor", "actress", "television", "series", "episode",
                  "director", "cinema", "hollywood", "tv", "streaming", "netflix",
                  "documentary", "producer", "screenplay", "actresses", "film director"},
    "Politics": {"president", "senator", "congress", "politician", "election", "governor",
                 "minister", "prime minister", "campaign", "political party", "senate",
                 "house of representatives", "vote", "republican", "democrat", "congressman",
                 "senators"},
    "Technology": {"software", "ai", "chatgpt", "artificial intelligence", "computer",
                   "internet", "app", "platform", "digital", "data", "algorithm", "robot",
                   "spacex", "openai", "machine learning", "llm"},
    "Science & Nature": {"biology", "chemistry", "physics", "space", "medical", "disease",
                         "planet", "gene", "dna", "climate", "species", "animal", "plant",
                         "ocean", "earthquake", "virus", "bacteria", "evolution", "telescope"},
    "History": {"century", "war", "ancient", "empire", "revolution", "kingdom", "historical",
                "medieval", "world war", "civil war", "independence", "treaty", "dynasty",
                "history of"},
    "Geography": {"country", "city", "river", "mountain", "island", "region", "capital",
                  "state", "province", "population", "located", "coast", "unincorporated"},
    "Death & Crime": {"death", "died", "murder", "killed", "crime", "criminal", "serial",
                      "killer", "victim", "shooting", "attack", "obituary", "rapist",
                      "manslaughter", "homicide"},
    "Business": {"company", "ceo", "entrepreneur", "billionaire", "startup", "corporation",
                 "market", "stock", "bank", "economy", "merger", "acquisition", "promotion"},
}

CLUSTER_COLORS = {
    "Sports": "#e74c3c",
    "Music": "#9b59b6",
    "Film & TV": "#3498db",
    "Politics": "#f39c12",
    "Technology": "#1abc9c",
    "Science & Nature": "#16a085",
    "History": "#8e44ad",
    "Geography": "#27ae60",
    "Death & Crime": "#7f8c8d",
    "Business": "#e67e22",
    "People": "#2ecc71",
    "Other": "#95a5a6",
}
HELPER_COLOR = "#b0b0b0"


def fetch_json(url):
    """Fetch and parse JSON from a URL with a timeout and user-agent."""
    with httpx.Client(headers=HEADERS, timeout=30.0) as client:
        resp = client.get(url)
        resp.raise_for_status()
        return resp.json()


def is_meaningful_category(cat):
    """Return False for Wikipedia maintenance categories, True for topic categories.

    Uses case-insensitive regex patterns (MAINT_CAT_PATTERNS) to catch
    categories like "Articles with short description", "CS1 errors", etc.
    """
    if len(cat) < 5:
        return False
    for p in MAINT_CAT_PATTERNS:
        if re.search(p, cat, re.IGNORECASE):
            return False
    return True


def fetch_top100(year, month, day):
    """Fetch the top 100 list from the Hatnote API.

    Filters out Special:, Wikipedia:, Talk:, and other non-article pages.
    Returns a list of dicts with id, title, rank, views, summary, image_url, url.
    Article IDs use underscores (matching Wikipedia URL convention).
    """
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
    return articles


async def fetch_single_metadata(client, title, sem):
    """Fetch categories, outgoing links (ns=0 only), and intro extract for one article.

    Uses an asyncio.Semaphore to cap concurrent requests. Retries up to 3 times
    on failure. pllimit=500 is sufficient for each individual article.
    """
    async with sem:
        params = {
            "action": "query",
            "prop": "categories|links|extracts",
            "titles": title,
            "format": "json",
            "cllimit": 200,
            "pllimit": 500,
            "exintro": 1,
            "explaintext": 1,
            "exchars": 800,
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
                        return title, {"categories": [], "links": [], "extract": ""}
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
                    return title, {"categories": cats, "links": links, "extract": extract}
            except Exception as e:
                if attempt < 2:
                    await asyncio.sleep(0.5)
                else:
                    print(f"  Failed to fetch {title}: {e}")
                    return title, {"categories": [], "links": [], "extract": ""}
        return title, {"categories": [], "links": [], "extract": ""}


async def fetch_all_metadata(titles, max_concurrent=5):
    """Fetch metadata for all articles concurrently with a concurrency limit.

    Returns a dict mapping article IDs to {categories, links, extract}.
    Completes in ~15 seconds for 100 articles at 5 concurrent workers.
    """
    sem = asyncio.Semaphore(max_concurrent)
    async with httpx.AsyncClient(headers=HEADERS) as client:
        tasks = [fetch_single_metadata(client, t, sem) for t in titles]
        results = await asyncio.gather(*tasks)
    return dict(results)


def assign_cluster(categories, summary):
    """Assign an article to a topic cluster by keyword matching.

    Scores each cluster (Sports, Music, Film & TV, etc.) against the
    article's categories and summary text. Returns the highest-scoring cluster.
    Keyword matching is fast, deterministic, and explainable.
    """
    text = " ".join(categories) + " " + summary.lower()
    scores = {}
    for cluster, keywords in TOPIC_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw.lower() in text)
        if score > 0:
            scores[cluster] = score
    if not scores:
        return "Other"
    return max(scores, key=scores.get)


def normalize_entity(name):
    """Strip leading articles from entity names for deduplication.

    "the United States" and "United States" map to the same entity.
    """
    n = name.strip().removeprefix("the ").removeprefix("The ").strip()
    return n


def extract_entities(texts):
    """Run spaCy NER on article text and return deduplicated entity map.

    Processes text through en_core_web_sm, collecting PERSON, ORG, GPE,
    EVENT, NORP, PRODUCT, and WORK_OF_ART entities. Deduplicates variants
    (e.g., "the UFC" vs "UFC") by normalizing and keeping the longest name.

    Returns (entity_map, final_map) where entity_map is {name: [article_ids]}.
    """
    try:
        import spacy
        nlp = spacy.load("en_core_web_sm", disable=["parser", "lemmatizer"])
    except Exception as e:
        print(f"spaCy not available: {e}")
        return {}, {}

    raw_map = collections.defaultdict(list)
    for article_id, text in texts.items():
        if not text.strip():
            continue
        doc = nlp(text[:5000])
        seen = set()
        for ent in doc.ents:
            if ent.label_ in {"PERSON", "ORG", "GPE", "EVENT", "NORP", "PRODUCT", "WORK_OF_ART"}:
                raw = ent.text.strip()
                if len(raw) < 3:
                    continue
                norm = normalize_entity(raw).lower()
                if norm in seen:
                    continue
                seen.add(norm)
                raw_map[raw].append(article_id)

    norm_map = collections.defaultdict(list)
    for raw, aids in raw_map.items():
        norm = normalize_entity(raw)
        norm_map[norm].append((raw, aids))

    entity_map = {}
    final_map = collections.defaultdict(list)
    for norm, variants in norm_map.items():
        all_aids = set()
        best_name = max(variants, key=lambda x: len(x[0]))[0]
        for raw, aids in variants:
            all_aids.update(aids)
        entity_map[best_name] = list(all_aids)
        for aid in all_aids:
            final_map[best_name].append(aid)

    return entity_map, final_map


def build_graph_nodes(articles, G):
    """Add article nodes to the graph with cluster assignments and metadata."""
    for a in articles:
        a["cluster"] = assign_cluster(a.get("categories", []), a.get("summary", ""))
        G.add_node(a["id"], **a, type="article")


def add_wikilink_edges(articles, article_ids, G):
    """Add edges for direct wikilinks between top 100 articles.

    Links are identified by matching outgoing links from each article's
    MediaWiki data against the set of top 100 article IDs.
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


def serialize_graph(G):
    """Convert NetworkX graph to JSON-serializable format.

    Strips intermediate keys (core_cats, links, extract, history) from
    article nodes. Helper nodes get HELPER_COLOR. Article sizes are
    log-scaled from view counts (range 6-35).
    """
    nodes_data = []
    for nid, ndata in G.nodes(data=True):
        node = dict(ndata)
        node["id"] = nid
        if node.get("type") == "article":
            node["color"] = CLUSTER_COLORS.get(node.get("cluster", "Other"), CLUSTER_COLORS["Other"])
            node["size"] = max(6, min(35, math.log2(node.get("views", 1000)) * 2.5))
        else:
            node["color"] = HELPER_COLOR
        for k in ("core_cats", "links", "extract", "history"):
            node.pop(k, None)
        nodes_data.append(node)

    links_data = []
    for s, t, edata in G.edges(data=True):
        links_data.append({
            "source": s,
            "target": t,
            "weight": edata.get("weight", 1),
            "type": edata.get("type", "unknown"),
        })

    return nodes_data, links_data


def main():
    """Run the full pipeline: fetch → enrich → analyze → build → export."""
    year, month, day = sys.argv[1:4] if len(sys.argv) >= 4 else ("2026", "5", "17")
    out_file = sys.argv[4] if len(sys.argv) >= 5 else "graph_data.json"
    min_entity_share = int(sys.argv[5]) if len(sys.argv) >= 6 else 3

    print(f"Fetching top 100 for {year}/{month}/{day}...")
    articles = fetch_top100(year, month, day)
    print(f"Got {len(articles)} articles")

    titles = [a["id"] for a in articles]
    print("Fetching article metadata (async, 5 concurrent)...")
    metadata = asyncio.run(fetch_all_metadata(titles))
    print(f"Got metadata for {len(metadata)} articles")

    for a in articles:
        meta = metadata.get(a["id"], {})
        all_cats = meta.get("categories", [])
        a["categories"] = [c for c in all_cats if is_meaningful_category(c)]
        a["links"] = meta.get("links", [])
        a["extract"] = meta.get("extract", "")

    meaningful_cat_count = sum(len(a["categories"]) for a in articles)
    link_count_total = sum(len(a["links"]) for a in articles)
    print(f"  {meaningful_cat_count} meaningful categories, {link_count_total} total links across all articles")

    print("Extracting named entities with spaCy...")
    texts = {}
    for a in articles:
        t = (a.get("summary", "") + " " + a.get("extract", "")).strip()
        if t:
            texts[a["id"]] = t
    entity_map, _ = extract_entities(texts)
    print(f"Found {len(entity_map)} unique named entities")

    print("Building graph...")
    G = nx.Graph()
    article_ids = {a["id"] for a in articles}

    build_graph_nodes(articles, G)
    n_wiki = add_wikilink_edges(articles, article_ids, G)
    print(f"  {n_wiki} direct wikilink edges between top 100 articles")

    add_category_helpers(articles, article_ids, G, min_cat_share=3)
    add_entity_helpers(articles, entity_map, G, min_entity_share=min_entity_share)

    nodes_data, links_data = serialize_graph(G)

    output = {
        "meta": {
            "date": f"{year}-{month}-{day}",
            "total_articles": len(articles),
            "total_nodes": len(nodes_data),
            "total_edges": len(links_data),
        },
        "nodes": nodes_data,
        "links": links_data,
    }

    with open(out_file, "w") as f:
        json.dump(output, f, indent=2)

    n_articles = sum(1 for n in nodes_data if n.get("type") == "article")
    n_helpers = sum(1 for n in nodes_data if n.get("type") == "helper")
    n_cat = sum(1 for n in nodes_data if n.get("helper_type") == "category")
    n_ent = sum(1 for n in nodes_data if n.get("helper_type") == "entity")
    n_wiki_e = sum(1 for l in links_data if l["type"] == "wikilink")
    n_cats = sum(1 for l in links_data if l["type"] == "category")
    n_ents = sum(1 for l in links_data if l["type"] == "entity")
    print(f"Graph saved to {out_file}")
    print(f"  {n_articles} articles + {n_helpers} helpers ({n_cat} categories, {n_ent} entities) = {len(nodes_data)} nodes")
    print(f"  {len(links_data)} edges ({n_wiki_e} wikilinks, {n_cats} cat, {n_ents} ent)")


if __name__ == "__main__":
    main()
